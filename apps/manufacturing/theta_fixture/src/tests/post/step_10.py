# Standard includes
from typing import Dict

# Corekinect libraries
from corekinect.mtib_client.v1.client.types import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData

# Theta uses nRF9151 for comms processor
THETA_COMMS_TARGET = HostType.HOST_TYPE_NRF9151


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
    client = usr_data[node].client

    success, error = client.cmd_comms_coproc_rekey_ipc(target=THETA_COMMS_TARGET)
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
