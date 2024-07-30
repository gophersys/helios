# Standard includes
import concurrent.futures
import json
import os

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import TestInfo

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import runnners_controller

# Test includes
from .step_1 import fw_flash_test_step_1
from .step_2 import fw_flash_test_step_2


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def fw_flash_test_init(config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: None) -> str:

    # Initialize the runners required to run this test
    error = runnners_controller.init(nodes)
    if error:
        return f"Could not initialize runners for test: {error}"

    def init_node(node: str) -> str:
        # Turn on power
        error = runnners_controller.enable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Turn on charging power, as the modem firmware fails to be flashed
        # when this rail is not on. Consumes too much power? Not sure?
        error = runnners_controller.set_5vin(node, True)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Upload all the firmware files needed for this run
        fw_files = [
            config.prod_fw_flash_test_nrf9160_modem_fw_name,
            config.prod_fw_flash_test_nrf9160_app_fw_name,
            config.prod_fw_flash_test_nrf52840_app_fw_name,
        ]

        # Build the assets directory based on test location
        assets_folder = "assets"

        # Upload
        for file_name in fw_files:
            error = runnners_controller.upload_fw_file(node, os.path.abspath(os.path.join(assets_folder, file_name)))
            if error:
                return f"Could not upload fw file {file_name} to node {node}: {error}"

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
        error = runnners_controller.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Turn off charging power
        error = runnners_controller.set_5vin(node, False)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Create a list of what files need to be deleted
        fw_files = [
            config.prod_fw_flash_test_nrf9160_modem_fw_name,
            config.prod_fw_flash_test_nrf9160_app_fw_name,
            config.prod_fw_flash_test_nrf52840_app_fw_name,
        ]

        # Delete firmware files
        for file_name in fw_files:
            error = runnners_controller.delete_fw_file(node, file_name)
            if error:
                return f"Could not delete fw file {file_name} from node {node}: {error}"

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
    error = runnners_controller.deinit()
    if error:
        return f"Could not deinitialize runners for test: {error}"

    return ""


# ---------------------------------------------------------------------------------
#                                                                              Test
# -------------------------------------------------------------------------------*/
prod_fw_flash_test: Test = Test(
    # Test metadata
    info=TestInfo(
        name="Production Firmware Flashing Test",
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
    # steps=[fw_flash_test_step_1, fw_flash_test_step_2],
    steps=[fw_flash_test_step_2],
)
