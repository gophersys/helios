# Standard includes
import concurrent.futures
import os
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo

# Corekinect libraries
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import MTIB_SERVICE_GRPC_SERVER_PORT

# Test includes
from .data import FwFlashTestSharedData, fw_flash_test_shared_data
from .step_1 import fw_flash_test_step_1
from .step_2 import fw_flash_test_step_2
from .step_3 import fw_flash_test_step_3


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def fw_flash_test_init(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, FwFlashTestSharedData]
) -> str:
    def init_node(node: str) -> str:
        # Create and connect MtibV1Client for this node
        client_config = MtibV1Client.Config(net=NetConfig(addr=node, port=MTIB_SERVICE_GRPC_SERVER_PORT))
        client = MtibV1Client(client_config)
        error = client.connect()
        if error:
            return f"Could not connect to mtib on host {node}: {error}"

        # Initialize shared data with client reference
        usr_data[node] = FwFlashTestSharedData()
        usr_data[node].client = client

        # Turn on power for flashing
        error = client.DutPowerEnable(4.0)
        if error:
            return f"Could not enable device power in host {node}: {error}"

        # Turn on charging power (modem firmware flash may need extra power)
        error = client.DutChargePowerEnable()
        if error:
            return f"Could not enable charging power in host {node}: {error}"

        # Upload firmware files to MTIB server
        assets_folder = "assets"

        # Upload modem firmware
        modem_fw_file = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf9151_modem_fw_name))
        error = client.UploadFwFile(modem_fw_file, HostType.HOST_TYPE_NRF9160_MODEM)
        if error:
            return f"Could not upload modem fw file to node {node}: {error}"

        # Upload nRF9151 app firmware
        comms_fw_file = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf9151_app_fw_name))
        error = client.UploadFwFile(comms_fw_file, HostType.HOST_TYPE_NRF9151)
        if error:
            return f"Could not upload nRF9151 app fw file to node {node}: {error}"

        # Upload nRF52840 app firmware
        app_fw_file = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf52840_app_fw_name))
        error = client.UploadFwFile(app_fw_file, HostType.HOST_TYPE_NRF52840)
        if error:
            return f"Could not upload nRF52840 app fw file to node {node}: {error}"

        return None

    # Run all hosts init in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(init_node, node): node for node in nodes}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                return error

    time.sleep(1)
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
        from protocols.mtib.mtib_pb2 import FwFileInfo as FwFileInfoProto

        error = client.DeleteFwFile(
            FwFileInfoProto(name=config.fw_flash_nrf9151_modem_fw_name, target=HostType.HOST_TYPE_NRF9160_MODEM)
        )
        if error:
            return f"Could not delete modem fw file from node {node}: {error}"

        error = client.DeleteFwFile(
            FwFileInfoProto(name=config.fw_flash_nrf9151_app_fw_name, target=HostType.HOST_TYPE_NRF9151)
        )
        if error:
            return f"Could not delete nRF9151 app fw file from node {node}: {error}"

        error = client.DeleteFwFile(
            FwFileInfoProto(name=config.fw_flash_nrf52840_app_fw_name, target=HostType.HOST_TYPE_NRF52840)
        )
        if error:
            return f"Could not delete nRF52840 app fw file from node {node}: {error}"

        # Turn off power
        client.DutChargePowerDisable()
        client.DutPowerDisable()

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
