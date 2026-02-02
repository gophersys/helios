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
def fw_flash_test_step_1_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, FwFlashTestSharedData]
) -> TestStepResult:
    """
    Flash all firmware serially:
    1. Flash nRF9151 modem firmware
    2. Flash nRF52840 app firmware
    """

    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    voltage_A0, error = client.AdcRead(0)
    if result.error:
        return result

    voltage_A1, error = client.AdcRead(1)
    if result.error:
        return result

    voltage_A2, error = client.AdcRead(2)
    if result.error:
        return result

    voltage_A3, error = client.AdcRead(3)
    if result.error:
        return result

    logging.debug(
        f"Node {node} 3.3V rail voltage before flashing: {voltage_A0}V {voltage_A1}V {voltage_A2}V {voltage_A3}V"
    )

    time.sleep(5)

    # Flash nRF52840 app firmware (retry once on failure)
    file_info = FwFileInfo(
        name=config.fw_flash_nrf52840_app_fw_name,
        target=HostType.HOST_TYPE_NRF52840,
    )
    time_ms, error = client.FlashFwFile(file_info, sector_erase=True, recover=True)
    if error:
        logging.warning(f"nRF52840 flash failed on first attempt: {error}, retrying...")
        time.sleep(2)
        time_ms, error = client.FlashFwFile(file_info, sector_erase=True, recover=True)
        if error:
            result.error = f"nRF52840 flash failed after retry: {error}"
            return result
    logging.debug(f"nRF52840 app firmware {config.fw_flash_nrf52840_app_fw_name} flashed in {time_ms}ms")

    # Flash modem firmware first
    file_info = FwFileInfo(
        name=config.fw_flash_nrf9151_modem_fw_name,
        target=HostType.HOST_TYPE_NRF9160_MODEM,
    )
    time_ms, error = client.FlashFwFile(file_info, sector_erase=True, recover=True)
    if error:
        result.error = f"Modem flash failed: {error}"
        return result
    logging.debug(f"Modem firmware {config.fw_flash_nrf9151_modem_fw_name} flashed in {time_ms}ms")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_1: TestStep = TestStep(
    info=StepInfo(
        name="Flash modem firmware and nRF52840 app",
        description="Flashes the nRF9151 modem firmware and nRF52840 app firmware serially.",
        noPassIsFatal=True,
    ),
    timeout_ms=300000,  # 5 minutes for both firmwares
    handler=fw_flash_test_step_1_handler,
)
