# Standard includes
import concurrent.futures
import time
from typing import List

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import StepInfo, TestInfo

# Corekinect Libraries
from tests.lib import Test, TestStep

# Test includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import mtib_servers
from .acceleromeer import verify_accelerometer
from .altimeter import verify_altimeter
from .chip_ids import verify_chip_ids
from .imei_iccid import verify_imei_iccid
from .modem import verify_modem_fw
from .personalization import clear_personalization, set_device_id
from .power import power_on_verify_comms
from .voltage import verify_voltage


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
DEFAULT_STEP_TIMEOUT_MS = 300000  # 5 minutes

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
        TestStep(
            info=StepInfo(
                name="Verify device responds to commands after power up.",
                description="Verifies that device responds to commands after power up using the runner API.",
                noPassIsFatal=True,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=power_on_verify_comms,
        ),
        # TODO: Rework fixture to enable correct voltage sensor reading before re-enabling this test
        # TestStep(
        #     info=StepInfo(
        #         name="Verify voltage",
        #         description="Verify the voltage on VBAT is reported by the DUT correctly.",
        #         noPassIsFatal=False,
        #     ),
        #     timeout_ms=DEFAULT_TIMEOUT,
        #     handler=verify_voltage,
        # ),
        TestStep(
            info=StepInfo(
                name="Get Chip IDs",
                description="Gets the chip IDs from the DUT.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=verify_chip_ids,
        ),
        TestStep(
            info=StepInfo(
                name="Get IMEI and ICCIDs.",
                description="Gets the device's IMEI and ICCIDs.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=verify_imei_iccid,
        ),
        TestStep(
            info=StepInfo(
                name="Verify Accelerometer",
                description="Verify the accelerometer readings from the DUT against the readings from the MTIB.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=verify_accelerometer,
        ),
        TestStep(
            info=StepInfo(
                name="Verify Altimeter",
                description="Verify the values reported by the DUT's Altimeter match the readings from the MTIB.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=verify_altimeter,
        ),
        TestStep(
            info=StepInfo(
                name="Verify Modem Firmware",
                description="Verify the modem firmware version is correct.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=verify_modem_fw,
        ),
        TestStep(
            info=StepInfo(
                name="Clear Personalization",
                description="Clear the personalization data from the device.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=clear_personalization,
        ),
        TestStep(
            info=StepInfo(
                name="Set Device ID",
                description="Set the device ID on the device.",
                noPassIsFatal=False,
            ),
            timeout_ms=DEFAULT_STEP_TIMEOUT_MS,
            handler=set_device_id,
        ),
    ],
)
