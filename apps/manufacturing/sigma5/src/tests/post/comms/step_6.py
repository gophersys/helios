# Standard includes
from typing import Dict

# Corekinect libraries
from src.tests.lib import *

# Post test includes
from src.tests.post.data import PostTestSharedData

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import *


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def enable_comms_app_protect(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)

    success, error = mtib_servers.sigma5_cmd_comms_rekey_ipc(node)
    if error:
        result.error = error

    if not success:
        result.reason = "Failed to rekey IPC: " + error
        return result

    logging.debug(f"IPC rekeyed for {node}")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_6_rekey_ipc: TestStep = TestStep(
    info=StepInfo(
        name="Rekey IPC",
        description="Replace hard coded IPC keys.",
        noPassIsFatal=True,
    ),
    timeout_ms=20000,
    handler=enable_comms_app_protect,
)
