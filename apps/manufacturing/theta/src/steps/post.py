import base64
import random
import traceback
import time
from typing import List, Optional, Tuple

import requests
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.utils import Logger

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

# External flash test constants
DEFAULT_TEST_PATTERN = "ALPHA_POST_TEST_PATTERN_2024"
DEFAULT_START_ADDR = "0x000000"
DEFAULT_END_ADDR = "0x100000"
DEFAULT_MIDDLE_START = "0x040000"
DEFAULT_MIDDLE_END = "0x080000"


# -------------------------------------------------
#                                           Helpers
# -------------------------------------------------
def _luhn_check(imei: str) -> str:
    """Validate IMEI using Luhn algorithm"""

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
        return f"IMEI checksum failed: checksum={checksum}"


def _validate_imei(imei: str) -> str:
    """Validate IMEI format and checksum"""
    if len(imei) != IMEI_LENGTH or not imei.isdigit():
        return f"IMEI ({imei}) length is invalid, expected {IMEI_LENGTH} digits, got {len(imei)}"
    return _luhn_check(imei)


def _validate_iccid(iccid: str) -> str:
    """Validate ICCID format and checksum"""
    if len(iccid) not in [ICCID_MIN_LENGTH, ICCID_MAX_LENGTH]:
        return f"ICCID ({iccid}) length is invalid, expected {ICCID_MIN_LENGTH} or {ICCID_MAX_LENGTH} digits, got {len(iccid)}"
    return _luhn_check(iccid)


def _run_flash_test_operations(
    client: MtibV1Client,
    logger: Logger,
    test_data_b64: str,
    random_middle_address: str,
    start_addr: str,
    end_addr: str,
    test_string: str,
) -> Optional[str]:
    """Run the actual flash test operations without erase operations."""

    # Step 1: Write known pattern to start of external flash
    logger.debug("Writing test pattern to start of external flash...")
    success, err = client.cmd_comms_coproc_write_ext_flash("comms", start_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to start of flash: {err}"

    # Step 2: Write known pattern to end of external flash
    logger.debug("Writing test pattern to end of external flash...")
    success, err = client.cmd_comms_coproc_write_ext_flash("comms", end_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to end of flash: {err}"

    # Step 3: Write known pattern to random middle address
    logger.debug(f"Writing test pattern to middle address {random_middle_address}...")
    success, err = client.cmd_comms_coproc_write_ext_flash("comms", random_middle_address, test_data_b64)
    if not success or err:
        return f"Failed to write to middle of flash: {err}"

    # Step 4: Verify pattern at start
    logger.debug("Reading and verifying pattern at start...")
    read_data, err = client.cmd_comms_coproc_read_ext_flash(start_addr, len(test_string))
    if not read_data or err:
        return f"Failed to read from start of flash: {err}"

    # Convert hex data back to string for comparison
    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at start. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from start: {e}"

    # Step 5: Verify pattern at end
    logger.debug("Reading and verifying pattern at end...")
    read_data, err = client.cmd_comms_coproc_read_ext_flash(end_addr, len(test_string))
    if not read_data or err:
        return f"Failed to read from end of flash: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at end. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from end: {e}"

    # Step 6: Verify pattern at middle
    logger.debug(f"Reading and verifying pattern at middle address {random_middle_address}...")
    read_data, err = client.cmd_comms_coproc_read_ext_flash(random_middle_address, len(test_string))
    if not read_data or err:
        return f"Failed to read from middle of flash: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at middle. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from middle: {e}"

    return None


# -------------------------------------------------
#                                      Verification Functions
# -------------------------------------------------
def _verify_chip_ids(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the chip IDs (external flash chip ID)
    """
    logger.info("Verifying chip IDs...")

    ext_flash_id, err = client.cmd_comms_coproc_get_chip_ids()
    if err:
        return f"Error getting chip IDs: {err}"

    logger.info(f"External flash chip ID: {ext_flash_id}")

    # Basic validation - ensure we got valid responses
    if not ext_flash_id:
        return "External flash chip ID is empty"

    # Validate the external flash chip ID
    if ext_flash_id != "0xef 0x40 0x17":
        return "External flash chip ID is invalid"

    logger.info("Chip ID verification completed successfully")
    return None


def _verify_modem_firmware_version(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the modem firmware version
    """
    logger.info("Verifying modem firmware version...")

    fw_version, err = client.cmd_comms_coproc_get_modem_fw_version()
    if err:
        return f"Error getting modem firmware version: {err}"

    logger.info(f"Modem firmware version: {fw_version}")

    # Basic validation - ensure we got a valid response
    if not fw_version:
        return "Modem firmware version is empty"

    logger.info("Modem firmware version verification completed successfully")
    return None


def _verify_imei_iccids(imei: str, iccid_list: List[str], logger: Logger) -> Optional[str]:
    """
    Verify the IMEI and ICCIDs
    """
    logger.info("Verifying IMEI and ICCIDs...")

    logger.info(f"IMEI: {imei}")
    logger.info(f"ICCIDs: {iccid_list}")

    # IMEI must be present
    if not imei:
        return "IMEI is empty"

    # ICCIDs must be present
    if not iccid_list:
        return "No ICCIDs found"

    # Validate the IMEI
    if err := _validate_imei(imei):
        return f"IMEI is invalid: {err}"

    # Validate each ICCID
    for iccid in iccid_list:
        # Strip any trailing 'F's (artifact of variable length buffers)
        iccid = iccid.rstrip("F")

        if err := _validate_iccid(iccid):
            return f"ICCID is invalid: {err}"

        # Check if ICCID is from a recognized carrier
        if not (
            iccid.startswith(VERIZON_PREFIX) or iccid.startswith(SORACOM_PREFIX) or iccid.startswith(ONOMONDO_PREFIX)
        ):
            return f"ICCID ({iccid}) is not from a recognized carrier"

    logger.info("IMEI and ICCID verification completed successfully")
    return None


def _verify_external_flash(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify external flash functionality
    """
    logger.info("Verifying external flash functionality...")

    # Convert test string to base64 for writing
    test_data_b64 = base64.b64encode(DEFAULT_TEST_PATTERN.encode("utf-8")).decode("utf-8")

    # Generate random address in middle third
    middle_start_int = int(DEFAULT_MIDDLE_START, 16)
    middle_end_int = int(DEFAULT_MIDDLE_END, 16)
    random_middle_address = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

    logger.debug(f"Testing external flash with pattern: {DEFAULT_TEST_PATTERN}")
    logger.debug(
        f"Test addresses - Start: {DEFAULT_START_ADDR}, End: {DEFAULT_END_ADDR}, Middle: {random_middle_address}"
    )

    # Try the test first without erasing
    logger.debug("Attempting external flash test without initial erase...")
    err = _run_flash_test_operations(
        client,
        logger,
        test_data_b64,
        random_middle_address,
        DEFAULT_START_ADDR,
        DEFAULT_END_ADDR,
        DEFAULT_TEST_PATTERN,
    )

    if not err:
        logger.debug("First test attempt succeeded!")
    else:
        logger.debug(f"First test attempt failed: {err}. Erasing flash and retrying...")

        # Erase external flash and retry
        erase_success, erase_err = client.cmd_comms_coproc_erase_ext_flash()
        if not erase_success or erase_err:
            return f"Failed to erase external flash for retry: {erase_err}"

        # Retry the test
        logger.debug("Retrying external flash test after erase...")
        err = _run_flash_test_operations(
            client,
            logger,
            test_data_b64,
            random_middle_address,
            DEFAULT_START_ADDR,
            DEFAULT_END_ADDR,
            DEFAULT_TEST_PATTERN,
        )

        if err:
            return f"External flash test failed after retry: {err}"

    # Cleanup - erase the flash after testing
    logger.debug("Performing cleanup erase of external flash...")
    cleanup_success, cleanup_err = client.cmd_comms_coproc_erase_ext_flash()
    if not cleanup_success or cleanup_err:
        logger.warning(f"Cleanup erase failed: {cleanup_err}")

    logger.info("External flash verification completed successfully")
    return None


def _save_device_info(
    proxy_server_url: str,
    device_id: str,
    pub_key: str,
    base64_key: str,
    imei: str,
    iccids: List[str],
    snr: str,
    logger: Logger,
) -> Optional[str]:
    """Save device information to Concord proxy server"""
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

        logger.info("Device information saved to proxy server successfully")
        return None

    except Exception as e:
        return f"An exception occurred whilst trying to save device info to proxy: \n{traceback.format_exc()}"


def _personalize_device(
    client: MtibV1Client, logger: Logger, device_id: str, proxy_server_url: str, snr: str, imei: str, iccids: List[str]
) -> Optional[str]:
    """
    Personalize the device with the given device ID and save to proxy server
    """
    logger.info(f"Personalizing device with ID: {device_id}")

    # Get device public key from the device
    hex_key, base64_key, err = client.cmd_comms_coproc_personalize(device_id)
    if err:
        return f"Error personalizing device: {err}"

    logger.info(f"Device personalized successfully")
    logger.info(f"Hex public key: {hex_key}")
    logger.info(f"Base64 public key: {base64_key}")

    # Basic validation - ensure we got valid keys
    if not hex_key or not base64_key:
        return "Personalization failed - missing public keys"

    # Save device information to proxy server
    err = _save_device_info(
        proxy_server_url,
        device_id,
        hex_key,
        base64_key,
        imei,
        iccids,
        snr,
        logger,
    )
    if err:
        return f"Error saving device info to proxy server: {err}"

    logger.info("Device personalization completed successfully")
    return None


def run_post_test(
    client: MtibV1Client, logger: Logger, device_id: str = None, proxy_server_url: str = None, snr: str = None
) -> Optional[str]:
    """
    Run the complete post test suite

    Args:
        client: MTIB client instance
        logger: Logger instance
        device_id: Optional device ID for personalization step
        proxy_server_url: Optional proxy server URL for personalization
        snr: Optional serial number for personalization

    Returns:
        None on success, error string on failure
    """
    logger.info("Starting post test suite...")

     # Turn off power
    error = client.DutPowerDisable()
    if error:
        return f"Could not disable device power: {error}"

     # Await some time for the power to be off
    time.sleep(2)

        # Turn on the device
    error = client.DutPowerEnable(4.0)
    if error:
        return f"Could not set VBAT: {error}"

    # Await some time for boot
    time.sleep(2)   

    # Setup the shell for the comms processor
    locked, error = client.cmd_comms_coproc_lock_shell()
    if error or not locked:
        return f"Could not lock shell: {error}"

    disabled, error = client.cmd_comms_coproc_debug_uart_disable()
    if error or not disabled:
        return f"Could not disable debug UART: {error}"

    # 1. Verify chip IDs
    err = _verify_chip_ids(client, logger)
    if err:
        return f"Error verifying chip IDs: {err}"

    # 2. Verify modem firmware version
    err = _verify_modem_firmware_version(client, logger)
    if err:
        return f"Error verifying modem firmware version: {err}"

    # 3. Verify IMEI and ICCIDs (collect them for personalization)
    imei, iccid_list, err = client.cmd_comms_coproc_get_imei_iccid()
    if err:
        return f"Error getting IMEI and ICCIDs: {err}"

    # Validate IMEI and ICCIDs
    err = _verify_imei_iccids(imei, iccid_list, logger)
    if err:
        return f"Error verifying IMEI and ICCIDs: {err}"

    # 4. Verify external flash
    err = _verify_external_flash(client, logger)
    if err:
        return f"Error verifying external flash: {err}"

    # 5. Personalize device (if all required parameters provided)
    if device_id and proxy_server_url and snr and imei and iccid_list:
        err = _personalize_device(client, logger, device_id, proxy_server_url, snr, imei, iccid_list)
        if err:
            return f"Error personalizing device: {err}"
    elif device_id or proxy_server_url or snr:
        logger.warning(
            "Personalization skipped - missing required parameters (device_id, proxy_server_url, snr, imei, iccids)"
        )

    # 6. Run app protect for both processors

    logger.info("Post test suite completed successfully")
    return None
