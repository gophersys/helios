# Standard includes
import concurrent.futures
import os
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo
from protocols.mtib.mtib_pb2 import GpioDirection, GpioResistorConfig, HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

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
    # Connect to all MTIB servers via V1
    err = mtib_servers.init(nodes)
    if err:
        return f"Failed to initialize MTIB servers: {err}"

    def init_node(node: str) -> str:
        usr_data[node] = FwFlashTestSharedData()

        # Configure GPIO 0+1 as output LOW (SWD level shifter — required for DUT boot)
        for gpio in (0, 1):
            err = mtib_servers.gpio_config(
                node, gpio, GpioDirection.GPIO_DIRECTION_OUTPUT, GpioResistorConfig.GPIO_RESISTOR_NONE
            )
            if err:
                return f"GPIO {gpio} config failed on {node}: {err}"
            err = mtib_servers.gpio_write(node, gpio, False)
            if err:
                return f"GPIO {gpio} write failed on {node}: {err}"

        # Power on DUT at 4.5V (BQ25180 UVLO requirement)
        err = mtib_servers.enable_power(node, 4.5)
        if err:
            return f"Could not enable device power on {node}: {err}"

        # Enable charge power (5V fixed)
        err = mtib_servers.enable_charge_power(node)
        if err:
            return f"Could not enable charging power on {node}: {err}"

        # Upload firmware files
        assets_folder = "assets"

        # Upload nRF52840 app firmware
        app_fw_path = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf52840_app_fw_name))
        err = mtib_servers.upload_fw_file(node, app_fw_path, HostType.HOST_TYPE_NRF52840)
        if err:
            return f"Could not upload nRF52840 app fw to {node}: {err}"

        # Upload nRF9151 comms firmware
        comms_fw_path = os.path.abspath(os.path.join(assets_folder, config.fw_flash_nrf9151_app_fw_name))
        err = mtib_servers.upload_fw_file(node, comms_fw_path, HostType.HOST_TYPE_NRF9151)
        if err:
            return f"Could not upload nRF9151 comms fw to {node}: {err}"

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
        # Delete uploaded firmware files
        mtib_servers.delete_fw_file(node, config.fw_flash_nrf52840_app_fw_name, HostType.HOST_TYPE_NRF52840)
        mtib_servers.delete_fw_file(node, config.fw_flash_nrf9151_app_fw_name, HostType.HOST_TYPE_NRF9151)

        # Power off
        mtib_servers.disable_charge_power(node)
        mtib_servers.disable_power(node)

        usr_data[node] = None
        return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(deinit_node, node): node for node in nodes}
        for future in concurrent.futures.as_completed(futures):
            error = future.result()
            if error:
                return error

    mtib_servers.deinit()
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
        "(nRF52840 app, nRF9151 comms) via V1 MTIB server, then sets AP protect.",
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
