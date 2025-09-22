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
def enable_app_protect(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)

    success, error = mtib_servers.enable_app_protect(node, HostType.HOST_TYPE_NRF52840)
    if error:
        result.error = error
        return result

    if not success:
        result.reason = "Failed to enable App Protect for app processor: " + error
        return result

    logging.debug(f"App Protect enabled for app processor on {node}")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_6_enable_app_protect: TestStep = TestStep(
    info=StepInfo(
        name="Enable App Protect",
        description="Enable App Protect for app processor.",
        noPassIsFatal=True,
    ),
    timeout_ms=20000,
    handler=enable_app_protect,
)
