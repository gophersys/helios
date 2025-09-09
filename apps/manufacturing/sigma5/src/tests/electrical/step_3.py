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
def electrical_test_step_3_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    # Apply +3.2V to +BATT test point
    result.error = mtib_servers.enable_power(node, 3.2)
    if result.error:
        return result

    result.success = True

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_3: TestStep = TestStep(
    info=StepInfo(
        sequence=3,
        name="Apply +3.2V to +BATT test point.",
        description="Apply +3.2V to +BATT test point using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=3000,
    handler=electrical_test_step_3_handler,
)
