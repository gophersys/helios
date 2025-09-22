import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class Sigma5ManufacturingConfig:
    # snrs: Dict[str, str] = field(default_factory=dict)
    snrs: Dict[str, str] = field(
        default_factory=lambda: {
            "slot-1": "000B",
            "slot-2": "000C",
            "slot-3": "000D",
            "slot-4": "000E",
            "slot-5": "000F",
            "verdin-imx8mm-15005679": "05JI",
        }
    )

    # Electrical test
    vin_rail_stabilization_period_s: int = 30
    uvp_n_stabilization_period_s: int = 10
    electrical_step_1a_vin_threshold_v: float = 0.55
    electrical_step_1b_vbckp_threshold_v: float = 0.3
    electrical_step_1d_near_zero_current_a: float = 0.01
    electrical_step_2a_vin_vbat_tolerance: float = 0.1
    electrical_step_2b_3v3_min: float = 3.2
    electrical_step_2b_3v3_max: float = 3.4
    electrical_step_2c_vbckp_min: float = 2.4
    electrical_step_2c_vbckp_max: float = 2.7
    electrical_step_2e_current_min: float = 0.01
    electrical_step_2e_current_max: float = 0.1
    electrical_step_3a_vin_vbat_tolerance: float = 0.1
    electrical_step_3b_current_min: float = 0.01
    electrical_step_3b_current_max: float = 0.1
    electrical_step_4a_vin_threshold_v: float = 0.6
    electrical_step_5a_vin_threshold_v: float = 4.55
    electrical_step_5b_3v3_min: float = 3.25
    electrical_step_5b_3v3_max: float = 3.35
    electrical_step_5c_vbckp_min: float = 2.385
    electrical_step_5c_vbckp_max: float = 2.715

    # Firmware flash test
    fw_flash_test_nrf9160_modem_fw_name: str = "mfw_nrf9160_1.3.6.zip"
    fw_flash_test_nrf9160_app_fw_name: str = "sigma_comm_eng_28.hex"
    fw_flash_test_nrf52840_app_fw_name: str = "sigma_app_eng_28.hex"

    # Post test
    post_test_app_accel_chip_id: str = "0x33"
    post_test_app_altimeter_chip_id: str = "0x60"
    post_test_app_external_flash_chip_id: str = "0xef 0x40 0x17"
    post_test_app_gps_ublox_sw_version: str = "ROM CORE 3.01 (107888)"
    post_test_app_gps_ublox_fw_version: str = "FWVER=SPG 3.01"
    post_test_app_gps_ublox_hw_version: str = "00080000"
    post_test_app_gps_ublox_proto_version: str = "PROTVER=18.00"
    post_test_app_gps_ublox_constellations: str = "GPS;GLO;GAL;BDS;SBAS;IMES;QZSS"
    post_test_app_accelerometer_error_margin: float = 0.99
    post_test_app_altimeter_pressure_error_margin: float = 0.040
    post_test_app_altimeter_temperature_error_margin: float = 20.0 # Its hot inside the fixture
    post_test_app_external_flash_test_string: str = "Hello, world!0xA54A"
    post_test_app_external_flash_size: int = 8388608
    post_test_app_external_flash_start: str = "0x0000"
    post_test_app_external_flash_end: str = "0x7F0000"
    post_test_app_external_flash_middle_start: str = "0x2AAAAA"
    post_test_app_external_flash_middle_end: str = "0x555555"
    post_test_comms_lora_available: str = "yes"
    post_test_comms_ext_flash_id: str = "0xef 0x40 0x17"
    post_test_comms_external_flash_test_string: str = "Hello, world!0xA54A"
    post_test_comms_external_flash_size: int = 8388608
    post_test_comms_external_flash_start: str = "0x0000"
    post_test_comms_external_flash_end: str = "0x7F0000"
    post_test_comms_external_flash_middle_start: str = "0x2AAAAA"
    post_test_comms_external_flash_middle_end: str = "0x555555"
    post_test_comms_expected_number_of_sims: int = 2

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @classmethod
    def unmarshall(cls, json_str: str):
        try:
            data = json.loads(json_str)
            return Sigma5ManufacturingConfig(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")
