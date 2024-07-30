# Standard includes
import json
import logging
import requests
from dataclasses import asdict, dataclass
from typing import Dict, List

# Corekinect libraries
from tests.lib import TestStepResult

# App includes
from config import conf

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import CMD_IMEI_ICCID_Response, runnners_controller

# ---------------------------------------------------------------------------------
#                                                                           Details
# -------------------------------------------------------------------------------*/


@dataclass
class ICCIDInfo:
    iccid: str = None
    major_industry_identifier: str = None
    country_code: str = None
    issuer_identification_number: str = None
    individual_account_identification: str = None
    check_digit: str = None
    is_verizon: bool = False
    is_soracom: bool = False

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return ICCIDInfo(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


@dataclass
class DeviceReadings:
    imei: str = None
    iccids: List[ICCIDInfo] = None

    def marshall(self) -> str:
        try:
            # Convert each ICCIDInfo object in iccids to a dictionary
            data = asdict(self)
            data["iccids"] = [asdict(iccid) for iccid in self.iccids]
            return json.dumps(data)
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)

            # Convert each dictionary of iccids back to an ICCIDInfo object
            iccids_data = data.get("iccids", [])
            data["iccids"] = [ICCIDInfo(**iccid) for iccid in iccids_data]

            return DeviceReadings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Helpers
# -------------------------------------------------------------------------------*/
def _luhn_check(imei) -> str:
    def digits_of(n):
        return [int(d) for d in str(n)]

    digits = digits_of(imei)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))

    if checksum % 10 == 0:
        return ""
    else:
        return f"IMEI checksum failed: {checksum=}"


def _validate_imei(imei: str) -> str:
    if len(imei) != 15 or not imei.isdigit():
        return f"IMEI ({imei}) length is invalid, expected 15 digits, got {len(imei)}"
    return _luhn_check(imei)


def _validate_iccid(iccid: str) -> str:
    if len(iccid) not in [19, 20]:
        return f"ICCID ({iccid}) length is invalid, expected 19 or 20 digits, got {len(iccid)}"
    return _luhn_check(iccid)


def _save_iccids(iccids: List[ICCIDInfo], imei: str, snr: str) -> str:
    # Call concord proxy
    try:
        # Create the request body
        body = {"iccid": iccids[0].iccid, "carrier": "Verizon", "snr": snr, "imei": imei}

        # Do request
        save_iccids_url = f"{conf.PROXY_SERVER_URL}/v1/devices/iccids/save"
        response: requests.Response = requests.post(url=save_iccids_url, json=body, verify=False)

        if response.status_code == 200:
            return ""
        else:
            return f"Call to concord proxy at {save_iccids_url} upload for iccid for {snr} failed with status code ({response.status_code}), body: {response.content}"
    except Exception as e:
        return f"An exception occurred whilst trying to save iccid to concord proxy: {str(e)}"


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def verify_imei_iccid(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    readings: DeviceReadings = DeviceReadings()
    response: CMD_IMEI_ICCID_Response

    # Get the IMEI and ICCID values from the DUT
    result.error, response = runnners_controller.dut_command_get_imei_iccid(node)
    if result.error:
        return result

    # IMEI must be present
    if not response.imei:
        result.reason = f"IMEI is empty; {response.imei=}"
        return result

    # ICCIDs must be present
    if not response.iccids:
        result.reason = f"No ICCIDs found; {response.iccids=}"
        return result

    # Validate the number of ICCIDs
    if len(response.iccids) != config.post_test_expected_number_of_sims:
        result.reason = f"Expected {config.post_test_expected_number_of_sims} ICCIDs, got {len(response.iccids)}"
        return

    # Validate the IMEI
    if error := _validate_imei(response.imei):
        result.reason = f"IMEI is invalid: {error=}"
        return result

    # Setup test step details
    readings.imei = response.imei
    readings.iccids = []

    # Validate each ICCID
    for iccid in response.iccids:
        # Strip any trailing 'F's.
        # Since ICCIDs can have variable lengths, this is an artifact of a 20
        # digit buffer filled with F's when a 19 digit buffer was needed
        iccid = iccid.rstrip("F")

        if error := _validate_iccid(iccid):
            result.reason = f"ICCID is invalid: {error=}"
            return result

        iccid_info = ICCIDInfo(iccid=iccid)

        if iccid.startswith("891480"):  # Determine if Verizon:
            iccid_info.is_verizon = True
            iccid_info.major_industry_identifier = 89
            iccid_info.country_code = 1
            iccid_info.issuer_identification_number = 480
            iccid_info.individual_account_identification = iccid[6:-1]
            iccid_info.check_digit = iccid[-1]
        elif iccid.startswith("8942310"):  # Determine if Soracom:
            iccid_info.is_soracom = True
            iccid_info.major_industry_identifier = 89
            iccid_info.country_code = 423
            iccid_info.issuer_identification_number = 10
            iccid_info.individual_account_identification = iccid[7:-1]
            iccid_info.check_digit = iccid[-1]
        else:  # ICCID is not recognized
            result.reason = f"ICCID ({iccid}) is not recognized"
            return result

        readings.iccids.append(iccid_info)

    # The first SIM present should be the Verizon SIM
    if not readings.iccids[0].is_verizon:
        result.reason = f"First ICCID is not a Verizon SIM: {readings.iccids[0]=}"
        return

    # Add test step details to the result
    result.details = readings.marshall()

    # TODO: Upload iccid to manufacturing server?
    # snr = config.snrs[node]
    # result.error = _save_iccids(readings.iccids, readings.imei, snr)
    # if result.error:
    #     return result

    # Pass
    result.success = True
    return result
