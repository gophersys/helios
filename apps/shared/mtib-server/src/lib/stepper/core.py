# Standard imports
import os
import time
import subprocess
from typing import Tuple

# Third party imports
import serial
from threading import Lock
from typing import Optional
import sys
from serial.tools import list_ports

# Corekinect imports
from corekinect.utils import Logger

# Project imports
from ..gpio import Pin, Gpio, Direction
from ..fluidterm import Miniterm, ask_for_port

from .fluidnc_cmd import FluidNCController


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
        reset_pin: Pin,
        baudrate: int = 115200,
    ):
        """
        Initialize the FluidNC object.

        Args:
            logger: The logger to use for the FluidNC object.
            assets_dir: The directory containing the assets for the FluidNC firmware.
            serial_port: The serial port to use for the FluidNC object.
            reset_pin: The GPIO pin used for reset
            baudrate: The baudrate for the serial connection
        """
        # Only initialize once
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.serial_port = serial_port
        self.reset_pin = reset_pin
        self.baudrate = baudrate
        self.command_lock = Lock()  # Mutex for command synchronization
        self.ser: Optional[serial.Serial] = None
        self.miniterm: Optional[Miniterm] = None
        self._initialized = False
        self.logger: Logger = logger
        self.assets_dir = assets_dir

        # Private attributes
        self._reset_gpio = Gpio(consumer="FluidNC", pin=self.reset_pin, direction=Direction.OUTPUT)
        self.controller: Optional[FluidNCController] = None

    def init(self) -> Optional[str]:
        """Initialize the FluidNC object. Safe to call multiple times."""
        if self._initialized:
            return None

        with self._instance_lock:
            if self._initialized:  # Double-check pattern
                return None

            # Initialize GPIO
            if err := self._reset_gpio.init():
                return f"Failed to initialize GPIO: {err}"

            # Reset ESP32
            self._reset_gpio.write(0)
            time.sleep(0.1)  # Brief reset pulse still needed
            self._reset_gpio.write(1)

            # Create FluidNC controller if not exists
            if self.controller is None:
                self.controller = FluidNCController(
                    logger=self.logger,
                    port=self.serial_port,
                    baudrate=self.baudrate,
                )

            # Initialize serial connection
            if err := self.controller.init():
                return f"Failed to initialize serial connection: {err}"

            # Poll until health check succeeds or timeout
            def wait_for_health(timeout_secs: float = 2.0) -> Tuple[bool, Optional[str]]:
                start_time = time.time()
                while (time.time() - start_time) < timeout_secs:
                    healthy, resp = self.controller.health_check(timeout=0.1)
                    if healthy:
                        return True, None
                    time.sleep(0.1)  # Small delay between retries
                return False, "Timed out waiting for health check"

            # Health check
            healthy, err = wait_for_health()
            if not healthy:
                self.logger.info("Health check failed, attempting to flash fluidnc")
                # Deinitialize serial connection before flashing
                self.controller.deinit()

                if err := self.flash_esp32():
                    return f"Failed to flash fluidnc to ESP32: {err}"

                # Reinitialize serial connection after flashing
                if err := self.controller.init():
                    return f"Failed to reinitialize serial connection after flash: {err}"

                # Health check after flashing
                healthy, err = wait_for_health()
                if not healthy:
                    return f"Failed health check after flashing: {err}"

            self.logger.debug("FluidNC initialized OK")
            self._initialized = True
            return None

    def flash_esp32(self) -> Optional[str]:
        """Flash the ESP32."""
        start_time = time.time()
        self.logger.warning(
            "No fluidnc firmware detected on ESP32, flashing... (this may take a while), only errors will be logged"
        )

        # Change to assets directory for script execution
        os.chdir(self.assets_dir)
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

    def send_command(self, cmd: str) -> Tuple[Optional[str], str]:
        """Send a command to FluidNC and get response.

        Args:
            cmd: Command to send

        Returns:
            Tuple of (error, response)
        """
        if not self._initialized or not self.ser:
            return "FluidNC not initialized", ""

        with self.command_lock:
            try:
                # Send command
                self.ser.write(f"{cmd}\n".encode())
                self.ser.flush()

                # Read response
                response = ""
                while True:
                    line = self.ser.readline().decode().strip()
                    if not line:
                        break
                    response += line + "\n"
                    if line == "ok" or line.startswith("error:"):
                        break

                return None, response.strip()
            except Exception as e:
                return f"Failed to send command: {e}", ""

    def check_status(self) -> Tuple[Optional[str], dict]:
        """Get FluidNC status.

        Returns:
            Tuple of (error, status_dict)
        """
        err, response = self.send_command("?")
        if err:
            return err, {}

        # Parse status response
        try:
            status = {}
            # Example parsing, adjust based on your needs
            for line in response.split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    status[key.strip()] = value.strip()
            return None, status
        except Exception as e:
            return f"Failed to parse status: {e}", {}

    def restart(self) -> Optional[str]:
        """Restart FluidNC."""
        err, _ = self.send_command("$bye")
        if err:
            return err
        time.sleep(2)  # Wait for reboot
        return None

    def start_terminal(self) -> Optional[str]:
        """Start an interactive terminal session."""
        if not self._initialized or not self.ser:
            return "FluidNC not initialized"

        try:
            # Create and configure miniterm
            self.miniterm = Miniterm(self.ser, echo=True, eol="lf", filters=["default"])

            # Configure control characters
            self.miniterm.exit_character = chr(0x1D)  # GS/CTRL+]
            self.miniterm.menu_character = chr(0x14)  # CTRL+T
            self.miniterm.raw = False
            self.miniterm.set_rx_encoding("UTF-8")
            self.miniterm.set_tx_encoding("UTF-8")

            # Print connection info
            sys.stderr.write(
                f"--- FluidNC Terminal on {self.ser.name} "
                f"{self.ser.baudrate},{self.ser.bytesize},{self.ser.parity},{self.ser.stopbits} ---\n"
            )
            sys.stderr.write("--- Quit: Ctrl+] | Menu: Ctrl+T | Help: Ctrl+T H ---\n")

            # Start terminal
            self.miniterm.start()
            try:
                self.miniterm.join(True)
            except KeyboardInterrupt:
                pass

            return None

        except Exception as e:
            return f"Terminal error: {e}"
        finally:
            if self.miniterm:
                self.miniterm.close()
                self.miniterm = None

    def deinit(self):
        """Deinitialize the FluidNC object."""
        with self._instance_lock:
            if self.controller:
                self.controller.deinit()
            self._initialized = False

    def __del__(self):
        """Cleanup when object is destroyed."""
        if hasattr(self, "ser") and self.ser:
            self.ser.close()


class StepperMotor:
    def __init__(
        self,
        fluidnc: FluidNC,
    ):
        self.fluidnc = fluidnc

    def init(self) -> Optional[str]:
        """
        Initialize the StepperMotor object.
        """
        # Ensure that the FluidNC instance is initialized
        if err := self.fluidnc.init():
            return f"Failed to initialize FluidNC: {err}"


# Example usage:
if __name__ == "__main__":
    fluidnc = FluidNC("/dev/ttyUSB0", Pin.SODIMM_22)

    if err := fluidnc.init():
        print(f"Failed to initialize: {err}")
        sys.exit(1)

    # Start interactive terminal
    if err := fluidnc.start_terminal():
        print(f"Terminal error: {err}")

    fluidnc.deinit()
