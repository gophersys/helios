# Standard includes
import concurrent.futures
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData, electrical_test_shared_data
from .step_1 import electrical_test_step_1
from .step_2 import electrical_test_step_2
from .step_3 import electrical_test_step_3
from .step_4 import electrical_test_step_4
from .step_5 import electrical_test_step_5
from .step_6 import electrical_test_step_6
from .step_7 import electrical_test_step_7


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def electrical_test_init(
    config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: Dict[str, ElectricalTestSharedData]
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

        usr_data[node] = ElectricalTestSharedData()

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
def electrical_test_deinit(
    config: Sigma5ManufacturingConfig, nodes: List[str], usr_data: Dict[str, ElectricalTestSharedData]
) -> str:
    # Turn off power
    for node in nodes:
        # Disable device power
        error = mtib_servers.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        # Turn off charging power
        error = mtib_servers.disable_charge_power(node)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        # Clear the shared data
        usr_data[node] = None

    # Await some time for the power to be off
    time.sleep(1)

    # Deinitialize our shared data
    usr_data.clear()

    electrical_test_shared_data.clear()

    # Deinitialize the runners used to run this test
    error = mtib_servers.deinit()
    if error:
        return f"Could not deinitialize runners for test: {error}"

    return ""


# ---------------------------------------------------------------------------------
#                                                                              Test
# -------------------------------------------------------------------------------*/
electrical_test: Test = Test(
    # Test metadata
    info=TestInfo(
        name="Electrical Test",
        defaultConfig=Sigma5ManufacturingConfig().marshall(),
        description="This test is a test designed to test the electrical state of" "a newly manufactured panel",
    ),
    # Configuration type (if applicable)
    config_type=Sigma5ManufacturingConfig,
    # Init/Deinit function (if applicable)
    init_func=electrical_test_init,
    deinit_func=electrical_test_deinit,
    # Any data we wanna share between steps
    usr_data=electrical_test_shared_data,
    usr_data_type=Dict[str, ElectricalTestSharedData],
    # Steps
    steps=[
        electrical_test_step_1,
        electrical_test_step_2,
        electrical_test_step_3,
        electrical_test_step_4,
        electrical_test_step_5,
        electrical_test_step_6,
        electrical_test_step_7,
    ],
)
