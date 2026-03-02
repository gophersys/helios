# Standard includes
from typing import Dict

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_10_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 10: Rekey IPC.
    Replace hard coded keys with device-specific keys.
    """
    result: TestStepResult = TestStepResult(success=False)

    success, error = mtib_servers.theta_cmd_rekey_ipc(node)
    if error:
        result.error = f"IPC rekey failed: {error}"
        return result

    if not success:
        result.reason = "IPC rekey returned failure"
        return result

    logging.debug("POST Step 10 PASS: IPC rekey completed successfully")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_10_rekey_ipc: TestStep = TestStep(
    info=StepInfo(
        name="Rekey IPC",
        description="Rekeys IPC to replace hard coded keys with device-specific keys.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_10_handler,
)
