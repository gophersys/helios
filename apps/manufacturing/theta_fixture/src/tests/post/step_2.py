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
    Theta has accelerometer (LIS2DW12), no altimeter.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    accel_id, alt_id, error = client.cmd_theta_app_get_chip_ids()
    if error:
        result.error = f"Failed to get app chip IDs: {error}"
        return result

    if not accel_id:
        result.reason = "Accelerometer chip ID is missing"
        return result

    logging.debug(f"POST Step 2 PASS: Accel ID={accel_id}, Alt ID={alt_id}")

    result.success = True
    result.details = f"accel_id={accel_id}"
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
