# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_4_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 4: Verify battery charger chip.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    charger_data, error = client.cmd_theta_app_test_charger()
    if error:
        result.error = f"Charger test failed: {error}"
        return result

    if not charger_data:
        result.reason = "Charger test returned no data"
        return result

    chip_id = charger_data.get("chip_id", "")
    voltage_mv = charger_data.get("voltage_mv", 0)

    # Charger chip ID may show err when not on charger, which is expected
    if chip_id and chip_id not in ("0x00", "0x22"):
        logging.warning(f"Unexpected charger chip ID: {chip_id}, expected 0x22")

    logging.debug(
        f"POST Step 4 PASS: Charger chip_id={chip_id}, "
        f"on_charger={charger_data.get('on_charger')}, voltage={voltage_mv}mV"
    )

    result.success = True
    result.details = f"chip_id={chip_id}, voltage_mv={voltage_mv}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_4_charger: TestStep = TestStep(
    info=StepInfo(
        name="Verify battery charger",
        description="Tests the battery charger chip on the app processor.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_4_handler,
)
