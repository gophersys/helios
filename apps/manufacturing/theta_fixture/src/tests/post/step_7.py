# Standard includes
import time
from typing import Dict, List

# Corekinect libraries
from corekinect.mtib_client.v1.client.types import HostType
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData

# Theta uses nRF9151 for comms processor
THETA_COMMS_TARGET = HostType.HOST_TYPE_NRF9151


# ---------------------------------------------------------------------------------
#                                                                    IMEI Validation
# -------------------------------------------------------------------------------*/
IMEI_LENGTH = 15
ICCID_MIN_LENGTH = 19
ICCID_MAX_LENGTH = 20

VERIZON_PREFIX = "89148"
SORACOM_PREFIX = "894231"
ONOMONDO_PREFIX = "894573"
ATT_PREFIX = "890103"


def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum([int(x) for x in str(d * 2)])
    return checksum % 10 == 0


def _validate_imei(imei: str) -> str:
    if len(imei) != IMEI_LENGTH or not imei.isdigit():
        return f"IMEI ({imei}) invalid: expected {IMEI_LENGTH} digits, got {len(imei)}"
    if not _luhn_check(imei):
        return f"IMEI ({imei}) failed Luhn checksum"
    return ""


def _validate_iccid(iccid: str) -> str:
    cleaned = iccid.rstrip("F")
    if len(cleaned) not in [ICCID_MIN_LENGTH, ICCID_MAX_LENGTH]:
        return f"ICCID ({cleaned}) invalid length: {len(cleaned)}"
    if not _luhn_check(cleaned):
        return f"ICCID ({cleaned}) failed Luhn checksum"
    # Check carrier recognition
    if not (
        cleaned.startswith(VERIZON_PREFIX)
        or cleaned.startswith(SORACOM_PREFIX)
        or cleaned.startswith(ONOMONDO_PREFIX)
        or cleaned.startswith(ATT_PREFIX)
    ):
        return f"ICCID ({cleaned}) is not from a recognized carrier"
    return ""


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_7_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 7: Verify IMEI and ICCIDs.
    Modem takes time to retrieve IMEI/ICCID, so retry with delays.
    Validates format and Luhn checksums.
    """
    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    max_retries = 5
    retry_delay = 3
    imei = None
    iccids = None

    for attempt in range(max_retries):
        imei, iccids, error = client.cmd_comms_coproc_get_imei_iccid(target=THETA_COMMS_TARGET)
        if error:
            result.error = f"IMEI/ICCID query failed: {error}"
            return result

        if imei and iccids:
            break

        if attempt < max_retries - 1:
            logging.debug(f"IMEI/ICCID not ready, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(retry_delay)

    # Validate IMEI
    if not imei:
        result.reason = "No IMEI returned from device"
        return result

    imei_error = _validate_imei(imei)
    if imei_error:
        result.reason = f"IMEI validation failed: {imei_error}"
        return result

    # Validate ICCIDs
    if not iccids:
        result.reason = "No ICCIDs returned from device"
        return result

    for iccid in iccids:
        iccid_error = _validate_iccid(iccid)
        if iccid_error:
            result.reason = f"ICCID validation failed: {iccid_error}"
            return result

    # Store in shared data for personalization step
    if node in usr_data:
        usr_data[node].imei = imei
        usr_data[node].iccids = iccids

    logging.debug(f"POST Step 7 PASS: IMEI={imei}, ICCIDs={iccids}")

    result.success = True
    result.details = f"imei={imei}, iccids={','.join(iccids)}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_7_imei: TestStep = TestStep(
    info=StepInfo(
        name="Verify IMEI and ICCIDs",
        description="Reads IMEI and ICCIDs from modem, validates format, Luhn checksums, and carrier recognition.",
        noPassIsFatal=True,
    ),
    timeout_ms=45000,
    handler=post_step_7_handler,
)
