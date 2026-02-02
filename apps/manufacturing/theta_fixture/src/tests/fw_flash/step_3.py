# Standard includes
import logging
from typing import Dict

# Corekinect libraries
from corekinect.mtib_client.v1.client.types import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import FwFlashTestSharedData

# Theta uses nRF9151 for comms processor
THETA_COMMS_TARGET = HostType.HOST_TYPE_NRF9151


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def fw_flash_test_step_3_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, FwFlashTestSharedData]
) -> TestStepResult:
    """
    Set AP protect on both processors (nRF52840 and nRF9151).
    This prevents debug access to the device after manufacturing.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Set AP protect on app processor (nRF52840)
    success, error = client.EnableAppProtect(HostType.HOST_TYPE_NRF52840)
    if error:
        result.error = f"Error setting AP protect on app processor: {error}"
        return result
    if not success:
        result.error = "Failed to set AP protect on app processor"
        return result

    # Set AP protect on comms processor (nRF9151)
    success, error = client.EnableAppProtect(THETA_COMMS_TARGET)
    if error:
        result.error = f"Error setting AP protect on comms processor: {error}"
        return result
    if not success:
        result.error = "Failed to set AP protect on comms processor"
        return result

    logging.debug("AP protect set successfully on both processors")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_3: TestStep = TestStep(
    info=StepInfo(
        name="Set AP protect",
        description="Enables AP protect on both nRF52840 and nRF9151 processors to prevent debug access.",
        noPassIsFatal=True,
    ),
    timeout_ms=30000,  # 30 seconds
    handler=fw_flash_test_step_3_handler,
)
