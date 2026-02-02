# Standard includes
import logging
from typing import Dict

# Corekinect libraries
from corekinect.mtib_client.v1.client.types import HostType
from protocols.mtib.mtib_pb2 import FwFileInfo
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
    Step 3 from test plan:
    3. When modem firmware is complete, flash nRF9151 with manufacturing firmware.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Flash nRF9151 application firmware
    file_info = FwFileInfo(
        name=config.fw_flash_nrf9151_app_fw_name,
        target=HostType.HOST_TYPE_NRF9151,
    )

    time_ms, error = client.FlashFwFile(file_info, sector_erase=True, recover=True)
    if error:
        result.error = f"nRF9151 app flash failed: {error}"
        return result

    logging.debug(f"nRF9151 {config.fw_flash_nrf9151_app_fw_name} app firmware flashed in {time_ms}ms")

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
