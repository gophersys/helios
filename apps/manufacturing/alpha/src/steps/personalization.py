# Standard includes
import logging
import os
import requests
import traceback
import sys
from typing import Callable, Optional, Any, Tuple

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Private includes
from corekinect.mtib_client.v1 import *

# Application includes
from config.env import AlphaEnvConfig

def _get_device_id(proxy_server_url: str, snr: str) -> Tuple[Optional[str], Optional[str]]:
    # Call concord proxy
    try:
        get_device_id_url = f"{proxy_server_url}/v1/devices/ids/assign"
        body = {"snr": snr}
        response: requests.Response = requests.post(url=get_device_id_url, json=body, verify=False)

        if response.status_code == 200:
            response_data = response.json()
            id = response_data.get("deviceId")
            return id, None
        else:
            return None, f"Call to concord proxy at {get_device_id_url} to get device id {snr} failed with status code ({response.status_code}), body: {response.content}"
    except Exception as e:
        return None, f"An exception occurred whilst trying to get device id from concord proxy: {str(e)}"

# def _upload_device_public_key(proxy_server_url: str, device_id: str, public_key: str) -> str:
#     # Call concord proxy
#     try:
#         # Create request body
#         body = {"deviceId": device_id, "pubKey": public_key}

#         # Do request
#         upload_public_key_url = f"{proxy_server_url}/v1/devices/keys/upload"
#         response: requests.Response = requests.post(url=upload_public_key_url, json=body, verify=False)

#         if response.status_code == 200:
#             return ""
#         else:
#             return f"Call to concord proxy at {upload_public_key_url} upload public key for {device_id} failed with status code ({response.status_code}), body: {response.content}"
#     except Exception as e:
#         return f"An exception occurred whilst trying to get device id from concord proxy: \n{traceback.format_exc()}"

# def _set_device_id(proxy_server_url: str, node: str, usr_data: None) -> TestStepResult:
#     result = TestStepResult(success=False)

#     #  Get the device ID from CoreCloud
#     result.error, device_id = _get_device_id(config, node)
#     if result.error:
#         return result

#     # Prepend "0x" to the device ID and convert it to an integer
#     try:
#         hex_device_id = "0x" + device_id
#         int_device_id = int(hex_device_id, 16)  # Convert hex string to integer
#     except ValueError as e:
#         result.error = f"Failed to convert device ID to integer: {e}"
#         return result

#     # Set the device id, to get back a public key
#     set_response: CMD_DEV_EC_PUB_KEY_Response
#     result.error, set_response = runnners_controller.dut_command_set_device_eui(node, int_device_id)
#     if result.error:
#         return result

#     # Verify that we succesfully set the device id
#     verify_response: CMD_PERSONALIZE_DEV_EUI_Response
#     error, verify_response = runnners_controller.dut_command_get_device_eui(node)

#     if error:
#         result.error = f"Could not read device ID from host {node}: {error=}"
#         return result

#     if int_device_id != verify_response.device_id:
#         result.error = f"Device ID set to {int_device_id} but read back {verify_response.device_id}."
#         return result

#     # Upload private key to CoreCloud
#     result.error = _upload_device_public_key(node, device_id, set_response.public_key)
#     if result.error:
#         return result

#     result.success = True
#     return result

def _init(client: MtibV1Client, logger: Logger, env_config: AlphaEnvConfig) -> Optional[str]:
    """
    Initialize the client
    """
    # Get the assets directory
    assets_dir = env_config.ASSETS_DIR

    # Ensure that the assets directory exists
    if not os.path.exists(assets_dir):
        return f"Assets directory {assets_dir} does not exist"

    # Ensure that the assets directory is a directory
    if not os.path.isdir(assets_dir):
        return f"Assets directory {assets_dir} is not a directory"

    # List files in the remote server
    files, err = client.ListFwFiles()
    if err:
        return f"Error listing firmware files: {err}"
    
    if files:
        for file in files:
            logger.info(f"Server has firmware file: {file}")
    else:
        logger.info("No firmware files found on server!")

    # Upload the modem firmware file
    if err := client.UploadFwFile(os.path.join(assets_dir, env_config.MODEM_FW_FILE), HostType.HOST_TYPE_NRF9160_MODEM):
        logger.fatal(f"Error uploading modem firmware file: {err}")

    # Upload the comms coproc firmware file
    if err := client.UploadFwFile(os.path.join(assets_dir, env_config.COMMS_COPROC_FW_FILE), HostType.HOST_TYPE_NRF9160):
        logger.fatal(f"Error uploading comms coproc firmware file: {err}")
    
    # Upload the app proc firmware file
    if err := client.UploadFwFile(os.path.join(assets_dir, env_config.APP_PROC_FW_FILE), HostType.HOST_TYPE_NRF52840):
        logger.fatal(f"Error uploading app proc firmware file: {err}")

def _power_on(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Power on the device
    """
    import time
    voltage_v = 4.0
    if err := client.DutPowerEnable(voltage_v):
        logger.fatal(f"Error enabling DUT power: {err}")

    logger.info("Waiting for device to power on...")
    time.sleep(2)

    # Sample power every 250ms for 2 seconds (8 samples)
    samples = []
    min_ma_draw = None
    max_ma_draw = None
    for _ in range(4):
        current_a, voltage_v, power_w, err = client.DutPowerRead()
        if err:
            logger.fatal(f"Error reading DUT power: {err}")
        ma_draw = current_a * 1000
        samples.append(ma_draw)
        if min_ma_draw is None or ma_draw < min_ma_draw:
            min_ma_draw = ma_draw
        if max_ma_draw is None or ma_draw > max_ma_draw:
            max_ma_draw = ma_draw
        time.sleep(0.25)

    avg_ma_draw = sum(samples) / len(samples)
    logger.info(f"Device powered on, power draw: min {min_ma_draw} mA, max {max_ma_draw} mA, avg {avg_ma_draw} mA")

    if avg_ma_draw < 10 or avg_ma_draw > 30:
        return f"Average power draw is not within expected range: {avg_ma_draw} mA, min {min_ma_draw} mA, max {max_ma_draw} mA"

    return None

def _flash_firmware(client: MtibV1Client, logger: Logger, env_config: AlphaEnvConfig) -> Optional[str]:
    """
    Flash the manufacturing firmware
    """
    logger.info(f"Flashing modem firmware, this will take a while...")
    
    # Flash the modem firmware
    file_info = FwFileInfo(name=env_config.MODEM_FW_FILE, target=HostType.HOST_TYPE_NRF9160_MODEM)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=False, recover=True)
    if err:
        return f"Failed to flash modem firmware: {err}"
    
    logger.info(f"Successfully flashed modem firmware in {time_ms}ms")
    logger.info(f"Flashing comms coproc firmware...")

    # Flash the comms coproc firmware
    file_info = FwFileInfo(name=env_config.COMMS_COPROC_FW_FILE, target=HostType.HOST_TYPE_NRF9160)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=False, recover=False)
    if err:
        return f"Failed to flash modem firmware: {err}"
    
    logger.info(f"Successfully flashed comms coproc firmware in {time_ms}ms")
    logger.info(f"Flashing app proc firmware...")

    # Flash the app proc firmware
    file_info = FwFileInfo(name=env_config.APP_PROC_FW_FILE, target=HostType.HOST_TYPE_NRF52840)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=False, recover=True)
    if err:
        return f"Failed to flash modem firmware: {err}"
    
    logger.info(f"Successfully flashed app proc firmware in {time_ms}ms")

    return None

def _personalize_device(client: MtibV1Client, logger: Logger, env_config: AlphaEnvConfig, serial_number: str) -> Optional[str]:
    """
    Personalize the device
    """
    logger.info(f"Personalizing device with serial number: {serial_number}")

    device_id, err = _get_device_id(env_config.PROXY_SERVER_URL, serial_number)
    if err:
        return f"Error getting device id: {err}"

    logger.info(f"Device ID: {device_id}")

    return None

def _power_off(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Power off the device
    """
    if err := client.DutPowerDisable():
        logger.fatal(f"Error disabling DUT power: {err}")

    return None

def personalization_step(client: MtibV1Client, logger: Logger, env_config: AlphaEnvConfig, serial_number: str) -> Optional[str]:
    logger.info(f"Personalizing device with serial number: {serial_number}")

    err = _init(client, logger, env_config)
    if err:
        return f"Error initializing application: {err}"
    
    err = _power_on(client, logger)
    if err:
        return f"Error powering on device: {err}"
    
    # err = _flash_firmware(client, logger, env_config)
    # if err:
    #     return f"Error flashing manufacturing firmware: {err}"
    
    err = _personalize_device(client, logger, env_config, serial_number)
    if err:
        return f"Error personalizing device: {err}"
    
    err = _power_off(client, logger)
    if err:
        return f"Error powering off device: {err}"

    return None
