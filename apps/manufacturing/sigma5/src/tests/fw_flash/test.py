# Standard includes
import concurrent.futures
import json
import os

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import *

# Test includes
from .step_1 import fw_flash_test_step_1
from .step_2 import fw_flash_test_step_2


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def fw_flash_test_init(config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: None) -> str:

    # Initialize the runners required to run this test
    error = mtib_servers.init(nodes)
    if error:
        return f"Could not initialize runners for test: {error}"

    def init_node(node: str) -> str:
        # Turn on power
        error = mtib_servers.enable_power(node, 4.0)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Turn on charging power, as the modem firmware fails to be flashed
        # when this rail is not on. Consumes too much power? Not sure?
        error = mtib_servers.set_5vin(node, True)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Firmware assets are packed with the client app (us), so we need to upload them
        # to the server so they can be flashed into the devices
        assets_folder = "assets"

        # First, upload the modem firmware for the nrf9160
        modem_fw_file = os.path.abspath(os.path.join(assets_folder, config.fw_flash_test_nrf9160_modem_fw_name))
        error = mtib_servers.upload_fw_file(node, modem_fw_file, HostType.HOST_TYPE_NRF9160_MODEM)
        if error:
            return f"Could not upload fw file {config.fw_flash_test_nrf9160_modem_fw_name} to node {node}: {error}"

        # Then, upload the app firmware for the nrf9160
        app_fw_file = os.path.abspath(os.path.join(assets_folder, config.fw_flash_test_nrf9160_app_fw_name))
        error = mtib_servers.upload_fw_file(node, app_fw_file, HostType.HOST_TYPE_NRF9160)
        if error:
            return f"Could not upload fw file {config.fw_flash_test_nrf9160_app_fw_name} to node {node}: {error}"

        # Then, upload the app firmware for the nrf52840
        app_fw_file = os.path.abspath(os.path.join(assets_folder, config.fw_flash_test_nrf52840_app_fw_name))
        error = mtib_servers.upload_fw_file(node, app_fw_file, HostType.HOST_TYPE_NRF52840)
        if error:
            return f"Could not upload fw file {config.fw_flash_test_nrf52840_app_fw_name} to node {node}: {error}"

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
def fw_flash_test_deinit(config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: None) -> str:
    def deinit_node(node: str) -> str:
        # Turn off power
        error = mtib_servers.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Turn off charging power
        error = mtib_servers.set_5vin(node, False)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Delete firmware files
        error = mtib_servers.delete_fw_file(
            node, config.fw_flash_test_nrf9160_modem_fw_name, HostType.HOST_TYPE_NRF9160_MODEM
        )
        if error:
            return f"Could not delete fw file {config.fw_flash_test_nrf9160_modem_fw_name} from node {node}: {error}"
        error = mtib_servers.delete_fw_file(node, config.fw_flash_test_nrf9160_app_fw_name, HostType.HOST_TYPE_NRF9160)
        if error:
            return f"Could not delete fw file {config.fw_flash_test_nrf9160_app_fw_name} from node {node}: {error}"
        error = mtib_servers.delete_fw_file(
            node, config.fw_flash_test_nrf52840_app_fw_name, HostType.HOST_TYPE_NRF52840
        )
        if error:
            return f"Could not delete fw file {config.fw_flash_test_nrf52840_app_fw_name} from node {node}: {error}"

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
fw_flash_test: Test = Test(
    # Test metadata
    info=TestInfo(
        name="Firmware Flashing Test",
        defaultConfig=Sigma5ManufacturingConfig().marshall(),
        description="This test is a test designed to upload manufacturing firmware"
        "to the modem, and both application cores in the Sigma 5 hardware",
    ),
    # Configuration type (if applicable)
    config_type=Sigma5ManufacturingConfig,
    # Init/Deinit function (if applicable)
    init_func=fw_flash_test_init,
    deinit_func=fw_flash_test_deinit,
    # Any data we wanna share between steps
    usr_data=None,
    usr_data_type=None,
    # Steps
    steps=[fw_flash_test_step_2],
)
