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
def fw_flash_test_step_2_handler(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    # Flash 9160
    result.error = runnners_controller.flash_fw_file(
        node, "Sigma5_9160_Eng_SSv0p9_308_Mfg.hex", DeviceType.DEVICE_NRF9160, False
    )  # It is NOT modem firmware

    if result.error:
        return result

    # Flash 52840
    result.error = runnners_controller.flash_fw_file(
        node, "Sigma5_52840_Eng_308.hex", DeviceType.DEVICE_NRF82840, False
    )  # It is NOT modem firmware

    if result.error:
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
