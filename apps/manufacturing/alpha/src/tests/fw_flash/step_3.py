# Standard includes
import logging
from typing import Dict

from protocols.mtib.mtib_pb2 import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import FwFlashTestSharedData


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

    # Enable AP protect on nRF52840
    success, err = mtib_servers.enable_app_protect(node, HostType.HOST_TYPE_NRF52840)
    if err:
        result.error = f"nRF52840 AP protect failed: {err}"
        return result

    logging.debug(f"nRF52840 AP protect enabled on {node}")

    # Enable AP protect on nRF9151
    success, err = mtib_servers.enable_app_protect(node, HostType.HOST_TYPE_NRF9151)
    if err:
        result.error = f"nRF9151 AP protect failed: {err}"
        return result

    logging.debug(f"nRF9151 AP protect enabled on {node}")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_3: TestStep = TestStep(
    info=StepInfo(
        name="Set AP protect",
        description="Enables AP protect on both nRF52840 and nRF9151 processors via V1 EnableAppProtect RPC.",
        noPassIsFatal=True,
    ),
    timeout_ms=30000,  # 30 seconds
    handler=fw_flash_test_step_3_handler,
)
