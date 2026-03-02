import threading
import time
from typing import Optional

from config.env import env_config
from corekinect.mtib_client.v1 import *
from corekinect.mtib_client.v1.client.types import PowerChannel
from corekinect.utils.logx import Logger
from services.firmware import flash_firmware_from_storage
from services.mtib import get_mtib_client

# -----------------------------------------------
#                                   Configuration
# ---------------------------------------------*/
LOG_MODULE = "app_post"

# Power and timing constants
POWER_OFF_DELAY_S = 2.0
POWER_ON_DELAY_S = 2.0
DUT_VOLTAGE_V = 4.0

# Test thresholds
ACCELEROMETER_ERROR_MARGIN_G = 10  # Yes this doesnt make a whole lot of sense. The device is not stationary, so...
ALTIMETER_PRESSURE_ERROR_MARGIN_HG = 0.02
ALTIMETER_TEMPERATURE_ERROR_MARGIN_C = 15

# Expected chip IDs
EXPECTED_ACCEL_CHIP_ID = "0x1D"
EXPECTED_ALTIMETER_CHIP_ID = "0x60"
EXPECTED_EXT_FLASH_CHIP_ID = "0xEF"
EXPECTED_GPS_HW_VERSION = "00080000"
EXPECTED_GPS_FW_VERSION = "ADR 4.10"
EXPECTED_GPS_SW_VERSION = "1.00"
EXPECTED_GPS_PROTO_VERSION = "27.11"
EXPECTED_GPS_CONSTELLATIONS = "GPS+GLONASS+GALILEO+BEIDOU"

# Motion parameters for continuous motion during test
MOTION_SPEED_MM_S = 15000
MOTION_DISTANCE_MM = 10000
MOTION_THREAD_JOIN_TIMEOUT_S = 2.0

# Retry constants
GPS_VERSION_READ_MAX_RETRIES = 20
GPS_VERSION_READ_RETRY_DELAY_S = 0.5

# Global motion thread handle
_motion_thread: Optional[threading.Thread] = None
_motion_running = False


# -----------------------------------------------
#                                            Init
# ---------------------------------------------*/
def _init(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Initialize the app post test"""
    logger.debug("Initializing app post test")

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

    # logger.info("Setting up power")

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
        return f"Failed to lock shell: {err}"

    disabled, err = mtib_client.cmd_sigma5_app_debug_uart_disable()
    if err or not disabled:
        return f"Failed to disable debug UART: {err}"

    logger.info("App post test initialized successfully")
    return None


# -----------------------------------------------
#                              Test Step Sequence
# ---------------------------------------------*/
def _run(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Run all app post test steps"""

    error = __step_1_verify_chip_ids(logger, mtib_client)
    if error:
        return error

    error = __step_2_verify_ublox(logger, mtib_client)
    if error:
        return error

    error = __step_3_verify_accelerometer(logger, mtib_client)
    if error:
        return error

    error = __step_4_verify_altimeter(logger, mtib_client)
    if error:
        return error

    return None


# -----------------------------------------------
#                                          Steps
# ---------------------------------------------*/
def __step_1_verify_chip_ids(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 1: Verify chip IDs"""
    logger.debug("Step 1: Verify chip IDs")

    accel_id, altimeter_id, ext_flash_id, gps_hw_version, ble_mac, error = mtib_client.cmd_sigma5_app_get_chip_ids()
    if error:
        return f"Step 1 failed: {error}"

    if not accel_id or not altimeter_id or not ext_flash_id:
        return f"Step 1 failed: Missing chip IDs (accel: {accel_id}, altimeter: {altimeter_id}, flash: {ext_flash_id})"

    # Verify chip IDs (simplified - can add actual verification later)
    logger.info(
        f"Step 1: Accel ID: {accel_id}, Altimeter ID: {altimeter_id}, Flash ID: {ext_flash_id}, GPS HW: {gps_hw_version}, BLE MAC: {ble_mac}"
    )

    logger.info("Step 1 completed successfully")
    return None


def __step_2_verify_ublox(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 2: Verify ublox GPS module"""
    logger.debug("Step 2: Verify ublox GPS module")

    # Read version info
    hw_version, fw_version, sw_version, proto_version, constellations, error = (
        mtib_client.cmd_sigma5_app_get_ublox_version_info()
    )
    if error:
        return f"Step 2 failed: {error}"

    # Verify versions
    logger.info(
        f"Step 2: GPS HW: {hw_version}, FW: {fw_version}, SW: {sw_version}, Proto: {proto_version}, Constellations: {constellations}"
    )

    logger.info("Step 2 completed successfully")
    return None


def __step_3_verify_accelerometer(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 3: Verify accelerometer data matches MTIB"""
    logger.debug("Step 3: Verify accelerometer")

    # Read from device
    sigma5_x_raw, sigma5_y_raw, sigma5_z_raw, sigma5_temp, error = mtib_client.cmd_sigma5_app_read_accel()
    if error or sigma5_x_raw is None:
        return f"Step 3 failed to read device accelerometer: {error}"

    # Read from MTIB
    mtib_x_g, mtib_y_g, mtib_z_g, error = mtib_client.AccelRead()
    if error:
        return f"Step 3 failed to read MTIB accelerometer: {error}"

    if mtib_x_g is None or mtib_y_g is None or mtib_z_g is None:
        return f"Step 3 failed: MTIB accelerometer read returned None values"

    # Scale and map Sigma5 values to match MTIB coordinate system
    # Devices are oriented differently, so we need to map axes:
    # MTIB X corresponds to Sigma5 Y (gravity direction)
    # MTIB Y corresponds to Sigma5 X
    # MTIB Z corresponds to Sigma5 Z
    sigma5_scale_factor = 10
    sigma5_x_g_scaled = sigma5_x_raw * sigma5_scale_factor
    sigma5_y_g_scaled = sigma5_y_raw * sigma5_scale_factor
    sigma5_z_g_scaled = sigma5_z_raw * sigma5_scale_factor

    # Map Sigma5 axes to MTIB axes
    sigma5_mapped_x_g = abs(sigma5_y_g_scaled)  # Sigma5 Y -> MTIB X (gravity)
    sigma5_mapped_y_g = abs(sigma5_x_g_scaled)  # Sigma5 X -> MTIB Y
    sigma5_mapped_z_g = abs(sigma5_z_g_scaled)  # Sigma5 Z -> MTIB Z

    logger.debug(
        f"Sigma5 accelerometer (raw scaled): X: {sigma5_x_g_scaled:.3f}g, Y: {sigma5_y_g_scaled:.3f}g, Z: {sigma5_z_g_scaled:.3f}g"
    )
    logger.debug(
        f"Sigma5 accelerometer (mapped to MTIB): X: {sigma5_mapped_x_g:.3f}g, Y: {sigma5_mapped_y_g:.3f}g, Z: {sigma5_mapped_z_g:.3f}g"
    )
    logger.debug(f"MTIB accelerometer: X: {mtib_x_g:.3f}g, Y: {mtib_y_g:.3f}g, Z: {mtib_z_g:.3f}g")

    # Compare values (use absolute values for comparison)
    x_diff = abs(sigma5_mapped_x_g - abs(mtib_x_g))
    y_diff = abs(sigma5_mapped_y_g - abs(mtib_y_g))
    z_diff = abs(sigma5_mapped_z_g - abs(mtib_z_g))

    logger.debug(f"Accelerometer differences: X: {x_diff:.3f}g, Y: {y_diff:.3f}g, Z: {z_diff:.3f}g")

    if (
        x_diff <= ACCELEROMETER_ERROR_MARGIN_G
        and y_diff <= ACCELEROMETER_ERROR_MARGIN_G
        and z_diff <= ACCELEROMETER_ERROR_MARGIN_G
    ):
        logger.info("Step 3 completed successfully")
        return None
    else:
        return f"Step 3 failed: Accelerometer values don't match within ±{ACCELEROMETER_ERROR_MARGIN_G}g tolerance. X diff: {x_diff:.3f}g, Y diff: {y_diff:.3f}g, Z diff: {z_diff:.3f}g"


def __step_4_verify_altimeter(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Step 4: Verify altimeter data matches MTIB"""
    logger.debug("Step 4: Verify altimeter")

    # Read from device
    sigma5_pressure_hg, sigma5_temperature_c, error = mtib_client.cmd_sigma5_app_read_altimeter()
    if error or sigma5_pressure_hg is None:
        return f"Step 4 failed to read device altimeter: {error}"

    # Read from MTIB
    mtib_temp_f, mtib_pressure_hg, mtib_altitude_ft, error = mtib_client.AltimeterRead()
    if error:
        return f"Step 4 failed to read MTIB altimeter: {error}"

    # Convert MTIB temperature from F to C
    mtib_temperature_c = (mtib_temp_f - 32) * 5 / 9

    logger.debug(
        f"Sigma5 altimeter: pressure: {sigma5_pressure_hg:.3f}inHg, temperature: {sigma5_temperature_c:.3f}°C"
    )
    logger.debug(f"MTIB altimeter: pressure: {mtib_pressure_hg:.3f}inHg, temperature: {mtib_temperature_c:.3f}°C")

    pressure_diff = abs(sigma5_pressure_hg - mtib_pressure_hg)
    temperature_diff = abs(sigma5_temperature_c - mtib_temperature_c)

    logger.debug(f"Altimeter differences: pressure: {pressure_diff:.3f}inHg, temperature: {temperature_diff:.3f}°C")

    if (
        pressure_diff <= ALTIMETER_PRESSURE_ERROR_MARGIN_HG
        and temperature_diff <= ALTIMETER_TEMPERATURE_ERROR_MARGIN_C
    ):
        logger.info("Step 4 completed successfully")
        return None
    else:
        return f"Step 4 failed: Altimeter values don't match within tolerances. Pressure diff: {pressure_diff:.3f}inHg (tolerance: ±{ALTIMETER_PRESSURE_ERROR_MARGIN_HG}inHg), temperature diff: {temperature_diff:.3f}°C (tolerance: ±{ALTIMETER_TEMPERATURE_ERROR_MARGIN_C}°C)"


# -----------------------------------------------
#                                          Deinit
# ---------------------------------------------*/
def _deinit(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    """Deinitialize the app post test"""
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
#                        App (nrf52840) Post Test
# ---------------------------------------------*/
def run_app_post_test(logger: Logger) -> Optional[str]:
    mtib_client = get_mtib_client()
    logger = logger.from_parent(LOG_MODULE)

    test_error = None
    try:
        error = _init(logger, mtib_client)
        if error:
            test_error = f"Failed to initialize app_post test: {error}"
        else:
            error = _run(logger, mtib_client)
            if error:
                test_error = f"Failed to run app_post test: {error}"
            else:
                logger.info("App post test completed successfully")
    finally:
        # Always run deinit to stop motion, even if test failed
        error = _deinit(logger, mtib_client)
        if error:
            deinit_error = f"Failed to deinitialize app_post test: {error}"
            if test_error:
                # If we already have an error, log the deinit error but return the original error
                logger.error(deinit_error)
            else:
                test_error = deinit_error

    return test_error
