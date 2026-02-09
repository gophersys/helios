# Standard includes
import logging
from typing import Dict

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

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

    TODO: V2 server does not yet have an EnableAppProtect RPC.
    This step is skipped for now and will be implemented when the
    V2 server handler is added. AP protect is the final step and
    not critical for initial V2 validation.
    """
    result: TestStepResult = TestStepResult(success=False)

    logging.warning(
        "AP protect step skipped — V2 server does not yet have EnableAppProtect RPC. "
        "This must be implemented before production use."
    )

    # TODO: Implement AP protect when V2 server supports it.
    # Expected V2 API (when available):
    #   err, session = client.debug_connect(target_id="nrf52840", probe_id="")
    #   err = client.enable_app_protect(session.session_id)
    #   client.debug_disconnect(session.session_id)
    #   ... same for nrf9151 ...

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_3: TestStep = TestStep(
    info=StepInfo(
        name="Set AP protect",
        description="Enables AP protect on both nRF52840 and nRF9151 processors to prevent debug access. "
        "(Currently skipped — V2 server handler not yet implemented.)",
        noPassIsFatal=True,
    ),
    timeout_ms=30000,  # 30 seconds
    handler=fw_flash_test_step_3_handler,
)
