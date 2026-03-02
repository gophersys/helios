"""pytest fixtures for Stage 4 product validation tests.

Provides session-scoped TestContext and per-test firmware variant
parametrization. Tests receive a connected, ready-to-use context.

Required environment variables (see TestContext.from_env):
    MTIB_HOST, MTIB_PORT, DEVICE_ID, FIXTURE_PROFILE_PATH

    CoreCloud env vars (DEV_1_0 namespace — requires SSH tunnel for DB):
    DEV_1_0_DB_DRIVER, DEV_1_0_DB_USERNAME, DEV_1_0_DB_PASSWORD, DEV_1_0_DB_HOST,
    DEV_1_0_DB_PORT, DEV_1_0_DB_DATABASE_NAME, DEV_1_0_SSH_HOST, DEV_1_0_SSH_PORT,
    DEV_1_0_SSH_USERNAME, DEV_1_0_SSH_PASSWORD (or DEV_1_0_SSH_PKEY_PATH)

Optional:
    FW_DEBUG_HEX: Path to debug firmware hex on MTIB filesystem
    FW_RELEASE_HEX: Path to release firmware hex on MTIB filesystem
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

import pytest

from .test_context import TestContext

log = logging.getLogger(__name__)

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
# When CONCORD_RUN_ID is not set, the reporter's pytest_configure is a no-op.
pytest_plugins = ["corekinect.test.validation.reporter"]


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


@pytest.fixture(scope="session")
def ctx(request) -> TestContext:
    """Session-scoped test context — connects once, reused across all tests.

    Reads configuration from environment variables. CLI options
    override env vars when provided.
    """
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


@pytest.fixture(autouse=True)
def _test_lifecycle(ctx: TestContext, request):
    """Auto-applied fixture for per-test setup/teardown.

    - Calls ctx.setup_test() before each test (marks test start, clears UART).
    - Calls ctx.teardown_test() after each test (dumps UART logs).
    """
    ctx.setup_test()
    yield
    artifacts_dir = os.environ.get("ARTIFACTS_DIR")
    ctx.teardown_test(request.node.name, artifacts_dir)


@pytest.fixture(params=["debug", "release"])
def firmware_build(ctx: TestContext, request) -> str:
    """Parametrize tests on debug + release firmware.

    Flashes the appropriate firmware before the first test of each
    variant, then automatically re-personalizes the device (J-Link
    chiperase wipes personalization). Subsequent tests in the same
    variant reuse the running firmware (no re-flash).

    The firmware hex path is read from FW_DEBUG_HEX / FW_RELEASE_HEX
    environment variables. These point to hex files already uploaded
    to the MTIB server filesystem.

    Re-personalization requires PROXY_SERVER_URL and DEVICE_SNR env vars.
    If PROXY_SERVER_URL is not set, re-personalization is skipped (tests
    that depend on CoreCloud connectivity may fail).

    Yields:
        "debug" or "release" — the current firmware variant.
    """
    variant = request.param
    hex_env_var = f"FW_{variant.upper()}_HEX"
    hex_path = os.environ.get(hex_env_var)

    if not hex_path:
        pytest.skip(f"{hex_env_var} not set — skipping {variant} build tests")

    # Flash firmware (the fixture controller handles recover + verify)
    log.info("Flashing %s firmware: %s", variant, hex_path)
    ctx.fixture.flash_firmware(hex_path, target="nrf52840")

    # Re-personalize after flash (chiperase wipes EC keypair + config)
    proxy_url = os.environ.get("PROXY_SERVER_URL")
    device_snr = os.environ.get("DEVICE_SNR")

    if proxy_url and device_snr:
        from .device_personalizer import DevicePersonalizer

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
        result, err = personalizer.repersonalize(
            power_cycle=True,   # Power cycle included in repersonalize
            lock_shells=True,
        )
        if err:
            pytest.fail(f"Re-personalization failed after {variant} flash: {err}")
        log.info("Re-personalized: device_id=%s", result.device_id)
    else:
        log.warning(
            "PROXY_SERVER_URL or DEVICE_SNR not set — skipping re-personalization. "
            "Tests requiring CoreCloud connectivity may fail."
        )
        # Still power cycle and wait for boot
        ctx.fixture.power_cycle()

    # Wait for CoreCloud boot message
    boot = ctx.cloud.wait_for_boot(boot_reason=0, timeout_s=120)
    log.info(
        "Device booted: reason=%s, mcu=%s",
        boot.boot_reason_str,
        boot.coprocessor_str,
    )

    yield variant
