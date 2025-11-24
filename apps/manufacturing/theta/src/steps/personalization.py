# Standard includes
import base64
import logging
import os
import re
import sys
import time
import traceback
from typing import Any, Callable, Optional, Tuple

import requests

# Application includes
from config.env import env_config

# Private includes
from corekinect.mtib_client.v1 import *

# Corekinect includes
from corekinect.utils import EnvConfig, Logger
from src.steps.post import run_post_test


def _clean_iccid(iccid: str) -> str:
    """Remove ANSI escape sequences and other trailing characters from ICCID."""
    # Remove ANSI escape sequences like [0m, [1m, etc.
    cleaned = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", iccid)
    # Remove any remaining non-printable characters
    cleaned = "".join(char for char in cleaned if char.isprintable())
    # Remove any trailing whitespace
    cleaned = cleaned.strip()
    return cleaned


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


def _init(client: MtibV1Client, logger: Logger) -> Optional[str]:
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

    # Check if within range
    # if avg_ma_draw < 8 or avg_ma_draw > 33:
    #     return f"Average power draw is not within expected range: {avg_ma_draw} mA, min {min_ma_draw} mA, max {max_ma_draw} mA"

    return None


def _flash_firmware(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Flash the manufacturing firmware
    """
    logger.info(f"Flashing modem firmware, this will take a while...")

    # Flash the modem firmware
    file_name = os.path.basename(env_config.MODEM_FW_FILE)
    file_info = FwFileInfo(name=file_name, target=HostType.HOST_TYPE_NRF9160_MODEM)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=True, recover=True)
    if err:
        return f"Failed to flash modem firmware: {err}"

    logger.info(f"Successfully flashed modem firmware in {time_ms}ms")
    logger.info(f"Flashing comms coproc firmware...")

    # Flash the comms coproc firmware
    # Extract just the file name from the path
    file_name = os.path.basename(env_config.COMMS_COPROC_FW_FILE)
    file_info = FwFileInfo(name=file_name, target=HostType.HOST_TYPE_NRF9160)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=True, recover=True)
    if err:
        return f"Failed to flash modem firmware: {err}"

    logger.info(f"Successfully flashed comms coproc firmware in {time_ms}ms")
    logger.info(f"Flashing app proc firmware...")

    # Flash the app proc firmware
    file_name = os.path.basename(env_config.APP_PROC_FW_FILE)
    file_info = FwFileInfo(name=file_name, target=HostType.HOST_TYPE_NRF52840)
    time_ms, err = client.FlashFwFile(file_info, sector_erase=True, recover=True)
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


def run_manufacturing(client: MtibV1Client, logger: Logger, serial_number: str) -> Optional[str]:
    start_time = time.time()
    logger.info(f"Personalizing device with serial number: {serial_number}")

    err = _init(client, logger)
    if err:
        return f"Error initializing application: {err}"

    err = _power_on(client, logger, 3)
    if err:
        return f"Error powering on device: {err}"

    # Use try-finally to ensure power off runs even if any step fails
    try:
        err = _flash_firmware(client, logger)
        if err:
            return f"Error flashing manufacturing firmware: {err}"

        device_id, err = _get_device_id(env_config.PROXY_SERVER_URL, serial_number, logger)
        if err:
            return f"Error getting device ID: {err}"

        err = run_post_test(client, logger, device_id, env_config.PROXY_SERVER_URL, serial_number)
        if err:
            return f"Error running post test: {err}"

        # If we reach here, all steps succeeded
        end_time = time.time()
        logger.info(f"Personalization took {end_time - start_time} seconds")
        return None

    finally:
        # Always power off the device, regardless of success or failure
        power_off_err = _power_off(client, logger)
        if power_off_err:
            logger.error(f"Error powering off device: {power_off_err}")
            # Don't return here as we want to preserve the original error if there was one
