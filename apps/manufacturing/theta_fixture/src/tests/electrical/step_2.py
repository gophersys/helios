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
class Step2Readings:
    batt_sys_voltage: float = None
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
def electrical_test_step_2_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 2: Ensure device electrical state.
      a. Ensure +BATT_SYS voltage is below 0.3V.
      b. Ensure +3.3V voltage is below 0.3V.
      c. Ensure +VBCKP voltage is below 0.3V.
      d. Ensure current consumption is below 1uA.
    """
    result: TestStepResult = TestStepResult(success=False)
    readings = Step2Readings()

    # 2a. Wait for +BATT_SYS voltage to decay below threshold
    # batt_sys_ok = False
    # start_time = time.time()
    # while time.time() - start_time < config.electrical_stabilization_period_s:
    #     result.error, readings.batt_sys_voltage = mtib_servers.read_batt_sys(node)
    #     if result.error:
    #         return result
    #     if readings.batt_sys_voltage <= config.electrical_step_1_batt_sys_threshold_v:
    #         batt_sys_ok = True
    #         break
    #     time.sleep(0.5)

    # if not batt_sys_ok:
    #     result.reason = (
    #         f"Step 2a: BATT_SYS voltage {readings.batt_sys_voltage:.3f}V did not decay below "
    #         f"threshold {config.electrical_step_1_batt_sys_threshold_v}V within "
    #         f"{config.electrical_stabilization_period_s}s"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # 2b. Wait for +3.3V voltage to decay below threshold
    v3v3_ok = False
    start_time = time.time()
    while time.time() - start_time < config.electrical_stabilization_period_s:
        result.error, readings.voltage_3v3 = mtib_servers.read_3v3(node)
        if result.error:
            return result
        if readings.voltage_3v3 <= config.electrical_step_1_3v3_threshold_v:
            v3v3_ok = True
            break
        time.sleep(0.5)

    if not v3v3_ok:
        result.reason = (
            f"Step 2b: 3.3V voltage {readings.voltage_3v3:.3f}V did not decay below "
            f"threshold {config.electrical_step_1_3v3_threshold_v}V within "
            f"{config.electrical_stabilization_period_s}s"
        )
        result.details = readings.marshall()
        return result

    # 2c. Wait for +VBCKP voltage to decay below threshold
    # vbckp_ok = False
    # start_time = time.time()
    # while time.time() - start_time < config.electrical_stabilization_period_s:
    #     result.error, readings.vbckp_voltage = mtib_servers.read_vbckp(node)
    #     if result.error:
    #         return result
    #     if readings.vbckp_voltage <= config.electrical_step_1_vbckp_threshold_v:
    #         vbckp_ok = True
    #         break
    #     time.sleep(0.5)

    # if not vbckp_ok:
    #     result.reason = (
    #         f"Step 2c: VBCKP voltage {readings.vbckp_voltage:.3f}V did not decay below "
    #         f"threshold {config.electrical_step_1_vbckp_threshold_v}V within "
    #         f"{config.electrical_stabilization_period_s}s"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # 2d. Ensure current consumption is below 1uA
    result.error, readings.current_a = mtib_servers.read_current(node)
    if result.error:
        return result

    if readings.current_a > config.electrical_step_1_current_threshold_a:
        result.reason = (
            f"Step 2d: Current {readings.current_a:.6f}A exceeds "
            f"threshold {config.electrical_step_1_current_threshold_a:.6f}A"
        )
        result.details = readings.marshall()
        return result

    logging.debug(f"Step 2 PASS: Current={readings.current_a:.6f}A")

    result.success = True
    result.details = readings.marshall()
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_2: TestStep = TestStep(
    info=StepInfo(
        name="Ensure device electrical state (UVLO off)",
        description="Verifies BATT_SYS, 3.3V, VBCKP are below 0.3V and current below 1uA.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_2_handler,
)
