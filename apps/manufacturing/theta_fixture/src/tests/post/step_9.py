# Standard includes
import logging
from typing import Dict

import requests

# Corekinect libraries
from corekinect.mtib_client.v1.client.types import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# App includes
from config import conf

# Test includes
from .data import PostTestSharedData

# Theta uses nRF9151 for comms processor
THETA_COMMS_TARGET = HostType.HOST_TYPE_NRF9151


# ---------------------------------------------------------------------------------
#                                                                          Helpers
# -------------------------------------------------------------------------------*/
def _get_device_id(proxy_server_url: str, snr: str) -> (str, str):
    """Get a device ID from CoreOps proxy server."""
    try:
        get_device_id_url = f"{proxy_server_url}/v1/devices/ids/assign"
        body = {"snr": snr}
        response = requests.post(url=get_device_id_url, json=body, verify=False)

        if response.status_code == 200:
            response_data = response.json()
            device_id = response_data.get("deviceId")
            return device_id, None
        else:
            return None, (
                f"Failed to get device ID for SNR {snr}: " f"status={response.status_code}, body={response.content}"
            )
    except Exception as e:
        return None, f"Exception getting device ID: {str(e)}"


def _save_device_info(
    proxy_server_url: str, device_id: str, hex_key: str, base64_key: str, imei: str, iccids: list, snr: str
) -> str:
    """Save device information to CoreOps proxy server."""
    try:
        # Save Device Public Key
        body = {"deviceId": device_id, "pubKey": base64_key}
        upload_url = f"{proxy_server_url}/v1/devices/keys/upload"
        response = requests.post(url=upload_url, json=body, verify=False)

        if response.status_code != 200:
            return f"Failed to upload public key: status={response.status_code}"

        # Save Device IMEI and ICCIDs
        for iccid in iccids:
            carrier = ""
            if iccid.startswith("891480"):
                carrier = "Verizon"
            elif iccid.startswith("8942310"):
                carrier = "Soracom"
            elif iccid.startswith("894573"):
                carrier = "Onomondo"
            elif iccid.startswith("890103"):
                carrier = "Att"
            else:
                return f"Unrecognized carrier for ICCID {iccid}"

            body = {"iccid": iccid, "carrier": carrier, "snr": snr, "imei": imei}
            save_url = f"{proxy_server_url}/v1/devices/iccids/save"
            response = requests.post(url=save_url, json=body, verify=False)

            if response.status_code != 200:
                return f"Failed to save ICCID {iccid}: status={response.status_code}"

        return None
    except Exception as e:
        return f"Exception saving device info: {str(e)}"


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_9_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 9: Personalize device.
    Get device ID from CoreOps, personalize via UART, save keys/IMEI/ICCIDs.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Get the serial number for this node from config
    snr = config.snrs.get(node)
    if not snr:
        result.error = f"No serial number configured for node {node}"
        return result

    # Get IMEI and ICCIDs from shared data (stored by step 7)
    node_data = usr_data.get(node)
    if not node_data:
        result.error = "No shared data available - prior steps must have passed"
        return result

    imei = node_data.imei
    iccids = node_data.iccids

    if not imei or not iccids:
        result.error = "IMEI/ICCIDs not available from step 7"
        return result

    # Get device ID from CoreOps
    proxy_url = conf.PROXY_SERVER_URL
    device_id, error = _get_device_id(proxy_url, snr)
    if error:
        result.error = f"Failed to get device ID: {error}"
        return result

    if not device_id:
        result.error = "CoreOps returned empty device ID"
        return result

    logging.debug(f"Got device ID: {device_id} for SNR: {snr}")

    # Personalize the device via UART
    hex_key, base64_key, error = client.cmd_comms_coproc_personalize(device_id, target=THETA_COMMS_TARGET)
    if error:
        result.error = f"Personalization failed: {error}"
        return result

    if not hex_key or not base64_key:
        result.reason = "Personalization returned empty keys"
        return result

    logging.debug(f"Device personalized, public key: {base64_key[:20]}...")

    # Save device information to CoreOps
    error = _save_device_info(proxy_url, device_id, hex_key, base64_key, imei, iccids, snr)
    if error:
        result.error = f"Failed to save device info: {error}"
        return result

    logging.debug(f"Personalize PASS: Device {device_id} personalized and saved to CoreOps")

    result.success = True
    result.details = f"device_id={device_id}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_9_personalize: TestStep = TestStep(
    info=StepInfo(
        name="Personalize device with CoreOps data",
        description="Gets device ID from CoreOps, personalizes device via UART, and saves keys/IMEI/ICCIDs.",
        noPassIsFatal=True,
    ),
    timeout_ms=30000,
    handler=post_step_9_handler,
)
