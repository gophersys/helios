# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import mtib_servers, CMD_POST_Response


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def verify_chip_ids(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    # Get the sensor values from the DUT
    dut_sensor_values: CMD_POST_Response
    result.error, dut_sensor_values = mtib_servers.dut_command_get_chip_id(node)

    if result.error:
        return result

    # Verify accelerometer IC ID
    if not dut_sensor_values.accel_ic_id == config.post_test_accel_chip_id:
        result.reason = (
            f"Accelerometer IC ID mismatch: {dut_sensor_values.accel_ic_id}, expected {config.post_test_accel_chip_id}"
        )
        return result

    # Verify altimeter IC ID
    if not dut_sensor_values.alt_ic_id == config.post_test_alt_chip_id:
        result.reason = (
            f"Altimeter IC ID mismatch: {dut_sensor_values.alt_ic_id}, expected {config.post_test_alt_chip_id}"
        )
        return result

    # Verify external flash IC ID
    if not dut_sensor_values.external_flash_ic_id == config.post_test_external_flash_chip_id:
        result.reason = f"External Flash IC ID mismatch: {dut_sensor_values.external_flash_ic_id} , expected {config.post_test_external_flash_chip_id}"
        return result

    # Verify lorawan connection
    if not dut_sensor_values.is_lora_connected:
        result.reason = "LoRaWAN connection not established"
        return result

    # Verify external flash test result
    if not dut_sensor_values.external_flash_test_pass:
        result.reason = "External flash test failed"
        return result
    else:
        logging.debug("External flash test passed")

    # Verify ublox GPS info
    # SW version
    if not dut_sensor_values.gps_ublox_sw_ver == config.post_test_gps_ublox_sw_version:
        result.reason = f"Ublox GPS SW version mismatch: {dut_sensor_values.gps_ublox_sw_ver} , expected {config.post_test_gps_ublox_sw_version}"
        return result

    # FW version
    if not dut_sensor_values.gps_ublox_fw_ver == config.post_test_gps_ublox_fw_version:
        result.reason = f"Ublox GPS FW version mismatch: {dut_sensor_values.gps_ublox_fw_ver} , expected {config.post_test_gps_ublox_fw_version}"
        return result

    # HW version
    if not dut_sensor_values.gps_ublox_hw_ver == config.post_test_gps_ublox_hw_version:
        result.reason = f"Ublox GPS HW version mismatch: {dut_sensor_values.gps_ublox_hw_ver} , expected {config.post_test_gps_ublox_hw_version}"
        return result

    # Protocol version
    if not dut_sensor_values.gps_ublox_proto_ver == config.post_test_gps_ublox_proto_version:
        result.reason = f"Ublox GPS Protocol version mismatch: {dut_sensor_values.gps_ublox_proto_ver} , expected {config.post_test_gps_ublox_proto_version}"
        return result

    # Constellations
    for constellation in dut_sensor_values.gps_ublox_supported_constellations:
        if constellation not in config.post_test_gps_ublox_constellations:
            result.reason = f"Ublox GPS Constellation mismatch: {dut_sensor_values.gps_ublox_supported_constellations} , expected {config.post_test_gps_ublox_constellations}"
            return result

    result.success = True
    return result
