# Standard includes
import json
from dataclasses import asdict, dataclass
import requests
import traceback
from typing import List

# Corekinect libraries
from src.tests.lib import *

# Post test includes
from src.tests.post.data import PostTestSharedData

# Shared includes
from config import conf
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class DeviceInfo:
    snr: str = None
    device_id: str = None
    pub_key: str = None
    base64_pub_key: str = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return DeviceInfo(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Helpers
# -------------------------------------------------
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
            return (
                None,
                f"Call to concord proxy at {get_device_id_url} to get device id {snr} failed with status code ({response.status_code}), body: {response.content}",
            )

    except Exception as e:
        return None, f"An exception occurred whilst trying to get device id from concord proxy: {str(e)}"


def _save_device_info(
    proxy_server_url: str,
    device_id: str,
    pub_key: str,
    base64_key: str,
    imei: str,
    iccids: List[str],
    snr: str,
) -> Optional[str]:
    try:
        # Save Device Public Key
        body = {"deviceId": device_id, "pubKey": base64_key}

        upload_public_key_url = f"{proxy_server_url}/v1/devices/keys/upload"
        response: requests.Response = requests.post(url=upload_public_key_url, json=body, verify=False)

        if response.status_code != 200:
            return f"Call to concord proxy at {upload_public_key_url} upload public key for {device_id} failed with status code ({response.status_code}), body: {response.content}"

        # Save Device IMEI and ICCIDs
        for iccid in iccids:
            carrier = ""
            if iccid.startswith("891480"):
                carrier = "Verizon"
            elif iccid.startswith("8942310"):
                carrier = "Soracom"
            elif iccid.startswith("894573"):
                carrier = "Onomondo"
            else:
                return f"Invalid ICCID found {iccid}"

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


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def personalize(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    info: DeviceInfo = DeviceInfo()

    # Get device ID from CoreOps
    device_id, error = _get_device_id(conf.PROXY_SERVER_URL, config.snrs[node])
    if error:
        result.success = False
        result.error = error
        result.details = info.marshall()
        return result

    # Get device public key from the DUT
    pub_key, base64_pub_key, error = mtib_servers.sigma5_cmd_comms_personalize(node, device_id)
    if error:
        result.success = False
        result.error = error
        result.details = info.marshall()
        return result

    # Save device info
    error = _save_device_info(
        conf.PROXY_SERVER_URL,
        device_id,
        pub_key,
        base64_pub_key,
        usr_data[node].imei,
        usr_data[node].iccids,
        config.snrs[node],
    )
    if error:
        result.success = False
        result.error = error
        result.details = info.marshall()
        return result

    # Setup test step details
    info.snr = config.snrs[node]
    info.device_id = device_id
    info.public_key = pub_key
    info.base64_key = base64_pub_key

    result.details = info.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_5_personalize: TestStep = TestStep(
    info=StepInfo(
        name="Personalize",
        description="Personalize DUT with device ID from CoreOps.",
        noPassIsFatal=True,
    ),
    timeout_ms=10000,
    handler=personalize,
)
