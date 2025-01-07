from dataclasses import dataclass
from datetime import datetime


@dataclass
class DownlinkMessage:
    downlink_message_id: int = None
    device_id: int = None
    device_type_id: int = None
    time_queued: datetime = None
    nonce_sent: int = None
    is_acked: bool = None
    is_naked: bool = None
    message: str = None


@dataclass
class JumpTrackGpsConfig:
    checkin_id: int = None
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_gps_config: int = None
    flags: int = None
    aiding_enabled: bool = None  # Decoded from flags
    gnss_update_frequency: int = None  # Decoded from flags
    low_power_enabled: bool = None  # Decoded from flags


class JumpTrackGpsConfig:
    checkin_id: int = None
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_gps_config: int = None
    flags: int = None
    aiding_enabled: bool = None  # Decoded from flags
    gnss_update_frequency: int = None  # Decoded from flags
    low_power_enabled: bool = None  # Decoded from flags
    target_accuracy: int = None
    target_pdop: int = None


@dataclass
class JumpTrackBleBeaconConfig:
    checkin_id: int = None
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_config: int = None
    flags: int = None
    is_beacon_enabled: bool = None  # Decoded from flags
    is_ble_beacon_scan_advertising_enabled: bool = None  # Decoded from flags
    beacon_period_seconds: int = None
    beacon_duration_milliseconds: int = None
    beacon_power: int = None
    ble_session_key_crc: int = None


@dataclass
class JumpTrackEmergencyConfig:
    device_id: int = None
    time_limit_minutes: int = None
    button_activation_time_seconds: int = None
    button_timeout_seconds: int = None
    downlink_message_id: int = None


@dataclass
class JumpTrackFallConfig:
    checkin_id: int = None
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_config: int = None
    flags: int = None
    jump_mode_enabled: bool = None
    jump_state_gps_report_period_seconds: int = None
    jump_state_state_duration_minutes: int = None
    free_fall_acceleration_threshold: int = None
    free_fall_acceleration_duration_centiseconds: int = None
    altitude_change_free_fall_trigger_ft_per_minute: int = None
    altitude_change_jump_trigger_ft_per_minute: int = None
    stable_altitude_num_samples: int = None
    stable_altitude_threshold_ft: int = None


@dataclass
class JumpTrackGndConfigV1:
    checkin_id: int = None
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_config: int = None
    gps_heartbeat_period_minutes: int = None
    continuous_motion_period_seconds: int = None
    stop_motion_timeout_seconds: int = None
    heartbeat_acquisition_timeout_seconds: int = None
    motion_acquisition_timeout_seconds: int = None
    motion_acceleration_threshold: int = None
    motion_acceleration_duration: int = None
    start_motion_window_start: int = None
    start_motion_window_end: int = None


@dataclass
class JumpTrackGndConfigV2:
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_config: int = None
    gps_heartbeat_period_minutes: int = None
    continuous_motion_period_seconds: int = None
    stop_motion_timeout_seconds: int = None
    heartbeat_acquisition_timeout_seconds: int = None
    motion_acquisition_timeout_seconds: int = None
    motion_acceleration_threshold: int = None
    motion_acceleration_duration: int = None
    start_motion_window_start_seconds: int = None
    start_motion_window_end_seconds: int = None
    motion_acquisition_on_time_seconds: int = None
    motion_initial_acquisition_on_time_seconds: int = None


@dataclass
class JumpTrackHipsConfig:
    device_id: int = None
    time_received: int = None
    from_device: int = None
    nonce_received: int = None
    time_of_config: int = None
    flags: int = None
    report_period_seconds: int = None
    force_checkin: bool = None  # Decoded from flags
    scan_constantly: bool = None  # Decoded from flags
    mode: int = None  # Decoded from flags
    group_code: int = None
    source_user_id: int = None


@dataclass
class JumpTrackLoRaConfig:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    time_of_lora_config: datetime = None
    flags: int = None
    lora_enabled: bool = None  # Decoded from flags
    session_config_crc: int = None


@dataclass
class JumpTrackModemConfig:
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    time_of_config: datetime = None
    short_backoff_time_seconds: int = None
    normal_backoff_time_seconds: int = None
    long_backoff_time_minutes: int = None
    registration_timeout_period_minutes: int = None
    socket_connection_timeout_period_minutes: int = None
    connection_failure_threshold: int = None
    socket_timeout_period_seconds: int = None


@dataclass
class JumpTrackRebootMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    reboot_pattern: int = None
    reboot_flags: int = None
    reboot_9160: bool = None
    reboot_52840: bool = None
    preserve_device_state: bool = None
    do_hard_reset: bool = None
    cold_restart_gps: bool = None
    reserved: int = None


@dataclass
class JumpTrackServerConfig:
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    flags: int = None
    server_type: int = None  # Decoded from flags
    production_server: bool = None  # Decoded from flags
    write: bool = None  # Decoded from flags
    port: int = None
    url: str = None
    url_encoded: bytes = None  # Generated from url


@dataclass
class JumpTrackSimConfig:
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    time_of_config: datetime = None
    flags: int = None
    default_sim_select: bool = None
    prevent_sim_swapping: int = None


@dataclass
class JumpTrackBootMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    boot_reason: int = None
    number_of_exceptions: int = None
    time_of_boot: datetime = None
    flag_mcu_type: int = None  # Extracted from boot_reason
    flag_fw_triggered: int = None  # Extracted from boot_reason
    flag_boot_reason: int = None  # Extracted from boot_reason
    mcu_type: str = None  # Decoded from boot_reason
    fw_triggered: bool = None  # Decoded from boot_reason
    boot_reason_str: str = None  # Decoded from boot_reason


@dataclass
class JumpTrackPositionMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    flags: int = None
    flags_reserved_31_28: int = None  # Decoded from flags
    flags_aiding_data_used: bool = None  # Decoded from flags
    flags_on_charger: bool = None  # Decoded from flags
    flags_fix_type: int = None  # Decoded from flags
    flags_num_of_satellites: int = None  # Decoded from flags
    flags_confirmed_time_available: bool = None  # Decoded from flags
    flags_confirmed_time: bool = None  # Decoded from flags
    flags_confirmed_date: bool = None  # Decoded from flags
    flags_valid_time: bool = None  # Decoded from flags
    flags_valid_date: bool = None  # Decoded from flags
    flags_gnss_fix_ok: bool = None  # Decoded from flags
    flags_gnss_fix_valid: bool = None  # Decoded from flags
    flags_psm_state: int = None  # Decoded from flags
    flags_reserved_7_5: int = None  # Decoded from flags
    flags_update_reason: int = None  # Decoded from flags
    flags_in_motion: bool = None  # Decoded from flags
    is_valid_gps_fix: bool = None
    is_gps_indoors: bool = None
    is_in_motion: bool = None
    update_reason: int = None
    update_reason_str: str = None  # Decoded from update_reason
    latitude: float = None
    longitude: float = None
    ttf: int = None
    accuracy: int = None
    altitude_gps: int = None
    altitude_calculated: int = None
    ground_speed: int = None
    heading: int = None
    time_of_fix: datetime = None
    battery_voltage: int = None
    battery_percentage: int = None
    air_pressure_in_hg: float = None
    temperature: float = None
    average_force: float = None
    max_force: float = None
    account_id: int = None
    data_source: int = None
    crc: int = None
    nonce_received: int = None
    f_cnt_up: int = None
    f_cnt_dn: int = None
    gateway_lat: float = None
    gateway_lon: float = None
    gateway_id: str = None
    gateway_count: int = None
    gateway_rssi: float = None
    gateway_snr: float = None
    channel: str = None
    spreading_factor: int = None
    network_time_received: datetime = None
    fix_type: int = None
    fix_type_str: str = None  # Decoded from fix_type
    num_satellites: int = None
    psm_state: int = None
    psm_state_str: str = None  # Decoded from psm_state
    pdop: int = None
    bms_temp: int = None
    gps_vert_accuracy: int = None
    emergency_event_id: int = None


@dataclass
class JumpTrackFirmwareMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    bootloader_91_version: int = None
    application_91_version: int = None
    bootloader_52_version: int = None
    application_52_version: int = None

    # Decoded from application_91_version
    nrf91_fw_version: str = None
    nrf91_fw_type_id: int = None
    nrf91_fw_is_manufacturing: bool = None
    nrf91_fw_target_board: str = None
    nrf91_fw_target_board_version: str = None
    nrf91_fw_target_microcontroller: str = None
    nrf91_fw_product_variant: str = None

    # Decoded from application_52_version
    nrf52_fw_version: str = None
    nrf52_fw_type_id: int = None
    nrf52_fw_is_manufacturing: bool = None
    nrf52_fw_target_board: str = None
    nrf52_fw_target_board_version: str = None
    nrf52_fw_target_microcontroller: str = None
    nrf52_fw_product_variant: str = None


@dataclass
class JumpTrackHardwareFailureMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    failure_time: datetime = None

    acc_failures: int = None
    is_acc_com_failure: bool = None
    acc_failures_reserved: int = None

    alt_failures: int = None
    is_alt_com_failure: bool = None
    is_alt_int_failure: bool = None
    alt_failures_reserved: int = None

    gps_failures: int = None
    is_gps_com_failure: bool = None
    is_gps_crystal_failure: bool = None
    is_gps_pvt_failure: bool = None  # decoded from gps_failures
    is_gps_v_back_failure: bool = None  # decoded from gps_failures
    gps_failures_reserved: int = None  # decoded from gps_failures

    lora_failures: int = None
    is_lora_com_failure: bool = None
    is_lora_pll_failure: bool = None
    lora_failures_reserved: int = None  # decoded from lora_failures

    ipc_failures: int = None
    is_ipc_com_failure: bool = None
    ipc_failures_reserved: int = None  # decoded from ipc_failures

    bms_failures: int = None
    is_bms_com_failure: bool = None
    bms_failures_reserved: int = None  # decoded from bms_failures

    ext_flash_failure: int = None
    is_ext_flash_com_failure: bool = None
    ext_flash_failures_reserved: int = None  # decoded from ext_flash_failure

    sec_element_failure: int = None
    is_sec_element_com_failure: bool = None
    sec_element_failures_reserved: int = None  # decoded from sec_element_failure


@dataclass
class JumpTrackHipsSensorMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    time_of_measurement: datetime = None
    group_code: int = None
    source_user_id: int = None
    hsi_data_value: float = None
    hr_data_value: int = None
    estimated_core_temp: float = None
    skin_temp: float = None
    nii: int = None
    risk: int = None
    confidence: int = None
    hips_battery_life: int = None


@dataclass
class NetworkStatusMessage:
    checkin_id: int = None
    device_id: int = None
    time_received: datetime = None
    from_device: bool = None
    nonce_received: int = None
    flags: int = None
    lte_connected: bool = None
    socket_connected: bool = None
    send_success: bool = None
    wireless_technology: bool = None
    wireless_technology_str: str = None  # Decoded from wireless_technology
    active_sim_slot: bool = None
    early_socket_disconnect: bool = None
    dnssec_resolved: bool = None
    time_spent: int = None
    time_of_connection: datetime = None
    rsrq: float = None
    rsrp: float = None
    number_of_bytes_sent: int = None
    number_of_bytes_received: int = None
    band: int = None
    energy_estimate: int = None
    network_id: int = None
