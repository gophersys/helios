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
class Step9Readings:
    sys_voltage: float = None
    voltage_3v3: float = None
    vbckp_voltage: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_9_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 9: Ensure device electrical state.
      a. Ensure +SYS voltage is 5V.
      b. Ensure +3.3V voltage is within 3.2V – 3.4V.
      c. Ensure +VBCKP voltage is within 2.4V – 2.6V.
    """
    result: TestStepResult = TestStepResult(success=False)
    readings = Step9Readings()

    # 9a. Wait for +SYS voltage to stabilize at 5V
    expected_sys = config.electrical_step_5_sys_expected_v
    sys_ok = False
    start_time = time.time()
    while time.time() - start_time < config.electrical_stabilization_period_s:
        result.error, readings.sys_voltage = mtib_servers.read_sys(node)
        if result.error:
            return result
        if abs(readings.sys_voltage - expected_sys) <= config.electrical_step_5_sys_tolerance_v:
            sys_ok = True
            break
        time.sleep(0.5)

    if not sys_ok:
        result.reason = (
            f"Step 9a: SYS {readings.sys_voltage:.3f}V did not stabilize within "
            f"{config.electrical_step_5_sys_tolerance_v}V of expected {expected_sys}V within "
            f"{config.electrical_stabilization_period_s}s"
        )
        result.details = readings.marshall()
        return result

    # 9b. Ensure +3.3V voltage is within 3.2V – 3.4V
    result.error, readings.voltage_3v3 = mtib_servers.read_3v3(node)
    if result.error:
        return result

    if (
        readings.voltage_3v3 < config.electrical_step_5_3v3_min_v
        or readings.voltage_3v3 > config.electrical_step_5_3v3_max_v
    ):
        result.reason = (
            f"Step 9b: 3.3V rail {readings.voltage_3v3:.3f}V outside range "
            f"[{config.electrical_step_5_3v3_min_v}, {config.electrical_step_5_3v3_max_v}]V"
        )
        result.details = readings.marshall()
        return result

    # 9c. Ensure +VBCKP voltage is within 2.4V – 2.6V
    result.error, readings.vbckp_voltage = mtib_servers.read_vbckp(node)
    if result.error:
        return result

    if (
        readings.vbckp_voltage < config.electrical_step_5_vbckp_min_v
        or readings.vbckp_voltage > config.electrical_step_5_vbckp_max_v
    ):
        result.reason = (
            f"Step 9c: VBCKP {readings.vbckp_voltage:.3f}V outside range "
            f"[{config.electrical_step_5_vbckp_min_v}, {config.electrical_step_5_vbckp_max_v}]V"
        )
        result.details = readings.marshall()
        return result

    logging.debug(
        f"Step 9 PASS: SYS={readings.sys_voltage:.3f}V, "
        f"3V3={readings.voltage_3v3:.3f}V, VBCKP={readings.vbckp_voltage:.3f}V"
    )

    result.success = True
    result.details = readings.marshall()
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_9: TestStep = TestStep(
    info=StepInfo(
        name="Ensure device electrical state (charger on)",
        description="Verifies SYS=5V, 3.3V within 3.2-3.4V, VBCKP within 2.4-2.6V with charger active.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_9_handler,
)
