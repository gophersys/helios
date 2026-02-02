# Standard includes
import time
from typing import Dict

# Corekinect libraries
from corekinect.mtib_client.v1.client.types import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData

# Theta uses nRF9151 for comms processor
THETA_COMMS_TARGET = HostType.HOST_TYPE_NRF9151


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_0_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 0: Power cycle device and lock shells.
    Power off, wait, power on at 4.0V, wait for boot, lock comms + app shells.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Power cycle the device to get a clean boot with manufacturing firmware
    error = client.DutPowerDisable()
    if error:
        result.error = f"Could not disable device power: {error}"
        return result

    error = client.DutChargePowerDisable()
    if error:
        result.error = f"Could not disable charging power: {error}"
        return result

    time.sleep(2)

    # Turn on the device at 4.0V
    error = client.DutPowerEnable(4.0)
    if error:
        result.error = f"Could not enable power: {error}"
        return result

    # Wait for shell to be ready (must lock before debug messages flood after ~8s)
    time.sleep(5)

    # Lock shell and disable debug UART on comms processor (nRF9151)
    locked, error = client.cmd_comms_coproc_lock_shell(target=THETA_COMMS_TARGET)
    if error or not locked:
        result.error = f"Could not lock comms shell: {error}"
        return result

    disabled, error = client.cmd_comms_coproc_debug_uart_disable(target=THETA_COMMS_TARGET)
    if error or not disabled:
        result.error = f"Could not disable comms debug UART: {error}"
        return result

    # Lock shell and disable debug UART on app processor (nRF52840)
    locked, error = client.cmd_theta_app_lock_shell()
    if error or not locked:
        result.error = f"Could not lock app shell: {error}"
        return result

    disabled, error = client.cmd_theta_app_debug_uart_disable()
    if error or not disabled:
        result.error = f"Could not disable app debug UART: {error}"
        return result

    logging.debug(f"POST Step 0 PASS: Device booted and shells locked")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_0_boot_and_lock: TestStep = TestStep(
    info=StepInfo(
        name="Boot device and lock shells",
        description="Power cycles the device, waits for boot, and locks comms + app UART shells.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=post_step_0_handler,
)
