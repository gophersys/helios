# Standard includes
import json
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
class Step6Readings:
    vin_voltage: float = None
    vbatt_voltage: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return Step6Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_6_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    readings = Step6Readings()

    # 6.a: Ensure +VIN test point is the same as +BATT
    result.error, readings.vin_voltage = runnners_controller.read_vin(node)
    if result.error:
        return result

    result.error, readings.vbatt_voltage = runnners_controller.read_vbat(node)
    if result.error:
        return result

    if abs(readings.vin_voltage - readings.vbatt_voltage) > config.electrical_step_6a_vin_vbat_tolerance:
        result.reason = f"Step 6.a failed: Expected +VIN = +VBAT, with tolerance {config.electrical_step_6a_vin_vbat_tolerance}, Actual +VIN = {readings.vin_voltage}V, +VBAT = {readings.vbatt_voltage}V"
        result.details = readings.marshall()
        return result

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_6: TestStep = TestStep(
    info=StepInfo(
        sequence=6,
        name="Ensure device electrical state.",
        description="Checks VIN vs BATT++ readings.",
        noPassIsFatal=False,
    ),
    timeout_ms=1000,
    handler=electrical_test_step_6_handler,
)
