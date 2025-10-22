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
def fw_flash_test_step_1_handler(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Build the file info
    file_info = FwFileInfo(
        name=config.fw_flash_test_nrf9160_modem_fw_name,
        target=HostType.HOST_TYPE_NRF9160_MODEM,
    )

    # We want to sector erase and recover the device, clean slate
    sector_erase = True
    recover = True

    time_ms, error = mtib_servers.flash_fw_file(node, file_info, sector_erase, recover)

    if error:
        result.error = error
        return result

    logging.debug(f"Time taken to flash {config.fw_flash_test_nrf9160_modem_fw_name}: {time_ms}ms")

    # Flash was succesful
    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_1: TestStep = TestStep(
    info=StepInfo(
        name="Flash nrf9160 modem firmware.",
        description="Flashes the nrf9160 modem firmware. using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,
    handler=fw_flash_test_step_1_handler,
)
