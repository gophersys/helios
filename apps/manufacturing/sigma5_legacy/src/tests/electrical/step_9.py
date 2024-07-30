# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import runnners_controller
# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_9_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Apply +5V to +5V_IN test point
    result.error = runnners_controller.set_5vin(node, True)
    if result.error:
        return result

    result.success = True

    # Allow some time for the voltage to be applied
    time.sleep(config.electrical_step_9_settle_time_s)

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_9: TestStep = TestStep(
    info=StepInfo(
        sequence=9,
        name="Apply +5V to +5V_IN test point.",
        description="Apply +5V to +5V_IN test point using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=electrical_test_step_9_handler,
)
