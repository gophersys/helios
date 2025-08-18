# Standard includes
import time

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client
from test.helper import run_sample

# Import types directly from the protocol
from protocols.mtib.mtib_pb2 import HostType


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Test the command interpreter functionality.
    """
    logger.info("Testing Command Interpreter")
    
    # Test target
    target = HostType.HOST_TYPE_NRF9160
    logger.info(f"Testing commands for target: {target}")
    
    # Test 1: Send NOP command
    logger.info("Test 1: Sending NOP command...")
    error, response = client.dut_command_send_nop(target)
    if error:
        logger.error(f"NOP command failed: {error}")
    else:
        logger.info(f"NOP command successful: {response}")
    
    # Test 2: Get sensor values
    logger.info("Test 2: Getting sensor values...")
    error, response = client.dut_command_get_sensor_value(target)
    if error:
        logger.error(f"Get sensor values failed: {error}")
    else:
        logger.info(f"Get sensor values successful:")
        logger.info(f"  Accelerometer X: {response.accelerometer_x_g} g")
        logger.info(f"  Accelerometer Y: {response.accelerometer_y_g} g")
        logger.info(f"  Accelerometer Z: {response.accelerometer_z_g} g")
        logger.info(f"  Altimeter Pressure: {response.altimeter_pressure_in_hg} inHg")
        logger.info(f"  Altimeter Temperature: {response.altimeter_temperature_c} °C")
        logger.info(f"  Voltage: {response.voltage_measurement} V")
    
    # Test 3: Get chip ID
    logger.info("Test 3: Getting chip ID...")
    error, response = client.dut_command_get_chip_id(target)
    if error:
        logger.error(f"Get chip ID failed: {error}")
    else:
        logger.info(f"Get chip ID successful:")
        logger.info(f"  Accelerometer IC ID: {response.accel_ic_id}")
        logger.info(f"  Altimeter IC ID: {response.alt_ic_id}")
        logger.info(f"  External Flash IC ID: {response.external_flash_ic_id}")
        logger.info(f"  External Flash Test Pass: {response.external_flash_test_pass}")
        logger.info(f"  LoRa Connected: {response.is_lora_connected}")
        logger.info(f"  GPS u-blox SW Version: {response.gps_ublox_sw_ver}")
        logger.info(f"  GPS u-blox HW Version: {response.gps_ublox_hw_ver}")
        logger.info(f"  GPS u-blox FW Version: {response.gps_ublox_fw_ver}")
        logger.info(f"  GPS u-blox Protocol Version: {response.gps_ublox_proto_ver}")
        logger.info(f"  GPS Supported Constellations: {response.gps_ublox_supported_constellations}")
    
    # Test 4: Get IMEI/ICCID
    logger.info("Test 4: Getting IMEI/ICCID...")
    error, response = client.dut_command_get_imei_iccid(target)
    if error:
        logger.error(f"Get IMEI/ICCID failed: {error}")
    else:
        logger.info(f"Get IMEI/ICCID successful:")
        logger.info(f"  IMEI: {response.imei}")
        logger.info(f"  ICCIDs: {response.iccids}")
    
    # Test 5: Get modem firmware version
    logger.info("Test 5: Getting modem firmware version...")
    error, response = client.dut_command_get_modem_fw(target)
    if error:
        logger.error(f"Get modem firmware failed: {error}")
    else:
        logger.info(f"Get modem firmware successful: {response.fw_version}")
    
    # Test 6: Get device EUI
    logger.info("Test 6: Getting device EUI...")
    error, response = client.dut_command_get_device_eui(target)
    if error:
        logger.error(f"Get device EUI failed: {error}")
    else:
        logger.info(f"Get device EUI successful:")
        logger.info(f"  Flags: {response.flags}")
        logger.info(f"  Read: {response.read}")
        logger.info(f"  Device ID: {response.device_id}")
    
    logger.info("Command interpreter test completed!")


if __name__ == "__main__":
    run_sample(sample, "uart_commands") 