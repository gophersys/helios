"""pytest fixtures for product validation tests.

Provides session-scoped TestContext and per-test firmware variant
parametrization. Tests receive a connected, ready-to-use context.

Mock mode (MOCK_CLOUD=1):
    Replaces all hardware and cloud dependencies with in-memory mocks.
    No MTIB connection, no CoreCloud DB, no physical hardware needed.

Required environment variables (set by K8s Job template):
    MTIB_HOST or MTIB_ADDRESS  - MTIB server IP (e.g., 10.4.45.33)
    MTIB_PORT                  - MTIB gRPC port (default: 50053)
    DEVICE_ID                  - Device ID hex string
    DEVICE_SNR                 - J-Link probe serial number (e.g., 0964)
    FIXTURE_PROFILE_PATH       - Fixture profile JSON path

    CoreCloud API (VAL_1_0 namespace — from corecloud-validation K8s secret):
    VAL_1_0_API_KEY                    - CoreCloud API key
    VAL_1_0_API_AUTH_USERNAME          - CoreCloud auth username
    VAL_1_0_API_AUTH_PASSWORD          - CoreCloud auth password
    VAL_1_0_API_AUTH_SERVER_HOST_NAME  - Auth server (auth.office.corekinect.cloud:2013)
    VAL_1_0_API_REST_SERVER_HOST_NAME  - REST API (val.office.corekinect.cloud:2018/api)

    Storage (MinIO — from K8s configmap):
    STORAGE_URL, STORAGE_ACCESS_KEY, STORAGE_SECRET_ACCESS_KEY, STORAGE_BUCKET

Optional:
    MOCK_CLOUD       - "1" for mock mode (no hardware)
    PIPELINE_ID      - Pipeline ID for firmware artifact fetching from MinIO
    DEVICE_IMEI      - Pre-known IMEI (skips modem shell read)
    DEVICE_ICCIDS    - Comma-separated ICCIDs (skips modem shell read)
    ARTIFACTS_DIR    - Directory for test artifacts

Concord Reporter (auto-activated by K8s Job):
    CONCORD_RUN_ID   - Validation run ID — activates the reporter plugin
    CONCORD_API_URL  - Concord HTTP API base URL
    CONCORD_API_KEY  - API key for reporter auth
"""

import os
import time
from pathlib import Path
from typing import List, Optional

import pytest
from dotenv import load_dotenv

# Load root .env before anything else (conftest runs from apps/validation/alpha/)
# In Docker container, the file is at /app/conftest.py, so parents[3] would fail.
# In local dev, it's at apps/validation/alpha/conftest.py, so parents[3] is repo root.
try:
    _root_env = Path(__file__).resolve().parents[3] / ".env"
    if _root_env.exists():
        load_dotenv(_root_env, override=False)
except IndexError:
    pass  # Running in container without parent directories

from corekinect.test.context import TestContext
from corekinect.utils import EnvConfig, Logger

# ── Structured configuration via EnvConfig ──────────────────────────
class ValidationConfig(EnvConfig):
    """Validation test config — loaded from env vars / .env file."""
    ENV_PREFIX = ""

    # MTIB connection — supports MTIB_ADDRESS (host:port) or MTIB_HOST + MTIB_PORT
    MTIB_ADDRESS: Optional[str] = None  # "10.4.45.33:50053" — from bench scheduler
    MTIB_HOST: Optional[str] = None
    MTIB_PORT: int = 50053

    # Device identity — from bench scheduler or env
    DEVICE_ID: str = "70B3D584C01E1FCC"
    DEVICE_SNR: Optional[str] = None
    FIXTURE_PROFILE_PATH: Optional[str] = None
    BENCH_ID: Optional[str] = None  # TestBench ID for unlock on finish

    # Firmware paths
    FW_DEBUG_HEX: Optional[str] = None
    FW_RELEASE_HEX: Optional[str] = None
    FW_DEBUG_COMMS_HEX: Optional[str] = None
    FW_RELEASE_COMMS_HEX: Optional[str] = None
    FW_MODEM_ZIP: Optional[str] = None

    # CoreOps re-personalization
    PROXY_SERVER_URL: Optional[str] = None
    DEVICE_IMEI: Optional[str] = None
    DEVICE_ICCIDS: Optional[str] = None

    # CoreCloud
    CORECLOUD_DB_ENV: Optional[str] = None

    # Test artifacts
    ARTIFACTS_DIR: Optional[str] = None

    # Mock mode
    MOCK_CLOUD: Optional[str] = None

    # Product context (from Concord catalog API)
    PRODUCT_SLUG: str = "alpha_b0"

    # MFG flash:Pipeline-based firmware assets (from CI trigger)
    PIPELINE_ID: Optional[str] = None
    CONCORD_API_URL: Optional[str] = None
    CONCORD_API_KEY: Optional[str] = None
    STORAGE_URL: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_ACCESS_KEY: Optional[str] = None
    STORAGE_BUCKET: str = "concord"


cfg = ValidationConfig()
log = Logger(log_name="validation")

# ── Mock mode detection ──────────────────────────────────────────
MOCK_MODE = (cfg.MOCK_CLOUD or "").strip().lower() in ("1", "true", "yes")

if MOCK_MODE:
    # Patch time.sleep to be near-instant in mock mode.
    # Stage 4 tests have time.sleep(30) and time.sleep(60) calls for hardware
    # settle times that are meaningless without real hardware.
    import time
    _real_sleep = time.sleep
    time.sleep = lambda s: _real_sleep(min(s, 0.01))

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
# When CONCORD_RUN_ID is not set, the reporter's pytest_configure is a no-op.
pytest_plugins = ["corekinect.test.reporter"]


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "corecloud: marks tests that require CoreCloud connectivity",
    )
    config.addinivalue_line(
        "markers",
        "nfc: marks tests that require NFC reader hardware",
    )


def _has_cloud_db() -> bool:
    """Check if CoreCloud DB credentials are configured."""
    return bool(
        cfg.CORECLOUD_DB_ENV
        or os.environ.get("DEV_1_0_DB_HOST")
        or os.environ.get("VAL_1_0_DB_HOST")
    )


def pytest_collection_modifyitems(config, items):
    """Skip cloud-dependent tests and reorder for firmware flash efficiency.

    1. Skips corecloud-marked tests in mock mode AND when DB creds are missing
       in hardware mode. Prevents 120s timeouts on every cloud-dependent test.
    2. Groups tests by firmware variant (all [debug] first, then [release])
       so firmware is flashed only twice per run instead of per-test.
    """
    skip_reason = None
    if _is_mock_mode(config):
        skip_reason = "Requires CoreCloud DB/API — skipped in mock mode"
    elif not _has_cloud_db():
        skip_reason = "CoreCloud DB not configured (DEV_1_0_DB_HOST not set)"

    if skip_reason:
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "corecloud" in item.keywords:
                item.add_marker(skip_marker)

    # Reorder: group tests by firmware_build param to minimize reflashing.
    # Default pytest ordering interleaves: test_A[debug], test_A[release], test_B[debug]...
    # Reordered: test_A[debug], test_B[debug]..., test_A[release], test_B[release]...
    # This reduces full flash cycles from 2*N to just 2.
    def _variant_sort_key(item):
        if "[release]" in item.nodeid:
            return (1, item.nodeid)
        if "[debug]" in item.nodeid:
            return (0, item.nodeid)
        return (-1, item.nodeid)  # non-parametrized first

    items.sort(key=_variant_sort_key)


def pytest_addoption(parser):
    """Add custom CLI options for validation tests."""
    parser.addoption(
        "--device-id",
        action="store",
        default=None,
        help="Device ID hex string (overrides DEVICE_ID env var)",
    )
    parser.addoption(
        "--mtib-host",
        action="store",
        default=None,
        help="MTIB server address (overrides MTIB_HOST env var)",
    )
    parser.addoption(
        "--mtib-addr",
        action="store",
        default=None,
        help="MTIB address for FUOTA tests (alias for --mtib-host, overrides MTIB_ADDRESS env var)",
    )
    parser.addoption(
        "--device-snr",
        action="store",
        default=None,
        help="Device serial number (overrides DEVICE_SNR env var)",
    )
    parser.addoption(
        "--artifacts-dir",
        action="store",
        default=None,
        help="Directory for test artifacts (overrides ARTIFACTS_DIR env var)",
    )
    parser.addoption(
        "--db-env",
        action="store",
        default=None,
        help="CoreCloud namespace, e.g. DEV_1_0 or VAL_1_0 (overrides CORECLOUD_DB_ENV env var)",
    )
    parser.addoption(
        "--mock-cloud",
        action="store_true",
        default=False,
        help="Run in mock mode (no hardware/cloud required). Same as MOCK_CLOUD=1 env var.",
    )
    parser.addoption(
        "--skip-personalization",
        action="store_true",
        default=False,
        help="Skip personalization tests (use after FUOTA when device already has keys).",
    )
    parser.addoption(
        "--pipeline-id",
        action="store",
        default=None,
        help="Pipeline ID for FUOTA tests (overrides PIPELINE_ID env var).",
    )


def _is_mock_mode(config) -> bool:
    """Check if mock mode is enabled via env var or CLI flag."""
    if MOCK_MODE:
        return True
    try:
        return config.getoption("--mock-cloud", default=False)
    except ValueError:
        return False


def _build_mock_context() -> TestContext:
    """Build a TestContext with all-mock components for offline testing."""
    from corekinect.test.mock_cloud import MockCloudClient
    from corekinect.test.mock_hardware import (
        MockFixtureController,
        MockPowerProfiler,
        MockUartDemuxer,
    )
    from corekinect.test.runner import ProductContext

    device_id = int(cfg.DEVICE_ID, 16)

    cloud = MockCloudClient(device_id=device_id)
    fixture = MockFixtureController()
    uart = MockUartDemuxer()
    power = MockPowerProfiler()

    # Load product context from API if available, else use defaults
    product_ctx = None
    api_url = cfg.CONCORD_API_URL
    api_key = cfg.CONCORD_API_KEY
    product_slug = cfg.PRODUCT_SLUG
    if api_url and api_key and product_slug:
        try:
            product_ctx = ProductContext.from_api(product_slug, api_url, api_key)
        except Exception:
            pass
    if not product_ctx:
        product_ctx = ProductContext.default("alpha", "b0")

    log.info(
        "Mock mode: device_id=%s, no hardware connection",
        cfg.DEVICE_ID,
    )

    # TestContext accepts any duck-typed components
    return TestContext(
        mtib=None,
        cloud=cloud,
        fixture=fixture,
        uart=uart,
        power=power,
        product=product_ctx,
    )


def _resolve_device_id_from_snr() -> Optional[str]:
    """Resolve DEVICE_ID from DEVICE_SNR via CoreOps proxy.

    If DEVICE_SNR is set but DEVICE_ID is not (or is default), calls the
    CoreOps proxy to get the actual device ID for this serial number.

    Returns the resolved device ID, or None if resolution fails.
    """
    snr = cfg.DEVICE_SNR
    if not snr:
        return None

    # Check if DEVICE_ID is already set to something non-default
    current_id = os.environ.get("DEVICE_ID", cfg.DEVICE_ID)
    if current_id and current_id != "70B3D584C01E1FCC":
        log.debug("DEVICE_ID already set to %s, skipping SNR lookup", current_id)
        return current_id

    try:
        from corekinect.core_ops import CoreOpsProxyClient

        client = CoreOpsProxyClient(logger=log)
        if not client.health_check():
            log.warning("CoreOps proxy not available — using default DEVICE_ID")
            return None

        device_id = client.assign_device_id(snr)
        log.info("Resolved SNR %s → DEVICE_ID %s via CoreOps proxy", snr, device_id)
        return device_id
    except Exception as e:
        log.warning("CoreOps proxy lookup failed: %s — using default DEVICE_ID", e)
        return None


@pytest.fixture(scope="session")
def ctx(request) -> TestContext:
    """Session-scoped test context — connects once, reused across all tests.

    In mock mode (MOCK_CLOUD=1 or --mock-cloud), returns a context with
    all-mock components. No hardware or network connection needed.

    In hardware mode, reads configuration from environment variables.
    CLI options override env vars when provided.
    """
    if _is_mock_mode(request.config):
        context = _build_mock_context()
        yield context
        return

    # CLI overrides
    if request.config.getoption("--device-id"):
        os.environ["DEVICE_ID"] = request.config.getoption("--device-id")
    if request.config.getoption("--mtib-host"):
        os.environ["MTIB_HOST"] = request.config.getoption("--mtib-host")
    if request.config.getoption("--artifacts-dir"):
        os.environ["ARTIFACTS_DIR"] = request.config.getoption("--artifacts-dir")
    if request.config.getoption("--db-env"):
        os.environ["CORECLOUD_DB_ENV"] = request.config.getoption("--db-env")

    # Resolve DEVICE_ID from DEVICE_SNR via CoreOps proxy if needed
    resolved_id = _resolve_device_id_from_snr()
    if resolved_id:
        os.environ["DEVICE_ID"] = resolved_id

    # Ensure PRODUCT_SLUG is available for product context loading
    if not os.environ.get("PRODUCT_SLUG"):
        os.environ["PRODUCT_SLUG"] = cfg.PRODUCT_SLUG

    context = TestContext.from_env()
    context.connect()
    yield context
    context.disconnect()


@pytest.fixture(scope="session")
def product(ctx):
    """Session-scoped product context from Concord catalog API.

    Provides deviceTypeId, deviceVariantId, appIds, coreCloudEnv from the
    Product model. Tests use this for FUOTA targets, device registration, etc.

    Usage in tests:
        def test_fuota(ctx, product):
            device_type = product.device_type_id   # 2
            app_ids = product.app_ids               # {"nrf52840": 109, "nrf9151": 108}
            cloud_env = product.core_cloud_env      # "VAL_1_0"
    """
    return ctx.product


@pytest.fixture(scope="session")
def mock_cloud(ctx):
    """Access MockCloudClient directly for scenario injection.

    Only available in mock mode. Returns None in hardware mode.

    Usage in tests:
        def test_something(ctx, mock_cloud):
            if mock_cloud:
                from corekinect.test.mock_cloud import Scenario, ScenarioEngine
                engine = ScenarioEngine(mock_cloud)
                engine.load(Scenario.happy_boot(device_id=mock_cloud.device_id))
            msg = ctx.cloud.wait_for_boot(timeout_s=5)
    """
    from corekinect.test.mock_cloud import MockCloudClient
    if isinstance(ctx.cloud, MockCloudClient):
        return ctx.cloud
    return None


@pytest.fixture(scope="session")
def pipeline_assets():
    """Session-scoped pipeline assets manager for Stage 4 validation.

    When PIPELINE_ID is set (from K8s Job trigger), provides access to
    firmware artifacts from the CI pipeline. Tests can use this to:
      - Download hex files for J-Link flashing
      - Download CFW files for FUOTA
      - Get version strings for each matrix build

    Usage in tests:
        def test_fuota(ctx, pipeline_assets):
            if pipeline_assets:
                mfg_app_hex = pipeline_assets.get_hex("MFG_BASE", "app")
                mfg_comms_hex = pipeline_assets.get_hex("MFG_BASE", "comms")
                cfw_files = pipeline_assets.get_cfw_files("MFG_BUMP")

    Returns None if PIPELINE_ID is not set (manual run without CI trigger).
    """
    if not cfg.PIPELINE_ID:
        log.info("PIPELINE_ID not set — pipeline_assets fixture returning None")
        yield None
        return

    try:
        from corekinect.test.firmware import PipelineAssets
        assets = PipelineAssets(
            pipeline_id=cfg.PIPELINE_ID,
            logger=log,
        )
        log.info("PipelineAssets initialized: %s", cfg.PIPELINE_ID)
        log.info(assets.summary())
        yield assets
        assets.cleanup()
    except Exception as e:
        log.error("Failed to initialize PipelineAssets: %s", e)
        yield None


@pytest.fixture(scope="session")
def mfg_flash(ctx, pipeline_assets):
    """Session-scoped fixture: Flash MFG_BASE firmware via J-Link.

    When pipeline_assets is available:
      1. Downloads MFG_BASE hex files from MinIO
      2. Uploads to MTIB server
      3. Flashes nRF52840 (app) and nRF9151 (comms) via J-Link
      4. Re-personalizes the device

    Runs once at the start of the test session, before any tests.
    Does nothing if pipeline_assets is not available (manual run).
    """
    if not pipeline_assets:
        log.info("No pipeline_assets — skipping Stage 4 MFG flash")
        yield None
        return

    try:
        # Download MFG_BASE hex files
        log.info("MFG flash:Downloading MFG_BASE firmware from pipeline...")
        app_hex_path = pipeline_assets.get_hex("MFG_BASE", "app")
        comms_hex_path = pipeline_assets.get_hex("MFG_BASE", "comms")
        log.info("MFG_BASE app hex: %s", app_hex_path)
        log.info("MFG_BASE comms hex: %s", comms_hex_path)

        # Upload to MTIB and flash nRF52840
        log.info("MFG flash:Flashing MFG_BASE nRF52840...")
        server_app = pipeline_assets.upload_to_mtib(app_hex_path, ctx.mtib, "nrf52840")
        ctx.fixture.flash_firmware(server_app, target="nrf52840")

        # Flash nRF9151 comms (if hex available)
        if comms_hex_path:
            log.info("MFG flash:Flashing MFG_BASE nRF9151...")
            server_comms = pipeline_assets.upload_to_mtib(comms_hex_path, ctx.mtib, "nrf9151")
            ctx.fixture.flash_firmware(server_comms, target="nrf9151")

        # Re-personalize after flash
        device_snr = cfg.DEVICE_SNR
        if device_snr:
            log.info("MFG flash:Re-personalizing device...")
            from corekinect.test.device_personalizer import DevicePersonalizer

            known_device_id = None
            if ctx.fixture.profile and ctx.fixture.profile.dut:
                known_device_id = ctx.fixture.profile.dut.device_id

            personalizer = DevicePersonalizer(
                mtib=ctx.mtib,
                snr=device_snr,
                imei=cfg.DEVICE_IMEI,
                iccids=[s.strip() for s in (cfg.DEVICE_ICCIDS or "").split(",") if s.strip()] or None,
                db_env=cfg.CORECLOUD_DB_ENV,
                logger=log,
                known_device_id=known_device_id,
            )
            result, err = personalizer.repersonalize(power_cycle=True, lock_shells=True)
            if err:
                log.warning("MFG flash:Re-personalization failed: %s", err)
            else:
                log.info("MFG flash:Re-personalized device_id=%s", result.device_id)
        else:
            # Just power cycle if no personalization
            log.info("MFG flash:Power cycling after flash...")
            ctx.fixture.power_cycle()

        log.info("MFG flash:MFG_BASE flash complete")
        yield "MFG_BASE"

    except Exception as e:
        log.error("MFG flash:MFG flash failed: %s", e)
        yield None


@pytest.fixture(autouse=True)
def _test_lifecycle(request):
    """Auto-applied fixture for per-test setup/teardown.

    - For tests that use the session-scoped ctx fixture: calls setup_test()
      before and teardown_test() after each test.
    - For smoke tests (own fixtures, no ctx): no-op.
    """
    # Only run lifecycle hooks for tests that use the ctx fixture.
    # Smoke tests define their own mtib/fixture/power fixtures and don't need ctx.
    if "ctx" not in request.fixturenames:
        yield
        return

    ctx = request.getfixturevalue("ctx")
    ctx.setup_test(test_name=request.node.name)  # mark_test_start + clear UART + set telemetry test

    yield
    artifacts_dir = cfg.ARTIFACTS_DIR
    ctx.teardown_test(request.node.name, artifacts_dir)
    # Upload UART log to MinIO (fire-and-forget)
    if artifacts_dir and ctx.artifacts.enabled:
        uart_log = os.path.join(artifacts_dir, f"{request.node.name}_uart.log")
        if os.path.isfile(uart_log):
            ctx.artifacts.upload(uart_log, f"{request.node.name}_uart.log")


# Track which files have been uploaded to the MTIB server this session.
# Keys are local file paths, values are the server-side filenames.
_uploaded_firmware: dict = {}

# Track currently flashed firmware variant to skip redundant reflashing.
# With test reordering (all [debug] first, then [release]), consecutive
# tests with the same variant reuse the already-flashed firmware.
_current_variant: str = ""


def _ensure_uploaded(ctx: TestContext, path: str, target: str) -> str:
    """Upload firmware to MTIB server from local file or MinIO storage.

    Supported path formats:
      - Local file (e.g., /firmware/app_nrf52840.hex) — uploaded via FirmwareAssetManager
      - MinIO key (e.g., firmware/builds/alpha/abc/app.hex) — downloaded then uploaded
      - Bare filename (e.g., app_nrf52840.hex) — assumed already on server

    Uses ctx.firmware (FirmwareAssetManager) for upload tracking and cleanup.

    Returns:
        The server-side filename to pass to flash_firmware().
    """
    # If it's a local file, upload using asset manager
    if os.path.isfile(path):
        if path not in _uploaded_firmware:
            log.info("Uploading firmware to MTIB: %s -> target=%s", path, target)
            server_name = ctx.firmware.upload_local(path, target)
            _uploaded_firmware[path] = server_name
            log.info("Upload complete: %s (server name: %s)", path, server_name)
        return _uploaded_firmware[path]

    # Check if it looks like a MinIO storage key (has path separators but not a local file)
    if "/" in path and ctx.firmware.storage_enabled:
        if path not in _uploaded_firmware:
            log.info("Fetching firmware from MinIO: %s -> target=%s", path, target)
            server_name = ctx.firmware.fetch_and_upload(path, target)
            _uploaded_firmware[path] = server_name
            log.info("Fetch+upload complete: %s (server name: %s)", path, server_name)
        return _uploaded_firmware[path]

    # Bare filename — assume already on server (backward compat)
    return path


@pytest.fixture(params=["debug", "release"])
def firmware_build(ctx: TestContext, request) -> str:
    """Parametrize tests on debug + release firmware.

    In mock mode, skips the actual flash + re-personalization and
    injects a happy_boot scenario via MockCloudClient.

    In hardware mode:
      1. Uploads firmware files from local paths to the MTIB server (once per session)
      2. Flashes the firmware to the DUT
      3. Re-personalizes if PROXY_SERVER_URL + DEVICE_SNR are set

    Firmware paths are read from env vars (FW_DEBUG_HEX, FW_RELEASE_HEX, etc.).
    Values can be local file paths (auto-uploaded) or bare filenames (pre-uploaded).
    Change firmware without code changes — just update the env vars.

    Yields:
        "debug" or "release" — the current firmware variant.
    """
    global _current_variant
    variant = request.param

    # ── Skip reflash if same variant is already loaded ──
    # With test reordering (all [debug] first, then [release]),
    # this avoids ~63s flash cycle for every consecutive same-variant test.
    if _current_variant == variant:
        log.info("Firmware %s already flashed, skipping flash cycle", variant)
        yield variant
        return

    # ── Mock mode: inject boot scenario instead of flashing ──
    from corekinect.test.mock_cloud import MockCloudClient
    if isinstance(ctx.cloud, MockCloudClient):
        from corekinect.test.mock_cloud import Scenario, ScenarioEngine
        # Simulate flash — resets transient fixture state (button, peltier, etc.)
        ctx.fixture.flash_firmware(f"mock_{variant}.hex")
        engine = ScenarioEngine(ctx.cloud)
        # Load comprehensive scenario — covers boot, network, position,
        # motion, biometric (on/off body), environmental data
        engine.load(Scenario.full_device_activity(device_id=ctx.cloud.device_id))
        log.info("Mock mode: simulated %s firmware flash + boot", variant)
        _current_variant = variant
        yield variant
        return

    # ── Hardware mode: actual flash + re-personalization ──
    hex_path = getattr(cfg, f"FW_{variant.upper()}_HEX", None)

    if not hex_path:
        pytest.skip(f"FW_{variant.upper()}_HEX not set — skipping {variant} build tests")

    # nRF9151 comms coprocessor hex (optional — skips comms flash if not set)
    comms_hex_path = getattr(cfg, f"FW_{variant.upper()}_COMMS_HEX", None)

    # nRF9151 modem firmware zip (required if comms is flashed — chiperase wipes modem)
    modem_fw_path = cfg.FW_MODEM_ZIP

    # Upload + flash nRF52840 application firmware
    server_hex = _ensure_uploaded(ctx, hex_path, "nrf52840")
    log.info("Flashing %s nRF52840: %s", variant, server_hex)
    ctx.fixture.flash_firmware(server_hex, target="nrf52840")

    # Flash nRF9151 comms coprocessor (if provided)
    if comms_hex_path:
        # Modem firmware must be flashed first — chiperase on the nRF9151 wipes
        # both the application and modem partitions.
        if modem_fw_path:
            server_modem = _ensure_uploaded(ctx, modem_fw_path, "nrf9151_modem")
            log.info("Flashing nRF9151 modem FW: %s", server_modem)
            ctx.fixture.flash_firmware(server_modem, target="nrf9151_modem")

        server_comms = _ensure_uploaded(ctx, comms_hex_path, "nrf9151")
        log.info("Flashing %s nRF9151: %s", variant, server_comms)
        ctx.fixture.flash_firmware(server_comms, target="nrf9151")

    # Re-personalize after flash (chiperase wipes EC keypair + config).
    # Best-effort: if personalization fails, tests that don't need CoreCloud
    # will still pass. Tests requiring cloud data will fail on their own.
    device_snr = cfg.DEVICE_SNR
    personalized = False

    if device_snr:
        from corekinect.test.device_personalizer import DevicePersonalizer

        # Use pre-known IMEI/ICCIDs if available (avoids modem read)
        imei = cfg.DEVICE_IMEI
        iccids_str = cfg.DEVICE_ICCIDS
        iccids = [s.strip() for s in iccids_str.split(",") if s.strip()] if iccids_str else None

        # Use device_id from fixture profile as fallback when CoreOps is unavailable
        known_device_id = None
        if ctx.fixture.profile and ctx.fixture.profile.dut:
            known_device_id = ctx.fixture.profile.dut.device_id

        db_env = cfg.CORECLOUD_DB_ENV
        personalizer = DevicePersonalizer(
            mtib=ctx.mtib,
            snr=device_snr,
            imei=imei,
            iccids=iccids,
            db_env=db_env,
            logger=log,
            known_device_id=known_device_id,
        )
        try:
            result, err = personalizer.repersonalize(
                power_cycle=True,   # Power cycle included in repersonalize
                lock_shells=True,
            )
            if err:
                log.warning(
                    "Re-personalization failed for %s: %s — "
                    "tests needing CoreCloud will fail",
                    variant, err,
                )
            else:
                log.info("Re-personalized: device_id=%s", result.device_id)
                personalized = True
        except Exception as e:
            log.warning(
                "Re-personalization exception for %s: %s — "
                "tests needing CoreCloud will fail",
                variant, e,
            )
    else:
        log.warning(
            "DEVICE_SNR not set — skipping re-personalization. "
            "Tests requiring CoreCloud connectivity may fail."
        )

    # If personalization didn't include a power cycle, do one now
    if not personalized:
        ctx.fixture.power_cycle()

    # Wait for CoreCloud boot message (only if DB is configured)
    db_env = cfg.CORECLOUD_DB_ENV or os.environ.get("DEV_1_0_DB_HOST")
    if db_env and personalized:
        boot = ctx.cloud.wait_for_boot(boot_reason=0, timeout_s=120)
        # Handle both dict (REST API) and object (mock) returns
        if isinstance(boot, dict):
            boot_reason = boot.get("bootReason", "unknown")
            log.info("Device booted: reason=%s", boot_reason)
        else:
            log.info(
                "Device booted: reason=%s, mcu=%s",
                getattr(boot, "boot_reason_str", "unknown"),
                getattr(boot, "coprocessor_str", "unknown"),
            )
    else:
        # No cloud DB or personalization failed — just wait for hardware boot
        log.info("Waiting for hardware boot settle (5s)...")
        time.sleep(5)

    _current_variant = variant
    yield variant
