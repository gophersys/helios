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
def fw_flash_test_step_2_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, FwFlashTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    # Flash nRF9151 comms firmware.
    # REV 1.2 (default): recover=True is safe — J-Link mux isolates each probe.
    # REV 1.1: recover must be False — no mux means recover erases ALL chips,
    # wiping the nRF52840 firmware just flashed in step 1.
    recover = config.fw_flash_step2_recover
    time_ms, err = mtib_servers.flash_fw_file(
        node,
        FwFileInfo(name=config.fw_flash_nrf9151_app_fw_name, target=HostType.HOST_TYPE_NRF9151),
        sector_erase=False,
        recover=recover,
    )

    if err:
        logging.warning(f"nRF9151 comms flash failed on first attempt: {err}, retrying...")
        time.sleep(2)

        time_ms, err = mtib_servers.flash_fw_file(
            node,
            FwFileInfo(name=config.fw_flash_nrf9151_app_fw_name, target=HostType.HOST_TYPE_NRF9151),
            sector_erase=False,
            recover=recover,
        )

        if err:
            result.error = f"nRF9151 comms flash failed after retry: {err}"
            return result

    logging.debug(f"nRF9151 comms firmware {config.fw_flash_nrf9151_app_fw_name} flashed in {time_ms}ms")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_2: TestStep = TestStep(
    info=StepInfo(
        name="Flash nRF9151 comms firmware",
        description="Flashes the nRF9151 comms processor with manufacturing firmware via V1 flash_fw_file.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,  # 2 minutes
    handler=fw_flash_test_step_2_handler,
)
