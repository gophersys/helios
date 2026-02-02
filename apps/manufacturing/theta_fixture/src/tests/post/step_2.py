# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_2_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 2: Verify app processor chip IDs.
    Supports both legacy Theta (accelerometer/altimeter) and Alpha (ext flash/BLE MAC) responses.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    id_1, id_2, error = client.cmd_theta_app_get_chip_ids()
    if error:
        result.error = f"Failed to get app chip IDs: {error}"
        return result

    if not id_1:
        result.reason = "Primary chip ID is missing"
        return result

    logging.debug(f"POST Step 2 PASS: ID1={id_1}, ID2={id_2}")

    result.success = True
    result.details = f"id_1={id_1}, id_2={id_2}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_2_app_chip_ids: TestStep = TestStep(
    info=StepInfo(
        name="Verify app processor chip IDs",
        description="Gets chip IDs from the app processor (nRF52840) and verifies accelerometer is present.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_2_handler,
)
