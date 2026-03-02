# Standard includes
import concurrent.futures
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import PostTestSharedData, post_test_shared_data
from .step_0 import post_step_0_boot_and_lock
from .step_1 import post_step_1_comms_chip_ids
from .step_2 import post_step_2_app_chip_ids
from .step_3 import post_step_3_bms
from .step_4 import post_step_4_charger
from .step_5 import post_step_5_gps
from .step_6 import post_step_6_modem_fw
from .step_7 import post_step_7_imei
from .step_8 import post_step_8_ext_flash
from .step_9 import post_step_9_personalize
from .step_10 import post_step_10_rekey_ipc


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def post_test_init(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, PostTestSharedData]
) -> str:
    # Connect to all MTIB servers via V1
    err = mtib_servers.init(nodes)
    if err:
        return f"Failed to initialize MTIB servers: {err}"

    # Initialize shared data for each node
    for node in nodes:
        usr_data[node] = PostTestSharedData()

    return ""


# ---------------------------------------------------------------------------------
#                                                                            Deinit
# -------------------------------------------------------------------------------*/
def post_test_deinit(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, PostTestSharedData]
) -> str:
    def deinit_node(node: str) -> str:
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
post_test: Test = Test(
    info=TestInfo(
        name="Execute Test Firmware",
        defaultConfig=ThetaFixtureConfig().marshall(),
        description="Runs the complete POST test suite including chip ID verification, "
        "BMS, charger, GPS, modem FW, IMEI/ICCID, external flash, "
        "device personalization, and IPC rekey.",
    ),
    config_type=ThetaFixtureConfig,
    init_func=post_test_init,
    deinit_func=post_test_deinit,
    usr_data=post_test_shared_data,
    usr_data_type=Dict[str, PostTestSharedData],
    steps=[
        post_step_0_boot_and_lock,     # 0. Power cycle and lock shells
        post_step_1_comms_chip_ids,    # 1. Verify comms processor chip IDs
        post_step_2_app_chip_ids,      # 2. Verify app processor chip IDs
        post_step_3_bms,               # 3. Verify BMS (gas gauge)
        post_step_4_charger,           # 4. Verify battery charger
        post_step_5_gps,               # 5. Verify GPS module
        post_step_6_modem_fw,          # 6. Verify modem firmware version
        post_step_7_imei,              # 7. Verify IMEI and ICCIDs
        post_step_8_ext_flash,         # 8. Verify external flash (both processors)
        post_step_9_personalize,       # 9. Personalize device with CoreOps
        post_step_10_rekey_ipc,        # 10. Rekey IPC
    ],
)
