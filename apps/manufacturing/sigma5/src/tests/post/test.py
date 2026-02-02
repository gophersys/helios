# Standard includes
import concurrent.futures
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import StepInfo, TestInfo

# Corekinect Libraries
from src.tests.lib import Test, TestStep

# Test includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers

# App POST steps
from .app.step_1 import app_post_step_1_verify_chip_ids
from .app.step_2 import app_post_step_2_verify_ublox
from .app.step_3 import app_post_step_3_verify_accelerometer
from .app.step_4 import app_post_step_4_verify_altimeter
from .app.step_5 import app_post_step_5_verify_ble
from .app.step_6 import app_post_step_6_enable_app_protect

# Comms POST steps
from .comms.step_1 import comms_post_step_1_verify_chip_ids
from .comms.step_2 import comms_post_step_2_verify_modem_fw
from .comms.step_3 import comms_post_step_3_verify_imei_iccids
from .comms.step_4 import comms_post_step_4_verify_external_flash
from .comms.step_5 import comms_post_step_5_personalize
from .comms.step_6 import comms_post_step_6_rekey_ipc
from .comms.step_7 import comms_post_step_7_enable_app_protect

# Post test includes
from .data import PostTestSharedData, post_test_shared_data


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def post_test_init(
    config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: Dict[str, PostTestSharedData]
) -> str:
    # HARDCODED: Override nodes for quick panel test
    nodes = ["verdin-imx8mm-15005679"]

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
        error = mtib_servers.disable_charge_power(node)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Await some time for the power to be off
        time.sleep(2)

        # Turn on the device
        error = mtib_servers.enable_power(node, 4.0)
        if error:
            return f"Could not set VBAT on host {node} to 3.8V: {error}"

        # Await some time for boot
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

        # Initialize the shared data
        usr_data[node] = PostTestSharedData()

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
def post_test_deinit(
    config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: Dict[str, PostTestSharedData]
) -> str:
    def deinit_node(node: str) -> str:
        # Turn off charging power
        error = mtib_servers.disable_charge_power(node)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Turn off power
        error = mtib_servers.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Clear the shared data
        usr_data[node] = None

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
    usr_data=post_test_shared_data,
    usr_data_type=Dict[str, PostTestSharedData],
    steps=[
        # App
        app_post_step_1_verify_chip_ids,
        app_post_step_2_verify_ublox,
        app_post_step_3_verify_accelerometer,
        app_post_step_4_verify_altimeter,
        app_post_step_5_verify_ble,  # TODO: Implement BLE in MTIB server
        
        # Comms
        comms_post_step_1_verify_chip_ids,
        comms_post_step_2_verify_modem_fw,
        comms_post_step_3_verify_imei_iccids,

        # External Flash
        comms_post_step_4_verify_external_flash,

        # Personalize
        comms_post_step_5_personalize,
        comms_post_step_6_rekey_ipc,

        # Ap Protect
        app_post_step_6_enable_app_protect,
        comms_post_step_7_enable_app_protect,
    ],
)
