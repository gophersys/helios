"""pytest fixtures for Stage 4 product validation tests.

Provides session-scoped TestContext and per-test firmware variant
parametrization. Tests receive a connected, ready-to-use context.

Mock mode (MOCK_CLOUD=1):
    Replaces all hardware and cloud dependencies with in-memory mocks.
    No MTIB connection, no CoreCloud DB, no physical hardware needed.
    Use ScenarioEngine to inject mock cloud messages in test bodies.

Required environment variables (hardware mode, default):
    MTIB_HOST, MTIB_PORT, DEVICE_ID, FIXTURE_PROFILE_PATH

    CoreCloud env vars (DEV_1_0 namespace — requires SSH tunnel for DB):
    DEV_1_0_DB_DRIVER, DEV_1_0_DB_USERNAME, DEV_1_0_DB_PASSWORD, DEV_1_0_DB_HOST,
    DEV_1_0_DB_PORT, DEV_1_0_DB_DATABASE_NAME, DEV_1_0_SSH_HOST, DEV_1_0_SSH_PORT,
    DEV_1_0_SSH_USERNAME, DEV_1_0_SSH_PASSWORD (or DEV_1_0_SSH_PKEY_PATH)

Optional:
    MOCK_CLOUD: Set to "1" to run in mock mode (no hardware required)
    DEVICE_ID: Device ID hex string (default in mock: 70B3D584C01E1FCC)
    FW_DEBUG_HEX: Path to debug nRF52840 app firmware hex on MTIB filesystem
    FW_RELEASE_HEX: Path to release nRF52840 app firmware hex on MTIB filesystem
    FW_DEBUG_COMMS_HEX: Path to debug nRF9151 comms coprocessor hex on MTIB filesystem
    FW_RELEASE_COMMS_HEX: Path to release nRF9151 comms coprocessor hex on MTIB filesystem
    FW_MODEM_ZIP: Path to nRF9151 modem firmware zip on MTIB filesystem (e.g., mfw_nrf91x1_2.0.2.zip)
    ARTIFACTS_DIR: Directory for test artifacts (UART logs, power traces)
    PROXY_SERVER_URL: CoreOps proxy URL for re-personalization (e.g., http://10.4.45.30:8001)
    DEVICE_SNR: J-Link probe serial number (e.g., 0964) — needed for re-personalization
    DEVICE_IMEI: Pre-known IMEI — skips modem read if set
    DEVICE_ICCIDS: Comma-separated ICCIDs — skips modem read if set

Concord Reporter (opt-in, Phase 6B):
    CONCORD_RUN_ID: Validation run ID — activates the reporter plugin.
    CONCORD_API_URL: Concord HTTP API base URL (e.g., http://concord-api:9001).
    CONCORD_API_KEY: API key for reporter auth.
    When set, test results are streamed to Concord in real-time.
    When NOT set, the reporter is completely inactive.
"""

import os
import logging
import time

import pytest

from corekinect.test.validation.test_context import TestContext

log = logging.getLogger(__name__)

# ── Mock mode detection ──────────────────────────────────────────
MOCK_MODE = os.environ.get("MOCK_CLOUD", "").strip().lower() in ("1", "true", "yes")

if MOCK_MODE:
    # Patch time.sleep to be near-instant in mock mode.
    # Stage 4 tests have time.sleep(30) and time.sleep(60) calls for hardware
    # settle times that are meaningless without real hardware.
    import time
    _real_sleep = time.sleep
    time.sleep = lambda s: _real_sleep(min(s, 0.01))

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
# When CONCORD_RUN_ID is not set, the reporter's pytest_configure is a no-op.
pytest_plugins = ["corekinect.test.validation.reporter"]


def _has_cloud_db() -> bool:
    """Check if CoreCloud DB credentials are configured."""
    return bool(
        os.environ.get("DEV_1_0_DB_HOST")
        or os.environ.get("CORECLOUD_DB_ENV")
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
    from corekinect.test.validation.mock_cloud import MockCloudClient
    from corekinect.test.validation.mock_hardware import (
        MockFixtureController,
        MockPowerProfiler,
        MockUartDemuxer,
    )

    device_id_hex = os.environ.get("DEVICE_ID", "70B3D584C01E1FCC")
    device_id = int(device_id_hex, 16)

    cloud = MockCloudClient(device_id=device_id)
    fixture = MockFixtureController()
    uart = MockUartDemuxer()
    power = MockPowerProfiler()

    log.info(
        "Mock mode: device_id=%s, no hardware connection",
        device_id_hex,
    )

    # TestContext accepts any duck-typed components
    return TestContext(
        mtib=None,
        cloud=cloud,
        fixture=fixture,
        uart=uart,
        power=power,
    )


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

    context = TestContext.from_env()
    context.connect()
    yield context
    context.disconnect()


@pytest.fixture(scope="session")
def mock_cloud(ctx):
    """Access MockCloudClient directly for scenario injection.

    Only available in mock mode. Returns None in hardware mode.

    Usage in tests:
        def test_something(ctx, mock_cloud):
            if mock_cloud:
                from corekinect.test.validation.mock_cloud import Scenario, ScenarioEngine
                engine = ScenarioEngine(mock_cloud)
                engine.load(Scenario.happy_boot(device_id=mock_cloud.device_id))
            msg = ctx.cloud.wait_for_boot(timeout_s=5)
    """
    from corekinect.test.validation.mock_cloud import MockCloudClient
    if isinstance(ctx.cloud, MockCloudClient):
        return ctx.cloud
    return None


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
    ctx.setup_test()  # mark_test_start + clear UART

    yield
    artifacts_dir = os.environ.get("ARTIFACTS_DIR")
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


def _ensure_uploaded(ctx: TestContext, local_path: str, target: str) -> str:
    """Upload a local firmware file to the MTIB server if not already uploaded.

    Env var values can be either:
      - A local file path (e.g., /firmware/app_nrf52840.hex) — uploaded automatically
      - A bare filename (e.g., app_nrf52840.hex) — assumed already on the server

    Returns:
        The server-side filename to pass to flash_firmware().
    """
    # If the file exists locally, upload it to the MTIB server
    if os.path.isfile(local_path):
        if local_path not in _uploaded_firmware:
            log.info("Uploading firmware to MTIB: %s → target=%s", local_path, target)
            ctx.fixture.upload_firmware(local_path, target)
            server_name = os.path.basename(local_path)
            _uploaded_firmware[local_path] = server_name
            log.info("Upload complete: %s (server name: %s)", local_path, server_name)
        return _uploaded_firmware[local_path]

    # Not a local file — treat as a server-side filename (backward compat)
    return local_path


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
    from corekinect.test.validation.mock_cloud import MockCloudClient
    if isinstance(ctx.cloud, MockCloudClient):
        from corekinect.test.validation.mock_cloud import Scenario, ScenarioEngine
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
    hex_env_var = f"FW_{variant.upper()}_HEX"
    hex_path = os.environ.get(hex_env_var)

    if not hex_path:
        pytest.skip(f"{hex_env_var} not set — skipping {variant} build tests")

    # nRF9151 comms coprocessor hex (optional — skips comms flash if not set)
    comms_hex_env = f"FW_{variant.upper()}_COMMS_HEX"
    comms_hex_path = os.environ.get(comms_hex_env)

    # nRF9151 modem firmware zip (required if comms is flashed — chiperase wipes modem)
    modem_fw_path = os.environ.get("FW_MODEM_ZIP")

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
    proxy_url = os.environ.get("PROXY_SERVER_URL")
    device_snr = os.environ.get("DEVICE_SNR")
    personalized = False

    if proxy_url and device_snr:
        from corekinect.test.validation.device_personalizer import DevicePersonalizer

        # Use pre-known IMEI/ICCIDs if available (avoids modem read)
        imei = os.environ.get("DEVICE_IMEI")
        iccids_str = os.environ.get("DEVICE_ICCIDS")
        iccids = [s.strip() for s in iccids_str.split(",") if s.strip()] if iccids_str else None

        personalizer = DevicePersonalizer(
            mtib=ctx.mtib,
            proxy_url=proxy_url,
            snr=device_snr,
            imei=imei,
            iccids=iccids,
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
            "PROXY_SERVER_URL or DEVICE_SNR not set — skipping re-personalization. "
            "Tests requiring CoreCloud connectivity may fail."
        )

    # If personalization didn't include a power cycle, do one now
    if not personalized:
        ctx.fixture.power_cycle()

    # Wait for CoreCloud boot message (only if DB is configured)
    db_env = os.environ.get("CORECLOUD_DB_ENV") or os.environ.get("DEV_1_0_DB_HOST")
    if db_env and personalized:
        boot = ctx.cloud.wait_for_boot(boot_reason=0, timeout_s=120)
        log.info(
            "Device booted: reason=%s, mcu=%s",
            boot.boot_reason_str,
            boot.coprocessor_str,
        )
    else:
        # No cloud DB or personalization failed — just wait for hardware boot
        log.info("Waiting for hardware boot settle (5s)...")
        time.sleep(5)

    _current_variant = variant
    yield variant
