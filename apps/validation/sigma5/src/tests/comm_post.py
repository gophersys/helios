import base64
import threading
import time
from typing import Optional

from config.env import env_config
from corekinect.mtib_client.v1 import HostType, MtibV1Client
from corekinect.mtib_client.v1.client.types import PowerChannel
from corekinect.utils.logx import Logger
from services.firmware import flash_firmware_from_storage
from services.mtib import get_mtib_client

LOG_MODULE = "comm_post"

# -----------------------------------------------
#                                   Configuration
# ---------------------------------------------*/

# Motion parameters for continuous motion during test
MOTION_SPEED_MM_S = 15000
MOTION_DISTANCE_MM = 10000
MOTION_THREAD_JOIN_TIMEOUT_S = 2.0

# Power and timing constants
POWER_OFF_DELAY_S = 2.0
POWER_ON_DELAY_S = 2.0
DUT_VOLTAGE_V = 4.0

# Chip ID constants (expected values - can be moved to config later)
EXPECTED_LORA_AVAILABLE = "1"  # Example - update with actual value
EXPECTED_EXT_FLASH_ID = "0xEF"  # Example - update with actual value

# IMEI validation constants
IMEI_LENGTH = 15

# ICCID validation constants
ICCID_MIN_LENGTH = 19
ICCID_MAX_LENGTH = 20
ICCID_PADDING_CHAR = "F"  # Trailing F's used for padding

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

# External flash test constants
EXTERNAL_FLASH_TEST_STRING = "COMMS_FLASH_TEST"
EXTERNAL_FLASH_TEST_ADDRESS = "0x1000"

# Retry constants
MODEM_FW_READ_MAX_RETRIES = 20
MODEM_FW_READ_RETRY_DELAY_S = 0.5

# Global motion thread handle
_motion_thread: Optional[threading.Thread] = None
_motion_running = False


# -----------------------------------------------
#                                            Init
# ---------------------------------------------*/
def _init(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Initialize the comm post test"""
    logger.debug("Initializing comm post test")

    # Start continuous motion to prove test can run while device moves
    logger.debug("Starting motion profile")
    global _motion_thread, _motion_running

    # Home the motion system first
    if err := mtib_client.MotionHome():
        return f"Failed to home motion system: {err}"

    logger.info("Motion system homed successfully")

    # Start motion in a background thread
    _motion_running = True

    def run_motion():
        global _motion_running
        motion_logger = logger.from_parent("motion")
        try:
            while _motion_running:
                # Start motion with distance-based movement (back and forth)
                for response in mtib_client.MotionStart(
                    duration_seconds=0,
                    dwell_seconds=0,
                    speed_mm_s=MOTION_SPEED_MM_S,
                    distance_mm=MOTION_DISTANCE_MM,
                ):
                    if not _motion_running:
                        break
                    if not response.success:
                        motion_logger.error(f"Motion error: {response.message}")
                        break
                    # There's metadata in the response that can be used to track/log progress
                    # motion_logger.info(f"Motion response: {response}")
        except Exception as e:
            if _motion_running:
                motion_logger.error(f"Error in motion thread: {e}")

    _motion_thread = threading.Thread(target=run_motion, daemon=True)
    _motion_thread.start()
    logger.info("Motion profile started successfully")

    # Flash firmware if path provided
    logger.info(f"Flashing firmware from: {env_config.FIRMWARE_BUCKET_FILE_PATH}")
    error = flash_firmware_from_storage(logger, env_config.FIRMWARE_BUCKET_FILE_PATH)
    if error:
        return f"Failed to flash firmware: {error}"
    logger.info("Firmware flashed successfully")

    logger.info("Setting up power")

    # Setup power
    if err := mtib_client.PowerDisable(channel=PowerChannel.CHARGER):
        return f"Failed to disable charge power: {err}"

    if err := mtib_client.PowerDisable(channel=PowerChannel.DUT):
        return f"Failed to disable DUT power: {err}"

    # Wait for power to be off
    time.sleep(POWER_OFF_DELAY_S)

    # Turn on the device
    if err := mtib_client.PowerEnable(channel=PowerChannel.DUT, voltage_v=DUT_VOLTAGE_V):
        return f"Failed to power on DUT: {err}"

    # Wait for device to boot
    time.sleep(POWER_ON_DELAY_S)

    # Setup the shell for the app processor
    locked, err = mtib_client.cmd_sigma5_app_lock_shell()
    if err or not locked:
        return f"Failed to lock app shell: {err}"

    disabled, err = mtib_client.cmd_sigma5_app_debug_uart_disable()
    if err or not disabled:
        return f"Failed to disable app debug UART: {err}"

    # Setup the shell for the comms processor
    locked, _ = mtib_client.lock_shell_comms()
    if not locked:
        return "Failed to lock comms shell"

    disabled, err = mtib_client.debug_disable_comms()
    if err or not disabled:
        return f"Failed to disable comms debug UART: {err}"

    logger.info("Comm post test initialized successfully")
    return None


# -----------------------------------------------
#                              Test Step Sequence
# ---------------------------------------------*/
def _run(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Run all comm post test steps"""

    error = __step_1_verify_chip_ids(logger, mtib_client)
    if error:
        return error

    error = __step_2_verify_modem_fw(logger, mtib_client)
    if error:
        return error

    error = __step_3_verify_imei_iccids(logger, mtib_client)
    if error:
        return error

    error = __step_4_verify_external_flash(logger, mtib_client)
    if error:
        return error

    error = __step_5_rekey_ipc(logger, mtib_client)
    if error:
        return error

    return None


# -----------------------------------------------
#                                          Steps
# ---------------------------------------------*/
def __step_1_verify_chip_ids(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 1: Verify chip IDs"""
    logger.debug("Step 1: Verify chip IDs")

    lora_available, ext_flash_id, error = mtib_client.cmd_comms_coproc_get_chip_ids()
    if error:
        return f"Step 1 failed: {error}"

    if not lora_available or not ext_flash_id:
        return f"Step 1 failed: Missing chip IDs (lora: {lora_available}, flash: {ext_flash_id})"

    # Verify chip IDs (simplified - can add actual verification later)
    logger.info(f"Step 1: LoRa Available: {lora_available}, Ext Flash ID: {ext_flash_id}")

    logger.info("Step 1 completed successfully")
    return None


def __step_2_verify_modem_fw(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 2: Verify modem firmware version"""
    logger.debug("Step 2: Verify modem firmware version")

    # Read with retry logic
    for attempt in range(MODEM_FW_READ_MAX_RETRIES):
        fw_version, error = mtib_client.cmd_comms_coproc_get_modem_fw_version()
        if error:
            return f"Step 2 failed: {error}"

        # Check if the result is empty, 0, or None
        if fw_version is None or fw_version == "" or fw_version == "0":
            if attempt < MODEM_FW_READ_MAX_RETRIES - 1:
                time.sleep(MODEM_FW_READ_RETRY_DELAY_S)
                continue
            else:
                return "Step 2 failed: Failed to get valid modem FW version after retries"
        else:
            break

    # Verify version (simplified - can add actual verification later)
    logger.info(f"Step 2: Modem FW Version: {fw_version}")

    logger.info("Step 2 completed successfully")
    return None


def __step_3_verify_imei_iccids(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 3: Verify IMEI and ICCIDs"""
    logger.debug("Step 3: Verify IMEI and ICCIDs")

    imei, iccids, error = mtib_client.cmd_comms_coproc_get_imei_iccid()
    if error:
        return f"Step 3 failed: {error}"

    # IMEI must be present
    if not imei:
        return f"Step 3 failed: IMEI is empty"

    # ICCIDs must be present
    if not iccids or len(iccids) == 0:
        return f"Step 3 failed: No ICCIDs found"

    # Basic validation - IMEI should be 15 digits
    if len(imei) != IMEI_LENGTH or not imei.isdigit():
        return f"Step 3 failed: IMEI length is invalid, expected {IMEI_LENGTH} digits, got {len(imei)}"

    # Basic validation - ICCIDs should be 19-20 digits
    for iccid in iccids:
        # Strip any trailing padding characters
        iccid = iccid.rstrip(ICCID_PADDING_CHAR)
        if len(iccid) not in [ICCID_MIN_LENGTH, ICCID_MAX_LENGTH] or not iccid.isdigit():
            return f"Step 3 failed: ICCID length is invalid, expected {ICCID_MIN_LENGTH}-{ICCID_MAX_LENGTH} digits, got {len(iccid)}"

    logger.info(f"Step 3: IMEI: {imei}, ICCIDs: {iccids}")

    logger.info("Step 3 completed successfully")
    return None


def __step_4_verify_external_flash(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 4: Verify external flash functionality"""
    logger.debug("Step 4: Verify external flash")

    # Simplified test - write a test pattern, read it back, and verify
    test_string = EXTERNAL_FLASH_TEST_STRING
    test_data_b64 = base64.b64encode(test_string.encode("utf-8")).decode("utf-8")
    test_address = EXTERNAL_FLASH_TEST_ADDRESS

    # Write test pattern
    write_success, write_error = mtib_client.cmd_comms_coproc_write_ext_flash(test_address, test_data_b64)
    if not write_success or write_error:
        return f"Step 4 failed: Failed to write to flash: {write_error}"

    # Read back
    read_data, read_error = mtib_client.cmd_comms_coproc_read_ext_flash(test_address, len(test_string))
    if not read_data or read_error:
        return f"Step 4 failed: Failed to read from flash: {read_error}"

    # Convert hex data back to string for comparison
    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Step 4 failed: Data mismatch. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Step 4 failed: Failed to parse read data: {e}"

    # Cleanup - erase the test data
    erase_success, erase_error = mtib_client.cmd_comms_coproc_erase_ext_flash()
    if not erase_success or erase_error:
        logger.warning(f"Failed to erase flash after test: {erase_error}")

    logger.info("Step 4 completed successfully")
    return None


def __step_5_rekey_ipc(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 5: Rekey IPC"""
    logger.debug("Step 5: Rekey IPC")

    success, error = mtib_client.cmd_comms_coproc_rekey_ipc()
    if error:
        return f"Step 5 failed: {error}"

    if not success:
        return "Step 5 failed: Rekey IPC returned false"

    logger.info("Step 5 completed successfully")
    return None


# -----------------------------------------------
#                                          Deinit
# ---------------------------------------------*/
def _deinit(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Deinitialize the comm post test"""
    # Turn off power
    if err := mtib_client.PowerDisable(channel=PowerChannel.DUT):
        return f"Failed to disable DUT power: {err}"

    if err := mtib_client.PowerDisable(channel=PowerChannel.CHARGER):
        return f"Failed to disable charge power: {err}"

    # Stop motion
    global _motion_thread, _motion_running
    if _motion_running:
        logger.debug("Stopping motion profile")
        _motion_running = False

        # Stop the motion system
        if err := mtib_client.MotionStop():
            logger.warning(f"Failed to stop motion: {err}")
        else:
            logger.info("Motion profile stopped successfully")

        # Wait for motion thread to finish
        if _motion_thread and _motion_thread.is_alive():
            _motion_thread.join(timeout=MOTION_THREAD_JOIN_TIMEOUT_S)

    return None


# -----------------------------------------------
#                        Comm (nrf9160) Post Test
# ---------------------------------------------*/
def run_comm_post_test(logger: Logger) -> Optional[str]:
    mtib_client = get_mtib_client()
    logger = logger.from_parent(LOG_MODULE)

    test_error = None
    try:
        error = _init(logger, mtib_client)
        if error:
            test_error = f"Failed to initialize comm_post test: {error}"
        else:
            error = _run(logger, mtib_client)
            if error:
                test_error = f"Failed to run comm_post test: {error}"
            else:
                logger.info("Comm post test completed successfully")
    finally:
        # Always run deinit to stop motion, even if test failed
        error = _deinit(logger, mtib_client)
        if error:
            deinit_error = f"Failed to deinitialize comm_post test: {error}"
            if test_error:
                # If we already have an error, log the deinit error but return the original error
                logger.error(deinit_error)
            else:
                test_error = deinit_error

    return test_error
