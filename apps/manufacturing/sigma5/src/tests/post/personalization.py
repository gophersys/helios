import logging
import requests
import traceback
from typing import Tuple, Optional

from config import conf
from tests.lib import TestStepResult

from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import (
    CMD_ACK_Response,
    CMD_DEV_EC_PUB_KEY_Response,
    CMD_PERSONALIZE_DEV_EUI_Response,
    mtib_servers,
)


def clear_personalization(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    logging.info("Clearing personalization...")
    result = TestStepResult(success=False)

    response: CMD_ACK_Response
    error, response = mtib_servers.dut_command_clear_personalization(node)

    if error:
        result.error = f"Could not clear personalization on host {node}: {error=}"
        return result

    if not response.ack:
        result.error = f"Could not clear personalization on host {node}: {response}"
        return result

    logging.info("Personalization cleared.")
    result.success = True
    return result


def _get_device_id(config: Sigma5ManufacturingConfig, node: str) -> Tuple[str, Optional[str]]:
    # Get the device serial number
    snr: str = config.snrs.get(node)
    if not snr:
        return f"No serial number was found for node {node} in test configuration", None

    # Call concord proxy
    try:
        get_device_id_url = f"{conf.PROXY_SERVER_URL}/v1/devices/ids/assign"
        body = {"snr": snr}
        response: requests.Response = requests.post(url=get_device_id_url, json=body, verify=False)

        if response.status_code == 200:
            response_data = response.json()
            id = response_data.get("deviceId")
            return "", id
        else:
            return (
                f"Call to concord proxy at {get_device_id_url} to get device id {snr} for {node} failed with status code ({response.status_code}), body: {response.content}",
                None,
            )
    except Exception as e:
        return f"An exception occurred whilst trying to get device id from concord proxy: {str(e)}", None


def _upload_device_public_key(node: str, device_id: str, public_key: str) -> str:
    # Call concord proxy
    try:
        # Create request body
        body = {"deviceId": device_id, "pubKey": public_key}

        # Do request
        upload_public_key_url = f"{conf.PROXY_SERVER_URL}/v1/devices/keys/upload"
        response: requests.Response = requests.post(url=upload_public_key_url, json=body, verify=False)

        if response.status_code == 200:
            return ""
        else:
            return f"Call to concord proxy at {upload_public_key_url} upload public key for {device_id} for {node} failed with status code ({response.status_code}), body: {response.content}"
    except Exception as e:
        return f"An exception occurred whilst trying to get device id from concord proxy: \n{traceback.format_exc()}"


def set_device_id(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    #  Get the device ID from CoreCloud
    result.error, device_id = _get_device_id(config, node)
    if result.error:
        return result

    # Prepend "0x" to the device ID and convert it to an integer
    try:
        hex_device_id = "0x" + device_id
        int_device_id = int(hex_device_id, 16)  # Convert hex string to integer
    except ValueError as e:
        result.error = f"Failed to convert device ID to integer: {e}"
        return result

    # Set the device id, to get back a public key
    set_response: CMD_DEV_EC_PUB_KEY_Response
    result.error, set_response = mtib_servers.dut_command_set_device_eui(node, int_device_id)
    if result.error:
        return result

    # Verify that we succesfully set the device id
    verify_response: CMD_PERSONALIZE_DEV_EUI_Response
    error, verify_response = mtib_servers.dut_command_get_device_eui(node)

    if error:
        result.error = f"Could not read device ID from host {node}: {error=}"
        return result

    if int_device_id != verify_response.device_id:
        result.error = f"Device ID set to {int_device_id} but read back {verify_response.device_id}."
        return result

    # Upload private key to CoreCloud
    result.error = _upload_device_public_key(node, device_id, set_response.public_key)
    if result.error:
        return result

    result.success = True
    return result
