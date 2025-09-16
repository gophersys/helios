# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_6_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Set HARD_RESET test point to digital low.
    result.error = mtib_servers.set_hard_reset(node, False)
    if result.error:
        return result

    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_6: TestStep = TestStep(
    info=StepInfo(
        name="Set HARD_RESET test point to digital low.",
        description=" Sets HARD_RESET test point to digital low.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=electrical_test_step_6_handler,
)
