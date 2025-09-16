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
def electrical_test_step_7_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Remove +5V
    result.error = mtib_servers.disable_charge_power(node)
    if result.error:
        return result

    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_7: TestStep = TestStep(
    info=StepInfo(
        name="Remove +5V",
        description="Removes +5V using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=electrical_test_step_7_handler,
)
