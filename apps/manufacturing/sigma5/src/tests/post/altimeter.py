# Standard includes
import json
import logging
from typing import List
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
    mtib_pressure_hg: float = None
    mtib_temperature_c: float = None
    dut_pressure_hg: float = None
    dut_temperature_c: float = None

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


def verify_altimeter(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    readings: DeviceReadings = DeviceReadings()

    # Get the sensor values from the DUT
    dut_sensor_values: CMD_GET_SENSOR_VALS_Response
    result.error, dut_sensor_values = mtib_servers.dut_command_get_sensor_value(node)

    if result.error:
        return result

    # Get the altimeter values from the MTIB
    result.error, mtib_alt_values = mtib_servers.read_altimeter(node)
    if result.error:
        return result

    # Set the readings
    readings.dut_pressure_hg = dut_sensor_values.altimeter_pressure_in_hg
    readings.dut_temperature_c = dut_sensor_values.altimeter_temperature_c
    readings.mtib_pressure_hg = mtib_alt_values.pressure_hg
    readings.mtib_temperature_c = mtib_alt_values.temperature_f

    # Marshall details into results regardless of outcome
    result.details = readings.marshall()

    # Check the pressure
    mtib_pressure_lower = mtib_alt_values.pressure_hg - config.post_test_altimeter_error_margin
    mtib_pressure_upper = mtib_alt_values.pressure_hg + config.post_test_altimeter_error_margin
    if not (mtib_pressure_lower <= dut_sensor_values.altimeter_pressure_in_hg <= mtib_pressure_upper):
        result.reason = f"Pressure out of range: got {dut_sensor_values.altimeter_pressure_in_hg}, expected {mtib_alt_values.pressure_hg}"
        return result

    # Check the temperature
    mtib_temp_lower = mtib_alt_values.temperature_f - config.post_test_temperature_error_margin
    mtib_temp_upper = mtib_alt_values.temperature_f + config.post_test_temperature_error_margin
    if not (mtib_temp_lower <= dut_sensor_values.altimeter_temperature_c <= mtib_temp_upper):
        result.reason = f"Temperature out of range: got {dut_sensor_values.altimeter_temperature_c}, expected {mtib_alt_values.temperature_f}"
        return result

    # Pass
    result.success = True
    return result
