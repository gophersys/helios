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
def post_step_6_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 6: Verify modem firmware version.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    fw_version, error = client.cmd_comms_coproc_get_modem_fw_version(target=THETA_COMMS_TARGET)
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
