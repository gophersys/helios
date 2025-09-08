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
class Step4Readings:
    vin_voltage: float = None
    vbatt_voltage: float = None
    _3v3_voltage: float = None
    vbckp_voltage: float = None
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
            return Step4Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_4_handler(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    readings = Step4Readings()

    # 4.a: Ensure +VIN test point is the same as +BATT
    result.error, readings.vin_voltage = mtib_servers.read_vin(node)
    if result.error:
        return result

    result.error, readings.vbatt_voltage = mtib_servers.read_vbat(node)
    if result.error:
        return result

    if abs(readings.vin_voltage - readings.vbatt_voltage) > config.electrical_step_4a_vin_vbat_tolerance:
        result.reason = f"Step 4.a failed: Expected +VIN = +VBAT, with tolerance {config.electrical_step_4a_vin_vbat_tolerance}, Actual +VIN = {readings.vin_voltage}V, +VBAT = {readings.vbatt_voltage}V"
        result.details = readings.marshall()
        return result

    # 4.b: Ensure regulated +3.3V test point voltage is within 3.2V - 3.4V
    result.error, readings._3v3_voltage = mtib_servers.read_3v3(node)
    if result.error:
        return result

    if not (config.electrical_step_4a_3v3_min <= readings._3v3_voltage <= config.electrical_step_4a_3v3_max):
        result.reason = f"Step 4.b failed: Expected +3.3V within {config.electrical_step_4a_3v3_min}V - {config.electrical_step_4a_3v3_max}V, Actual +3.3V = {readings._3v3_voltage}V"
        result.details = readings.marshall()
        return result

    # 4.c: Ensure +VBCKP test point voltage is within +2.4V - 2.6V
    result.error, readings.vbckp_voltage = mtib_servers.read_vbckp(node)
    if result.error:
        return result

    if not (config.electrical_step_4c_vbckp_min <= readings.vbckp_voltage <= config.electrical_step_4c_vbckp_max):
        result.reason = f"Step 4.c failed: Expected +VBCKP within {config.electrical_step_4c_vbckp_min}V - {config.electrical_step_4c_vbckp_max}V, Actual +3.3V = {readings.vbckp_voltage}V"
        result.details = readings.marshall()
        return result

    # TODO: Remove step 4.d from documentation or correct test

    # 4.e: Ensure UVP_N test point voltage is digital high
    result.error, readings.uvp_n_value = mtib_servers.read_uvp_n(node)
    if result.error:
        return result

    if readings.uvp_n_value is not True:
        result.reason = f"Step 4.e failed: Expected UVP_N digital high, Actual UVP_N = {readings.uvp_n_value}"
        result.details = readings.marshall()
        return result

    # 4.f: Ensure proper power consumption (no short circuits)
    result.error, readings.current_a = mtib_servers.read_current(node)
    if result.error:
        return result

    if not (config.electrical_step_4f_current_min <= readings.current_a <= config.electrical_step_4f_current_max):
        result.reason = f"Step 4.f failed: Expected current consumption within {config.electrical_step_4f_current_min}A - {config.electrical_step_4f_current_max}A, Actual current = {readings.current_a}A"
        result.details = readings.marshall()
        return result

    # Succeeded
    result.success = True
    result.details = readings.marshall()

    return result


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/
electrical_test_step_4: TestStep = TestStep(
    info=StepInfo(
        sequence=4,
        name="Ensure device electrical state.",
        description="Checks VIN, 3.3V, VBCKUP, UVP_N and current consumption against thresholds.",
        noPassIsFatal=False,
    ),
    timeout_ms=1000,
    handler=electrical_test_step_4_handler,
)
