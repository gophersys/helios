import logging
from time import sleep

from tests.lib import TestStepResult

from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import CMD_GET_SENSOR_VALS_Response, mtib_servers


def _set_voltage(node: str, voltage: float) -> str:
    if error := mtib_servers.set_vbat(node, voltage):
        return f"Could not set VBAT on host {node} to {voltage}V: {error}"

    logging.debug(f"Set VBAT on host {node} to {voltage}V")
    sleep(5)
    return ""


def _check_voltage(node: str, voltage: float) -> str:
    dut_sensor_values: CMD_GET_SENSOR_VALS_Response
    error, dut_sensor_values = mtib_servers.dut_command_get_sensor_value(node)

    if error:
        return f"Could not get sensor values from host {node}: {error=}"

    logging.debug(f"Voltage measurement: {dut_sensor_values.voltage_measurement}V")

    voltage_upper = voltage + Sigma5ManufacturingConfig.post_test_voltage_error_margin
    voltage_lower = voltage - Sigma5ManufacturingConfig.post_test_voltage_error_margin
    if not voltage_lower <= dut_sensor_values.voltage_measurement <= voltage_upper:
        return f"Voltage out of range: {dut_sensor_values.voltage_measurement}V vs {voltage}V (Range: {voltage_lower} to {voltage_upper})"
    else:
        logging.debug(
            f"Voltage in range: {dut_sensor_values.voltage_measurement}V vs {voltage}V (Range: {voltage_lower} to {voltage_upper})"
        )

    return ""


def verify_voltage(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    logging.info("Starting voltage verification...")
    result = TestStepResult(success=False)

    # Set and check voltages
    for voltage in Sigma5ManufacturingConfig.post_test_voltages:
        if error := _set_voltage(node, voltage):
            result.reason = f"Unable to set voltage to {voltage}V: {error=}"
            return result
        if error := _check_voltage(node, voltage):
            result.reason = f"Voltage check failed at {voltage}V: {error=}"
            return result

    # Pass
    logging.info("Voltage sensor verified.")
    result.success = True
    return result
