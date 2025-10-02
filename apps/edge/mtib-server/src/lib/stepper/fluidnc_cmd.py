import time
import serial
from xmodem import XMODEM
from typing import Optional

# Corekinect imports
from corekinect.utils import Logger


class FluidNCController:
    def __init__(
        self,
        logger: Logger,
        port: str,
        baudrate: int = 115200,
        parity: str = "N",
        rtscts: bool = False,
        xonxoff: bool = False,
        timeout: float = 1,
        rts: bool = None,
        dtr: bool = None,
    ):
        """
        Initialize the FluidNC controller (without opening the serial connection).
        """
        self.logger = logger
        self._port = port
        self._baudrate = baudrate
        self._parity = parity
        self._rtscts = rtscts
        self._xonxoff = xonxoff
        self._timeout = timeout
        self._rts = rts
        self._dtr = dtr
        self.serial = None
        self._is_connected = False

    def init(self) -> Optional[str]:
        """Initialize and open the serial connection."""
        try:
            if self._is_connected:
                return None

            self.serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                parity=self._parity,
                rtscts=self._rtscts,
                xonxoff=self._xonxoff,
                timeout=self._timeout,
            )

            if self._rts is not None:
                self.serial.rts = bool(self._rts)
            if self._dtr is not None:
                self.serial.dtr = bool(self._dtr)

            # Clear input and output buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            self._is_connected = True
            return None
        except serial.SerialException as e:
            return f"Failed to open serial port: {e}"
        except Exception as e:
            return f"Unexpected error initializing serial connection: {e}"

    def deinit(self):
        """Close the serial connection and cleanup."""
        if self.serial and self._is_connected:
            try:
                self.serial.close()
            except Exception as e:
                self.logger.error(f"Error closing serial port: {e}")
            finally:
                self.serial = None
                self._is_connected = False

    def send_command(self, command, wait_response=True, response_timeout=1):
        """
        Send a command to the device and optionally wait for a response.

        Args:
            command (str): The command string to send.
            wait_response (bool): Whether to wait for a response.
            response_timeout (float): Maximum time to wait for a response (in seconds).

        Returns:
            str: The device response (if wait_response is True); otherwise, None.
        """
        if not command.endswith("\n"):
            command += "\n"
        self.serial.write(command.encode("utf-8"))
        self.serial.flush()
        if wait_response:
            deadline = time.time() + response_timeout
            response = b""
            while time.time() < deadline:
                if self.serial.in_waiting:
                    response += self.serial.read(self.serial.in_waiting)
                    # Stop reading if a newline is received (assume end of response)
                    if b"\n" in response:
                        break
                time.sleep(0.05)
            return response.decode("utf-8", errors="replace").strip()
        return None

    def health_check(self, timeout=1):
        """
        Perform a health check by sending an Enter (newline) to the device and checking for "OK" in the response.

        Args:
            expected (str): Expected substring in the reply (default "OK").
            timeout (float): Maximum time to wait for a response.

        Returns:
            tuple: (bool, str) where the boolean indicates whether the health check passed,
                and the string is the actual response.
        """
        # Sending an empty command (i.e. just a newline) to simulate pressing Enter.
        response = self.send_command("\n", wait_response=True, response_timeout=timeout)
        return ("ok" in response), response

    def set_rts(self, state):
        """
        Set the RTS (Request To Send) line.

        Args:
            state (bool): Desired RTS state.

        Returns:
            bool: The new RTS state.
        """
        self.serial.rts = bool(state)
        return self.serial.rts

    def set_dtr(self, state):
        """
        Set the DTR (Data Terminal Ready) line.

        Args:
            state (bool): Desired DTR state.

        Returns:
            bool: The new DTR state.
        """
        self.serial.dtr = bool(state)
        return self.serial.dtr

    def set_break(self, state):
        """
        Set the BREAK condition on the serial line.

        Args:
            state (bool): Desired BREAK condition.

        Returns:
            bool: The new BREAK condition.
        """
        self.serial.break_condition = bool(state)
        return self.serial.break_condition

    def change_baudrate(self, new_baudrate):
        """
        Change the baudrate of the serial connection.

        Args:
            new_baudrate (int): The new baudrate value.

        Returns:
            int: The new baudrate.
        """
        self.serial.baudrate = new_baudrate
        return self.serial.baudrate

    def get_port_settings(self):
        """
        Retrieve the current serial port settings.

        Returns:
            dict: A dictionary containing the current port settings.
        """
        return {
            "port": self.serial.port,
            "baudrate": self.serial.baudrate,
            "bytesize": self.serial.bytesize,
            "parity": self.serial.parity,
            "stopbits": self.serial.stopbits,
            "rts": self.serial.rts,
            "dtr": self.serial.dtr,
            "rtscts": self.serial.rtscts,
            "xonxoff": self.serial.xonxoff,
            "break_condition": self.serial.break_condition,
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
            bool: True if the upload succeeded; False otherwise.

        Raises:
            IOError: If there is a problem opening the file or during the upload.
        """
        try:
            with open(local_filename, "rb") as f:
                # Tell the device to prepare for a XMODEM upload.
                command = f"$Xmodem/Receive={destname}\n"
                self.serial.write(command.encode("utf-8"))
                self.serial.flush()
                # Initialize and perform the XMODEM transfer.
                modem = XMODEM(self._getc, self._putc)
                success = modem.send(f)
                return success
        except Exception as e:
            raise IOError("Error during file upload: " + str(e))

    def _getc(self, size, timeout=1):
        """
        Internal helper for XMODEM: read bytes from the serial port.
        """
        self.serial.timeout = timeout
        data = self.serial.read(size)
        return data or None

    def _putc(self, data, timeout=1):
        """
        Internal helper for XMODEM: write bytes to the serial port.
        """
        written = self.serial.write(data)
        return written


# === Example usage ===
if __name__ == "__main__":
    # Replace '/dev/ttyUSB0' with your serial port (or "COM3" on Windows)
    controller = FluidNCController(port="/dev/ttyUSB0", baudrate=115200, timeout=1)
    try:
        # Send a command and print the response.
        response = controller.send_command("status")
        print("Response:", response)

        # Perform a health check (the response must contain "OK").
        healthy, health_response = controller.health_check("status", "OK")
        if healthy:
            print("Health check passed:", health_response)
        else:
            print("Health check failed:", health_response)

        # Get and display current port settings.
        settings = controller.get_port_settings()
        print("Port settings:", settings)

        # (Optional) Upload a file using XMODEM:
        # success = controller.upload_file_xmodem("local_config.flnc", "config.flnc")
        # print("File upload success:", success)

    finally:
        controller.deinit()
