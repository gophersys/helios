# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_8_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 8: Apply 5.0V to +CHRG
    """
    result: TestStepResult = TestStepResult(success=False)

    result.error = mtib_servers.enable_charge_power(node)
    if result.error:
        return result

    logging.debug(f"Step 8: Applied 5.0V to +CHRG")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_8: TestStep = TestStep(
    info=StepInfo(
        name="Apply 5.0V to +CHRG",
        description="Applies 5.0V to the charger input to test load sharing.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_8_handler,
)
