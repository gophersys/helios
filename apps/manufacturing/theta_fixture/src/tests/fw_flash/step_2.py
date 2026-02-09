# Standard includes
import logging
from typing import Dict

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import FwFlashTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def fw_flash_test_step_2_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, FwFlashTestSharedData]
) -> TestStepResult:
    """
    Flash nRF9151 with manufacturing application firmware via debug session.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Flash nRF9151 application firmware
    err, session = client.debug_connect(target_id="nrf9151", probe_id="")
    if err:
        result.error = f"nRF9151 debug connect failed: {err}"
        return result

    err, flash_result = client.flash_program(
        session_id=session.session_id,
        filename=config.fw_flash_nrf9151_app_fw_name,
        erase_before=True,
        verify_after=True,
        reset_after=True,
    )
    client.debug_disconnect(session.session_id)

    if err:
        result.error = f"nRF9151 app flash failed: {err}"
        return result

    logging.debug(
        f"nRF9151 {config.fw_flash_nrf9151_app_fw_name} app firmware flashed in {flash_result.time_ms}ms"
    )

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_2: TestStep = TestStep(
    info=StepInfo(
        name="Flash nRF9151 manufacturing firmware",
        description="Flashes the nRF9151 comms processor with the manufacturing test firmware.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,  # 2 minutes
    handler=fw_flash_test_step_2_handler,
)
