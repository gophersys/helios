# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                      Step Details
# -------------------------------------------------------------------------------*/
@dataclass
class Step8Readings:
    vin_stabilization_period_s: int = None
    vin_voltage: float = None
    uvp_n_value: bool = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return Step8Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_8_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    readings = Step8Readings()

    # 8.a: Ensure +VIN test point voltage is below 0.3V.
    vin_success = False
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=config.vin_rail_stabilization_period_s):
        # Read the pin voltage
        result.error, readings.vin_voltage = mtib_servers.read_vin(node)
        if result.error:
            return result

        # Check results against configuration
        if readings.vin_voltage > config.electrical_step_8a_vin_threshold_v:
            # The voltage hasn't settled yet, sleep for some time before continuing the loop
            time.sleep(0.5)
        else:
            vin_success = True
            break

    readings.vin_stabilization_period_s = (datetime.now() - start_time).seconds

    if not vin_success:
        result.reason = f"Step 8.a failed due to VIN {readings.vin_voltage} being more than expected threshold {config.electrical_step_8a_vin_threshold_v}, after {config.vin_rail_stabilization_period_s}s"
        result.details = readings.marshall()
        return result

    # 8.b: Ensure UVP_N test point voltage is digital low
    result.error, readings.uvp_n_value = mtib_servers.read_uvp_n(node)
    if result.error:
        return result

    if readings.uvp_n_value is not False:
        result.reason = f"Step 8.b failed: Expected UVP_N digital low, Actual UVP_N = {readings.uvp_n_value}"
        result.details = readings.marshall()
        return result

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_8: TestStep = TestStep(
    info=StepInfo(
        sequence=8,
        name="Ensure device electrical state.",
        description="Checks VIN, and UVP_N against thresholds.",
        noPassIsFatal=False,
    ),
    timeout_ms=30000,
    handler=electrical_test_step_8_handler,
)
