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
def post_step_1_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 1: Verify comms processor chip IDs.
    Check external flash chip ID (W25Q64 = 0xef 0x40 0x17).
    """
    result: TestStepResult = TestStepResult(success=False)

    lora_available, ext_flash_id, error = usr_data[node].comms_cmds.get_chip_ids()
    if error:
        result.error = f"Failed to get comms chip IDs: {error}"
        return result

    if not ext_flash_id:
        result.reason = "External flash chip ID is empty"
        return result

    # Validate external flash chip ID (W25Q64)
    if ext_flash_id != "0xef 0x40 0x17":
        result.reason = f"Unexpected flash chip ID: {ext_flash_id}, expected 0xef 0x40 0x17"
        return result

    logging.debug(f"POST Step 1 PASS: Ext flash ID={ext_flash_id}, LoRa={lora_available}")

    result.success = True
    result.details = f"ext_flash_id={ext_flash_id}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_1_comms_chip_ids: TestStep = TestStep(
    info=StepInfo(
        name="Verify comms processor chip IDs",
        description="Gets chip IDs from the comms processor (nRF9151) and verifies external flash chip ID.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_1_handler,
)
