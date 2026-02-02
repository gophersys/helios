# Standard includes
import concurrent.futures
import time
from typing import Dict, List

# Protocol includes
from protocols.cluster_test.cluster_test_pb2 import TestInfo

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
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
from .step_8 import electrical_test_step_8
from .step_9 import electrical_test_step_9
from .step_10 import electrical_test_step_10


# ---------------------------------------------------------------------------------
#                                                                              Init
# -------------------------------------------------------------------------------*/
def electrical_test_init(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, ElectricalTestSharedData]
) -> str:
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
def electrical_test_deinit(
    config: ThetaFixtureConfig, nodes: List[str], usr_data: Dict[str, ElectricalTestSharedData]
) -> str:
    for node in nodes:
        error = mtib_servers.disable_power(node)
        if error:
            return f"Could not disable device power in host {node}: {error}"

        error = mtib_servers.disable_charge_power(node)
        if error:
            return f"Could not disable charging power in host {node}: {error}"

        usr_data[node] = None

    time.sleep(1)

    usr_data.clear()
    electrical_test_shared_data.clear()

    error = mtib_servers.deinit()
    if error:
        return f"Could not deinitialize runners for test: {error}"

    return ""


# ---------------------------------------------------------------------------------
#                                                                              Test
# -------------------------------------------------------------------------------*/
electrical_test: Test = Test(
    info=TestInfo(
        name="Electrical Power Test",
        defaultConfig=ThetaFixtureConfig().marshall(),
        description="Tests the electrical power system of the Theta board including "
        "UVLO, power supply regulation, and charger load sharing.",
    ),
    config_type=ThetaFixtureConfig,
    init_func=electrical_test_init,
    deinit_func=electrical_test_deinit,
    usr_data=electrical_test_shared_data,
    usr_data_type=Dict[str, ElectricalTestSharedData],
    steps=[
        electrical_test_step_1,  # 1. Apply +3.4V to +BATT_IN
        electrical_test_step_2,  # 2. Ensure device electrical state (UVLO off)
        electrical_test_step_3,  # 3. Apply +3.7V to +BATT_IN
        electrical_test_step_4,  # 4. Ensure +3.3V remains below 0.3V for 2 seconds
        electrical_test_step_5,  # 5. Ensure device electrical state (powered)
        electrical_test_step_6,  # 6. Apply +4.5V to +BATT_IN
        electrical_test_step_7,  # 7. Ensure +SYS voltage is same as +BATT_IN
        electrical_test_step_8,  # 8. Apply 5.0V to +CHRG
        # electrical_test_step_9,  # 9. Ensure device electrical state (charger on)
        electrical_test_step_10,  # 10. Remove power from +CHRG
    ],
)
