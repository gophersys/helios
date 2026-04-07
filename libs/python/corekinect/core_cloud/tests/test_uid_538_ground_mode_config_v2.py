"""
Manual script for sending a GroundModeConfigV2 message via CoreCloud API.

This is NOT an automated test — it performs real API calls and was placed here
by mistake. It has been converted to a skipped test to prevent collection errors.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Manual script, not an automated test — requires live API connection")


def test_ground_mode_config_v2_send():
    """Placeholder — original script sent config via send_via_api()."""
    from corekinect.core_cloud.messages import GroundModeConfigV2

    gnd_conf = GroundModeConfigV2(
        gps_heartbeat_period_minutes=60,
        continuous_motion_period_seconds=0,
        stop_motion_timeout_seconds=60,
        heartbeat_acquisition_timeout_seconds=60,
        stop_motion_acquisition_timeout_seconds=0,
        motion_acceleration_threshold=29,
        motion_acceleration_duration=2,
        start_motion_window_start_seconds=3,
        start_motion_window_end_seconds=10,
        motion_acquisition_on_time_seconds=30,
        motion_initial_acquisition_on_time_seconds=60,
    )

    b64 = gnd_conf.pack_to_base64()
    assert b64 is not None
