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
class Step10Readings:
    vin_stabilization_period_s: int = None
    vin_voltage: float = None
    _3v3_voltage: float = None
    vbckp_voltage: float = None
    uvp_n_value: bool = None
    chrg_det_value: bool = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return Step10Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_10_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    readings = Step10Readings()

    # 10.a: Ensure +VIN test point is 5V
    vin_success = False
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=config.vin_rail_stabilization_period_s):
        # Read the pin voltage
        result.error, readings.vin_voltage = runnners_controller.read_vin(node)
        if result.error:
            return result

        # Check results against configuration
        if readings.vin_voltage < config.electrical_step_10a_vin_threshold_v:
            # The voltage hasn't settled yet, sleep for some time before continuing the loop
            time.sleep(0.5)
        else:
            vin_success = True
            break

    readings.vin_stabilization_period_s = (datetime.now() - start_time).seconds

    if not vin_success:
        result.reason = f"Step 10.a failed due to VIN {readings.vin_voltage} being less than expected threshold {config.electrical_step_10a_vin_threshold_v}, after {config.vin_rail_stabilization_period_s}s"
        result.details = readings.marshall()
        return result

    # 10.b: Ensure regulated +3.3V test point voltage is within 3.2V - 3.4V
    result.error, readings._3v3_voltage = runnners_controller.read_3v3(node)
    if result.error:
        return result

    if not (config.electrical_step_10b_3v3_min <= readings._3v3_voltage <= config.electrical_step_10b_3v3_max):
        result.reason = f"Step 10.b failed: Expected +3.3V within {config.electrical_step_10b_3v3_min}V - {config.electrical_step_10b_3v3_max}V, Actual +3.3V = {readings._3v3_voltage}V"
        result.details = readings.marshall()
        return result

    # 10.c: Ensure +VBCKP test point voltage is within +2.4V - 2.6V
    result.error, readings.vbckp_voltage = runnners_controller.read_vbckp(node)
    if result.error:
        return result

    if not (config.electrical_step_10c_vbckp_min <= readings.vbckp_voltage <= config.electrical_step_10c_vbckp_max):
        result.reason = f"Step 10.c failed: Expected +VBCKP within {config.electrical_step_10c_vbckp_min}V - {config.electrical_step_10c_vbckp_max}V, Actual +3.3V = {readings.vbckp_voltage}V"
        result.details = readings.marshall()
        return result

    # 10.d: Ensure UVP_N test point voltage is digital high
    if node == "slot-3":
        result.error, readings.uvp_n_value = runnners_controller.read_uvp_n(node)
        if result.error:
            return result

        if readings.uvp_n_value is not True:
            result.reason = f"Step 10.d failed: Expected UVP_N digital high, Actual UVP_N = {readings.uvp_n_value}"
            result.details = readings.marshall()
            return result

    # 10.e: Ensure CHRG_DET test point is digital low
    result.error, readings.chrg_det_value = runnners_controller.read_chrg_det(node)
    if result.error:
        return result

    if readings.chrg_det_value is not False:
        result.reason = f"Step 10.e failed: Expected CHRG_DET digital low, Actual CHRG_DET = {readings.chrg_det_value}"
        result.details = readings.marshall()
        return result

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_10: TestStep = TestStep(
    info=StepInfo(
        sequence=10,
        name="Ensure device electrical state.",
        description="Checks VIN, 3.3V, VBCKUP, UVP_N and CHRG_DET against thresholds.",
        noPassIsFatal=False,
    ),
    timeout_ms=30000,
    handler=electrical_test_step_10_handler,
)
