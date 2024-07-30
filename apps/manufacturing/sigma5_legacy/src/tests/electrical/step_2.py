# Standard includes
import time
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import runnners_controller

# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                      Step Details
# -------------------------------------------------------------------------------*/
@dataclass
class Step2Readings:
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
            return Step2Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_2_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:

    result: TestStepResult = TestStepResult(success=False)

    readings = Step2Readings()

    # 2.a: Ensure +VIN test point voltage is below 0.3V.
    vin_success = False
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=config.vin_rail_stabilization_period_s):
        # Read the pin voltage
        result.error, readings.vin_voltage = runnners_controller.read_vin(node)
        if result.error:
            return result

        # Check results against configuration
        if readings.vin_voltage > config.electrical_step_2a_vin_threshold_v:
            # The voltage hasn't settled yet, sleep for some time before continuing the loop
            time.sleep(0.5)
        else:
            vin_success = True
            break

    readings.vin_stabilization_period_s = (datetime.now() - start_time).seconds

    if not vin_success:
        result.reason = f"Step 2.a failed due to VIN {readings.vin_voltage} being more than expected threshold {config.electrical_step_2a_vin_threshold_v}, after {config.vin_rail_stabilization_period_s}s"
        result.details = readings.marshall()
        return result

    # 2.b: TODO: remove Ensure +VBCKP test point voltage is below 0.3

    # 2.c: Ensure UVP_N test point voltage is digital low
    result.error, readings.uvp_n_value = runnners_controller.read_uvp_n(node)
    if result.error:
        return result

    if readings.uvp_n_value is not False:
        result.reason = f"Step 2.c failed: Expected UVP_N digital low, Actual UVP_N = {readings.uvp_n_value}"
        result.details = readings.marshall()
        return result

    # 2.d. Ensure near zero current consumption
    result.error, readings.current_a = runnners_controller.read_current(node)
    if result.error:
        return result

    if readings.current_a > config.electrical_step_2a_near_zero_current_a:
        result.reason = (
            f"Step 2.d failed: Expected near-zero current consumption, Actual current = {readings.current_a}A"
        )
        result.details = readings.marshall()
        return result

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_2: TestStep = TestStep(
    info=StepInfo(
        sequence=2,
        name="Ensure device electrical state.",
        description="Checks VIN, UVP_N and current consumption against thresholds.",
        noPassIsFatal=False,
    ),
    timeout_ms=180000,
    handler=electrical_test_step_2_handler,
)
