# Standard includes
import json
import logging
from dataclasses import asdict, dataclass
from typing import List

# Corekinect libraries
from src.tests.lib import *

# Post test includes
from src.tests.post.data import PostTestSharedData

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                           Constants
# -------------------------------------------------
# IMEI validation constants
IMEI_LENGTH = 15

# ICCID validation constants
ICCID_MIN_LENGTH = 19
ICCID_MAX_LENGTH = 20

# Carrier identification constants
VERIZON_PREFIX = "89148"
SORACOM_PREFIX = "894231"
ONOMONDO_PREFIX = "894573"

# Verizon ICCID structure
VERIZON_MII = "89"
VERIZON_COUNTRY_CODE = "1"
VERIZON_IIN = "480"

# Soracom ICCID structure
SORACOM_MII = "89"
SORACOM_COUNTRY_CODE = "423"
SORACOM_IIN = "10"

# Onomondo ICCID structure
ONOMONDO_MII = "89"
ONOMONDO_COUNTRY_CODE = "45"
ONOMONDO_IIN = "74"


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
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
    is_onomondo: bool = False


@dataclass
class DeviceInfo:
    imei: str = None
    iccids: List[ICCIDInfo] = None

    def marshall(self) -> str:
        try:
            # Convert each ICCIDInfo object in iccids to a dictionary
            data = asdict(self)
            if self.iccids:
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
            if iccids_data:
                data["iccids"] = [ICCIDInfo(**iccid) for iccid in iccids_data]
            return DeviceInfo(**data)
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
    if len(imei) != IMEI_LENGTH or not imei.isdigit():
        return f"IMEI ({imei}) length is invalid, expected {IMEI_LENGTH} digits, got {len(imei)}"
    return _luhn_check(imei)


def _validate_iccid(iccid: str) -> str:
    if len(iccid) not in [ICCID_MIN_LENGTH, ICCID_MAX_LENGTH]:
        return f"ICCID ({iccid}) length is invalid, expected {ICCID_MIN_LENGTH} or {ICCID_MAX_LENGTH} digits, got {len(iccid)}"
    return _luhn_check(iccid)


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_imei_iccids(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result: TestStepResult = TestStepResult(success=False)

    device_info: DeviceInfo = DeviceInfo(iccids=[])

    # Get the IMEI and ICCID values from the DUT
    imei, iccids, error = mtib_servers.sigma5_cmd_comms_get_imei_iccid(node)
    if error:
        result.error = error
        result.details = device_info.marshall()
        return result

    # IMEI must be present
    if not imei:
        result.reason = f"IMEI is empty; {imei=}"
        result.details = device_info.marshall()
        return result

    # ICCIDs must be present
    if not iccids:
        result.reason = f"No ICCIDs found; {iccids=}"
        result.details = device_info.marshall()
        return result

    # Validate the number of ICCIDs
    if len(iccids) != config.post_test_expected_number_of_sims:
        result.reason = f"Expected {config.post_test_expected_number_of_sims} ICCIDs, got {len(iccids)}"
        result.details = device_info.marshall()
        return result

    # Validate the IMEI
    if error := _validate_imei(imei):
        result.reason = f"IMEI is invalid: {error=}"
        result.details = device_info.marshall()
        return result

    # Setup test step details
    device_info.imei = imei

    # Validate each ICCID
    for iccid in iccids:
        # Strip any trailing 'F's.
        # Since ICCIDs can have variable lengths, this is an artifact of a 20
        # digit buffer filled with F's when a 19 digit buffer was needed
        iccid = iccid.rstrip("F")

        if error := _validate_iccid(iccid):
            result.reason = f"ICCID is invalid: {error=}"
            result.details = device_info.marshall()
            return result

        iccid_info = ICCIDInfo(iccid=iccid)

        if iccid.startswith(VERIZON_PREFIX):  # Determine if Verizon:
            iccid_info.is_verizon = True
            iccid_info.major_industry_identifier = VERIZON_MII
            iccid_info.country_code = VERIZON_COUNTRY_CODE
            iccid_info.issuer_identification_number = VERIZON_IIN
            iccid_info.individual_account_identification = iccid[6:-1]
            iccid_info.check_digit = iccid[-1]
        elif iccid.startswith(SORACOM_PREFIX):  # Determine if Soracom:
            iccid_info.is_soracom = True
            iccid_info.major_industry_identifier = SORACOM_MII
            iccid_info.country_code = SORACOM_COUNTRY_CODE
            iccid_info.issuer_identification_number = SORACOM_IIN
            iccid_info.individual_account_identification = iccid[7:-1]
            iccid_info.check_digit = iccid[-1]
        elif iccid.startswith(ONOMONDO_PREFIX):  # Determine if Onomondo:
            iccid_info.is_onomondo = True
            iccid_info.major_industry_identifier = ONOMONDO_MII
            iccid_info.country_code = ONOMONDO_COUNTRY_CODE
            iccid_info.issuer_identification_number = ONOMONDO_IIN
            iccid_info.individual_account_identification = iccid[7:-1]
            iccid_info.check_digit = iccid[-1]
        else:  # ICCID is not recognized
            result.reason = f"ICCID ({iccid}) is not recognized"
            result.details = device_info.marshall()
            return result

        device_info.iccids.append(iccid_info)

    # The first SIM present should be the Verizon SIM
    if device_info.iccids and not device_info.iccids[0].is_verizon:
        result.reason = f"First ICCID is not a Verizon SIM: {device_info.iccids[0]=}"
        result.details = device_info.marshall()
        return result

    # Add test step details to the result
    result.details = device_info.marshall()

    logging.debug(f"IMEI: {device_info.imei}")
    logging.debug(f"ICCIDs: {[iccid.iccid for iccid in device_info.iccids]}")

    # Save user data
    usr_data[node].imei = device_info.imei
    usr_data[node].iccids = [iccid.iccid for iccid in device_info.iccids]

    # Pass
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_3_verify_imei_iccids: TestStep = TestStep(
    info=StepInfo(
        name="Verify IMEI ICCIDs",
        description="Verify the IMEI and ICCIDs are present and are corre3ct.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_imei_iccids,
)
