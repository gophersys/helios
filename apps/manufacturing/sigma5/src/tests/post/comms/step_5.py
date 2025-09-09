# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Post test includes
from src.tests.post.data import PostTestSharedData

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def personalize(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)

    # TODO: Personalize DUT with device ID from CoreOps.
    logging.debug(f"Personalizing DUT with user data: {usr_data[node]}")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_5_personalize: TestStep = TestStep(
    info=StepInfo(
        name="Personalize",
        description="Personalize DUT with device ID from CoreOps.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=personalize,
)
