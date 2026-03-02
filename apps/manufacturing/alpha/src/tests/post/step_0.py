# Standard includes
import logging
import time
from typing import Dict

from protocols.mtib.mtib_pb2 import GpioDirection, GpioResistorConfig
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_0_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 0: Power cycle device and lock shells via V1 MTIB server.

    Sequence:
    1. Configure GPIO 0+1 as output LOW (SWD level shifter enable)
    2. Power on DUT at 4.5V
    3. Wait for boot (~3s)
    4. Lock comms + app shells (with retry)
    5. Disable debug UART output on both processors
    """
    result: TestStepResult = TestStepResult(success=False)

    # Configure GPIO 0+1 as output LOW (required for DUT boot)
    for gpio in (0, 1):
        err = mtib_servers.gpio_config(
            node, gpio, GpioDirection.GPIO_DIRECTION_OUTPUT, GpioResistorConfig.GPIO_RESISTOR_NONE
        )
        if err:
            result.error = f"GPIO {gpio} config failed: {err}"
            return result
        err = mtib_servers.gpio_write(node, gpio, False)
        if err:
            result.error = f"GPIO {gpio} write failed: {err}"
            return result

    # Power on DUT at 4.5V
    err = mtib_servers.enable_power(node, 4.5)
    if err:
        result.error = f"Failed to enable DUT power: {err}"
        return result

    # Wait for boot
    time.sleep(3)

    # Lock comms shell (nRF9151) with retry
    comms_locked = False
    for attempt in range(3):
        success, err = mtib_servers.theta_cmd_lock_shell(node)
        if success:
            comms_locked = True
            break
        logging.warning(f"Comms lock_shell attempt {attempt + 1}/3 failed: {err}")
        time.sleep(2)

    if not comms_locked:
        result.error = "Failed to lock comms shell after 3 attempts"
        return result

    # Lock app shell (nRF52840) with retry
    app_locked = False
    for attempt in range(3):
        success, err = mtib_servers.theta_app_cmd_lock_shell(node)
        if success:
            app_locked = True
            break
        logging.warning(f"App lock_shell attempt {attempt + 1}/3 failed: {err}")
        time.sleep(2)

    if not app_locked:
        result.error = "Failed to lock app shell after 3 attempts"
        return result

    # Silence debug output on both processors
    mtib_servers.theta_cmd_debug_uart_disable(node)
    mtib_servers.theta_app_cmd_debug_uart_disable(node)

    logging.debug("POST Step 0 PASS: Device booted and shells locked via V1")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_0_boot_and_lock: TestStep = TestStep(
    info=StepInfo(
        name="Boot device and lock shells",
        description="Power cycles the device, waits for boot, and locks comms + app UART shells "
        "via V1 UART commands with retry logic.",
        noPassIsFatal=True,
    ),
    timeout_ms=600000,  # 10 minutes — includes TX backlog drain which can take 3-5 mins
    handler=post_step_0_handler,
)
