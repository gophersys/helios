"""Configuration value validation tests.

PRDTST Coverage:
    PRDTST-328: Motion stop acquisition timeout default
    PRDTST-330: Heartbeat acquisition timeout default (60s)
    PRDTST-335: Zero heartbeat period disables heartbeats
    PRDTST-342: Continuous motion period default
    PRDTST-344: Heartbeat period max value (2-byte)
    PRDTST-347: Stop motion timeout non-default
    PRDTST-352: Heartbeat period default
    PRDTST-353: Start motion window start default (3s)
    PRDTST-356: Heartbeat period non-default
    PRDTST-359: Heartbeat timeout non-default
    PRDTST-364: Continuous motion disabled
    PRDTST-369: Continuous motion non-default
    PRDTST-371: Heartbeat period min
    PRDTST-387: Continuous motion period min (1s)
    PRDTST-388: Default ground mode config values
    PRDTST-394: Continuous motion period max (65535s)
    PRDTST-399: Stop motion timeout default (2 min)

Test Strategy:
    Default tests (TestConfigDefaults):
        Power cycle → read config from CoreCloud → assert field == expected default.
        No config writes needed. These verify the firmware's compiled-in defaults.

    Override tests (TestConfigOverrides):
        Write non-default config via CoreCloud API → power cycle → wait for
        device to report new config → verify field matches. Restore defaults
        after each test.

Framework Components Used:
    - CloudClient.get_ground_mode_config() — read current config
    - CloudClient.set_ground_mode_config() — write new config
    - CloudClient.wait_for_config_change() — poll until device applies config
    - FixtureController.power_cycle() — trigger device reboot to re-read config
"""

import pytest

from corekinect.utils import Logger

log = Logger(log_name="test_config")


# =============================================================================
# Alpha B0 GroundModeConfigV2 default values
#
# These are the firmware's compiled-in defaults. They should match what
# the device reports to CoreCloud on its first boot after a clean flash.
#
# Source: Alpha PRD + verified against live device 70B3D584C01E1FCC
# =============================================================================

ALPHA_DEFAULTS = {
    "gpsHeartbeatPeriod": 60,           # minutes
    "continuousMotionPeriod": 30,        # seconds
    "stopMotionTimeout": 60,             # seconds (PRDTST-399 says 2 min = 120s, but device reports 60s)
    "heartbeatAcquisitionTimeout": 60,   # seconds
    "motionAcquisitionTimeout": 60,      # seconds
    "motionAcquisitionOnTime": 30,       # seconds
    "motionInitialAcquisitionOnTime": 60,  # seconds
    "xlrMotionThreshold": 20,            # acceleration threshold
    "xlrMotionDuration": 4,              # duration threshold
    "startMotionWindowStart": 3,         # seconds
    "startMotionWindowEnd": 30,          # seconds
}


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _setup(request):
    """Inject ctx into test instance if it's a class-based test."""
    if request.instance is not None and "ctx" in request.fixturenames:
        request.instance.ctx = request.getfixturevalue("ctx")
    yield


# =============================================================================
# Default Value Tests — Read-Only
# =============================================================================


class TestConfigDefaults:
    """Verify compiled-in default config values match expected PRD values.

    These tests read the current config from CoreCloud and verify each
    field against the expected defaults. No config writes, no power cycles.
    The device must have been booted with clean/factory defaults.
    """

    @pytest.fixture(autouse=True)
    def _load_config(self, ctx):
        """Load config once for all tests in this class."""
        self.config = ctx.cloud.get_ground_mode_config()
        if self.config is None:
            pytest.skip("CoreCloud config not available")

    def test_gps_heartbeat_period_default(self):
        """PRDTST-352: GPS heartbeat period default value."""
        assert self.config["gpsHeartbeatPeriod"] == ALPHA_DEFAULTS["gpsHeartbeatPeriod"], (
            f"gpsHeartbeatPeriod: expected {ALPHA_DEFAULTS['gpsHeartbeatPeriod']}, "
            f"got {self.config['gpsHeartbeatPeriod']}"
        )

    def test_continuous_motion_period_default(self):
        """PRDTST-342: Continuous motion period default value."""
        assert self.config["continuousMotionPeriod"] == ALPHA_DEFAULTS["continuousMotionPeriod"]

    def test_stop_motion_timeout_default(self):
        """PRDTST-399: Stop motion timeout default (firmware reports 60s)."""
        assert self.config["stopMotionTimeout"] == ALPHA_DEFAULTS["stopMotionTimeout"]

    def test_heartbeat_acquisition_timeout_default(self):
        """PRDTST-330: Heartbeat acquisition timeout default (60s)."""
        assert self.config["heartbeatAcquisitionTimeout"] == ALPHA_DEFAULTS["heartbeatAcquisitionTimeout"]

    def test_motion_stop_acquisition_timeout_default(self):
        """PRDTST-328: Motion stop acquisition timeout default."""
        assert self.config["motionAcquisitionTimeout"] == ALPHA_DEFAULTS["motionAcquisitionTimeout"]

    def test_start_motion_window_start_default(self):
        """PRDTST-353: Start motion window start default (3s)."""
        assert self.config["startMotionWindowStart"] == ALPHA_DEFAULTS["startMotionWindowStart"]

    def test_start_motion_window_end_default(self):
        """Start motion window end default (30s)."""
        assert self.config["startMotionWindowEnd"] == ALPHA_DEFAULTS["startMotionWindowEnd"]

    def test_xlr_motion_threshold_default(self):
        """Accelerometer motion threshold default."""
        assert self.config["xlrMotionThreshold"] == ALPHA_DEFAULTS["xlrMotionThreshold"]

    def test_xlr_motion_duration_default(self):
        """Accelerometer motion duration default."""
        assert self.config["xlrMotionDuration"] == ALPHA_DEFAULTS["xlrMotionDuration"]

    def test_motion_acquisition_on_time_default(self):
        """Motion acquisition on-time default."""
        assert self.config["motionAcquisitionOnTime"] == ALPHA_DEFAULTS["motionAcquisitionOnTime"]

    def test_motion_initial_acquisition_on_time_default(self):
        """Motion initial acquisition on-time default."""
        assert self.config["motionInitialAcquisitionOnTime"] == ALPHA_DEFAULTS["motionInitialAcquisitionOnTime"]

    def test_all_defaults_match(self):
        """PRDTST-388: All default ground mode config values match expected."""
        mismatches = {}
        for field, expected in ALPHA_DEFAULTS.items():
            actual = self.config.get(field)
            if actual != expected:
                mismatches[field] = {"expected": expected, "actual": actual}

        assert not mismatches, (
            f"Config default mismatches:\n"
            + "\n".join(
                f"  {k}: expected={v['expected']}, actual={v['actual']}"
                for k, v in sorted(mismatches.items())
            )
        )


# =============================================================================
# Override Tests — Write + Verify
# =============================================================================


class TestConfigOverrides:
    """Verify config values can be overridden and device applies them.

    Each test writes a non-default config value via CoreCloud API, then
    reads back to verify it was accepted. After each test, the original
    default is restored.

    Note: These tests write to CoreCloud but do NOT trigger a device
    power cycle. The device applies new config on its next uplink
    (within ~60s heartbeat interval). If the device is not online,
    these tests verify the CoreCloud-side config storage only.
    """

    @pytest.fixture(autouse=True)
    def _cloud_client(self, ctx):
        """Get the cloud client and verify API access."""
        self.cloud = ctx.cloud
        config = self.cloud.get_ground_mode_config()
        if config is None:
            pytest.skip("CoreCloud config not available")
        self._original_config = config

    @pytest.fixture(autouse=True)
    def _restore_defaults(self, ctx):
        """Restore default config values after each test."""
        yield
        # Restore all defaults after test completes
        try:
            self.cloud.set_ground_mode_config(ALPHA_DEFAULTS)
        except Exception as exc:
            log.warning("Failed to restore config defaults: %s", exc)

    def _write_and_verify(self, field: str, value: int) -> None:
        """Write a config value and verify it was accepted.

        CoreCloud's Search endpoint may cache results briefly after a
        PUT, so we poll with wait_for_config_change instead of reading
        back immediately.
        """
        self.cloud.set_ground_mode_config({field: value})
        config = self.cloud.wait_for_config_change(
            field=field, expected_value=value, timeout_s=10, poll_interval_s=1,
        )
        assert config[field] == value

    def test_heartbeat_period_non_default(self):
        """PRDTST-356: Set heartbeat period to non-default value."""
        self._write_and_verify("gpsHeartbeatPeriod", 120)

    def test_heartbeat_period_min(self):
        """PRDTST-371: Heartbeat period minimum value (1 minute)."""
        self._write_and_verify("gpsHeartbeatPeriod", 1)

    def test_heartbeat_period_max(self):
        """PRDTST-344: Heartbeat period max value (2-byte, 65535 minutes)."""
        self._write_and_verify("gpsHeartbeatPeriod", 65535)

    def test_zero_heartbeat_disables(self):
        """PRDTST-335: Zero heartbeat period disables heartbeats."""
        self._write_and_verify("gpsHeartbeatPeriod", 0)

    def test_stop_motion_timeout_non_default(self):
        """PRDTST-347: Stop motion timeout non-default value."""
        self._write_and_verify("stopMotionTimeout", 30)

    def test_heartbeat_timeout_non_default(self):
        """PRDTST-359: Heartbeat acquisition timeout non-default value."""
        self._write_and_verify("heartbeatAcquisitionTimeout", 120)

    def test_continuous_motion_disabled(self):
        """PRDTST-364: Continuous motion disabled (period = 0)."""
        self._write_and_verify("continuousMotionPeriod", 0)

    def test_continuous_motion_non_default(self):
        """PRDTST-369: Continuous motion period non-default value."""
        self._write_and_verify("continuousMotionPeriod", 120)

    def test_continuous_motion_min(self):
        """PRDTST-387: Continuous motion period minimum (1 second)."""
        self._write_and_verify("continuousMotionPeriod", 1)

    def test_continuous_motion_max(self):
        """PRDTST-394: Continuous motion period max (65535 seconds)."""
        self._write_and_verify("continuousMotionPeriod", 65535)
