# Standard includes
from typing import Dict

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_6_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 6: Verify modem firmware version.
    """
    result: TestStepResult = TestStepResult(success=False)

    fw_version, error = usr_data[node].comms_cmds.get_modem_fw_version()
    if error:
        result.error = f"Failed to get modem FW version: {error}"
        return result

    if not fw_version:
        result.reason = "Modem firmware version is empty"
        return result

    logging.debug(f"POST Step 6 PASS: Modem FW version={fw_version}")

    result.success = True
    result.details = f"modem_fw={fw_version}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_6_modem_fw: TestStep = TestStep(
    info=StepInfo(
        name="Verify modem firmware version",
        description="Gets and verifies the modem firmware version from the comms processor.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_6_handler,
)
