import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from corekinect.mtib_client.v1 import *
from corekinect.mtib_client.v1.client.types import PowerChannel
from corekinect.utils.logx import Logger
from services.mtib import get_mtib_client

# -----------------------------------------------
#                                   Configuration
# ---------------------------------------------*/
LOG_MODULE = "electrical"

# Test point constants (Sigma5 saddle)
TP52_VIN = 1  # ADC channel
TP11_3V3 = 4  # ADC channel
TP30_VBCKP = 5  # ADC channel

# Test thresholds (simplified from manufacturing config)
VIN_RAIL_STABILIZATION_PERIOD_S = 30
STEP_1A_VIN_THRESHOLD_V = 0.55
STEP_1D_NEAR_ZERO_CURRENT_A = 0.01
STEP_2A_VIN_VBAT_TOLERANCE = 0.1
STEP_2B_3V3_MIN = 3.2
STEP_2B_3V3_MAX = 3.4
STEP_2C_VBCKP_MIN = 2.4
STEP_2C_VBCKP_MAX = 2.7
STEP_2E_CURRENT_MIN = 0.01
STEP_2E_CURRENT_MAX = 0.1
STEP_3A_VIN_VBAT_TOLERANCE = 0.1
STEP_3B_CURRENT_MIN = 0.01
STEP_3B_CURRENT_MAX = 0.1
STEP_4A_VIN_THRESHOLD_V = 4.55
STEP_4B_3V3_MIN = 3.25
STEP_4B_3V3_MAX = 3.35
STEP_4C_VBCKP_MIN = 2.385
STEP_4C_VBCKP_MAX = 2.715

# Motion parameters for continuous motion during test
MOTION_SPEED_MM_S = 15000
MOTION_DISTANCE_MM = 10000
MOTION_THREAD_JOIN_TIMEOUT_S = 2.0

# Power and timing constants
INIT_POWER_VOLTAGE_V = 4.0
STEP_1_POWER_VOLTAGE_V = 2.4
STEP_2_POWER_VOLTAGE_V = 3.2
STEP_3_POWER_VOLTAGE_V = 3.6
VIN_RAIL_CHECK_DELAY_S = 0.5

# Global motion thread handle
_motion_thread: Optional[threading.Thread] = None
_motion_running = False


# -----------------------------------------------
#                                            Init
# ---------------------------------------------*/
def _init(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
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

    # Setup the right power supply for the test
    if err := mtib_client.PowerDisable(channel=PowerChannel.CHARGER):
        return f"Failed to disable charge power: {err}"

    if err := mtib_client.PowerEnable(channel=PowerChannel.DUT, voltage_v=INIT_POWER_VOLTAGE_V):
        return f"Failed to power on DUT: {err}"

    # Ensure a clean hardware state
    logger.debug("Erasing flash memory on MCUs")
    if err := mtib_client.EraseFlash(target=HostType.HOST_TYPE_NRF9160, recover=True):
        return f"Failed to erase flash memory on NRF9160: {err}"

    if err := mtib_client.EraseFlash(target=HostType.HOST_TYPE_NRF52840, recover=True):
        return f"Failed to erase flash memory on NRF52840: {err}"

    logger.info("Successfully erased flash memory on MCUs")

    return None


# -----------------------------------------------
#                              Test Step Sequence
# ---------------------------------------------*/
def _run(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    error = __step_1(logger, mtib_client)
    if error:
        return error

    error = __step_2(logger, mtib_client)
    if error:
        return error

    error = __step_3(logger, mtib_client)
    if error:
        return error

    return None


# -----------------------------------------------
#                                          Steps
# ---------------------------------------------*/
def __step_1(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    logger.debug("Step 1: Apply +2.5V to +BATT")

    # Apply +2.5V to +BATT test point
    if err := mtib_client.PowerEnable(channel=PowerChannel.DUT, voltage_v=STEP_1_POWER_VOLTAGE_V):
        return f"Step 1 failed to enable power: {err}"

    # a. Verify +VIN < 0.3V (using threshold 0.55V from config)
    vin_success = False
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=VIN_RAIL_STABILIZATION_PERIOD_S):
        vin_voltage, err = mtib_client.AdcRead(channel=TP52_VIN)
        if err:
            return f"Step 1.a failed to read VIN: {err}"

        if vin_voltage > STEP_1A_VIN_THRESHOLD_V:
            time.sleep(VIN_RAIL_CHECK_DELAY_S)
        else:
            vin_success = True
            break

    if not vin_success:
        return f"Step 1.a failed: VIN {vin_voltage}V exceeds threshold {STEP_1A_VIN_THRESHOLD_V}V"

    # d. Verify +BATT current < 10mA
    power_result, err = mtib_client.PowerRead(channel=PowerChannel.DUT)
    if err:
        return f"Step 1.d failed to read current: {err}"

    current_a = power_result.current_ma / 1000.0
    if current_a > STEP_1D_NEAR_ZERO_CURRENT_A:
        return f"Step 1.d failed: Current {current_a}A exceeds threshold {STEP_1D_NEAR_ZERO_CURRENT_A}A"

    logger.info("Step 1 completed successfully")
    return None


def __step_2(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    logger.debug("Step 2: Apply +3.2V to +BATT")

    # Apply +3.2V to +BATT test point
    if err := mtib_client.PowerEnable(channel=PowerChannel.DUT, voltage_v=STEP_2_POWER_VOLTAGE_V):
        return f"Step 2 failed to enable power: {err}"

    # 2.a: Ensure +VIN test point is the same as +BATT
    vin_voltage, err = mtib_client.AdcRead(channel=TP52_VIN)
    if err:
        return f"Step 2.a failed to read VIN: {err}"

    power_result, err = mtib_client.PowerRead(channel=PowerChannel.DUT)
    if err:
        return f"Step 2.a failed to read VBAT: {err}"

    vbatt_voltage = power_result.voltage_v
    if abs(vin_voltage - vbatt_voltage) > STEP_2A_VIN_VBAT_TOLERANCE:
        return (
            f"Step 2.a failed: VIN {vin_voltage}V != VBAT {vbatt_voltage}V (tolerance {STEP_2A_VIN_VBAT_TOLERANCE}V)"
        )

    # 2.b: Ensure regulated +3.3V test point voltage is within 3.2V - 3.4V
    _3v3_voltage, err = mtib_client.AdcRead(channel=TP11_3V3)
    if err:
        return f"Step 2.b failed to read 3V3: {err}"

    if not (STEP_2B_3V3_MIN <= _3v3_voltage <= STEP_2B_3V3_MAX):
        return f"Step 2.b failed: 3V3 {_3v3_voltage}V not in range [{STEP_2B_3V3_MIN}V, {STEP_2B_3V3_MAX}V]"

    # 2.e: Ensure proper power consumption (no short circuits)
    power_result, err = mtib_client.PowerRead(channel=PowerChannel.DUT)
    if err:
        return f"Step 2.e failed to read current: {err}"

    current_a = power_result.current_ma / 1000.0
    if not (STEP_2E_CURRENT_MIN <= current_a <= STEP_2E_CURRENT_MAX):
        return f"Step 2.e failed: Current {current_a}A not in range [{STEP_2E_CURRENT_MIN}A, {STEP_2E_CURRENT_MAX}A]"

    logger.info("Step 2 completed successfully")
    return None


def __step_3(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    logger.debug("Step 3: Apply +3.6V to +BATT")

    # Apply +3.6V to +BATT test point
    if err := mtib_client.PowerEnable(channel=PowerChannel.DUT, voltage_v=STEP_3_POWER_VOLTAGE_V):
        return f"Step 3 failed to enable power: {err}"

    # 3.a: Ensure +VIN test point is the same as +BATT
    vin_voltage, err = mtib_client.AdcRead(channel=TP52_VIN)
    if err:
        return f"Step 3.a failed to read VIN: {err}"

    power_result, err = mtib_client.PowerRead(channel=PowerChannel.DUT)
    if err:
        return f"Step 3.a failed to read VBAT: {err}"

    vbatt_voltage = power_result.voltage_v
    if abs(vin_voltage - vbatt_voltage) > STEP_3A_VIN_VBAT_TOLERANCE:
        return (
            f"Step 3.a failed: VIN {vin_voltage}V != VBAT {vbatt_voltage}V (tolerance {STEP_3A_VIN_VBAT_TOLERANCE}V)"
        )

    # 3.b: Verify current consumption
    power_result, err = mtib_client.PowerRead(channel=PowerChannel.DUT)
    if err:
        return f"Step 3.b failed to read current: {err}"

    current_a = power_result.current_ma / 1000.0
    if not (STEP_3B_CURRENT_MIN <= current_a <= STEP_3B_CURRENT_MAX):
        return f"Step 3.b failed: Current {current_a}A not in range [{STEP_3B_CURRENT_MIN}A, {STEP_3B_CURRENT_MAX}A]"

    logger.info("Step 3 completed successfully")
    return None


# -----------------------------------------------
#                                          Deinit
# ---------------------------------------------*/
def _deinit(logger: Logger, mtib_client: MtibV1Client) -> Optional[str]:
    # Turn off power
    if err := mtib_client.PowerDisable(channel=PowerChannel.DUT):
        return f"Failed to disable DUT power: {err}"

    # Turn off charging power
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
#                                 Electrical Test
# ---------------------------------------------*/
def run_electrical_test(logger: Logger) -> Optional[str]:
    mtib_client = get_mtib_client()
    logger = logger.from_parent(LOG_MODULE)

    test_error = None
    try:
        error = _init(logger, mtib_client)
        if error:
            test_error = f"Failed to initialize electrical test: {error}"
        else:
            error = _run(logger, mtib_client)
            if error:
                test_error = f"Failed to run electrical test: {error}"
            else:
                logger.info("Electrical test completed successfully")
    finally:
        # Always run deinit to stop motion, even if test failed
        error = _deinit(logger, mtib_client)
        if error:
            deinit_error = f"Failed to deinitialize electrical test: {error}"
            if test_error:
                # If we already have an error, log the deinit error but return the original error
                logger.error(deinit_error)
            else:
                test_error = deinit_error

    return test_error
