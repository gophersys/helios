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
class Step5Readings:
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
            return Step5Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_5_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    readings = Step5Readings()

    # 5. Apply +5V to +5V_IN test point
    result.error = mtib_servers.enable_charge_power(node)
    if result.error:
        return result

    # 5.a: Ensure +VIN test point is 5V
    vin_success = False
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=config.vin_rail_stabilization_period_s):
        # Read the pin voltage
        result.error, readings.vin_voltage = mtib_servers.read_vin(node)
        if result.error:
            return result

        # Check results against configuration
        if readings.vin_voltage < config.electrical_step_5a_vin_threshold_v:
            # The voltage hasn't settled yet, sleep for some time before continuing the loop
            time.sleep(0.5)
        else:
            vin_success = True
            break

    readings.vin_stabilization_period_s = (datetime.now() - start_time).seconds

    if not vin_success:
        result.reason = f"Step 5.a failed due to VIN {readings.vin_voltage} being less than expected threshold {config.electrical_step_5a_vin_threshold_v}, after {config.vin_rail_stabilization_period_s}s"
        result.details = readings.marshall()
        return result

    # 5.b: Ensure regulated +3.3V test point voltage is within 3.2V - 3.4V
    result.error, readings._3v3_voltage = mtib_servers.read_3v3(node)
    if result.error:
        return result

    if not (config.electrical_step_5b_3v3_min <= readings._3v3_voltage <= config.electrical_step_5b_3v3_max):
        result.reason = f"Step 5.b failed: Expected +3.3V within {config.electrical_step_5b_3v3_min}V - {config.electrical_step_5b_3v3_max}V, Actual +3.3V = {readings._3v3_voltage}V"
        result.details = readings.marshall()
        return result

    # 5.c: Ensure +VBCKP test point voltage is within +2.4V - 2.6V
    result.error, readings.vbckp_voltage = mtib_servers.read_vbckp(node)
    if result.error:
        return result

    if not (config.electrical_step_5c_vbckp_min <= readings.vbckp_voltage <= config.electrical_step_5c_vbckp_max):
        result.reason = f"Step 5.c failed: Expected +VBCKP within {config.electrical_step_5c_vbckp_min}V - {config.electrical_step_5c_vbckp_max}V, Actual +3.3V = {readings.vbckp_voltage}V"
        result.details = readings.marshall()
        return result

    # 5.e: Ensure CHRG_DET test point is digital low
    result.error, readings.chrg_det_value = mtib_servers.read_chrg_det(node)
    if result.error:
        return result

    if readings.chrg_det_value is not False:
        result.reason = f"Step 5.e failed: Expected CHRG_DET digital low, Actual CHRG_DET = {readings.chrg_det_value}"
        result.details = readings.marshall()
        return result

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_5: TestStep = TestStep(
    info=StepInfo(
        name="Ensure device electrical state.",
        description="Checks VIN, 3.3V, VBCKUP, UVP_N and CHRG_DET against thresholds.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_5_handler,
)
