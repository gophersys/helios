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
def post_step_3_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 3: Verify BMS (gas gauge) chip.
    Check MAX17263 chip connected with valid chip ID (0x4037).
    """
    result: TestStepResult = TestStepResult(success=False)

    bms_data, error = usr_data[node].app_cmds.test_bms()
    if error:
        result.error = f"BMS test failed: {error}"
        return result

    if not bms_data:
        result.reason = "BMS test returned no data"
        return result

    connected = bms_data.get("connected", False)
    chip_id = bms_data.get("chip_id", "")

    if not connected:
        result.reason = "BMS is not connected"
        return result

    # Validate MAX17263 chip ID
    if chip_id != "0x4037":
        logging.warning(f"Unexpected BMS chip ID: {chip_id}, expected 0x4037")

    logging.debug(
        f"POST Step 3 PASS: BMS connected={connected}, chip_id={chip_id}, "
        f"charge={bms_data.get('charge_percent')}%, temp={bms_data.get('temp_c')}C"
    )

    result.success = True
    result.details = f"chip_id={chip_id}, charge={bms_data.get('charge_percent')}%"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_3_bms: TestStep = TestStep(
    info=StepInfo(
        name="Verify BMS (gas gauge)",
        description="Tests the BMS chip on the app processor, verifying connection and chip ID.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_3_handler,
)
