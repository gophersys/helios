"""pytest fixtures for Sigma5 Stage 4 product validation tests.

Sigma5 is an asset tracker device with:
- LIS2DE12 accelerometer (motion detection)
- BMP388 pressure sensor (altitude)
- ZOE-M8 GPS module
- MAX17055 fuel gauge
- Qi wireless charging
- NO biometric sensors (no PPG/VSM)
- NO NFC
- NO RGB LEDs

Required environment variables:
    MTIB_HOST, MTIB_PORT, DEVICE_ID, FIXTURE_PROFILE_PATH

Optional:
    MOCK_CLOUD: Set to "1" for mock mode
    FW_DEBUG_HEX, FW_RELEASE_HEX: Firmware paths
    FW_DEBUG_COMMS_HEX, FW_RELEASE_COMMS_HEX: Comms coprocessor firmware
    FW_MODEM_ZIP: nRF9160 modem firmware
    ARTIFACTS_DIR: Test artifacts directory
    DEVICE_SNR, DEVICE_IMEI, DEVICE_ICCIDS: Device identity
    CONCORD_RUN_ID, CONCORD_API_URL, CONCORD_API_KEY: Reporter config
"""

import os
import time
from pathlib import Path
from typing import Optional

import pytest
from dotenv import load_dotenv

try:
    _root_env = Path(__file__).resolve().parents[3] / ".env"
    if _root_env.exists():
        load_dotenv(_root_env, override=False)
except IndexError:
    pass

from corekinect.test.validation.test_context import TestContext
from corekinect.utils import EnvConfig, Logger


class ValidationConfig(EnvConfig):
    """Sigma5 validation test config."""
    ENV_PREFIX = ""

    MTIB_ADDRESS: Optional[str] = None
    MTIB_HOST: Optional[str] = None
    MTIB_PORT: int = 50053

    DEVICE_ID: str = ""
    DEVICE_SNR: Optional[str] = None
    FIXTURE_PROFILE_PATH: Optional[str] = None
    BENCH_ID: Optional[str] = None

    FW_DEBUG_HEX: Optional[str] = None
    FW_RELEASE_HEX: Optional[str] = None
    FW_DEBUG_COMMS_HEX: Optional[str] = None
    FW_RELEASE_COMMS_HEX: Optional[str] = None
    FW_MODEM_ZIP: Optional[str] = None

    PROXY_SERVER_URL: Optional[str] = None
    DEVICE_IMEI: Optional[str] = None
    DEVICE_ICCIDS: Optional[str] = None

    CORECLOUD_DB_ENV: Optional[str] = None
    ARTIFACTS_DIR: Optional[str] = None
    MOCK_CLOUD: Optional[str] = None


cfg = ValidationConfig()
log = Logger(log_name="sigma5-validation")

MOCK_MODE = (cfg.MOCK_CLOUD or "").strip().lower() in ("1", "true", "yes")

if MOCK_MODE:
    import time
    _real_sleep = time.sleep
    time.sleep = lambda s: _real_sleep(min(s, 0.01))

pytest_plugins = ["corekinect.test.validation.reporter"]


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "corecloud: marks tests that require CoreCloud connectivity",
    )
    config.addinivalue_line(
        "markers",
        "motion: marks tests that require motion actuator",
    )
    config.addinivalue_line(
        "markers",
        "gps: marks tests that require GPS signal/simulation",
    )


def _has_cloud_db() -> bool:
    return bool(
        cfg.CORECLOUD_DB_ENV
        or os.environ.get("DEV_1_0_DB_HOST")
        or os.environ.get("VAL_1_0_DB_HOST")
    )


def pytest_collection_modifyitems(config, items):
    """Skip cloud tests if not configured; reorder for firmware efficiency."""
    skip_reason = None
    if _is_mock_mode(config):
        skip_reason = "Requires CoreCloud DB/API - skipped in mock mode"
    elif not _has_cloud_db():
        skip_reason = "CoreCloud DB not configured"

    if skip_reason:
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "corecloud" in item.keywords:
                item.add_marker(skip_marker)

    def _variant_sort_key(item):
        if "[release]" in item.nodeid:
            return (1, item.nodeid)
        if "[debug]" in item.nodeid:
            return (0, item.nodeid)
        return (-1, item.nodeid)

    items.sort(key=_variant_sort_key)


def pytest_addoption(parser):
    parser.addoption("--device-id", action="store", default=None)
    parser.addoption("--mtib-host", action="store", default=None)
    parser.addoption("--artifacts-dir", action="store", default=None)
    parser.addoption("--db-env", action="store", default=None)
    parser.addoption("--mock-cloud", action="store_true", default=False)


def _is_mock_mode(config) -> bool:
    if MOCK_MODE:
        return True
    try:
        return config.getoption("--mock-cloud", default=False)
    except ValueError:
        return False


def _build_mock_context() -> TestContext:
    from corekinect.test.validation.mock_cloud import MockCloudClient
    from corekinect.test.validation.mock_hardware import (
        MockFixtureController,
        MockPowerProfiler,
        MockUartDemuxer,
    )

    device_id = int(cfg.DEVICE_ID, 16) if cfg.DEVICE_ID else 0

    cloud = MockCloudClient(device_id=device_id)
    fixture = MockFixtureController()
    uart = MockUartDemuxer()
    power = MockPowerProfiler()

    log.info("Mock mode: device_id=%s", cfg.DEVICE_ID or "mock")

    return TestContext(
        mtib=None,
        cloud=cloud,
        fixture=fixture,
        uart=uart,
        power=power,
    )


@pytest.fixture(scope="session")
def ctx(request) -> TestContext:
    """Session-scoped test context."""
    if _is_mock_mode(request.config):
        context = _build_mock_context()
        yield context
        return

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
    """Access MockCloudClient for scenario injection."""
    from corekinect.test.validation.mock_cloud import MockCloudClient
    if isinstance(ctx.cloud, MockCloudClient):
        return ctx.cloud
    return None


@pytest.fixture(autouse=True)
def _test_lifecycle(request):
    """Per-test setup/teardown."""
    if "ctx" not in request.fixturenames:
        yield
        return

    ctx = request.getfixturevalue("ctx")
    ctx.setup_test()
    yield
    artifacts_dir = cfg.ARTIFACTS_DIR
    ctx.teardown_test(request.node.name, artifacts_dir)
    if artifacts_dir and ctx.artifacts.enabled:
        uart_log = os.path.join(artifacts_dir, f"{request.node.name}_uart.log")
        if os.path.isfile(uart_log):
            ctx.artifacts.upload(uart_log, f"{request.node.name}_uart.log")


_uploaded_firmware: dict = {}
_current_variant: str = ""


def _ensure_uploaded(ctx: TestContext, path: str, target: str) -> str:
    """Upload firmware to MTIB server."""
    if os.path.isfile(path):
        if path not in _uploaded_firmware:
            log.info("Uploading firmware: %s -> %s", path, target)
            server_name = ctx.firmware.upload_local(path, target)
            _uploaded_firmware[path] = server_name
        return _uploaded_firmware[path]

    if "/" in path and ctx.firmware.storage_enabled:
        if path not in _uploaded_firmware:
            log.info("Fetching from MinIO: %s -> %s", path, target)
            server_name = ctx.firmware.fetch_and_upload(path, target)
            _uploaded_firmware[path] = server_name
        return _uploaded_firmware[path]

    return path


@pytest.fixture(params=["debug", "release"])
def firmware_build(ctx: TestContext, request) -> str:
    """Parametrize tests on debug + release firmware."""
    global _current_variant
    variant = request.param

    if _current_variant == variant:
        log.info("Firmware %s already flashed, skipping", variant)
        yield variant
        return

    from corekinect.test.validation.mock_cloud import MockCloudClient
    if isinstance(ctx.cloud, MockCloudClient):
        from corekinect.test.validation.mock_cloud import Scenario, ScenarioEngine
        ctx.fixture.flash_firmware(f"mock_{variant}.hex")
        engine = ScenarioEngine(ctx.cloud)
        engine.load(Scenario.full_device_activity(device_id=ctx.cloud.device_id))
        log.info("Mock mode: simulated %s flash + boot", variant)
        _current_variant = variant
        yield variant
        return

    hex_path = getattr(cfg, f"FW_{variant.upper()}_HEX", None)
    if not hex_path:
        pytest.skip(f"FW_{variant.upper()}_HEX not set")

    comms_hex_path = getattr(cfg, f"FW_{variant.upper()}_COMMS_HEX", None)
    modem_fw_path = cfg.FW_MODEM_ZIP

    # Flash nRF52840
    server_hex = _ensure_uploaded(ctx, hex_path, "nrf52840")
    log.info("Flashing %s nRF52840: %s", variant, server_hex)
    ctx.fixture.flash_firmware(server_hex, target="nrf52840")

    # Flash nRF9160 comms (if provided)
    if comms_hex_path:
        if modem_fw_path:
            server_modem = _ensure_uploaded(ctx, modem_fw_path, "nrf9160_modem")
            log.info("Flashing nRF9160 modem: %s", server_modem)
            ctx.fixture.flash_firmware(server_modem, target="nrf9160_modem")

        server_comms = _ensure_uploaded(ctx, comms_hex_path, "nrf9160")
        log.info("Flashing %s nRF9160: %s", variant, server_comms)
        ctx.fixture.flash_firmware(server_comms, target="nrf9160")

    # Re-personalize
    device_snr = cfg.DEVICE_SNR
    personalized = False

    if device_snr:
        from corekinect.test.validation.device_personalizer import DevicePersonalizer

        imei = cfg.DEVICE_IMEI
        iccids_str = cfg.DEVICE_ICCIDS
        iccids = [s.strip() for s in iccids_str.split(",") if s.strip()] if iccids_str else None

        known_device_id = None
        if ctx.fixture.profile and ctx.fixture.profile.dut:
            known_device_id = ctx.fixture.profile.dut.device_id

        personalizer = DevicePersonalizer(
            mtib=ctx.mtib,
            snr=device_snr,
            imei=imei,
            iccids=iccids,
            db_env=cfg.CORECLOUD_DB_ENV,
            logger=log,
            known_device_id=known_device_id,
        )
        try:
            result, err = personalizer.repersonalize(power_cycle=True, lock_shells=True)
            if err:
                log.warning("Re-personalization failed: %s", err)
            else:
                log.info("Re-personalized: device_id=%s", result.device_id)
                personalized = True
        except Exception as e:
            log.warning("Re-personalization exception: %s", e)
    else:
        log.warning("DEVICE_SNR not set - skipping re-personalization")

    if not personalized:
        ctx.fixture.power_cycle()

    db_env = cfg.CORECLOUD_DB_ENV or os.environ.get("DEV_1_0_DB_HOST")
    if db_env and personalized:
        boot = ctx.cloud.wait_for_boot(boot_reason=0, timeout_s=120)
        if isinstance(boot, dict):
            log.info("Device booted: reason=%s", boot.get("bootReason", "unknown"))
        else:
            log.info("Device booted: reason=%s", getattr(boot, "boot_reason_str", "unknown"))
    else:
        log.info("Waiting for hardware boot settle (5s)...")
        time.sleep(5)

    _current_variant = variant
    yield variant
