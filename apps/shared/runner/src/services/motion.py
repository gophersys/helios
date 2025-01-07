import re
import threading
from datetime import datetime
from time import sleep, time
from typing import Tuple

import serial
from corekinect.utils import Logger, SingletonThreadSafeMeta


class MotionDevice(metaclass=SingletonThreadSafeMeta):
    """Abstract base class for motion devices."""

    GRBL_ALARMS = {
        "1": "Hard limit has been triggered. Machine position is likely lost due to sudden halt. Re-homing is highly recommended.",
        "2": "Soft limit alarm. G-code motion target exceeds machine travel. Machine position retained. Alarm may be safely unlocked",
        "3": "Reset while in motion. Machine position is likely lost due to sudden halt. Re-homing is highly recommended.",
        "4": "Probe fail. Probe is not in the expected initial state before starting probe cycle when G38.2 and G38.3 is not triggered and G38.4 and G38.5 is triggered.",
        "5": "Probe fail. Probe did not contact the workpiece within the programmed travel for G38.2 and G38.4.",
        "6": "Homing fail. The active homing cycle was reset.",
        "7": "Homing fail. Safety door was opened during homing cycle.",
        "8": "Homing fail. Pull off travel failed to clear limit switch. Try increasing pull-off setting or check wiring.",
        "9": "Homing fail. Could not find limit switch within search distances. Try increasing max travel, decreasing pull-off distance, or check wiring.",
        "10": "Homing fail. Second dual axis limit switch failed to trigger within configured search distance after first. Try increasing trigger fail distance or check wiring.",
    }

    GRBL_ERRORS = {
        "1": "G-code words consist of a letter and a value. Letter was not found.",
        "2": "Missing the expected G-code word value or numeric value format is not valid.",
        "3": "Grbl '$' system command was not recognized or supported.",
        "4": "Negative value received for an expected positive value.",
        "5": "Homing cycle is not enabled via settings.",
        "6": "Minimum step pulse time must be greater than 3 microseconds.",
        "7": "EEPROM read failed. Auto-restoring affected EEPROM to default values.",
        "8": "Grbl '$' command cannot be used unless Grbl is IDLE. Ensures smooth operation during a job.",
        "9": "G-code commands are locked out during alarm or jog state.",
        "10": "Soft limits cannot be enabled without homing also enabled.",
        "11": "Max characters per line exceeded. Received command line was not executed.",
        "12": "Grbl '$' setting value causes the step rate to exceed the maximum supported.",
        "13": "Safety door detected as opened and door state initiated.",
        "14": "Build info or startup line exceeded EEPROM line length limit. Line not stored.",
        "15": "Jog target exceeds machine travel. Jog command has been ignored.",
        "16": "Jog command has no '=' or contains prohibited g-code.",
        "17": "Laser mode requires PWM output.",
        "20": "Unsupported or invalid g-code command found in block.",
        "21": "More than one g-code command from same modal group found in block.",
        "22": "Feed rate has not yet been set or is undefined.",
        "23": "G-code command requires an integer value.",
        "24": "More than one g-code command that requires axis words found in block.",
        "25": "Repeated g-code word found in block.",
        "26": "No axis words found in block for g-code command or current modal state which requires them.",
        "27": "Line number value is invalid.",
        "28": "G-code command is missing a required value word.",
        "29": "G59.x work coordinate systems are not supported.",
        "30": "G53 only allowed with G0 and G1 motion modes.",
        "31": "Axis words found in block when no command or current modal state uses them.",
        "32": "G2 and G3 arcs require at least one in-plane axis word.",
        "33": "Motion command target is invalid.",
        "34": "Arc radius value is invalid.",
        "35": "G2 and G3 arcs require at least one in-plane offset word.",
        "36": "Unused value words found in block.",
        "37": "G43.1 dynamic tool length offset is not assigned to configured tool length axis.",
        "38": "Tool number greater than max supported value.",
    }

    def __init__(self, serial_port, baudrate=115200) -> None:
        try:
            self.serial_path = serial_port
            self.serial = serial.Serial(self.serial_path, baudrate, timeout=1)
            self.log = Logger.get_test_case_logger()
            self.log.debug(f"Connection established on {self.serial_path}.")
            self._lock = threading.RLock()
            self._stop_motion = threading.Event()
            self._in_motion = False
            self._reset()
            self.home()
            self._verify_and_apply_settings()
        except Exception as e:
            self.log.error(f"Error initializing MotionDevice: {e}")
            self.serial.close()
            raise e

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_motion.set()
        self.home()
        self.serial.close()
        self.log.debug(f"Connection closed on {self.serial_path}.")

    def _verify_and_apply_settings(self):
        """Verify and apply GRBL settings, modal statuses, and coordinate offsets."""
        self._verify_configurations()
        self._verify_status()
        self._verify_offsets()

    def _verify_configurations(self):
        """Verify and apply GRBL configurations ($$)."""
        self.log.debug("Verifying GRBL configurations.")
        current_config = self._get_current_config()
        updated_config = False

        # Compare and update configurations
        for key, expected_value in self.ROD_CONFIG.items():
            current_value = current_config.get(key, None)
            if current_value != expected_value:
                self.log.debug(f"Setting {key} from {current_value} to {expected_value}")
                self._send_command(f"{key}={expected_value}", check_ok=True)
                updated_config = True

        if updated_config:
            self.log.debug("Configurations updated. Restarting the device.")
            self._reset()
            self._send_command("$H")
            self._verify_configurations()
        else:
            self.log.debug("Configuration verification complete.")

    def _get_current_config(self):
        """Retrieve current GRBL configuration as a dictionary."""
        raw_config = self._send_command("$$", check_ok=False, return_data=True)
        config_data = {}
        for line in raw_config.split("\n"):
            if line.startswith("$"):
                key_value = line.split("=")
                if len(key_value) == 2:
                    key, value = key_value
                    config_data[key] = value
                    self.log.debug(f"Current config: {key}={value}")

        if any(key not in config_data for key in self.ROD_CONFIG.keys()):
            self.log.error(
                f"Some configurations are missing... expected: {self.ROD_CONFIG.keys()=}, found: {config_data.keys()=}"
            )
            raise Exception(
                f"Some configurations are missing... expected: {self.ROD_CONFIG.keys()=}, found: {config_data.keys()}"
            )

        return config_data

    def _verify_status(self):
        """Verify the GRBL modal group status ($G) and set if needed."""
        self.log.debug("Verifying GRBL modal statuses.")
        current_status = self._get_current_status()

        update_status = False

        if current_status != self.ROD_STATUS:
            self.log.debug(
                f"Current status {current_status=} differs from expected {self.ROD_STATUS=}. Applying settings."
            )
            self._apply_status()
            update_status = True
        else:
            self.log.debug("Modal statuses are correct.")

        if update_status:
            self.log.debug("Statuses updated. Restarting the device.")
            self._reset()
            self._send_command("$H")
            self._verify_status()
        else:
            self.log.debug("Modal statuses verification complete.")

    def _get_current_status(self):
        """Retrieve current GRBL modal group status."""
        self.serial.reset_input_buffer()
        raw_status = self._send_command("$G", check_ok=False, return_data=True)
        status_line = ""

        for line in raw_status.split("\n"):
            if line.startswith("[GC:"):
                status_line = line
                self.log.debug(f"Current status: {status_line}")

        if not status_line:
            self.log.error(
                f"Failed to read status line. Raw status: {raw_status=}, status_line: {status_line=}, expected: {self.ROD_STATUS=}"
            )
            raise Exception(
                f"Failed to read status line. Raw status: {raw_status=}, status_line: {status_line=}, expected: {self.ROD_STATUS=}"
            )

        return status_line

    def _apply_status(self):
        """Apply the desired GRBL modal group statuses."""
        # Extract modal codes from ROD_STATUS
        modal_codes = self.ROD_STATUS.strip("[]").split(":")[1].split()
        for code in modal_codes:
            if code.startswith(("G", "M", "T", "F", "S")):
                self._send_command(code)
                self.log.debug(f"Applied modal code: {code}")

    def _offset_round(self, value):
        """Custom rounding logic based on the described rules."""
        if abs(value) >= 100:
            # Round to the nearest hundred
            return round(value / 100) * 100
        else:
            # Round to the nearest whole number
            return round(value)

    def _verify_offsets(self):
        """Verify the GRBL coordinate offsets ($#) and set if needed."""
        self.log.debug("Verifying GRBL coordinate offsets.")
        current_offsets = self._get_current_offsets()

        updated_offsets = False

        for key, expected_value in self.ROD_OFFSETS.items():
            current_value = current_offsets.get(key, None)
            for i, value in enumerate(current_value):
                # Apply custom rounding rules
                # _exp_val = self._offset_round(expected_value[i])
                # _cur_val = self._offset_round(value)
                _exp_val = round(expected_value[i], 3)
                _cur_val = round(value, 3)
                if _cur_val != _exp_val:
                    self.log.debug(f"Setting {key} from {_cur_val} to {_exp_val}")
                    self._apply_offset(key, expected_value)
                    updated_offsets = True
            else:
                self.log.debug(f"Offset {key} is correct.")

        if updated_offsets:
            self.log.debug("Offsets updated. Restarting the device.")
            self._reset()
            self._send_command("$H")
            self._verify_status()
        else:
            self.log.debug("Coordinate offsets verification complete.")

    def _get_current_offsets(self):
        """Retrieve current GRBL coordinate offsets as a dictionary."""
        self.serial.reset_input_buffer()
        raw_offsets = self._send_command("$#", check_ok=False, return_data=True)
        offsets = {}

        for line in raw_offsets.split("\n"):
            if line.startswith("["):
                if "PRB" in line:
                    self.log.debug("Skipping PRB (probe position) offset since it is read-only.")
                    continue
                if "TLO" in line:
                    self.log.debug("Skipping TLO (tool length offset) since we don't support it.")
                    continue
                key, values = line[1:-1].split(":")
                if "," in values:
                    values_list = [float(v) for v in values.split(",")]
                    offsets[key] = values_list
                else:
                    offsets[key] = float(values)
                self.log.debug(f"Current offset: {key}={offsets[key]}")
            else:
                self.log.debug(f"Skipping line: {line}")

        if any(key not in offsets for key in self.ROD_OFFSETS.keys()):
            self.log.error(
                f"Some offsets are missing... expected: {self.ROD_OFFSETS.keys()=}, found: {offsets.keys()=}"
            )
            raise Exception(
                f"Some offsets are missing... expected: {self.ROD_OFFSETS.keys()=}, found: {offsets.keys()}"
            )

        return offsets

    def _apply_offset(self, key, value):
        """Apply the desired coordinate offset."""
        if key.startswith("G5"):  # G54-G59 coordinate systems
            # Set coordinate system offset using G10 L2 Pn
            pn = int(key[2:])
            if isinstance(value, list):
                x, y, z = value
                cmd = f"G10 L2 P{pn} X{x} Y{y} Z{z}"
                self._send_command(cmd)
        elif key == "G28":
            # Set G28 positions

            for i, axis in enumerate(self.AVAILABLE_AXIS):
                # Move to each axis position and run G28.1 <axis><position>
                pos = f"{axis}{value[i]}"
                self._send_command(pos)

                # Set the position using G28.1
                cmd = f"G28.1 {pos}"
                self._send_command(cmd)
        elif key == "G30":
            # Set G30 position

            for i, axis in enumerate(self.AVAILABLE_AXIS):
                # Move to each axis position and run G30.1 <axis><position>
                pos = f"{axis}{value[i]}"
                self._send_command(pos)

                # Set the position using G30.1
                cmd = f"G30.1 {pos}"
                self._send_command(cmd)
        elif key == "G92":
            # Set G92 offsets
            x, y, z = value
            cmd = f"G92 X{x} Y{y} Z{z}"
            self._send_command(cmd)
        elif key == "TLO":
            # Tool length offset
            tlo = value
            cmd = f"G43.1 Z{tlo}"
            self._send_command(cmd)
        # Note: PRB (probe position) is read-only and cannot be set.
        else:
            self.log.warning(f"Unknown or unsupported offset key: {key}")

    def _check_for_errors(self, response: str):
        """
        Checks the response string for alarms or errors and raises exceptions if found.
        """
        lower_response = response.lower()
        if "alarm:" in lower_response:
            alarm_code = lower_response.split("alarm:")[1].split("\n")[0].strip()
            alarm_message = self.GRBL_ALARMS.get(alarm_code, "Unknown alarm code.")
            self.log.warning(f"Received ALARM:{alarm_code} - {alarm_message}")
            raise Exception(f"ALARM:{alarm_code} - {alarm_message}")

        if "error:" in lower_response:
            error_code = lower_response.split("error:")[1].split("\n")[0].strip()
            error_message = self.GRBL_ERRORS.get(error_code, "Unknown error code.")
            self.log.error(f"Received error:{error_code} - {error_message}")
            raise Exception(f"Error:{error_code} - {error_message}")

    def _extract_expected_position(self, command: str) -> dict:
        """
        Parses the command to extract expected position values.
        Supports commands like 'G1 X80.0 Y50.0 F1000' or 'X-400'.
        """
        expected_position = {}
        matches = re.findall(r"([XYZABCUVW])([-+]?[0-9]*\.?[0-9]+)", command)
        for axis, value in matches:
            expected_position[axis] = float(value)
        return expected_position

    def _read_reply(self, timeout: float = 5.0) -> str:
        reply = ""
        start_time = time()
        while True:
            if time() - start_time > timeout:
                self.log.error("Timeout waiting for response from device.")
                raise TimeoutError("No response from device within timeout period.")

            try:
                line = self.serial.readline().decode("utf-8").strip()
                if line:
                    self.log.debug(f"Read from device: {line}")
                    reply += line + "\n"
                    if any(keyword in line.lower() for keyword in ["ok", "error", "alarm", "err"]):
                        break
                else:
                    continue  # Keep reading until timeout or a line is received
            except Exception as e:
                self.log.error(f"Error reading from serial port: {e}")
                raise e
        return reply

    def _handle_reply(self, reply: str, command: str, check_ok: bool, reset_after_first_fail: bool):
        # Call the common error checking method
        self._check_for_errors(reply)

        # Continue with the rest of the method
        lower_reply = reply.lower()
        if check_ok and "ok" not in lower_reply:
            self.log.warning(f"Command failed: {command}, Reply: {reply}")
            if reset_after_first_fail:
                self.log.warning("Attempting to reset the device and try again...")
                self._reset()
                self._send_command("$H", reset_after_first_fail=False)
                self._send_command(command, check_ok, reset_after_first_fail=False)
            else:
                self.log.error(f"Command failed: {command}, Reply: {reply}")
                raise Exception(f"Command failed: {command}, Reply: {reply}")

    def _get_current_position(self) -> dict:
        """Retrieve the current position of the device."""
        status_report = self._send_command("?", check_ok=False, return_data=True)
        return self._parse_status_report(status_report)

    def _wait_until_position(self, expected_position: dict, timeout: float = 10.0):
        start_time = time()
        while True:
            if time() - start_time > timeout:
                self.log.error("Timeout waiting for device to reach the expected position.")
                raise TimeoutError("Device did not reach the expected position within timeout period.")

            current_position = self._get_current_position()
            # self.log.debug(f"Current position: {current_position}")

            if self._positions_match(current_position, expected_position):
                self.log.debug(f"Device reached the expected position: {expected_position}")
                break

            sleep(0.1)  # Small delay before the next status check

    def _parse_status_report(self, status_report: str) -> dict:
        """
        Parses the status report from the device and returns the current position.
        Expected status report format: <Idle|MPos:0.000,0.000,0.000|...>
        """
        # Call the common error checking method
        self._check_for_errors(status_report)

        # Proceed with parsing the position
        match = re.search(r"<.*?MPos:([^|>]+)", status_report)
        if not match:
            self.log.error(f"Failed to parse status report: {status_report}")
            raise Exception(f"Failed to parse status report: {status_report}")

        positions = match.group(1).split(",")
        position_dict = {axis: float(pos) for axis, pos in zip(self.AVAILABLE_AXIS, positions)}
        return position_dict

    def _positions_match(self, current_position: dict, expected_position: dict, tolerance: float = None) -> bool:
        if tolerance is None:
            tolerance = abs(float(self.ROD_OFFSETS.get("G54", [0, 0, 0])[0]))

        for axis in expected_position:
            # self.log.debug(f"{abs(current_position[axis] - expected_position[axis])=}, {tolerance=}")
            if abs(current_position[axis] - expected_position[axis]) > tolerance:
                # self.log.debug(f"Position mismatch: {current_position} != {expected_position}")
                return False
        return True

    def _send_command(
        self,
        command: str,
        check_ok: bool = True,
        reset_after_first_fail: bool = True,
        return_data: bool = False,
        verify_position: bool = False,
        timeout: float = 10.0,
        retry_count: int = 0,
        max_retries: int = 1,
    ) -> str | None:
        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write(f"{command}\n".encode())
            self.log.debug(f"Sent to device: {command.strip()}")

            try:
                reply = self._read_reply(timeout=timeout)
                self._handle_reply(reply, command, check_ok, reset_after_first_fail)

                if verify_position:
                    expected_position = self._extract_expected_position(command)
                    self._wait_until_position(expected_position, timeout)
            except Exception as e:
                self.log.warning(f"Error during command execution: {e}")
                if retry_count < max_retries:
                    self.log.warning(
                        "First error encountered. Resetting and re-homing the device, then retrying the command."
                    )
                    sleep(2)
                    self._reset()
                    self.home()
                    # Retry the command with incremented retry_count
                    return self._send_command(
                        command,
                        check_ok=check_ok,
                        reset_after_first_fail=False,
                        return_data=return_data,
                        verify_position=verify_position,
                        timeout=timeout,
                        retry_count=retry_count + 1,
                        max_retries=max_retries,
                    )
                else:
                    self.log.error("Command failed after retry. No further retries will be attempted.")
                    raise e

            if return_data:
                return reply

    def _wait_for_reset(self, time_out_sec=60):
        """Wait for the device to restart."""
        start_time = time()
        while True:
            try:
                line = self.serial.readline().decode("utf-8").strip()
                if line:
                    self.log.debug(f"Reply: {line}")
                    if "Grbl" in line:
                        self.log.debug("Device restarted.")
                        break
                else:
                    if time() - start_time > time_out_sec:
                        self.log.critical("Device restart timed out.")
                        raise ConnectionError("Device restart timed out.")
            except Exception as e:
                self.log.error(f"Error reading from serial port: {e}")
                if time() - start_time > time_out_sec:
                    self.log.critical("Device restart timed out.")
                    raise ConnectionError("Device restart timed out.")
                break

        # Send enter key to clear any pending commands
        self.serial.write(b"\n")
        sleep(1)
        # Clear any initial responses
        while self.serial.in_waiting:
            self.serial.readline()

    def _reset(self):
        """Reset the motion control unit. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _reset_mcu")

    def _continuous_motion(
        self, duration_sec: int | float, num_cycles: int, cycle_time: int | float, positions: Tuple[str, str]
    ):
        try:
            self.log.debug(f"Running continuous motion for {duration_sec} seconds.")
            end_time = time() + duration_sec
            while not self._stop_motion.is_set() and time() < end_time:
                self.trigger_motion(num_cycles=num_cycles, cycle_time=cycle_time, positions=positions)
        except Exception as e:
            self.log.error(f"Exception in continuous motion: {e}")
            self.stop_motion()
            raise e

    def home(self):
        """Home the motion device."""
        self.log.debug("Homing the motion device.")
        self._send_command("$H", reset_after_first_fail=True)

    def trigger_motion(self, num_cycles: int, cycle_time: int | float, positions: Tuple[str, str]):
        self.log.debug(f"Triggering motion for {num_cycles} cycles.")
        for _ in range(num_cycles):

            # Set the in_motion flag
            self._in_motion = True

            for position in positions:
                self._send_command(position, verify_position=True)
                sleep(cycle_time)

            # Reset the in_motion flag
            self._in_motion = False

    def continuous_motion(
        self,
        duration_sec: int | float,
        num_cycles: int,
        cycle_time: int | float,
        positions: Tuple[str, str],
        use_threads: bool = False,
    ):
        """Run continuous motion for a specified duration."""
        try:
            if use_threads:
                self._stop_motion.clear()
                motion_thread = threading.Thread(
                    target=self._continuous_motion, args=(duration_sec, num_cycles, cycle_time, positions)
                )
                motion_thread.start()
            else:
                self._continuous_motion(duration_sec, num_cycles, cycle_time, positions)
        except Exception as e:
            self.log.error(f"Error during continuous motion: {e}")
            self.stop_motion()
            raise e

    def stop_motion(self):
        """Stop the motion device."""
        self._stop_motion.set()

    def is_in_motion(self):
        """Return the current motion status."""
        return self._in_motion


class FluidNCDevice(MotionDevice):
    """Base class for FluidNC devices."""

    def _reset(self):
        """Pulse the reset line for FluidNC."""
        self.log.debug("Restarting the FluidNC device.")
        self.serial.rts = True
        self.serial.dtr = False
        sleep(1)
        self.serial.rts = False
        sleep(1)

        self._wait_for_reset()


class GrblDevice(MotionDevice):
    """Base class for GRBL devices."""

    def _reset(self):
        """Send CTRL-X to reset the MCU."""
        self.log.debug("Restarting the GRBL device.")
        self.serial.write(b"\x18")
        sleep(1)

        self._wait_for_reset()


class DevTable(FluidNCDevice):
    """Class for Development Motion Table (old Ortur laser bed)"""

    SAFE_POSITIONS: Tuple[str, str] = ("X80", "X20")
    ROD_CONFIG = None
    ROD_STATUS = None
    ROD_OFFSETS = None

    def __init__(self, serial_port="/dev/ttyUSB1", baudrate=115200) -> None:
        super().__init__(serial_port, baudrate)

    def trigger_motion(self, num_cycles=1, cycle_time=5):
        super().trigger_motion(num_cycles, cycle_time, self.SAFE_POSITIONS)

    def continuous_motion(
        self,
        duration_sec: int | float = 48,
        num_cycles: int = 1,
        cycle_time: int | float = 5,
        use_threads: bool = False,
    ):
        super().continuous_motion(duration_sec, num_cycles, cycle_time, self.SAFE_POSITIONS, use_threads)


class MotionRod(GrblDevice):
    """Class validation Motion Rod"""

    SAFE_POSITIONS: Tuple[str, str] = ("X-400", "X-100")

    # Device Settings
    AVAILABLE_AXIS = ("X",)
    ROD_CONFIG = {
        "$0": "10",
        "$1": "100",
        "$2": "0",
        "$3": "0",
        "$4": "0",
        "$5": "0",
        "$6": "0",
        "$10": "1",
        "$11": "0.010",
        "$12": "0.002",
        "$13": "0",
        "$20": "1",
        "$21": "1",
        "$22": "1",
        "$23": "0",
        "$24": "500.000",
        "$25": "5000.000",
        "$26": "250",
        "$27": "2.000",
        "$30": "1000",
        "$31": "0",
        "$32": "0",
        "$100": "21.221",
        "$101": "250.000",
        "$102": "250.000",
        "$110": "15000.000",
        "$111": "500.000",
        "$112": "500.000",
        "$120": "6000.000",
        "$121": "10.000",
        "$122": "10.000",
        "$130": "675.000",
        "$131": "200.000",
        "$132": "200.000",
    }
    ROD_STATUS = "[GC:G0 G54 G17 G21 G90 G94 M5 M9 T0 F0 S0]"
    ROD_OFFSETS = {
        "G54": [-1.979, 0.000, 0.000],
        "G55": [0.000, 0.000, 0.000],
        "G56": [0.000, 0.000, 0.000],
        "G57": [0.000, 0.000, 0.000],
        "G58": [0.000, 0.000, 0.000],
        "G59": [0.000, 0.000, 0.000],
        "G28": [0, 0.000, 0.000],
        "G30": [0, 0.000, 0.000],
        "G92": [0.000, 0.000, 0.000],
    }

    def __init__(self, serial_port="/dev/ttyACM0", baudrate=115200) -> None:
        super().__init__(serial_port, baudrate)

    def trigger_motion(self, num_cycles=1, cycle_time=5):
        super().trigger_motion(num_cycles, cycle_time, self.SAFE_POSITIONS)

    def continuous_motion(
        self,
        duration_sec: int | float = 48,
        num_cycles: int = 1,
        cycle_time: int | float = 5,
        use_threads: bool = False,
    ):
        super().continuous_motion(duration_sec, num_cycles, cycle_time, self.SAFE_POSITIONS, use_threads)


if __name__ == "__main__":
    from datetime import datetime

    time_before_motion = datetime.utcnow()
    mr = MotionRod(serial_port="/dev/ttyACM0")
    while True:
        mr.trigger_motion()
        time_before_motion = datetime.utcnow()
        breakpoint
