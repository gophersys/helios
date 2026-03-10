"""pytest fixtures for Theta Stage 4 product validation tests.

Theta is an asset tracker device with:
- LSM6DSO 6-axis IMU (motion detection)
- BME280 environmental sensor (temp/humidity/pressure)
- u-blox GPS module
- BQ25798 battery charger
- Optional NFC on membrane daughter board
- NO biometric sensors (no PPG/VSM)
- NO RGB status LEDs

Required environment variables:
    MTIB_HOST, MTIB_PORT, DEVICE_ID, FIXTURE_PROFILE_PATH

Optional:
    MOCK_CLOUD: Set to "1" for mock mode
    FW_DEBUG_HEX, FW_RELEASE_HEX: Firmware paths
    FW_DEBUG_COMMS_HEX, FW_RELEASE_COMMS_HEX: Comms coprocessor firmware
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
    """Theta validation test config."""
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

    PROXY_SERVER_URL: Optional[str] = None
    DEVICE_IMEI: Optional[str] = None
    DEVICE_ICCIDS: Optional[str] = None

    CORECLOUD_DB_ENV: Optional[str] = None
    ARTIFACTS_DIR: Optional[str] = None
    MOCK_CLOUD: Optional[str] = None


cfg = ValidationConfig()
log = Logger(log_name="theta-validation")

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


@pytest.fixture(scope="session")
def ctx():
    """Shared test context for all tests."""
    profile_path = cfg.FIXTURE_PROFILE_PATH
    if not profile_path:
        default_profile = Path(__file__).parent / "fixtures" / "theta_c0.json"
        if default_profile.exists():
            profile_path = str(default_profile)
        else:
            pytest.fail("FIXTURE_PROFILE_PATH not set and no default fixture found")

    mtib_address = cfg.MTIB_ADDRESS or f"{cfg.MTIB_HOST}:{cfg.MTIB_PORT}"
    if not mtib_address or mtib_address == ":50053":
        pytest.fail("MTIB_ADDRESS or MTIB_HOST not configured")

    log.info("Creating TestContext: mtib=%s profile=%s", mtib_address, profile_path)

    context = TestContext(
        mtib_address=mtib_address,
        fixture_profile_path=profile_path,
        mock_mode=MOCK_MODE,
        artifacts_dir=cfg.ARTIFACTS_DIR,
    )

    # Override device ID if provided
    if cfg.DEVICE_ID:
        context.device_id = cfg.DEVICE_ID

    yield context

    log.info("Tearing down TestContext")
    context.teardown()


@pytest.fixture
def firmware_build(ctx):
    """Ensure DUT has firmware flashed and is ready for testing."""
    # For most tests, we assume firmware is already flashed
    # Individual tests can request a specific firmware variant if needed
    yield ctx
