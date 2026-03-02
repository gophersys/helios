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
def electrical_test_step_6_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 6: Apply +4.5V to +BATT_IN
    """
    result: TestStepResult = TestStepResult(success=False)

    result.error = mtib_servers.enable_power(node, config.electrical_high_voltage_v)
    if result.error:
        return result

    logging.debug(f"Step 6: Applied {config.electrical_high_voltage_v}V to +BATT_IN")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_6: TestStep = TestStep(
    info=StepInfo(
        name="Apply +4.5V to +BATT_IN",
        description="Applies 4.5V to the battery input to test higher voltage operation.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_6_handler,
)
