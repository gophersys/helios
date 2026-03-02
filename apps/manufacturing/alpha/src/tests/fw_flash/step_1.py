# Standard includes
import logging
import time
from typing import Dict

from protocols.mtib.mtib_pb2 import FwFileInfo, HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import FwFlashTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def fw_flash_test_step_1_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, FwFlashTestSharedData]
) -> TestStepResult:
    """
    Flash nRF52840 app firmware via V1 flash_fw_file (with retry on failure).
    """
    result: TestStepResult = TestStepResult(success=False)

    time.sleep(5)

    # Flash nRF52840 app firmware (with recover to clear APPROTECT)
    time_ms, err = mtib_servers.flash_fw_file(
        node,
        FwFileInfo(name=config.fw_flash_nrf52840_app_fw_name, target=HostType.HOST_TYPE_NRF52840),
        sector_erase=False,
        recover=True,
    )

    if err:
        logging.warning(f"nRF52840 flash failed on first attempt: {err}, retrying...")
        time.sleep(2)

        time_ms, err = mtib_servers.flash_fw_file(
            node,
            FwFileInfo(name=config.fw_flash_nrf52840_app_fw_name, target=HostType.HOST_TYPE_NRF52840),
            sector_erase=False,
            recover=True,
        )

        if err:
            result.error = f"nRF52840 flash failed after retry: {err}"
            return result

    logging.debug(
        f"nRF52840 app firmware {config.fw_flash_nrf52840_app_fw_name} flashed in {time_ms}ms"
    )

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_1: TestStep = TestStep(
    info=StepInfo(
        name="Flash nRF52840 app firmware",
        description="Flashes the nRF52840 app processor with manufacturing firmware via V1 flash_fw_file.",
        noPassIsFatal=True,
    ),
    timeout_ms=300000,  # 5 minutes
    handler=fw_flash_test_step_1_handler,
)
