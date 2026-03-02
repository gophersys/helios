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
def electrical_test_step_1_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 1: Apply +3.4V to +BATT_IN
    """
    result: TestStepResult = TestStepResult(success=False)

    result.error = mtib_servers.enable_power(node, config.electrical_uvlo_voltage_v)
    if result.error:
        return result

    logging.debug(f"Step 1: Applied {config.electrical_uvlo_voltage_v}V to +BATT_IN")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_1: TestStep = TestStep(
    info=StepInfo(
        name="Apply +3.4V to +BATT_IN",
        description="Applies 3.4V (below UVLO threshold) to the battery input.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_1_handler,
)
