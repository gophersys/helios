from dataclasses import dataclass


@dataclass(frozen=True)
class JumpTrackGPSConfigConstants:
    message_id = 0x28
    message_length = 0x7
    packed_format = "> B H I B B B"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "flags",  # unsigned char = B = 1 byte
        "target_accuracy",  # unsigned char = B = 1 byte
        "target_pdop",  # unsigned char = B = 1 byte
    ]
    aiding_enabled_bits = (3, 3)
    gnss_update_frequency_bits = (1, 2)
    low_power_enable_bits = (0, 0)


@dataclass(frozen=True)
class JumpTrackBleBeaconConfigConstants:
    message_id = 0x2C
    message_length = 0xC
    packed_format = "> B H I B B B b I"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "flags",  # unsigned char = B = 1 byte
        "beacon_period_seconds",  # unsigned char = B = 1 byte
        "beacon_duration_milliseconds",  # unsigned char = B = 1 byte
        "beacon_power",  # unsigned char = B = 1 byte
        "ble_session_key_crc",  # signed char = b = 1 byte
    ]
    is_beacon_bits = (1, 1)
    is_ble_beacon_scan_adv_enabled_bits = (0, 0)


@dataclass(frozen=True)
class JumpTrackEmergencyConfigConstants:
    message_id = 0x20
    message_length = 0x7
    packed_format = "> B H I B B B"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "time_limit_minutes",  # unsigned char = B = 1 byte
        "button_activation_time_seconds",  # unsigned char = B = 1 byte
        "button_timeout_seconds",  # unsigned char = B = 1 byte
    ]


@dataclass(frozen=True)
class JumpTrackFallConfigConstants:
    message_id = 0x22
    message_length = 0xF
    packed_format = "> B H I B B B B B H H B B"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "flags",  # unsigned char = B = 1 byte
        "jump_state_gps_report_period_seconds",  # unsigned char = B = 1 byte
        "jump_state_state_duration_minutes",  # unsigned char = B = 1 byte
        "free_fall_acceleration_threshold",  # unsigned char = B = 1 byte
        "free_fall_acceleration_duration_centiseconds",  # unsigned char = B = 1 byte
        "altitude_change_free_fall_trigger_ft_per_minute",  # unsigned short = H = 2 bytes
        "altitude_change_jump_trigger_ft_per_minute",  # unsigned short = H = 2 bytes
        "stable_altitude_num_samples",  # unsigned char = B = 1 byte
        "stable_altitude_threshold_ft",  # unsigned char = B = 1 byte
    ]
    jump_mode_enabled_bits = (7, 7)


@dataclass(frozen=True)
class JumpTrackGroundV1ConfigConstants:
    message_id = 0x21
    message_length = 0xE
    packed_format = "> B H I H B B B B B B B B"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "gps_heartbeat_period_minutes",  # unsigned short = H = 2 bytes
        "continuous_motion_period_seconds",  # unsigned char = B = 1 byte
        "stop_motion_timeout_seconds",  # unsigned char = B = 1 byte
        "heartbeat_acquisition_timeout_seconds",  # unsigned char = B = 1 byte
        "motion_acquisition_timeout_seconds",  # unsigned char = B = 1 byte
        "motion_acceleration_threshold",  # unsigned char = B = 1 byte
        "motion_acceleration_duration",  # unsigned char = B = 1 byte
        "start_motion_window_start",  # unsigned char = B = 1 byte
        "start_motion_window_end",  # unsigned char = B = 1 byte
    ]


@dataclass(frozen=True)
class JumpTrackGroundV2ConfigConstants:
    message_id = 0x36
    message_length = 0x15
    packed_format = "> B H I H H B B B B B B B B B I"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "gps_heartbeat_period_minutes",  # unsigned short = H = 2 bytes
        "continuous_motion_period_seconds",  # unsigned char = H = 2 bytes
        "stop_motion_timeout_seconds",  # unsigned char = B = 1 byte
        "heartbeat_acquisition_timeout_seconds",  # unsigned char = B = 1 byte
        "motion_acquisition_timeout_seconds",  # unsigned char = B = 1 byte
        "motion_acceleration_threshold",  # unsigned char = B = 1 byte
        "motion_acceleration_duration",  # unsigned char = B = 1 byte
        "start_motion_window_start_seconds",  # unsigned char = B = 1 byte
        "start_motion_window_end_seconds",  # unsigned char = B = 1 byte
        "motion_acquisition_on_time_seconds",  # unsigned char = B = 1 byte
        "motion_initial_acquisition_on_time_seconds",  # unsigned char = B = 1 byte
        "reserved",  # unsigned int = I = 4 bytes
    ]


@dataclass(frozen=True)
class JumpTrackHipsConfigConstants:
    message_id = 0x33
    message_length = 0xB
    packed_format = "> B H I I B H"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "flags",  # unsigned int = I = 4 bytes
        "group_code",  # unsigned char = B = 1 byte
        "source_user_id",  # unsigned short = H = 2 bytes
    ]
    force_checkin_bits = (7, 7)
    scan_constantly_bits = (6, 6)
    mode_bits = (0, 5)


@dataclass(frozen=True)
class JumpTrackLoRaConfigConstants:
    message_id = 0x26
    message_length = 0xC
    packed_format = "> B H I I I"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "flags",  # unsigned int = I = 4 bytes
        "session_config_crc",  # unsigned int = I = 4 bytes
    ]
    session_config_crc: int = 0  # NOTE: Session Config CRC is always 0, this may change in the future.
    lora_enabled_bits = (0, 0)


@dataclass(frozen=True)
class JumpTrackModemConfigConstants:
    message_id = 0x37
    message_length = 0xB
    packed_format = "> B H I B B B B B B B"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "short_backoff_time_seconds",  # unsigned char = B = 1 byte
        "normal_backoff_time_seconds",  # unsigned char = B = 1 byte
        "long_backoff_time_minutes",  # unsigned char = B = 1 byte
        "registration_timeout_period_minutes",  # unsigned char = B = 1 byte
        "socket_connection_timeout_period_minutes",  # unsigned char = B = 1 byte
        "connection_failure_threshold",  # unsigned char = B = 1 byte
        "socket_timeout_period_seconds",  # unsigned char = B = 1 byte
    ]


@dataclass(frozen=True)
class JumpTrackSimConfigConstants:
    message_id = 0x34
    message_length = 0x8
    packed_format = "> B H I I"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "timestamp",  # unsigned int = I = 4 bytes
        "flags",  # unsigned int = I = 4 bytes
    ]
    prevent_sim_swapping_bits = (1, 1)
    default_sim_select_bits = (0, 0)


@dataclass(frozen=True)
class JumpTrackServerConfigConstants:
    message_id = 0x35
    message_length: int  # Variable length message, calculated after the url and port are set.
    packed_format = f"> B H B H"  # plus " {len(self.url_encoded)}s"
    packed_struct = [
        "message_id",
        "message_length",
        "flags",
        "port",
        "url_encoded",
    ]
    server_type_bits = (2, 4)
    production_server_bits = (1, 1)
    write_bits = (0, 0)


@dataclass(frozen=True)
class JumpTrackRebootMessageConstants:
    message_id = 0x1E
    message_length = 0x8
    packed_format = "> B H I I"
    packed_struct = [
        "message_id",  # unsigned char = B = 1 byte
        "message_length",  # unsigned short = H = 2 bytes
        "reboot_pattern",  # unsigned int = I = 4 bytes
        "flags",  # unsigned int = I = 4 bytes
    ]
    reboot_pattern = 0xBEEFFACE
    reboot_9160_bits = (31, 31)
    reboot_52840_bits = (30, 30)
    do_hard_reset_bits = (29, 29)
    preserve_device_state_bits = (28, 28)
    cold_restart_gps_bits = (27, 27)
    reserved_bits = (0, 26)


@dataclass(frozen=True)
class JumpTrackPositionV5MessageConstants:
    message_id = 0x27
    message_length = None
    packed_format = None
    packed_struct = None
    reserved_31_28_bits = (28, 31)
    aiding_data_used_bits = (27, 27)
    on_charger_bits = (26, 26)
    fix_type_bits = (23, 25)
    num_of_satellites_bits = (18, 22)
    confirmed_time_available_bits = (17, 17)
    confirmed_time_bits = (16, 16)
    confirmed_date_bits = (15, 15)
    valid_time_bits = (14, 14)
    valid_date_bits = (13, 13)
    gnss_fix_ok_bits = (12, 12)
    gnss_fix_valid_bits = (11, 11)
    psm_state_bits = (8, 10)
    reserved_7_5_bits = (5, 7)
    update_reason_bits = (1, 4)
    in_motion_bits = (0, 0)

    fix_type_map = {
        0: "No Fix",
        1: "Dead Reckoning Only",
        2: "2D Fix",
        3: "3D Fix",
        4: "GNSS + Dead Reckoning Combined",
        5: "Time Only Fix",
    }

    psm_state_map = {
        0: "PSM is not active (device is in continuous mode)",
        1: "PSM Enabled (intermediate state before Acquisition state)",
        2: "Acquisition",
        3: "Tracking",
        4: "Power Optimized Tracking",
        5: "Inactive",
    }

    update_reason_map = {
        0: "Device Boot/First network join",
        1: "Heartbeat Message",
        2: "Stop Motion Event",
        3: "Emergency",
        4: "Jumping",
        5: "Continuous Motion",
        6: "In Plane",
        7: "Fall",
        8: "Landed",
        15: "Manufacturing Test",
    }


@dataclass(frozen=True)
class JumpTrackBootMessageConstants:
    message_id = 0x11
    message_length = None
    packed_format = None
    packed_struct = None
    mcu_type_bits = (7, 7)
    fw_triggered_bits = (6, 6)
    boot_reason_bits = (0, 5)

    mcu_type_map = {
        0: "nrf9160",
        1: "nrf52840",
    }

    fw_triggered_map = {
        0: "Soft reset",
        1: "FW-triggered reset",
    }

    boot_reason_map = {
        0: "Normal boot",
        1: "Reboot due to exception",
        2: "Reboot due to completing FUOTA",
        3: "Reboot due to being placed on charger",
        4: "Reboot due to error",
        5: "Reboot due to receiving valid reboot message",
        6: "Reboot due to watchdog timer expiration",
        7: "Reboot due to user button sequence",
    }


@dataclass
class DeviceType:
    board_name: str
    board_revision: str
    product_name: str
    target_microcontroller: str
    is_bootloader: bool
    is_manufacturing: bool


@dataclass(frozen=True)
class JumpTrackFirmwareV2MessageConstants:
    message_id = 0x16
    message_length = None
    packed_format = None
    packed_struct = None
    device_type_bits = (12, 21)
    device_version_bits = (2, 11)
    gold_bits = (1, 1)
    production_build_bits = (0, 0)

    # ID: board_name, board_revision, product_name, target_microcontroller, is_bootloader, is_manufacturing
    device_type_map = {
        44: DeviceType("RTEC", "E0", "Sigma 3", "nrf9160", False, False),
        45: DeviceType("RTEC", "E0", "Sigma 3", "nrf52840", False, False),
        46: DeviceType("RTEC", "E0", "Sigma 3 Manufacturing", "nrf9160", False, True),
        48: DeviceType("Sigma 5", "A3", "Sigma 5", "nrf9160", False, False),
        49: DeviceType("Sigma 5", "A3", "Sigma 5", "nrf52840", False, False),
        50: DeviceType("Sigma 5", "A3", "Sigma 5 Manufacturing", "nrf9160", False, True),
        51: DeviceType("Sigma 5", "B0", "Sigma 5", "nrf9160", False, False),
        52: DeviceType("Sigma 5", "B0", "Sigma 5", "nrf52840", False, False),
        53: DeviceType("Sigma 5", "B0", "Sigma 5 Manufacturing", "nrf9160", False, True),
        54: DeviceType("Lumen", "A0", "Lumen", "nrf9160", False, False),
        55: DeviceType("Lumen", "A0", "Lumen", "nrf52840", False, False),
        56: DeviceType("Sigma 7", "A0", "Sigma 7", "nrf9160", False, False),
        57: DeviceType("Sigma 7", "A0", "Sigma 7", "nrf52840", False, False),
        58: DeviceType("Sigma 5", "A0", "Theta PoC", "nrf9160", False, False),
        59: DeviceType("Sigma 5", "A0", "Theta PoC", "nrf52840", False, False),
        61: DeviceType("Sigma 5", "C0", "Sigma 5", "nrf9160", False, False),
        62: DeviceType("Sigma 5", "C0", "Sigma 5", "nrf52840", False, False),
        63: DeviceType("Sigma 5", "C0", "Sigma 5 Manufacturing", "nrf9160", False, True),
    }


@dataclass(frozen=True)
class JumpTrackHardwareFailureV2MessageConstants:
    message_id = 0x25
    message_length = None
    packed_format = None
    packed_struct = None

    accelerometer_communication_error_bits = (7, 7)
    accelerometer_reserved_bits = (0, 6)

    altimeter_communication_error_bits = (7, 7)
    altimeter_interrupt_failure_bits = (6, 6)
    altimeter_reserved_bits = (0, 5)

    gps_communication_error_bits = (7, 7)
    gps_crystal_failure_bits = (6, 6)
    gps_pvt_failure_bits = (5, 5)
    gps_v_back_failure_bits = (4, 4)
    gps_reserved_bits = (0, 3)

    lora_communication_error_bits = (7, 7)
    lora_pll_lock_failure_bits = (6, 6)
    lora_reserved_bits = (0, 5)

    ipc_communication_error_bits = (7, 7)
    ipc_reserved_bits = (0, 6)

    bms_communication_error_bits = (7, 7)
    bms_reserved_bits = (0, 6)

    external_flash_communication_error_bits = (7, 7)
    external_flash_reserved_bits = (0, 6)

    secure_element_communication_error_bits = (7, 7)
    secure_element_reserved_bits = (0, 6)


@dataclass(frozen=True)
class NetworkStatusV4MessageConstants:
    message_id = 0x09
    message_length = None
    packed_format = None
    packed_struct = None

    # flag bits
    flags_lte_connected_bits = (7, 7)
    flags_socket_connected_bits = (6, 6)
    flags_send_success_bits = (5, 5)
    flags_wireless_technology_bits = (4, 4)
    flags_active_sim_slot_bits = (3, 3)
    flags_early_socket_disconnect_bits = (2, 2)
    flags_dnssec_resolved_bits = (1, 1)
    flags_reserved_bits = (0, 0)

    wireless_technology_map = {
        0: "LTE Cat-M",
        1: "NB-IOT",
    }

    wireless_technology_map = {
        0: "LTE Cat-M",
        1: "NB-IOT",
    }
