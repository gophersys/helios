# Standard includes
import logging
import os
import base64
import requests
import traceback
import sys
import time
from typing import Callable, Optional, Any, Tuple

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Private includes
from corekinect.mtib_client.v1 import *

# Application includes
from config.env import AlphaEnvConfig


def _get_device_id(proxy_server_url: str, snr: str, logger: Logger) -> Tuple[Optional[str], Optional[str]]:
    # Call concord proxy
    try:
        get_device_id_url = f"{proxy_server_url}/v1/devices/ids/assign"
        body = {"snr": snr}
        response: requests.Response = requests.post(url=get_device_id_url, json=body, verify=False)

        if response.status_code == 200:
            response_data = response.json()
            id = response_data.get("deviceId")

            logger.info(f"Device ID: {id}")

            return id, None
        else:
            return (
                None,
                f"Call to concord proxy at {get_device_id_url} to get device id {snr} failed with status code ({response.status_code}), body: {response.content}",
            )

    except Exception as e:
        return None, f"An exception occurred whilst trying to get device id from concord proxy: {str(e)}"


def _get_device_public_key(
    client: MtibV1Client, device_id: str, logger: Logger
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Use the MTIB client to programatically get the device public key
    try:
        # Get the device public key
        hex_key, base64_key, err = client.alpha_cmd_personalize(device_id, HostType.HOST_TYPE_NRF9160)
        if err:
            return None, None, f"Error getting device public key: {err}"

        # Do a quick check to see if the public key is valid
        if not hex_key or not base64_key:
            return None, None, f"Invalid public key: {hex_key} {base64_key}"

        # Verify that the base64 key is valid by decoding it and comparing to hex
        try:
            decoded_bytes = base64.b64decode(base64_key)
            decoded_hex = decoded_bytes.hex()
            if decoded_hex != hex_key:
                return (
                    None,
                    None,
                    f"Base64 key does not match hex key: decoded_hex={decoded_hex}, hex_key={hex_key}",
                )
        except Exception as e:
            return None, None, f"Failed to verify base64 key: {e}"

        logger.info(f"Device public key (base64): {base64_key}")

        return hex_key, base64_key, None
    except Exception as e:
        return None, None, f"An exception occurred whilst trying to get device public key from concord proxy: {str(e)}"


def _get_device_imei_iccids(
    client: MtibV1Client, device_id: str, logger: Logger
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Use the MTIB client to programatically get the device IMEI and ICCIDs
    try:
        # Get the device IMEI and ICCIDs
        imei, iccids, err = client.alpha_cmd_get_imei_iccids(device_id, HostType.HOST_TYPE_NRF9160)
        if err:
            return None, None, f"Error getting device IMEI and ICCIDs: {err}"

        logger.info(f"Device IMEI: {imei}")
        logger.info(f"Device ICCIDs: {iccids}")

        return imei, iccids, None
    except Exception as e:
        return None, None, f"An exception occurred whilst trying to get device IMEI and ICCIDs: {str(e)}"


def _save_device_info(
    proxy_server_url: str,
    device_id: str,
    pub_key: str,
    base64_key: str,
    imei: str,
    iccids: str,
    snr: str,
    logger: Logger,
) -> Optional[str]:
    try:
        # Save Device Public Key
        body = {"deviceId": device_id, "pubKey": base64_key}

        upload_public_key_url = f"{proxy_server_url}/v1/devices/keys/upload"
        response: requests.Response = requests.post(url=upload_public_key_url, json=body, verify=False)

        if response.status_code != 200:
            return f"Call to concord proxy at {upload_public_key_url} upload public key for {device_id} failed with status code ({response.status_code}), body: {response.content}"

        # Save Device IMEI and ICCIDs
        for iccid in iccids.split(","):
            carrier = "Verizon" if iccid.startswith("891480") else "Soracom"

            # Create the request body
            body = {"iccid": iccid, "carrier": carrier, "snr": snr, "imei": imei}

            # Do request
            save_iccids_url = f"{proxy_server_url}/v1/devices/iccids/save"
            response: requests.Response = requests.post(url=save_iccids_url, json=body, verify=False)

            if response.status_code != 200:
                return f"Call to concord proxy at {save_iccids_url} upload for iccid for {snr} failed with status code ({response.status_code}), body: {response.content}"

        return None

    except Exception as e:
        return f"An exception occurred whilst trying to save device info to proxy: \n{traceback.format_exc()}"


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
    if err := client.UploadFwFile(
        os.path.join(assets_dir, env_config.MODEM_FW_FILE), HostType.HOST_TYPE_NRF9160_MODEM
    ):
        logger.fatal(f"Error uploading modem firmware file: {err}")

    # Upload the comms coproc firmware file
    if err := client.UploadFwFile(
        os.path.join(assets_dir, env_config.COMMS_COPROC_FW_FILE), HostType.HOST_TYPE_NRF9160
    ):
        logger.fatal(f"Error uploading comms coproc firmware file: {err}")

    # Upload the app proc firmware file
    if err := client.UploadFwFile(os.path.join(assets_dir, env_config.APP_PROC_FW_FILE), HostType.HOST_TYPE_NRF52840):
        logger.fatal(f"Error uploading app proc firmware file: {err}")


def _power_on(client: MtibV1Client, logger: Logger, delay: int = 3) -> Optional[str]:
    """
    Power on the device
    """
    import time

    voltage_v = 4.0
    if err := client.DutPowerEnable(voltage_v):
        logger.fatal(f"Error enabling DUT power: {err}")

    logger.info("Waiting for device to power on...")
    time.sleep(delay)

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
    file_name = os.path.basename(env_config.MODEM_FW_FILE)
    file_info = FwFileInfo(name=file_name, target=HostType.HOST_TYPE_NRF9160_MODEM)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=False, recover=True)
    if err:
        return f"Failed to flash modem firmware: {err}"

    logger.info(f"Successfully flashed modem firmware in {time_ms}ms")
    logger.info(f"Flashing comms coproc firmware...")

    # Flash the comms coproc firmware
    # Extract just the file name from the path
    file_name = os.path.basename(env_config.COMMS_COPROC_FW_FILE)
    file_info = FwFileInfo(name=file_name, target=HostType.HOST_TYPE_NRF9160)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=False, recover=False)
    if err:
        return f"Failed to flash modem firmware: {err}"

    logger.info(f"Successfully flashed comms coproc firmware in {time_ms}ms")
    logger.info(f"Flashing app proc firmware...")

    # Flash the app proc firmware
    file_name = os.path.basename(env_config.APP_PROC_FW_FILE)
    file_info = FwFileInfo(name=file_name, target=HostType.HOST_TYPE_NRF52840)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=False, recover=True)
    if err:
        return f"Failed to flash modem firmware: {err}"

    logger.info(f"Successfully flashed app proc firmware in {time_ms}ms")

    return None


def _power_off(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Power off the device
    """
    if err := client.DutPowerDisable():
        logger.fatal(f"Error disabling DUT power: {err}")

    return None


def _reset(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Reset the device
    """
    err = _power_off(client, logger)
    if err:
        return f"Error powering off device: {err}"

    err = _power_on(client, logger, delay=3)
    if err:
        return f"Error powering on device: {err}"


def personalization_step(
    client: MtibV1Client, logger: Logger, env_config: AlphaEnvConfig, serial_number: str
) -> Optional[str]:
    start_time = time.time()
    logger.info(f"Personalizing device with serial number: {serial_number}")

    err = _init(client, logger, env_config)
    if err:
        return f"Error initializing application: {err}"

    err = _power_on(client, logger, 3)
    if err:
        return f"Error powering on device: {err}"

    err = _flash_firmware(client, logger, env_config)
    if err:
        return f"Error flashing manufacturing firmware: {err}"

    err = _reset(client, logger)
    if err:
        return f"Error resetting device: {err}"

    device_id, err = _get_device_id(env_config.PROXY_SERVER_URL, serial_number, logger)
    if err:
        return f"Error personalizing device: {err}"

    pub_key, base64_key, err = _get_device_public_key(client, device_id, logger)
    if err:
        return f"Error getting device public key: {err}"

    imei, iccids, err = _get_device_imei_iccids(client, device_id, logger)
    if err:
        return f"Error getting device IMEI and ICCIDs: {err}"

    err = _save_device_info(
        env_config.PROXY_SERVER_URL, device_id, pub_key, base64_key, imei, iccids, serial_number, logger
    )
    if err:
        return f"Error saving device info: {err}"

    err = _power_off(client, logger)
    if err:
        return f"Error powering off device: {err}"

    end_time = time.time()
    logger.info(f"Personalization took {end_time - start_time} seconds")

    return None
