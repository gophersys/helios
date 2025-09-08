# Standard includes
import json
import logging
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import TestStepResult

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import CMD_GET_SENSOR_VALS_Response, mtib_servers


# ---------------------------------------------------------------------------------
#                                                                           Details
# -------------------------------------------------------------------------------*/
@dataclass
class DeviceReadings:
    mtib_x_g: float = None
    mtib_y_g: float = None
    mtib_z_g: float = None
    dut_x_g: float = None
    dut_y_g: float = None
    dut_z_g: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return DeviceReadings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def verify_accelerometer(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    readings: DeviceReadings = DeviceReadings()

    # Get the sensor values from the DUT
    dut_sensor_values: CMD_GET_SENSOR_VALS_Response
    result.error, dut_sensor_values = mtib_servers.dut_command_get_sensor_value(node)

    if result.error:
        return result

    # Get the accelerometer values from the MTIB
    result.error, mtib_accel_values = mtib_servers.read_accelerometer(node)
    if result.error:
        return result

    # Device orientation is not important so ignore the sign
    readings.mtib_x_g = abs(mtib_accel_values.x)
    readings.mtib_y_g = abs(mtib_accel_values.y)
    readings.mtib_z_g = abs(mtib_accel_values.z)
    readings.dut_x_g = abs(dut_sensor_values.accelerometer_x_g)
    readings.dut_y_g = abs(dut_sensor_values.accelerometer_y_g)
    readings.dut_z_g = abs(dut_sensor_values.accelerometer_z_g)

    # Marshall details into results regardless of outcome
    result.details = readings.marshall()

    # Check X
    x_upper = readings.mtib_x_g + config.post_test_accelerometer_error_margin
    x_lower = readings.mtib_x_g - config.post_test_accelerometer_error_margin
    if not x_lower <= readings.dut_x_g <= x_upper:
        result.reason = f"X axis out of range: got {readings.dut_x_g}, expected {readings.mtib_x_g} (Range: {x_lower} to {x_upper})"
        return result

    # Check Y
    y_upper = readings.mtib_y_g + config.post_test_accelerometer_error_margin
    y_lower = readings.mtib_y_g - config.post_test_accelerometer_error_margin
    if not y_lower <= readings.dut_y_g <= y_upper:
        result.reason = f"Y axis out of range: got {readings.dut_y_g}, expected {readings.mtib_y_g} (Range: {y_lower} to {y_upper})"
        return result

    # Check Z
    z_upper = readings.mtib_z_g + config.post_test_accelerometer_error_margin
    z_lower = readings.mtib_z_g - config.post_test_accelerometer_error_margin
    if not z_lower <= readings.dut_z_g <= z_upper:
        result.reason = f"Z axis out of range: got {readings.dut_z_g}, expected {readings.mtib_z_g} (Range: {z_lower} to {z_upper})"
        return result

    # Pass
    result.success = True
    return result
