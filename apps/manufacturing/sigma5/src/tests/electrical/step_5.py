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
def electrical_test_step_5_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    # Apply +3.6V to +BATT test point
    result.error = mtib_servers.set_vbat(node, 3.6)
    if result.error:
        return result

    result.success = True

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_5: TestStep = TestStep(
    info=StepInfo(
        sequence=5,
        name="Apply +3.6V to +BATT test point.",
        description="Apply +3.6V to +BATT test point using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=1000,
    handler=electrical_test_step_5_handler,
)
