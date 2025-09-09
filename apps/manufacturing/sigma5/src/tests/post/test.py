# Standard includes
import concurrent.futures
import time
from typing import List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import StepInfo, TestInfo

# Corekinect Libraries
from src.tests.lib import Test, TestStep

# Test includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers
from .app.step_1 import app_post_step_1_verify_chip_ids
from .app.step_2 import app_post_step_2_verify_ublox
from .app.step_3 import app_post_step_3_verify_accelerometer
from .app.step_4 import app_post_step_4_verify_altimeter
from .comms.step_1 import comms_post_step_1_verify_chip_ids
from .comms.step_2 import comms_post_step_2_verify_modem_fw


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def post_test_init(config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: None) -> str:
    # Initialize the runners required to run this test
    error = mtib_servers.init(nodes)
    if error:
        return f"Could not initialize runners for test: {error}"

    def init_node(node: str) -> str:
        # Turn off power
        error = mtib_servers.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Turn off charging power
        error = mtib_servers.set_5vin(node, False)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Turn on the device
        error = mtib_servers.set_vbat(node, 4.0)
        if error:
            return f"Could not set VBAT on host {node} to 3.8V: {error}"

        time.sleep(2)

        # Setup the shell for the app processor
        locked, error = mtib_servers.sigma5_cmd_app_lock_shell(node)
        if error or not locked:
            return f"Could not lock shell on host {node}: {error}"
        disabled, error = mtib_servers.sigma5_cmd_app_debug_uart_disable(node)
        if error or not disabled:
            return f"Could not disable debug UART on host {node}: {error}"

        # Setup the shell for the comms processor
        locked, error = mtib_servers.sigma5_cmd_comms_lock_shell(node)
        if error or not locked:
            return f"Could not lock shell on host {node}: {error}"
        disabled, error = mtib_servers.sigma5_cmd_comms_debug_uart_disable(node)
        if error or not disabled:
            return f"Could not disable debug UART on host {node}: {error}"

        return None

    # Run all hosts init in parallel to speed things up
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(init_node, node): node for node in nodes}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                return error

    # Await some time for the power to be off
    time.sleep(1)

    return ""


# ---------------------------------------------------------------------------------
#                                                                            Deinit
# -------------------------------------------------------------------------------*/
def post_test_deinit(config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: None) -> str:
    def deinit_node(node: str) -> str:
        # Turn off charging power
        error = mtib_servers.set_5vin(node, False)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Turn off power
        error = mtib_servers.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        return None

    # Run all hosts deinit in parallel to speed things up
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(deinit_node, node): node for node in nodes}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                return error

    # Await some time for the power to be off
    time.sleep(1)

    # Deinitialize the runners used to run this test
    error = mtib_servers.deinit()
    if error:
        return f"Could not deinitialize runners for test: {error}"

    return ""


# ---------------------------------------------------------------------------------
#                                                                              Test
# -------------------------------------------------------------------------------*/
post_test: Test = Test(
    info=TestInfo(
        name="POST Test",
        defaultConfig=Sigma5ManufacturingConfig().marshall(),
        description="This test is a test designed to test the functionality of"
        "components populated on the Sigma 5 hardware through a series"
        "of communication commands with the device itself",
    ),
    config_type=Sigma5ManufacturingConfig,
    init_func=post_test_init,
    deinit_func=post_test_deinit,
    usr_data=None,
    usr_data_type=None,
    steps=[
        # App
        app_post_step_1_verify_chip_ids,
        app_post_step_2_verify_ublox,
        app_post_step_3_verify_accelerometer,
        # app_post_step_4_verify_altimeter,
        # Comms
        comms_post_step_1_verify_chip_ids,
        comms_post_step_2_verify_modem_fw,
    ],
)
