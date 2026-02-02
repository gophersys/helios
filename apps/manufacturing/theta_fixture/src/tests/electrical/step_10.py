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
def electrical_test_step_10_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 10: Remove power from +CHRG
    """
    result: TestStepResult = TestStepResult(success=False)

    result.error = mtib_servers.disable_charge_power(node)
    if result.error:
        return result

    logging.debug(f"Step 10: Removed power from +CHRG")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_10: TestStep = TestStep(
    info=StepInfo(
        name="Remove power from +CHRG",
        description="Disables charger power after load sharing test is complete.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_10_handler,
)
