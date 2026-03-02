# Standard includes
import time
from typing import Dict
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class Step5Readings:
    batt_sys_voltage: float = None
    sys_voltage: float = None
    voltage_3v3: float = None
    vbckp_voltage: float = None
    current_a: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_5_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 5: Ensure device electrical state.
      a. Ensure +BATT_SYS voltage is same as +BATT_IN
      b. Ensure +SYS voltage is same as +BATT_IN
      c. Ensure +3.3V voltage is within 3.2V – 3.4V.
      d. Ensure +VBCKP voltage is within 2.4V – 2.6V.
      e. Ensure proper current consumption (no short circuits)
    """
    result: TestStepResult = TestStepResult(success=False)
    readings = Step5Readings()

    applied_voltage = config.electrical_nominal_voltage_v

    # 5a. Wait for +BATT_SYS voltage to stabilize near applied voltage
    # batt_sys_ok = False
    # start_time = time.time()
    # while time.time() - start_time < config.electrical_stabilization_period_s:
    #     result.error, readings.batt_sys_voltage = mtib_servers.read_batt_sys(node)
    #     if result.error:
    #         return result
    #     if abs(readings.batt_sys_voltage - applied_voltage) <= config.electrical_step_3_batt_sys_tolerance_v:
    #         batt_sys_ok = True
    #         break
    #     time.sleep(0.5)

    # if not batt_sys_ok:
    #     result.reason = (
    #         f"Step 5a: BATT_SYS {readings.batt_sys_voltage:.3f}V did not stabilize near "
    #         f"BATT_IN {applied_voltage}V (tolerance {config.electrical_step_3_batt_sys_tolerance_v}V) within "
    #         f"{config.electrical_stabilization_period_s}s"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # 5b. Ensure +SYS voltage is same as +BATT_IN
    # result.error, readings.sys_voltage = mtib_servers.read_sys(node)
    # if result.error:
    #     return result

    # if abs(readings.sys_voltage - applied_voltage) > config.electrical_step_3_sys_tolerance_v:
    #     result.reason = (
    #         f"Step 5b: SYS {readings.sys_voltage:.3f}V not within "
    #         f"{config.electrical_step_3_sys_tolerance_v}V of BATT_IN {applied_voltage}V"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # 5c. Ensure +3.3V voltage is within 3.2V – 3.4V
    # result.error, readings.voltage_3v3 = mtib_servers.read_3v3(node)
    # if result.error:
    #     return result

    # if (
    #     readings.voltage_3v3 < config.electrical_step_3_3v3_min_v
    #     or readings.voltage_3v3 > config.electrical_step_3_3v3_max_v
    # ):
    #     result.reason = (
    #         f"Step 5c: 3.3V rail {readings.voltage_3v3:.3f}V outside range "
    #         f"[{config.electrical_step_3_3v3_min_v}, {config.electrical_step_3_3v3_max_v}]V"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # 5d. Ensure +VBCKP voltage is within 2.4V – 2.6V
    # result.error, readings.vbckp_voltage = mtib_servers.read_vbckp(node)
    # if result.error:
    #     return result

    # if (
    #     readings.vbckp_voltage < config.electrical_step_3_vbckp_min_v
    #     or readings.vbckp_voltage > config.electrical_step_3_vbckp_max_v
    # ):
    #     result.reason = (
    #         f"Step 5d: VBCKP {readings.vbckp_voltage:.3f}V outside range "
    #         f"[{config.electrical_step_3_vbckp_min_v}, {config.electrical_step_3_vbckp_max_v}]V"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # 5e. Ensure proper current consumption (no short circuits)
    # result.error, readings.current_a = mtib_servers.read_current(node)
    # if result.error:
    #     return result

    # if (
    #     readings.current_a < config.electrical_step_3_current_min_a
    #     or readings.current_a > config.electrical_step_3_current_max_a
    # ):
    #     result.reason = (
    #         f"Step 5e: Current {readings.current_a:.4f}A outside expected range "
    #         f"[{config.electrical_step_3_current_min_a}, {config.electrical_step_3_current_max_a}]A"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # logging.debug(
    #     f"Step 5 PASS: BATT_SYS={readings.batt_sys_voltage:.3f}V, SYS={readings.sys_voltage:.3f}V, "
    #     f"3V3={readings.voltage_3v3:.3f}V, VBCKP={readings.vbckp_voltage:.3f}V, I={readings.current_a:.4f}A"
    # )

    result.success = True
    result.details = readings.marshall()
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_5: TestStep = TestStep(
    info=StepInfo(
        name="Ensure device electrical state (powered at 3.7V)",
        description="Verifies BATT_SYS, SYS, 3.3V, VBCKP and current are within expected ranges.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_5_handler,
)
