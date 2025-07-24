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

# def _get_device_id(proxy_server_url: str, snr: str) -> Tuple[str, Optional[str]]:
#     # Call concord proxy
#     try:
#         get_device_id_url = f"{proxy_server_url}/v1/devices/ids/assign"
#         body = {"snr": snr}
#         response: requests.Response = requests.post(url=get_device_id_url, json=body, verify=False)

#         if response.status_code == 200:
#             response_data = response.json()
#             id = response_data.get("deviceId")
#             return "", id
#         else:
#             return (
#                 f"Call to concord proxy at {get_device_id_url} to get device id {snr} for {node} failed with status code ({response.status_code}), body: {response.content}",
#                 None,
#             )
#     except Exception as e:
#         return f"An exception occurred whilst trying to get device id from concord proxy: {str(e)}", None

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

    # List the files in the assets directory
    files = os.listdir(assets_dir)
    logger.info(f"Assets directory {assets_dir} contains the following files: {files}")

def personalization_step(client: MtibV1Client, logger: Logger, env_config: AlphaEnvConfig) -> Optional[str]:
    """
    Personalization step
    """
    err = _init(client, logger, env_config)
    if err:
        return f"Error initializing application: {err}"

    return None

