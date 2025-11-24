# Standard imports
import os
import subprocess
import sys
import time
import yaml
from threading import Lock
from typing import Optional, Tuple

# Third party imports
import serial

# Corekinect imports
from corekinect.utils import Logger

# Project imports
from src.services.gpio import Gpio, Pin, Direction
from xmodem import XMODEM


class FluidNC:
    # Class-level lock for singleton pattern
    _instance_lock = Lock()
    _instance: Optional["FluidNC"] = None

    def __new__(cls, *args, **kwargs):
        """Ensure only one instance of FluidNC exists."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(
        self,
        logger: Logger,
        assets_dir: str,
        serial_port: str,
        reset_pin: str,
    ):
        """
        Initialize the FluidNC object.

        Args:
            logger: The logger to use for the FluidNC object.
            assets_dir: The directory containing the assets for the FluidNC firmware.
            serial_port: The serial port to use for the FluidNC object.
            reset_pin: The GPIO pin used for reset
        """
        # Only initialize once
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.serial_port = serial_port
        self.reset_pin = reset_pin
        self.baudrate = 115200
        self.parity = "N"
        self.rtscts = False
        self.xonxoff = False
        self.timeout = 1
        self.rts = None
        self.dtr = None

        self.command_lock = Lock()  # Mutex for command synchronization
        self.ser: Optional[serial.Serial] = None
        self._initialized = False
        self._is_connected = False
        self.logger: Logger = logger
        self.assets_dir = assets_dir

        # Private attributes
        self._reset_gpio = Gpio(consumer="FluidNC", pin=self.reset_pin, direction=Direction.OUTPUT)
        self._pushback = None  # For XMODEM protocol handling

    def init(self) -> Optional[str]:
        """Initialize the FluidNC object. Safe to call multiple times."""
        if self._initialized:
            return None

        with self._instance_lock:
            self.logger.info("Initializing FluidNC...")

            if self._initialized:  # Double-check pattern
                return None

            # Initialize GPIO
            if err := self._reset_gpio.init():
                return f"Failed to initialize GPIO: {err}"

            # Reset ESP32
            self._reset_gpio.write(0)
            time.sleep(0.1)  # Brief reset pulse still needed
            self._reset_gpio.write(1)
            time.sleep(0.5)  # Allow some time for the reset to complete

            # Initialize serial connection
            if err := self._init_serial():
                return f"Failed to initialize serial connection: {err}"

            # Poll until health check succeeds or timeout
            def wait_for_health(timeout_secs: float = 2.0) -> Tuple[bool, Optional[str]]:
                start_time = time.time()
                while (time.time() - start_time) < timeout_secs:
                    healthy, err = self.health_check(timeout=1)
                    if err:
                        return False, f"Health check failed: {err}"
                    if healthy:
                        return True, None
                return False, "Timed out waiting for health check"

            # Health check
            healthy, err = wait_for_health()
            if not healthy:
                self.logger.info("Health check failed, attempting to flash fluidnc")
                # Deinitialize serial connection before flashing
                self._deinit_serial()

                if err := self._flash_esp32():
                    return f"Failed to flash fluidnc to ESP32: {err}"

                # Reset ESP32
                self._reset_gpio.write(0)
                time.sleep(0.1)  # Brief reset pulse still needed
                self._reset_gpio.write(1)
                time.sleep(3)  # Allow some time for the reset to complete

                # Reinitialize serial connection after flashing
                if err := self._init_serial():
                    return f"Failed to reinitialize serial connection after flash: {err}"

                # Health check after flashing
                healthy, err = wait_for_health(10)
                if not healthy:
                    return f"Failed health check after flashing: {err}"

            # Upload the config file
            if not self.upload_file_xmodem(self.assets_dir + "/config.yaml", "config.yaml"):
                return "Failed to upload config file"

            # Reset ESP32
            self._reset_gpio.write(0)
            time.sleep(0.1)  # Brief reset pulse still needed
            self._reset_gpio.write(1)
            time.sleep(3)  # Allow some time for the reset to complete

            # FluidNC automatically reboots after config upload, so wait for it to boot
            self.logger.info("Waiting for FluidNC to reboot after config upload...")

            # Health check after reboot
            healthy, err = wait_for_health(15)  # Give more time for boot
            if not healthy:
                return f"Failed health check after reboot: {err}"

            # Get the status
            healthy, status = self.get_status()
            if not healthy:
                return f"Failed to get status after reset: {status}"

            self.logger.info(f"FluidNC status: {status}")

            # Check if FluidNC is in alarm state due to configuration errors

            # Go to Home
            self.logger.info("Going to Home...")
            if err := self.home():
                return f"Failed to go to Home: {err}"

            # Health check after home
            healthy, err = wait_for_health()
            if not healthy:
                return f"Failed health check after home: {err}"

            self.logger.info("FluidNC initialized OK")
            self._initialized = True
            return None

    def _flash_esp32(self) -> Optional[str]:
        """Flash the ESP32."""
        start_time = time.time()
        self.logger.warning(
            "No fluidnc firmware detected on ESP32, flashing... (this may take a while), only errors will be logged"
        )

        # Save the original working directory
        original_cwd = os.getcwd()

        # Change to assets directory for script execution
        os.chdir(self.assets_dir + "/fluidNc")
        try:
            result = subprocess.run(
                ["./install-no-radio.sh", self.serial_port],
                capture_output=True,  # This captures both stdout and stderr
                text=True,
                check=False,  # Don't raise exception on non-zero exit
            )

            if result.returncode != 0:
                error_output = result.stdout + result.stderr  # Combine both outputs
                return f"Flash failed: {error_output}"

            self.logger.info(f"FluidNC flashed in {time.time() - start_time:.2f} seconds")

            return None

        except Exception as e:
            return f"Failed to flash fluidnc to ESP32: {e}"
        finally:
            # Always restore the original working directory
            os.chdir(original_cwd)

    def _init_serial(self) -> Optional[str]:
        """Initialize and open the serial connection."""
        try:
            if self._is_connected:
                return None

            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                parity=self.parity,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff,
                timeout=self.timeout,
            )

            if self.rts is not None:
                self.ser.rts = bool(self.rts)
            if self.dtr is not None:
                self.ser.dtr = bool(self.dtr)

            # Clear input and output buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            self._is_connected = True
            return None
        except serial.SerialException as e:
            return f"Failed to open serial port: {e}"
        except Exception as e:
            return f"Unexpected error initializing serial connection: {e}"

    def _deinit_serial(self):
        """Close the serial connection and cleanup."""
        if self.ser and self._is_connected:
            try:
                self.ser.close()
            except Exception as e:
                self.logger.error(f"Error closing serial port: {e}")
            finally:
                self.ser = None
                self._is_connected = False

    def send_command(self, command, wait_response=True, response_timeout=1) -> Tuple[Optional[bool], Optional[str]]:
        """
        Send a command to the device and optionally wait for a response.

        Args:
            command (str): The command string to send.
            wait_response (bool): Whether to wait for a response.
            response_timeout (float): Maximum time to wait for a response (in seconds).

        Returns:
            str: The device response (if wait_response is True); otherwise, None.
        """

        # Uncomment to print any data in the input buffer, helpful for debugging
        # if self.ser.in_waiting:
        #     data = self.ser.read(self.ser.in_waiting)
        #     print(data)

        if not command.endswith("\n"):
            command += "\n"
        self.ser.write(command.encode("utf-8"))
        self.ser.flush()

        # Clear any data in the input buffer
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        if wait_response:
            deadline = time.time() + response_timeout
            response_lines = []
            while time.time() < deadline:
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting)
                    response_lines.append(data.decode("utf-8", errors="replace"))

                    # Check if we have a complete response (look for "ok" or "error")
                    full_response = "".join(response_lines)
                    if "ok" in full_response.lower() or "error" in full_response.lower():
                        return True, full_response
                time.sleep(0.05)

            # Join all response lines and clean up
            full_response = "".join(response_lines).strip()
            return False, full_response if full_response else None
        return True, "No response received from FluidNC"

    def home(self, retries: int = 3) -> Optional[str]:
        """Home the FluidNC with optional retry mechanism.

        Args:
            retries: Number of times to retry homing if it fails (default: 3)

        Returns:
            Optional[str]: Error message if homing failed after all retries, None if successful
        """
        last_error = None

        for attempt in range(retries):
            if attempt > 0:
                self.logger.info(f"Homing attempt {attempt + 1}/{retries}")
                time.sleep(1)  # Brief delay between retries

            success, response = self.send_command("$h", wait_response=True, response_timeout=10)
            if not success:
                last_error = f"Failed to home FluidNC: {response}"
                self.logger.warning(f"Homing attempt {attempt + 1} failed: {last_error}")
                continue

            # Parse the response to determine if homing was successful
            response_lower = response.lower()

            # Check for error indicators FIRST (before success indicators)
            if "alarm:" in response_lower or "homing fail" in response_lower or "error" in response_lower:
                last_error = f"Homing failed: {response}"
                self.logger.warning(f"Homing attempt {attempt + 1} failed: {last_error}")
                continue

            # Check for success indicators
            if "homed:y" in response_lower:
                self.logger.info(f"Homing successful on attempt {attempt + 1}")
                return None  # Success - no error

            # If we get here, it's an unknown response - treat as success if it contains "homed"
            if "homed" in response_lower:
                self.logger.info(f"Homing successful on attempt {attempt + 1}")
                return None  # Success - no error

            # Check if we got "ok" but no clear success/failure indicators
            if "ok" in response_lower:
                # If we only got "ok" without "homed:y", it might be a failure
                # Look for any alarm or error messages in the full response
                if "alarm" in response_lower or "error" in response_lower:
                    last_error = f"Homing failed: {response}"
                    self.logger.warning(f"Homing attempt {attempt + 1} failed: {last_error}")
                    continue
                # If no alarms/errors, assume success
                self.logger.info(f"Homing successful on attempt {attempt + 1}")
                return None

            # Unknown response - treat as error for this attempt
            last_error = f"Unknown response from FluidNC: {response}"
            self.logger.warning(f"Homing attempt {attempt + 1} failed: {last_error}")

        # If we get here, all retries failed
        self.logger.error(f"Homing failed after {retries} attempts. Last error: {last_error}")
        return f"Homing failed after {retries} attempts. Last error: {last_error}"

    def _set_acceleration_to_config(self, axis: str, acceleration: float) -> Optional[str]:
        """Set the acceleration to the config file."""
        try:
            # Modify the config file in place
            with open(self.assets_dir + "/config.yaml", "r") as f:
                config = yaml.safe_load(f)
            config["axes"][axis.lower()]["acceleration_mm_per_sec2"] = str(acceleration)

            # Save the config file
            with open(self.assets_dir + "/config.yaml", "w") as f:
                yaml.dump(config, f)

            # Upload the config file
            if not self.upload_file_xmodem(self.assets_dir + "/config.yaml", "config.yaml"):
                return "Failed to upload config file"

            # Reset ESP32
            self._reset_gpio.write(0)
            time.sleep(0.1)  # Brief reset pulse still needed
            self._reset_gpio.write(1)
            time.sleep(3)  # Allow some time for the reset to complete

            # Health check after reset
            healthy, err = self.health_check(1)
            if not healthy:
                return f"Failed health check after reset: {err}"

            return None
        except Exception as e:
            return f"Failed to set acceleration {axis} to config: {e}"

    def _get_acceleration_from_config(self, axis: str) -> Tuple[Optional[float], Optional[str]]:
        """Get the acceleration from the config file."""
        try:
            with open(self.assets_dir + "/config.yaml", "r") as f:
                config = yaml.safe_load(f)
            return float(config["axes"][axis.lower()]["acceleration_mm_per_sec2"]), None
        except Exception as e:
            return None, f"Failed to get acceleration {axis} from config: {e}"

    def _get_max_distance_from_config(self, axis: str) -> Tuple[Optional[float], Optional[str]]:
        """Get the max distance from the config file."""
        try:
            with open(self.assets_dir + "/config.yaml", "r") as f:
                config = yaml.safe_load(f)
            return float(config["axes"][axis.lower()]["max_travel_mm"]), None
        except Exception as e:
            return None, f"Failed to get max distance {axis} from config: {e}"

    def _get_max_speed_from_config(self, axis: str) -> Tuple[Optional[float], Optional[str]]:
        """Get the max speed from the config file."""
        try:
            with open(self.assets_dir + "/config.yaml", "r") as f:
                config = yaml.safe_load(f)
            return float(config["axes"][axis.lower()]["max_rate_mm_per_min"]), None
        except Exception as e:
            return None, f"Failed to get max speed {axis} from config: {e}"

    def bounce_axis(
        self,
        axis: str,
        duration_seconds: float,
        dwell_seconds: float,
        speed_mm_s: float,
        distance_mm: float,
        accel_mm_s2: float,
        progress_callback=None,
    ) -> Optional[str]:
        """Bounce an axis by a given distance or duration.

        Args:
            axis: Axis to move (X, Y, Z)
            duration_seconds: Duration of motion in seconds (ignored if distance_mm > 0)
            dwell_seconds: Dwell time in seconds
            speed_mm_s: Speed in mm/s
            distance_mm: Distance in mm (if > 0, overrides duration-based calculation)
            progress_callback: Optional callback function to report progress

        Returns:
            Optional[str]: Error message if motion failed, None if successful
        """
        # Check that the acceleration matches, otherwise set it to the config
        current_accel, err = self._get_acceleration_from_config(axis)
        if err:
            return f"Failed to get acceleration {axis} from config: {err}"

        self.logger.info(f"Current acceleration {axis}: {current_accel} mm/s^2, requested: {accel_mm_s2} mm/s^2")
        if current_accel != accel_mm_s2:
            if err := self._set_acceleration_to_config(axis, accel_mm_s2):
                return f"Failed to set acceleration {axis} to {accel_mm_s2} mm/s^2: {err}"

        # Home the axis
        err = self.home()
        if err:
            return f"Failed to home {axis}: {err}"

        # Get max distance from config
        max_distance, err = self._get_max_distance_from_config(axis)
        if err:
            return f"Failed to get max distance {axis} from config: {err}"

        # Convert speed from mm/s to mm/min for G-code (F parameter)
        speed_mm_per_min = speed_mm_s * 60

        # Calculate target distance based on mode
        if distance_mm > 0:
            # Distance-based: use the specified distance
            target_distance = distance_mm
            target_duration = target_distance / speed_mm_s if speed_mm_s > 0 else 1.0
        else:
            # Duration-based: calculate distance from duration
            target_distance = duration_seconds * speed_mm_s
            target_duration = duration_seconds

        self.logger.info(
            f"Starting bounce motion: axis={axis}, target_distance={target_distance}mm, "
            f"speed={speed_mm_s}mm/s ({speed_mm_per_min}mm/min), max_travel={max_distance}mm"
        )

        # Set relative positioning mode
        err = self._set_relative_mode()
        if err:
            return err

        start_time = time.time()
        total_distance_covered = 0.0
        last_reported_distance = 0.0  # Track last reported distance for progress callbacks
        direction = 1  # 1 for forward, -1 for reverse
        iteration = 0

        # Calculate how much to move per iteration (don't exceed max_travel)
        move_distance = min(target_distance, max_distance)

        try:
            # Loop condition depends on motion mode
            if distance_mm > 0:
                # Distance-based: continue until distance is covered
                should_continue = lambda: total_distance_covered < target_distance
            else:
                # Duration-based: continue until time duration is reached
                should_continue = lambda: (time.time() - start_time) < target_duration

            while should_continue():
                iteration += 1
                self.logger.info(f"=== Bounce iteration {iteration} ===")

                # Calculate remaining distance for this iteration
                remaining = target_distance - total_distance_covered
                current_move = min(move_distance, remaining)

                # Only move forward (direction = 1)
                self.logger.info(
                    f"Moving {axis}+{current_move:.2f}mm (remaining: {remaining:.2f}mm, "
                    f"total covered: {total_distance_covered:.2f}mm)"
                )

                # Send G-code command
                gcode = f"G01 {axis}{current_move:.2f} F{speed_mm_per_min:.0f}"
                success, response = self.send_command(gcode, wait_response=False, response_timeout=1)
                if not success:
                    return f"Failed to send G-code command: {response}"

                # Wait for motion to complete
                err = self._wait_for_motion_completion(timeout_seconds=60)
                if err:
                    return f"Motion failed: {err}"

                # Update total distance covered (forward move)
                total_distance_covered += current_move

                # Report progress if we've covered 500mm since last report
                if progress_callback and (total_distance_covered - last_reported_distance >= 500):
                    elapsed = time.time() - start_time
                    progress_data = {
                        "time_elapsed_seconds": int(elapsed),
                        "distance_covered_mm": total_distance_covered,
                    }
                    if distance_mm > 0:
                        progress_data["distance_remaining_mm"] = max(target_distance - total_distance_covered, 0)
                        progress_data["target_distance_mm"] = int(target_distance)
                    else:
                        progress_data["time_remaining_seconds"] = int(max(target_duration - elapsed, 0))
                        progress_data["target_duration_seconds"] = int(target_duration)
                    progress_callback(progress_data)
                    last_reported_distance = total_distance_covered

                # Check if we're done after forward move (for distance-based only)
                # For duration-based, we need to check elapsed time, so we continue the loop
                if distance_mm > 0 and total_distance_covered >= target_distance:
                    # Report final progress
                    if progress_callback:
                        elapsed = time.time() - start_time
                        progress_data = {
                            "time_elapsed_seconds": int(elapsed),
                            "distance_covered_mm": total_distance_covered,
                            "distance_remaining_mm": 0,
                            "target_distance_mm": int(target_distance),
                        }
                        progress_callback(progress_data)
                    break

                # Move back to complete the bounce
                self.logger.info(f"Moving back {axis}-{current_move:.2f}mm")

                gcode_back = f"G01 {axis}-{current_move:.2f} F{speed_mm_per_min:.0f}"
                success, response = self.send_command(gcode_back, wait_response=False, response_timeout=1)
                if not success:
                    return f"Failed to send back G-code command: {response}"

                # Wait for back motion to complete
                err = self._wait_for_motion_completion(timeout_seconds=60)
                if err:
                    return f"Back motion failed: {err}"

                # Add back movement to total distance
                total_distance_covered += current_move

                # Check elapsed time for duration-based motion
                elapsed = time.time() - start_time

                # Report progress after back move if we've covered 500mm since last report
                if progress_callback and (total_distance_covered - last_reported_distance >= 500):
                    progress_data = {
                        "time_elapsed_seconds": int(elapsed),
                        "distance_covered_mm": total_distance_covered,
                    }
                    if distance_mm > 0:
                        progress_data["distance_remaining_mm"] = max(target_distance - total_distance_covered, 0)
                        progress_data["target_distance_mm"] = int(target_distance)
                    else:
                        progress_data["time_remaining_seconds"] = int(max(target_duration - elapsed, 0))
                        progress_data["target_duration_seconds"] = int(target_duration)
                    progress_callback(progress_data)
                    last_reported_distance = total_distance_covered

                # For duration-based motion, check if we've reached the target duration
                if distance_mm <= 0 and elapsed >= target_duration:
                    self.logger.info(
                        f"Duration-based motion completed: elapsed {elapsed:.2f}s >= target {target_duration:.2f}s"
                    )
                    break

                # Add dwell time if specified
                if dwell_seconds > 0:
                    self.logger.info(f"Dwelling for {dwell_seconds}s...")
                    time.sleep(dwell_seconds)

            # Restore absolute positioning mode
            err = self._set_absolute_mode()
            if err:
                return err

            elapsed_time = time.time() - start_time

            # Report final progress if we haven't reported the final distance yet
            if progress_callback and total_distance_covered != last_reported_distance:
                progress_data = {
                    "time_elapsed_seconds": int(elapsed_time),
                    "distance_covered_mm": total_distance_covered,
                }
                if distance_mm > 0:
                    progress_data["distance_remaining_mm"] = 0
                    progress_data["target_distance_mm"] = int(target_distance)
                else:
                    progress_data["time_remaining_seconds"] = 0
                    progress_data["target_duration_seconds"] = int(target_duration)
                progress_callback(progress_data)

            self.logger.info(
                f"Bounce motion completed: covered {total_distance_covered:.2f}mm in "
                f"{elapsed_time:.2f}s over {iteration} iterations"
            )

            return None

        except Exception as e:
            # Make sure to restore absolute mode even on error
            self._set_absolute_mode()
            return f"Error in bounce_axis: {str(e)}"

    def _reset_esp32_and_recover(self) -> Optional[str]:
        """
        Reset the ESP32 and wait for it to recover.
        This handles cases where the ESP32 goes into a corrupted state.
        """
        self.logger.warning("ESP32 appears to be in corrupted state, attempting reset and recovery...")

        try:
            # Close serial connection
            # self._deinit_serial()

            # Reset ESP32 using GPIO
            self.logger.info("Resetting ESP32 via GPIO...")
            self._reset_gpio.write(0)
            time.sleep(0.1)  # Brief reset pulse still needed
            self._reset_gpio.write(1)
            time.sleep(0.5)  # Allow some time for the reset to complete

            # # Reinitialize serial connection
            # self.logger.info("Reinitializing serial connection...")
            # if err := self._init_serial():
            #     return f"Failed to reinitialize serial after reset: {err}"

            # Wait for FluidNC to boot and respond
            self.logger.info("Waiting for FluidNC to boot...")
            time.sleep(2)

            # Test communication
            for attempt in range(5):
                success, status = self.get_status()
                if success and status in ["IDLE", "RUN", "ALARM"]:
                    self.logger.info(f"ESP32 recovered successfully, status: {status}")
                    return None
                self.logger.info(f"Recovery attempt {attempt + 1}/5, waiting...")
                time.sleep(1)

            return "ESP32 failed to recover after reset"

        except Exception as e:
            return f"Error during ESP32 reset and recovery: {e}"

    def _clear_serial_buffer(self):
        """Clear any corrupted or pending data in the serial buffer."""
        if self.ser and self.ser.is_open:
            try:
                # Clear input buffer
                self.ser.reset_input_buffer()
                # Clear output buffer
                self.ser.reset_output_buffer()
                # Read any remaining data
                while self.ser.in_waiting > 0:
                    self.ser.read(self.ser.in_waiting)
            except Exception as e:
                self.logger.warning(f"Error clearing serial buffer: {e}")

    def _set_relative_mode(self) -> Optional[str]:
        """Set FluidNC to relative positioning mode."""
        success, response = self.send_command("G91", wait_response=False, response_timeout=1)
        self.logger.info("Set relative positioning mode (G91)")
        return None

    def _set_absolute_mode(self) -> Optional[str]:
        """Set FluidNC to absolute positioning mode."""
        success, response = self.send_command("G90", wait_response=False, response_timeout=1)
        self.logger.info("Set absolute positioning mode (G90)")
        return None

    def _wait_for_motion_completion(self, timeout_seconds: float = 30.0) -> Optional[str]:
        """
        Wait for motion to complete by monitoring the status.

        Args:
            timeout_seconds: Maximum time to wait for motion completion

        Returns:
            Optional[str]: Error message if motion failed or timed out, None if successful
        """
        start_time = time.time()
        consecutive_failures = 0
        max_consecutive_failures = 3

        # First, wait for status to become RUN
        self.logger.info("Waiting for motion to start...")
        while (time.time() - start_time) < timeout_seconds:
            success, status = self.get_status()
            if not success:
                consecutive_failures += 1
                self.logger.warning(
                    f"Status check failed ({consecutive_failures}/{max_consecutive_failures}): {status}"
                )
                if consecutive_failures >= max_consecutive_failures:
                    # Try to reset and recover the ESP32
                    self.logger.error("Too many consecutive failures, attempting ESP32 reset and recovery...")
                    err = self._reset_esp32_and_recover()
                    if err:
                        return f"Failed to recover ESP32: {err}"
                    # Reset failure counter and continue
                    consecutive_failures = 0
                    continue
                time.sleep(0.5)  # Wait longer on failure
                continue

            consecutive_failures = 0  # Reset on success

            if status == "RUN":
                self.logger.info("Motion started successfully")
                break
            elif status in ["ALARM", "ERROR"]:
                return f"Motion failed with status: {status}"

            time.sleep(0.5)  # Increased to 1.0s to reduce communication load
        else:
            return f"Timeout waiting for motion to start after {timeout_seconds}s"

        # Now wait for motion to complete (status to return to IDLE)
        self.logger.info("Waiting for motion to complete...")
        consecutive_failures = 0

        while (time.time() - start_time) < timeout_seconds:
            success, status = self.get_status()
            time.sleep(0.1)
            if not success:
                consecutive_failures += 1
                self.logger.warning(
                    f"Status check failed ({consecutive_failures}/{max_consecutive_failures}): {status}"
                )
                if consecutive_failures >= max_consecutive_failures:
                    # Try to reset and recover the ESP32
                    self.logger.error(
                        "Too many consecutive failures during motion completion, attempting ESP32 reset and recovery..."
                    )
                    err = self._reset_esp32_and_recover()
                    if err:
                        return f"Failed to recover ESP32: {err}"
                    # Reset failure counter and continue
                    consecutive_failures = 0
                    continue
                time.sleep(0.01)  # Wait longer on failure
                continue

            consecutive_failures = 0  # Reset on success

            if status == "IDLE":
                self.logger.info("Motion completed successfully")
                return None
            elif status in ["ALARM", "ERROR"]:
                return f"Motion failed with status: {status}"

            time.sleep(0.5)  # Increased to 1.0s to reduce communication load
        else:
            return f"Timeout waiting for motion to complete after {timeout_seconds}s"

    def start(
        self,
        duration_seconds: float,
        dwell_seconds: float,
        speed_mm_s: float,
        distance_mm: float,
        accel_mm_s2: float,
        progress_callback=None,
    ) -> Optional[str]:
        """Start motion on the Y axis (wrapper for bounce_axis).

        Args:
            duration_seconds: Duration of motion in seconds (ignored if distance_mm > 0)
            dwell_seconds: Dwell time in seconds
            speed_mm_s: Speed in mm/s
            distance_mm: Distance in mm (if > 0, overrides duration-based calculation)
            accel_mm_s2: Acceleration in mm/s^2
            progress_callback: Optional callback function to report progress
        Returns:
            Optional[str]: Error message if motion failed, None if successful
        """
        return self.bounce_axis(
            "X", duration_seconds, dwell_seconds, speed_mm_s, distance_mm, accel_mm_s2, progress_callback
        )

    def check_config_errors(self) -> Optional[str]:
        """Check for configuration errors in FluidNC.

        Returns:
            Optional[str]: Error message if configuration errors found, None if OK
        """
        try:
            # Send $ command to get configuration status
            success, response = self.send_command("$", wait_response=True, response_timeout=2)
            if not success:
                return f"Failed to get configuration status: {response}"

            # Look for error indicators in the response
            response_lower = response.lower()
            if "error:" in response_lower or "configuration is invalid" in response_lower:
                return f"Configuration errors detected: {response}"

            return None  # No configuration errors
        except Exception as e:
            return f"Error checking configuration: {e}"

    def get_status(self) -> Tuple[Optional[bool], Optional[str]]:
        """Get the status of the FluidNC with error recovery."""
        # Clear any corrupted data in the buffer first
        self._clear_serial_buffer()

        success, response = self.send_command("?", wait_response=True, response_timeout=2)
        if not success:
            return False, f"Failed to get status of FluidNC: {response}"

        # Check for corrupted response (contains non-printable characters)
        if response and any(ord(c) < 32 and c not in "\r\n\t" for c in response):
            self.logger.warning("Received corrupted status response, attempting ESP32 reset and recovery")
            err = self._reset_esp32_and_recover()
            if err:
                return False, f"Failed to recover from corruption: {err}"
            # Retry status check after recovery
            success, response = self.send_command("?", wait_response=True, response_timeout=2)
            if not success:
                return False, f"Failed to get status after corruption recovery: {response}"

        # Parse just the state from the response
        try:
            state = self._parse_status_state(response)
            return True, state
        except Exception as e:
            return False, f"Failed to parse status response: {e}"

    def _parse_status_state(self, response: str) -> str:
        """Parse just the state from FluidNC status response.

        Args:
            response: Raw status response from FluidNC

        Returns:
            str: State (IDLE, RUN, ALARM, etc.)
        """
        # Clean up the response - remove \r characters and split by \n
        cleaned_response = response.replace("\r", "").strip()
        lines = cleaned_response.split("\n")

        for line in reversed(lines):
            if line.startswith("<") and line.endswith(">"):
                status_line = line[1:-1]  # Remove < and >
                # Get the first part before any |
                state = status_line.split("|")[0]
                return state.upper()

        return "UNKNOWN"

    def health_check(self, timeout=1) -> Tuple[Optional[bool], Optional[str]]:
        """
        Perform a health check by sending an Enter (newline) to the device and checking for "OK" in the response.

        Args:
            timeout (float): Maximum time to wait for a response.

        Returns:
            tuple: (bool, str) where the boolean indicates whether the health check passed,
                and the string is the actual response.
        """
        # Sending an empty command (i.e. just a newline) to simulate pressing Enter.
        success, response = self.send_command("\n", wait_response=True, response_timeout=timeout)
        if not success:
            return False, response
        return True, None

    def set_break(self, state):
        """
        Set the BREAK condition on the serial line.

        Args:
            state (bool): Desired BREAK condition.

        Returns:
            bool: The new BREAK condition.
        """
        self.ser.break_condition = bool(state)
        return self.ser.break_condition

    def get_port_settings(self):
        """
        Retrieve the current serial port settings.

        Returns:
            dict: A dictionary containing the current port settings.
        """
        return {
            "port": self.ser.port,
            "baudrate": self.ser.baudrate,
            "bytesize": self.ser.bytesize,
            "parity": self.ser.parity,
            "stopbits": self.ser.stopbits,
            "rts": self.ser.rts,
            "dtr": self.ser.dtr,
            "rtscts": self.ser.rtscts,
            "xonxoff": self.ser.xonxoff,
            "break_condition": self.ser.break_condition,
        }

    def upload_file_xmodem(self, local_filename, destname):
        """
        Upload a file to the FluidNC device using the XMODEM protocol.

        The device is expected to enter XMODEM reception mode when it receives a command
        in the following format:
            "$Xmodem/Receive=<destname>"

        Args:
            local_filename (str): Path to the local file to upload.
            destname (str): The destination filename on the device.

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        try:
            with open(local_filename, "rb") as f:
                # Tell the device to prepare for a XMODEM upload.
                command = f"$Xmodem/Receive={destname}"

                self.logger.info(f"Sending command: {command}")

                # Send the command directly without waiting for a response
                # because FluidNC will immediately enter XMODEM mode
                if not command.endswith("\n"):
                    command += "\n"
                self.ser.write(command.encode("utf-8"))
                self.ser.flush()

                # Wait a bit for the device to enter XMODEM mode
                time.sleep(1.0)

                # Clear any pending data and set appropriate timeout for XMODEM
                self.ser.timeout = 0.5
                while True:
                    data = self.ser.read_until()
                    if not data:
                        break

                # Initialize and perform the XMODEM transfer with proper mode
                modem = XMODEM(self._getc, self._putc, mode="xmodem")
                success = modem.send(f, callback=self._xmodem_progress)
                if not success:
                    return False, "XMODEM transfer failed"

                self.logger.info("XMODEM upload completed successfully")

                # Verify the uploaded file by checking its contents
                time.sleep(1.0)  # Give FluidNC time to process the file
                verify_success, verify_response = self.send_command(
                    "$localfs/Show=config.yaml", wait_response=True, response_timeout=5
                )
                if verify_success:
                    self.logger.info("Configuration file uploaded and verified successfully")
                else:
                    self.logger.warning(f"Could not verify uploaded config file: {verify_response}")

                return True, None
        except Exception as e:
            return False, f"Error during file upload: {e}"

    def _getc(self, size, timeout=1):
        """
        Internal helper for XMODEM: read bytes from the serial port.
        Handles pushback for protocol responses.
        """
        if not self.ser or not self.ser.is_open:
            return None

        # Check for pushback first
        if self._pushback is not None:
            pushback_data = self._pushback
            self._pushback = None
            return pushback_data

        self.ser.timeout = timeout
        try:
            data = self.ser.read(size)
            return data if data else None
        except Exception as e:
            self.logger.error(f"Error reading from serial port: {e}")
            return None

    def _putc(self, data, timeout=1):
        """
        Internal helper for XMODEM: write bytes to the serial port.
        """
        if not self.ser or not self.ser.is_open:
            return 0

        try:
            written = self.ser.write(data)
            self.ser.flush()  # Ensure data is sent immediately
            return written
        except Exception as e:
            self.logger.error(f"Error writing to serial port: {e}")
            return 0

    def _xmodem_progress(self, packets, good, bad):
        """
        Callback for XMODEM transfer progress.
        """
        self.logger.info(f"XMODEM progress: {packets} packets, {good} good, {bad} bad")

    def restart(self) -> Optional[str]:
        """Restart FluidNC."""
        success, response = self.send_command("$bye", wait_response=True, response_timeout=1)
        if not success:
            return f"Failed to restart FluidNC: {response}"
        time.sleep(2)  # Wait for reboot
        return None

    def stop(self) -> Optional[str]:
        """Emergency stop all motion."""
        self.logger.info("Sending emergency stop command to FluidNC")

        if not self.ser or not self._is_connected:
            return "Serial connection not available"

        try:
            # Send emergency stop character (Ctrl+X = \x18)
            # This is the standard G-code emergency stop command
            self.ser.write(b"\x18")
            self.ser.flush()
            return None
        except Exception as e:
            return f"Error sending stop command: {e}"

    def deinit(self):
        """Deinitialize the FluidNC object."""
        with self._instance_lock:
            self._deinit_serial()
            self._initialized = False

    def __del__(self):
        """Cleanup when object is destroyed."""
        if hasattr(self, "ser") and self.ser:
            self.ser.close()
