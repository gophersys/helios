# Standard includes
import concurrent.futures
import os
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo

# Corekinect libraries
from corekinect.mtib_client.v2 import MtibV2Client, ClientConfig, NetConfig
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import FwFlashTestSharedData, fw_flash_test_shared_data
from .step_1 import fw_flash_test_step_1
from .step_2 import fw_flash_test_step_2
from .step_3 import fw_flash_test_step_3

# V2 gRPC server port
MTIB_V2_PORT = 50052


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def fw_flash_test_init(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, FwFlashTestSharedData]
) -> str:
    def init_node(node: str) -> str:
        # Create and connect MtibV2Client for this node
        client_config = ClientConfig(net=NetConfig(addr=node, port=MTIB_V2_PORT))
        client = MtibV2Client(client_config)
        error = client.connect()
        if error:
            return f"Could not connect to mtib on host {node}: {error}"

        # Initialize shared data with client reference
        usr_data[node] = FwFlashTestSharedData()
        usr_data[node].client = client

        # Turn on power for flashing — 4.5V required for Alpha B0 (BQ25180 UVLO)
        error = client.power_enable(channel=0, voltage_v=4.5)
        if error:
            return f"Could not enable device power in host {node}: {error}"

        # Turn on charging power (modem firmware flash may need extra power)
        error = client.power_enable(channel=1)
        if error:
            return f"Could not enable charging power in host {node}: {error}"

        # Upload firmware files to MTIB server
        assets_folder = "assets"

        # Upload modem firmware
        modem_fw_path = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf9151_modem_fw_name))
        with open(modem_fw_path, "rb") as f:
            modem_fw_data = f.read()
        error, _ = client.upload_file(config.fw_flash_nrf9151_modem_fw_name, modem_fw_data)
        if error:
            return f"Could not upload modem fw file to node {node}: {error}"

        # Upload nRF9151 app firmware
        comms_fw_path = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf9151_app_fw_name))
        with open(comms_fw_path, "rb") as f:
            comms_fw_data = f.read()
        error, _ = client.upload_file(config.fw_flash_nrf9151_app_fw_name, comms_fw_data)
        if error:
            return f"Could not upload nRF9151 app fw file to node {node}: {error}"

        # Upload nRF52840 app firmware
        app_fw_path = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf52840_app_fw_name))
        with open(app_fw_path, "rb") as f:
            app_fw_data = f.read()
        error, _ = client.upload_file(config.fw_flash_nrf52840_app_fw_name, app_fw_data)
        if error:
            return f"Could not upload nRF52840 app fw file to node {node}: {error}"

        # Configure GPIO for SWD level shifter (output, drive low)
        client.gpio_config(pin=0, direction=1)
        client.gpio_config(pin=1, direction=1)
        client.gpio_write(pin=0, value=False)
        client.gpio_write(pin=1, value=False)

        return None

    # Run all hosts init in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(init_node, node): node for node in nodes}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                return error

    time.sleep(5)
    return ""


# ---------------------------------------------------------------------------------
#                                                                            Deinit
# -------------------------------------------------------------------------------*/
def fw_flash_test_deinit(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, FwFlashTestSharedData]
) -> str:
    def deinit_node(node: str) -> str:
        node_data = usr_data.get(node)
        if not node_data or not node_data.client:
            return None

        client = node_data.client

        # Delete firmware files from MTIB server
        client.delete_file(config.fw_flash_nrf9151_modem_fw_name)
        client.delete_file(config.fw_flash_nrf9151_app_fw_name)
        client.delete_file(config.fw_flash_nrf52840_app_fw_name)

        # Turn off power
        client.power_disable(channel=1)
        client.power_disable(channel=0)

        # Disconnect client
        client.disconnect()
        usr_data[node] = None
        return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(deinit_node, node): node for node in nodes}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                return error

    time.sleep(1)
    return ""


# ---------------------------------------------------------------------------------
#                                                                              Test
# -------------------------------------------------------------------------------*/
fw_flash_test: Test = Test(
    info=TestInfo(
        name="Flash Manufacturing Firmware",
        defaultConfig=ThetaFixtureConfig().marshall(),
        description="Flashes manufacturing firmware onto both microcontrollers "
        "(nRF9151 modem + app, nRF52840 app) for testing, then sets AP protect.",
    ),
    config_type=ThetaFixtureConfig,
    init_func=fw_flash_test_init,
    deinit_func=fw_flash_test_deinit,
    usr_data=fw_flash_test_shared_data,
    usr_data_type=Dict[str, FwFlashTestSharedData],
    steps=[
        fw_flash_test_step_1,
        fw_flash_test_step_2,
        fw_flash_test_step_3,
    ],
)
