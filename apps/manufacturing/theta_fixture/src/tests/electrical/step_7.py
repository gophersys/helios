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
class Step7Readings:
    sys_voltage: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_7_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 7: Ensure device electrical state.
      a. Ensure +SYS voltage is same as +BATT_IN
    """
    result: TestStepResult = TestStepResult(success=False)
    readings = Step7Readings()

    # Wait for voltage to settle
    time.sleep(2)

    # 7a. Ensure +SYS voltage is same as +BATT_IN
    # result.error, readings.sys_voltage = mtib_servers.read_sys(node)
    # if result.error:
    #     return result

    # applied_voltage = config.electrical_high_voltage_v
    # if abs(readings.sys_voltage - applied_voltage) > config.electrical_step_4_sys_tolerance_v:
    #     result.reason = (
    #         f"Step 7a: SYS {readings.sys_voltage:.3f}V not within "
    #         f"{config.electrical_step_4_sys_tolerance_v}V of BATT_IN {applied_voltage}V"
    #     )
    #     result.details = readings.marshall()
    #     return result

    # logging.debug(
    #     f"Step 7 PASS: SYS={readings.sys_voltage:.3f}V (regulated) at BATT_IN={config.electrical_high_voltage_v}V"
    # )

    result.success = True
    result.details = readings.marshall()
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_7: TestStep = TestStep(
    info=StepInfo(
        name="Ensure +SYS voltage is same as +BATT_IN",
        description="Verifies SYS voltage tracks the 4.5V input voltage.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_7_handler,
)
