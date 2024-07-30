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
def electrical_test_step_1_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Apply +2.5V to +BATT test point
    result.error = runnners_controller.set_vbat(node, 2.5)
    if result.error:
        return result

    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_1: TestStep = TestStep(
    info=StepInfo(
        sequence=1,
        name="Apply +2.5V to +BATT test point.",
        description="Apply +2.5V to +BATT test point using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=1000,
    handler=electrical_test_step_1_handler,
)
