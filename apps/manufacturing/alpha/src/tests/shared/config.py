import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class ThetaFixtureConfig:
    # Serial numbers for each slot (4-panel fixture)
    snrs: Dict[str, str] = field(
        default_factory=lambda: {
            "slot-1": "000A",
            "slot-2": "000B",
            "slot-3": "000C",
            "slot-4": "000D",
        }
    )

    # Electrical test - Step 1: Apply +3.4V, verify device is off (UVLO)
    electrical_uvlo_voltage_v: float = 3.4
    electrical_step_1_batt_sys_threshold_v: float = 0.3
    electrical_step_1_3v3_threshold_v: float = 0.55  # Used to be 0.3
    electrical_step_1_vbckp_threshold_v: float = 0.55  # Used to be 0.3
    electrical_step_1_current_threshold_a: float = 0.001

    # Electrical test - Step 2: Apply +3.7V, verify startup delay
    electrical_nominal_voltage_v: float = 3.7
    electrical_step_2_3v3_threshold_v: float = 3.65
    electrical_step_4_stabilization_period_s: float = 1.7

    # Electrical test - Step 3: Verify device powered up
    electrical_step_3_batt_sys_tolerance_v: float = 0.15
    electrical_step_3_sys_tolerance_v: float = 0.15
    electrical_step_3_3v3_min_v: float = 3.2
    electrical_step_3_3v3_max_v: float = 3.4
    electrical_step_3_vbckp_min_v: float = 2.4
    electrical_step_3_vbckp_max_v: float = 2.6
    electrical_step_3_current_min_a: float = 0.005
    electrical_step_3_current_max_a: float = 0.150

    # Electrical test - Step 4: Apply +4.5V, verify SYS follows BATT_IN
    electrical_high_voltage_v: float = 4.5
    electrical_step_4_sys_tolerance_v: float = 0.15

    # Electrical test - Step 5: Apply 5.0V to +CHRG, verify load sharing
    electrical_chrg_voltage_v: float = 5.0
    electrical_step_5_sys_expected_v: float = 5.0
    electrical_step_5_sys_tolerance_v: float = 0.3
    electrical_step_5_3v3_min_v: float = 3.2
    electrical_step_5_3v3_max_v: float = 3.4
    electrical_step_5_vbckp_min_v: float = 2.4
    electrical_step_5_vbckp_max_v: float = 2.6

    # Electrical test - General
    electrical_stabilization_period_s: int = 30

    # Firmware flash — manufacturing firmware (flashed via V1 MTIB server)
    fw_flash_nrf9151_app_fw_name: str = "alpha_comm_mfg_1.hex"
    fw_flash_nrf52840_app_fw_name: str = "alpha_app_mfg_1.hex"

    # Firmware flash — J-Link recover behavior
    # True (default, REV 1.2): safe because J-Link mux isolates each probe
    # False (REV 1.1): no mux, recover erases ALL chips — step 1 recovery covers both
    fw_flash_step2_recover: bool = True

    # POST test - External flash
    post_ext_flash_test_pattern: str = "ALPHA_POST_TEST_PATTERN_2024"
    post_ext_flash_start_addr: str = "0x000000"
    post_ext_flash_end_addr: str = "0x100000"
    post_ext_flash_middle_start: str = "0x040000"
    post_ext_flash_middle_end: str = "0x080000"

    # POST test - IMEI/ICCID
    post_expected_num_sims: int = 2

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @classmethod
    def unmarshall(cls, json_str: str):
        try:
            data = json.loads(json_str)
            return ThetaFixtureConfig(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")
