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
def electrical_test_step_11_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Set HARD_RESET test point to digital low.
    result.error = runnners_controller.set_hard_reset(node, False)
    if result.error:
        return result

    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_11: TestStep = TestStep(
    info=StepInfo(
        sequence=11,
        name="Set HARD_RESET test point to digital low.",
        description=" Sets HARD_RESET test point to digital low using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=1000,
    handler=electrical_test_step_11_handler,
)
