from corekinect.core_cloud.msg_def_v1_0 import *


def gps_config():
    """Gps config."""
    conf = GPSConfMsg(
        is_psm_enabled=False,
        is_aiding_enabled=False,
        gnss_update_freq=0,
        target_fix_accuracy=10,
        target_fix_pdop=30,
    )

    conf.send(device_id=0x70B3D584C01E1445, env_namespace="VAL_1_0")


def ground_config():
    """Ground config."""
    conf = GroundModeConfigV2(
        gps_heartbeat_period_minutes=60,
        continuous_motion_period_seconds=6,
        stop_motion_timeout_seconds=60,
        heartbeat_acquisition_timeout_seconds=60,
        stop_motion_acquisition_timeout_seconds=60,
        motion_acceleration_threshold=3,
        motion_acceleration_duration=4,
        start_motion_window_start_seconds=3,
        start_motion_window_end_seconds=60,
        motion_acquisition_on_time_seconds=6,
        motion_initial_acquisition_on_time_seconds=60,
    )

    conf.send(device_id=0x70B3D584C01E1445, env_namespace="VAL_1_0")


def position_message():
    """Position message."""
    msg = PositionMsgV6.last(0x70B3D584C01E1445, env="VAL_1_0")
    print(msg.device_id_str)
    print(msg.temperature_celsius)
    print(msg.pressure_altitude_meters)


def scratchpad_message():
    """Scratchpad message."""
    from zoneinfo import ZoneInfo

    start_time = datetime(2025, 10, 23, 16, 0, 0, tzinfo=ZoneInfo("America/Phoenix"))
    msgs = ScratchpadMsg.since_server_time(0x70B3D584C01E1445, start_time=start_time, env="VAL_1_0")
    breakpoint
    for message in msgs:
        print(message.payload_as_string)


if __name__ == "__main__":
    scratchpad_message()
