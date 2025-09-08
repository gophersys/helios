import logging
from time import sleep

from tests.lib import TestStepResult

from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import CMD_ACK_Response, mtib_servers


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def power_on_verify_comms(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    voltage = 3.2

    logging.info(f"snr for {node}: {config.snrs[node]}")

    # Power on DUT at battery
    if error := mtib_servers.set_vbat(node, voltage):
        return f"Could not set VBAT on host {node} to {voltage}V: {error}"

    if error := mtib_servers.enable_power(node):
        return f"Could not enable device power on host {node}: {error}"

    sleep(5)

    response: CMD_ACK_Response
    result.error, response = mtib_servers.dut_command_send_nop(node)

    if result.error:
        result.error = f"Could not send NOP to host {node}: {result.error}"
        return result

    result.success = True
    return result
