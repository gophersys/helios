import base64
import random
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

import requests
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import HostType
from corekinect.utils import Logger

# Theta uses nRF9151 for comms processor
THETA_COMMS_TARGET = HostType.HOST_TYPE_NRF9151

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
ATT_PREFIX = "890103"

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


def _run_comms_flash_test_operations(
    client: MtibV1Client,
    logger: Logger,
    test_data_b64: str,
    random_middle_address: str,
    start_addr: str,
    end_addr: str,
    test_string: str,
) -> Optional[str]:
    """Run comms processor flash test operations without erase operations."""

    # Step 1: Write known pattern to start of external flash
    logger.debug("[Comms] Writing test pattern to start of external flash...")
    success, err = client.cmd_comms_coproc_write_ext_flash(start_addr, test_data_b64, target=THETA_COMMS_TARGET)
    if not success or err:
        return f"Failed to write to start of flash: {err}"

    # Step 2: Write known pattern to end of external flash
    logger.debug("[Comms] Writing test pattern to end of external flash...")
    success, err = client.cmd_comms_coproc_write_ext_flash(end_addr, test_data_b64, target=THETA_COMMS_TARGET)
    if not success or err:
        return f"Failed to write to end of flash: {err}"

    # Step 3: Write known pattern to random middle address
    logger.debug(f"[Comms] Writing test pattern to middle address {random_middle_address}...")
    success, err = client.cmd_comms_coproc_write_ext_flash(
        random_middle_address, test_data_b64, target=THETA_COMMS_TARGET
    )
    if not success or err:
        return f"Failed to write to middle of flash: {err}"

    # Step 4: Verify pattern at start
    logger.debug("[Comms] Reading and verifying pattern at start...")
    read_data, err = client.cmd_comms_coproc_read_ext_flash(start_addr, len(test_string), target=THETA_COMMS_TARGET)
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
    logger.debug("[Comms] Reading and verifying pattern at end...")
    read_data, err = client.cmd_comms_coproc_read_ext_flash(end_addr, len(test_string), target=THETA_COMMS_TARGET)
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
    logger.debug(f"[Comms] Reading and verifying pattern at middle address {random_middle_address}...")
    read_data, err = client.cmd_comms_coproc_read_ext_flash(
        random_middle_address, len(test_string), target=THETA_COMMS_TARGET
    )
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


def _run_app_flash_test_operations(
    client: MtibV1Client,
    logger: Logger,
    test_data_b64: str,
    random_middle_address: str,
    start_addr: str,
    end_addr: str,
    test_string: str,
) -> Optional[str]:
    """Run app processor flash test operations without erase operations."""

    # Step 1: Write known pattern to start of external flash
    logger.debug("[App] Writing test pattern to start of external flash...")
    success, err = client.cmd_theta_app_write_ext_flash(start_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to start of flash: {err}"

    # Step 2: Write known pattern to end of external flash
    logger.debug("[App] Writing test pattern to end of external flash...")
    success, err = client.cmd_theta_app_write_ext_flash(end_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to end of flash: {err}"

    # Step 3: Write known pattern to random middle address
    logger.debug(f"[App] Writing test pattern to middle address {random_middle_address}...")
    success, err = client.cmd_theta_app_write_ext_flash(random_middle_address, test_data_b64)
    if not success or err:
        return f"Failed to write to middle of flash: {err}"

    # Step 4: Verify pattern at start
    logger.debug("[App] Reading and verifying pattern at start...")
    read_data, err = client.cmd_theta_app_read_ext_flash(start_addr, len(test_string))
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
    logger.debug("[App] Reading and verifying pattern at end...")
    read_data, err = client.cmd_theta_app_read_ext_flash(end_addr, len(test_string))
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
    logger.debug(f"[App] Reading and verifying pattern at middle address {random_middle_address}...")
    read_data, err = client.cmd_theta_app_read_ext_flash(random_middle_address, len(test_string))
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
    Verify the chip IDs (comms external flash chip ID)
    """
    logger.info("Verifying comms processor chip IDs...")

    lora_available, ext_flash_id, err = client.cmd_comms_coproc_get_chip_ids(target=THETA_COMMS_TARGET)
    if err:
        return f"Error getting comms chip IDs: {err}"

    logger.info(f"Comms external flash chip ID: {ext_flash_id}")
    if lora_available:
        logger.info(f"LoRa available: {lora_available}")

    # Basic validation - ensure we got valid responses
    if not ext_flash_id:
        return "External flash chip ID is empty"

    # Validate the external flash chip ID (W25Q64 - 0xef 0x40 0x17)
    if ext_flash_id != "0xef 0x40 0x17":
        logger.warning(f"Unexpected flash chip ID: {ext_flash_id}, expected 0xef 0x40 0x17")

    logger.info("Comms chip ID verification completed successfully")
    return None


def _verify_app_chip_ids(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the app processor chip IDs (accelerometer)
    Note: Theta does not have an altimeter
    """
    logger.info("Verifying app processor chip IDs...")

    accel_id, alt_id, err = client.cmd_theta_app_get_chip_ids()
    if err:
        return f"Error getting app chip IDs: {err}"

    logger.info(f"Accelerometer chip ID: {accel_id}")
    if alt_id:
        logger.info(f"Altimeter chip ID: {alt_id}")

    # Basic validation - Theta only has accelerometer (LIS2DW12)
    if not accel_id:
        return "Accelerometer chip ID is missing"

    logger.info("App chip ID verification completed successfully")
    return None


def _verify_modem_firmware_version(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the modem firmware version
    """
    logger.info("Verifying modem firmware version...")

    fw_version, err = client.cmd_comms_coproc_get_modem_fw_version(target=THETA_COMMS_TARGET)
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
            iccid.startswith(VERIZON_PREFIX)
            or iccid.startswith(SORACOM_PREFIX)
            or iccid.startswith(ONOMONDO_PREFIX)
            or iccid.startswith(ATT_PREFIX)
        ):
            return f"ICCID ({iccid}) is not from a recognized carrier"

    logger.info("IMEI and ICCID verification completed successfully")
    return None


def _verify_comms_external_flash(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify comms processor external flash functionality
    """
    logger.info("[Comms] Verifying external flash functionality...")

    # Convert test string to base64 for writing
    test_data_b64 = base64.b64encode(DEFAULT_TEST_PATTERN.encode("utf-8")).decode("utf-8")

    # Generate random address in middle third
    middle_start_int = int(DEFAULT_MIDDLE_START, 16)
    middle_end_int = int(DEFAULT_MIDDLE_END, 16)
    random_middle_address = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

    logger.debug(f"[Comms] Testing external flash with pattern: {DEFAULT_TEST_PATTERN}")
    logger.debug(
        f"[Comms] Test addresses - Start: {DEFAULT_START_ADDR}, End: {DEFAULT_END_ADDR}, Middle: {random_middle_address}"
    )

    # Try the test first without erasing
    logger.debug("[Comms] Attempting external flash test without initial erase...")
    err = _run_comms_flash_test_operations(
        client,
        logger,
        test_data_b64,
        random_middle_address,
        DEFAULT_START_ADDR,
        DEFAULT_END_ADDR,
        DEFAULT_TEST_PATTERN,
    )

    if not err:
        logger.debug("[Comms] First test attempt succeeded!")
    else:
        logger.debug(f"[Comms] First test attempt failed: {err}. Erasing flash and retrying...")

        # Erase external flash and retry
        erase_success, erase_err = client.cmd_comms_coproc_erase_ext_flash(target=THETA_COMMS_TARGET)
        if not erase_success or erase_err:
            return f"[Comms] Failed to erase external flash for retry: {erase_err}"

        # Retry the test
        logger.debug("[Comms] Retrying external flash test after erase...")
        err = _run_comms_flash_test_operations(
            client,
            logger,
            test_data_b64,
            random_middle_address,
            DEFAULT_START_ADDR,
            DEFAULT_END_ADDR,
            DEFAULT_TEST_PATTERN,
        )

        if err:
            return f"[Comms] External flash test failed after retry: {err}"

    # Cleanup - erase the flash after testing
    logger.debug("[Comms] Performing cleanup erase of external flash...")
    cleanup_success, cleanup_err = client.cmd_comms_coproc_erase_ext_flash(target=THETA_COMMS_TARGET)
    if not cleanup_success or cleanup_err:
        logger.warning(f"[Comms] Cleanup erase failed: {cleanup_err}")

    logger.info("[Comms] External flash verification completed successfully")
    return None


def _verify_app_external_flash(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify app processor external flash functionality
    """
    logger.info("[App] Verifying external flash functionality...")

    # Convert test string to base64 for writing
    test_data_b64 = base64.b64encode(DEFAULT_TEST_PATTERN.encode("utf-8")).decode("utf-8")

    # Generate random address in middle third
    middle_start_int = int(DEFAULT_MIDDLE_START, 16)
    middle_end_int = int(DEFAULT_MIDDLE_END, 16)
    random_middle_address = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

    logger.debug(f"[App] Testing external flash with pattern: {DEFAULT_TEST_PATTERN}")
    logger.debug(
        f"[App] Test addresses - Start: {DEFAULT_START_ADDR}, End: {DEFAULT_END_ADDR}, Middle: {random_middle_address}"
    )

    # Try the test first without erasing
    logger.debug("[App] Attempting external flash test without initial erase...")
    err = _run_app_flash_test_operations(
        client,
        logger,
        test_data_b64,
        random_middle_address,
        DEFAULT_START_ADDR,
        DEFAULT_END_ADDR,
        DEFAULT_TEST_PATTERN,
    )

    if not err:
        logger.debug("[App] First test attempt succeeded!")
    else:
        logger.debug(f"[App] First test attempt failed: {err}. Erasing flash and retrying...")

        # Erase external flash and retry
        erase_success, erase_err = client.cmd_theta_app_erase_ext_flash()
        if not erase_success or erase_err:
            return f"[App] Failed to erase external flash for retry: {erase_err}"

        # Retry the test
        logger.debug("[App] Retrying external flash test after erase...")
        err = _run_app_flash_test_operations(
            client,
            logger,
            test_data_b64,
            random_middle_address,
            DEFAULT_START_ADDR,
            DEFAULT_END_ADDR,
            DEFAULT_TEST_PATTERN,
        )

        if err:
            return f"[App] External flash test failed after retry: {err}"

    # Cleanup - erase the flash after testing
    logger.debug("[App] Performing cleanup erase of external flash...")
    cleanup_success, cleanup_err = client.cmd_theta_app_erase_ext_flash()
    if not cleanup_success or cleanup_err:
        logger.warning(f"[App] Cleanup erase failed: {cleanup_err}")

    logger.info("[App] External flash verification completed successfully")
    return None


def _verify_external_flash(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify external flash functionality on both processors in parallel
    """
    logger.info("Verifying external flash functionality on both processors...")

    errors = []

    # Run both flash tests in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_verify_comms_external_flash, client, logger): "comms",
            executor.submit(_verify_app_external_flash, client, logger): "app",
        }

        for future in as_completed(futures):
            processor = futures[future]
            try:
                err = future.result()
                if err:
                    errors.append(f"{processor}: {err}")
            except Exception as e:
                errors.append(f"{processor}: Exception - {str(e)}")

    if errors:
        return "; ".join(errors)

    logger.info("External flash verification completed successfully on both processors")
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
            elif iccid.startswith("890103"):
                carrier = "ATT"
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
    hex_key, base64_key, err = client.cmd_comms_coproc_personalize(device_id, target=THETA_COMMS_TARGET)
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


def _verify_bms(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the BMS (battery management system / gas gauge) chip
    """
    logger.info("Verifying BMS (gas gauge)...")

    result, err = client.cmd_theta_app_test_bms()
    if err:
        return f"Error testing BMS: {err}"

    connected = result.get("connected", False)
    chip_id = result.get("chip_id", "")
    charge_percent = result.get("charge_percent", 0)
    capacity = result.get("capacity_mah", 0)
    temp = result.get("temp_c", 0)

    logger.info(f"BMS connected: {connected}")
    logger.info(f"BMS chip ID: {chip_id}")
    logger.info(f"Charge: {charge_percent}%")
    logger.info(f"Capacity: {capacity} mAh")
    logger.info(f"Temperature: {temp} C")

    if not connected:
        return "BMS is not connected"

    # MAX17263 chip ID should be 0x4037
    if chip_id != "0x4037":
        logger.warning(f"Unexpected BMS chip ID: {chip_id}, expected 0x4037")

    logger.info("BMS verification completed successfully")
    return None


def _verify_charger(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the battery charger chip
    """
    logger.info("Verifying battery charger...")

    result, err = client.cmd_theta_app_test_charger()
    if err:
        return f"Error testing charger: {err}"

    chip_id = result.get("chip_id", "")
    on_charger = result.get("on_charger", False)
    charging = result.get("charging", False)
    charge_done = result.get("charge_done", False)
    voltage = result.get("voltage_mv", 0)

    logger.info(f"Charger chip ID: {chip_id}")
    logger.info(f"On charger: {on_charger}")
    logger.info(f"Charging: {charging}")
    logger.info(f"Charge done: {charge_done}")
    logger.info(f"Battery voltage: {voltage} mV")

    # Note: Charger chip ID may show err: -22 when not on charger, which is expected
    # We only log a warning if we get a valid ID that doesn't match expected
    if chip_id and chip_id != "0x00" and chip_id != "0x22":
        logger.warning(f"Unexpected charger chip ID: {chip_id}, expected 0x22")

    logger.info("Charger verification completed successfully")
    return None


def _verify_gps(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Verify the GPS (GNSS) module communication
    """
    logger.info("Verifying GPS module...")

    result, err = client.cmd_theta_app_test_gps()
    if err:
        return f"Error testing GPS: {err}"

    in_shutdown = result.get("shutdown", True)
    is_tracking = result.get("tracking", False)
    comms_ok = result.get("comms_ok", False)

    logger.info(f"GPS shutdown: {in_shutdown}")
    logger.info(f"GPS tracking: {is_tracking}")
    logger.info(f"GPS comms: {'OK' if comms_ok else 'FAIL'}")

    if in_shutdown:
        return "GPS is in shutdown mode - communication failed"

    logger.info("GPS verification completed successfully")
    return None


def _rekey_ipc(client: MtibV1Client, logger: Logger) -> Optional[str]:
    """
    Rekey IPC to replace hard coded keys with device-specific keys
    """
    logger.info("Rekeying IPC...")

    success, err = client.cmd_comms_coproc_rekey_ipc(target=THETA_COMMS_TARGET)
    if err:
        return f"Error rekeying IPC: {err}"

    if not success:
        return "Failed to rekey IPC"

    logger.info("IPC rekey completed successfully")
    return None


def _set_ap_protect(client: MtibV1Client, logger: Logger) -> Optional[str]:
    # Set AP protect to 1 for both processors
    success, err = client.EnableAppProtect(HostType.HOST_TYPE_NRF52840)
    if err:
        return f"Error setting AP protect on app processor: {err}"
    if not success:
        return "Failed to set AP protect on app processor"

    success, err = client.EnableAppProtect(THETA_COMMS_TARGET)
    if err:
        return f"Error setting AP protect on comms processor: {err}"
    if not success:
        return "Failed to set AP protect on comms processor"

    logger.info("AP protect set successfully on both processors")
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

    # Await some time for boot (5s to let logs settle before shell commands)
    time.sleep(5)

    # Setup the shell for the comms processor
    locked, error = client.cmd_comms_coproc_lock_shell(target=THETA_COMMS_TARGET)
    if error or not locked:
        return f"Could not lock comms shell: {error}"

    disabled, error = client.cmd_comms_coproc_debug_uart_disable(target=THETA_COMMS_TARGET)
    if error or not disabled:
        return f"Could not disable comms debug UART: {error}"

    # Setup the shell for the app processor
    locked, error = client.cmd_theta_app_lock_shell()
    if error or not locked:
        return f"Could not lock app shell: {error}"

    disabled, error = client.cmd_theta_app_debug_uart_disable()
    if error or not disabled:
        return f"Could not disable app debug UART: {error}"

    # 1. Verify chip IDs (comms processor)
    err = _verify_chip_ids(client, logger)
    if err:
        return f"Error verifying comms chip IDs: {err}"

    # 2. Verify app processor chip IDs
    err = _verify_app_chip_ids(client, logger)
    if err:
        return f"Error verifying app chip IDs: {err}"

    # 3. Verify BMS (gas gauge)
    err = _verify_bms(client, logger)
    if err:
        return f"Error verifying BMS: {err}"

    # 4. Verify battery charger
    err = _verify_charger(client, logger)
    if err:
        return f"Error verifying charger: {err}"

    # 5. Verify GPS module
    err = _verify_gps(client, logger)
    if err:
        return f"Error verifying GPS: {err}"

    # 6. Verify modem firmware version
    err = _verify_modem_firmware_version(client, logger)
    if err:
        return f"Error verifying modem firmware version: {err}"

    # 7. Verify IMEI and ICCIDs (collect them for personalization)
    # Modem takes ~9 seconds to retrieve IMEI/ICCID, so retry with delays
    max_retries = 5
    retry_delay = 3  # seconds
    imei = None
    iccid_list = None

    for attempt in range(max_retries):
        imei, iccid_list, err = client.cmd_comms_coproc_get_imei_iccid(target=THETA_COMMS_TARGET)
        if err:
            return f"Error getting IMEI and ICCIDs: {err}"

        # Check if we got valid data (modem may not have retrieved it yet)
        if imei and iccid_list:
            break

        if attempt < max_retries - 1:
            logger.info(
                f"IMEI/ICCID not ready yet, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})..."
            )
            time.sleep(retry_delay)

    # Validate IMEI and ICCIDs
    err = _verify_imei_iccids(imei, iccid_list, logger)
    if err:
        return f"Error verifying IMEI and ICCIDs: {err}"

    # 8. Verify external flash
    err = _verify_external_flash(client, logger)
    if err:
        return f"Error verifying external flash: {err}"

    # 9. Personalize device (if all required parameters provided)
    if device_id and proxy_server_url and snr and imei and iccid_list:
        err = _personalize_device(client, logger, device_id, proxy_server_url, snr, imei, iccid_list)
        if err:
            return f"Error personalizing device: {err}"
    elif device_id or proxy_server_url or snr:
        logger.warning(
            "Personalization skipped - missing required parameters (device_id, proxy_server_url, snr, imei, iccids)"
        )

    # 10. Rekey IPC to replace hard coded keys
    err = _rekey_ipc(client, logger)
    if err:
        return f"Error rekeying IPC: {err}"

    # # 11. Run app protect for both processors
    err = _set_ap_protect(client, logger)
    if err:
        return f"Error setting AP protect: {err}"

    logger.info("Theta post test suite completed successfully")
    return None
