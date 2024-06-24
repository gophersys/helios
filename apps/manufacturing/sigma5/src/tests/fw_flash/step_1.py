# Standard includes
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import DeviceType, runnners_controller

# Test includes


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def fw_flash_test_step_1_handler(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Flash the modem firmware first
    result.error = runnners_controller.flash_fw_file(
        node, config.fw_flash_test_nrf9160_modem_fw_name, DeviceType.DEVICE_NRF9160, True
    )  # It is indeed modem firmware

    if result.error:
        return result

    # Flash was succesful
    result.success = True

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_1: TestStep = TestStep(
    info=StepInfo(
        sequence=1,
        name="Flash nrf9160 modem firmware.",
        description="Flashes the nrf9160 modem firmware. using the runner API.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=fw_flash_test_step_1_handler,
)
