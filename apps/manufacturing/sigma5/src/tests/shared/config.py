import json
from dataclasses import asdict, dataclass, field
from typing import Dict


@dataclass(frozen=True)
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
    electrical_step_1a_vin_threshold_v: float = 0.5
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
    electrical_step_4a_vin_threshold_v: float = 0.5
    electrical_step_5a_vin_threshold_v: float = 4.65
    electrical_step_5b_3v3_min: float = 3.25
    electrical_step_5b_3v3_max: float = 3.35
    electrical_step_5c_vbckp_min: float = 2.4
    electrical_step_5c_vbckp_max: float = 2.7

    # Firmware flash test
    fw_flash_test_nrf9160_modem_fw_name: str = "mfw_nrf9160_1.3.6.zip"
    fw_flash_test_nrf9160_app_fw_name: str = "sigma_comm_eng_7.hex"
    fw_flash_test_nrf52840_app_fw_name: str = "sigma_app_eng_7.hex"

    # Post test
    post_test_accelerometer_error_margin: float = 0.2  # G's
    post_test_altimeter_error_margin: float = 0.01  # inHg
    post_test_temperature_error_margin: float = 6.0  # °C
    post_test_voltage_error_margin: float = 0.1
    post_test_accel_chip_id = 0x33
    post_test_alt_chip_id = 0x60
    post_test_external_flash_chip_id = "efaa21"
    post_test_gps_ublox_sw_version = "ROM CORE 3.01 (107888)"
    post_test_gps_ublox_fw_version = "FWVER=SPG 3.01"
    post_test_gps_ublox_hw_version = "00080000"
    post_test_gps_ublox_proto_version = "PROTVER=18.00"
    post_test_gps_ublox_constellations = ["GPS", "GLO", "GAL", "BDS", "SBAS", "IMES", "QZSS"]
    post_test_voltages = [2.8, 3.0, 3.2, 3.4]
    post_test_expected_number_of_sims = 2

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
