# Standard includes
import logging
from typing import Dict

# Corekinect libraries
from corekinect.mtib_client.v2.client.shell import boot_and_lock_shells
from corekinect.mtib_client.v2.client.cmd_comms import CommsShellCommands
from corekinect.mtib_client.v2.client.cmd_alpha_app import AlphaAppShellCommands
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_0_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 0: Power cycle device and lock shells using V2 boot_and_lock_shells().

    This replaces the V1 manual power-cycle + lock + debug_disable sequence.
    boot_and_lock_shells() handles:
    - Power cycling with UART-before-power-on race
    - Parallel lock_shell on both UARTs
    - J-Link debug reset on first attempt for clean boot
    - TX backlog drain
    - debug_enable 0 to silence noise
    - Retries on failure
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Configure GPIO for SWD level shifter (output, drive low)
    client.gpio_config(pin=0, direction=1)
    client.gpio_config(pin=1, direction=1)
    client.gpio_write(pin=0, value=False)
    client.gpio_write(pin=1, value=False)

    # Boot and lock both shells — handles power cycle, lock race, TX drain
    app_shell, comms_shell, err = boot_and_lock_shells(
        client, app_port="uart1", comms_port="uart0"
    )
    if err:
        result.error = f"Failed to boot and lock shells: {err}"
        return result

    # Store persistent shells and command wrappers in shared data
    usr_data[node].app_shell = app_shell
    usr_data[node].comms_shell = comms_shell
    usr_data[node].app_cmds = AlphaAppShellCommands(app_shell)
    usr_data[node].comms_cmds = CommsShellCommands(comms_shell)

    logging.debug("POST Step 0 PASS: Device booted and shells locked")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_0_boot_and_lock: TestStep = TestStep(
    info=StepInfo(
        name="Boot device and lock shells",
        description="Power cycles the device, waits for boot, and locks comms + app UART shells "
        "using V2 boot_and_lock_shells() with automatic retry and TX backlog drain.",
        noPassIsFatal=True,
    ),
    timeout_ms=600000,  # 10 minutes — includes TX backlog drain which can take 3-5 mins
    handler=post_step_0_handler,
)
