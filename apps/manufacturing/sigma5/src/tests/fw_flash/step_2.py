# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import *

# Test includes


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def fw_flash_test_step_2_handler(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Flash 9160
    file_info = FwFileInfo(
        name=config.fw_flash_test_nrf9160_app_fw_name,
        target=HostType.HOST_TYPE_NRF9160,
    )
    sector_erase = True
    recover = True
    time_taken, error = mtib_servers.flash_fw_file(node, file_info, sector_erase, recover)

    if error:
        result.error = error
        return result

    # Flash 52840
    file_info = FwFileInfo(
        name=config.fw_flash_test_nrf52840_app_fw_name,
        target=HostType.HOST_TYPE_NRF52840,
    )
    sector_erase = True
    recover = True
    time_taken, error = mtib_servers.flash_fw_file(node, file_info, sector_erase, recover)

    if error:
        result.error = error
        return result

    # Flash was succesful
    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_2: TestStep = TestStep(
    info=StepInfo(
        sequence=2,
        name="Flash Corekinect apps.",
        description="Flashes the Corekinect firmware on both MCUs. using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=30000,
    handler=fw_flash_test_step_2_handler,
)
