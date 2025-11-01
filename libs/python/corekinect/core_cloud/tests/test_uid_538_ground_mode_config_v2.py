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

gnd_conf.send_via_api(0x70B3D584C01E1445, env="VAL_1_0")

b64 = gnd_conf.pack_to_base64()
breakpoint
# NgAVAAAAAAA8AAA8PAAdAgMKHjwAAAAA
