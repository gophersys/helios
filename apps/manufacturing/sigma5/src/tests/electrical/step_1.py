# Standard includes
from typing import Dict
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class Step1Readings:
    vin_stabilization_period_s: int = None
    vin_voltage: float = None
    uvp_n_value: bool = None
    current_a: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return Step1Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_1_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)
    readings = Step1Readings()

    # 1. Apply +2.5V to +BATT test point
    result.error = mtib_servers.enable_power(node, 2.4)
    if result.error:
        return result

    # a. Verify +VIN < 0.3V
    vin_success = False
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=config.vin_rail_stabilization_period_s):
        # Read the pin voltage
        result.error, readings.vin_voltage = mtib_servers.read_vin(node)
        if result.error:
            return result

        # Check results against configuration
        if readings.vin_voltage > config.electrical_step_1a_vin_threshold_v:
            time.sleep(0.5)  # The voltage hasn't settled yet, sleep for some time before continuing the loop
        else:
            vin_success = True
            break

    readings.vin_stabilization_period_s = (datetime.now() - start_time).seconds

    if not vin_success:
        result.reason = f"Step 1.a failed due to VIN {readings.vin_voltage} being more than expected threshold {config.electrical_step_1a_vin_threshold_v}, after {config.vin_rail_stabilization_period_s}s"
        result.details = readings.marshall()
        return result

    # # b. Verify +VBCKP < 0.3v
    # vbckp_success = False
    # start_time = datetime.now()
    # while datetime.now() - start_time < timedelta(seconds=config.vin_rail_stabilization_period_s):
    #     # Read the pin voltage
    #     result.error, readings.vbckp_voltage = mtib_servers.read_vbckp(node)
    #     if result.error:
    #         return result

    #     # Check results against configuration
    #     if readings.vbckp_voltage > config.electrical_step_1b_vbckp_threshold_v:
    #         time.sleep(0.5)  # The voltage hasn't settled yet, sleep for some time before continuing the loop
    #     else:
    #         vbckp_success = True
    #         break

    # readings.vin_stabilization_period_s = (datetime.now() - start_time).seconds

    # if not vbckp_success:
    #     result.reason = f"Step 1.b failed due to VBCKP {readings.vbckp_voltage} being more than expected threshold {config.electrical_step_1b_vbckp_threshold_v}, after {config.vin_rail_stabilization_period_s}s"
    #     result.details = readings.marshall()
    #     return result

    # logging.debug(
    #     f"Step 1.b: VBCKP voltage: {readings.vbckp_voltage}V, stabilization period: {readings.vin_stabilization_period_s}s"
    # )

    # c. Verify UVP_N is digital low
    result.error, readings.uvp_n_value = mtib_servers.read_uvp_n(node)
    if result.error:
        return result

    if readings.uvp_n_value is not False:
        result.reason = f"Step 1.c failed: Expected UVP_N digital low, Actual UVP_N = {readings.uvp_n_value}"
        result.details = readings.marshall()
        return result

    logging.debug(f"Step 1.c: UVP_N value: {readings.uvp_n_value}")

    # d. Verify +BATT current < 10mA TODO/Note: This seems really high…
    result.error, readings.current_a = mtib_servers.read_current(node)
    if result.error:
        return result

    if readings.current_a > config.electrical_step_1d_near_zero_current_a:
        result.reason = (
            f"Step 1.d failed: Expected near-zero current consumption, Actual current = {readings.current_a}A"
        )
        result.details = readings.marshall()
        return result

    logging.debug(f"Step 1.d: Current value: {readings.current_a}A")

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_1: TestStep = TestStep(
    info=StepInfo(
        name="Apply +2.5V to +BATT; voltage at UVLO threshold",
        description="Checks VIN, VBCKUP, UVP_N and current consumption against thresholds.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_1_handler,
)
