import logging
import os
import re
import subprocess
import time
from typing import Dict, Tuple

from src.shared.types import *
from corekinect.utils import Logger

FW_FILE_STORAGE_DIR = "/tmp/fw_files"


class Jlink:
    def __init__(self, logger: Logger):
        self.chip_to_serial = {
            HostType.HOST_TYPE_NRF9160: None,
            HostType.HOST_TYPE_NRF52840: None,
            HostType.HOST_TYPE_NRF9160_MODEM: None,
            HostType.HOST_TYPE_NRF5340: None,
        }
        self.logger = logger
        self.unknown_serials = []
        self._assign_jlinks()

    def _assign_jlinks(self):
        try:
            serials = subprocess.check_output(["nrfjprog", "--ids"]).decode().split()
        except Exception as e:
            self.logger.error(f"Error getting J-Link serials: {e}")
            serials = []

        for serial in serials:
            # Try to get device version
            success = self._try_detect_device(serial)
            if not success:
                # If detection failed, try recovery and detect again
                self.logger.info(f"J-Link {serial} detection failed, attempting recovery...")
                if self._try_recover_device(serial):
                    self._try_detect_device(serial)

    def _try_detect_device(self, serial: str) -> bool:
        """Try to detect device type for a J-Link serial number. Returns True if successful."""
        try:
            result = subprocess.check_output(
                ["nrfjprog", "--snr", serial, "--deviceversion"], stderr=subprocess.STDOUT
            ).decode()

            # Log the raw output for debugging
            self.logger.info(f"J-Link {serial} deviceversion output: {result}")
            result_lower = result.lower()

            # Check for access protection error
            if "access protection is enabled" in result_lower:
                self.logger.info(f"J-Link {serial} has access protection enabled")
                return False

            # Check for other error conditions
            if "low voltage" in result_lower or "error" in result_lower:
                self.logger.warning(f"J-Link {serial} detected but no device connected or low voltage condition")
                self.unknown_serials.append(serial)
                return False

            # Successfully detected device
            self.logger.info(f"J-Link serial {serial} detected with device version {result}")
            self._assign_device_type(serial, result_lower)
            return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            self.logger.error(f"Error reading device info for J-Link {serial}: {error_msg}")

            # Check if this might be access protection
            if "access protection" in error_msg.lower() or "error -90" in error_msg.lower():
                self.logger.info(f"J-Link {serial} might have access protection (detected in exception)")
                return False

            self.unknown_serials.append(serial)
            return False

    def _try_recover_device(self, serial: str) -> bool:
        """Try to recover a J-Link device. Returns True if recovery was successful."""
        try:
            self.logger.info(f"Attempting recovery for J-Link {serial}...")
            recover_result = subprocess.run(
                ["nrfjprog", "--snr", serial, "--recover"],
                capture_output=True,
                text=True,
                timeout=60,  # 30s + buffer
            )

            if recover_result.returncode == 0:
                self.logger.info(f"Successfully recovered J-Link {serial}")
                return True
            else:
                self.logger.error(f"Failed to recover J-Link {serial}: {recover_result.stderr}")
                self.unknown_serials.append(serial)
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"Recovery timeout for J-Link {serial}")
            self.unknown_serials.append(serial)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during recovery for J-Link {serial}: {e}")
            self.unknown_serials.append(serial)
            return False

    def _assign_device_type(self, serial: str, result_lower: str):
        """Assign the J-Link serial to the appropriate device type."""
        if "nrf91" in result_lower:
            self.chip_to_serial[HostType.HOST_TYPE_NRF9160] = serial
            self.chip_to_serial[HostType.HOST_TYPE_NRF9160_MODEM] = serial  # Same chip, different targets
        elif "nrf52" in result_lower:
            self.chip_to_serial[HostType.HOST_TYPE_NRF52840] = serial
        elif "nrf5340" in result_lower:
            self.chip_to_serial[HostType.HOST_TYPE_NRF5340] = serial
        else:
            self.logger.warning(f"Unknown device version for serial {serial}")
            self.unknown_serials.append(serial)

    def _run_nrfjprog(self, serial_number, firmware_file_path, modem) -> Tuple[bool, str]:
        # Construct the nrfjprog command
        if modem is True:
            nrfjprog_command = [
                "nrfjprog",
                "-s",
                str(serial_number),
                "--recover",
                "--program",
                firmware_file_path,
                "--verify",
                firmware_file_path,
                "--log",
            ]
        else:
            nrfjprog_command = [
                "nrfjprog",
                "-s",
                str(serial_number),
                "--recover",
                "--program",
                firmware_file_path,
                "--verify",
                firmware_file_path,
                "--log",
            ]

        try:
            # Start the programming process
            start = time.time()
            self.logger.info(
                f"Programming '{firmware_file_path}' to board on programmer {serial_number} with command '{nrfjprog_command}'"
            )

            # Run the nrfjprog command
            result = subprocess.run(nrfjprog_command, capture_output=True, text=True, check=True)

            # logging.info the output from nrfjprog
            self.logger.info(result.stdout)

            self.logger.info(f"Programming complete in {time.time() - start} seconds")
            return True, ""

        except subprocess.CalledProcessError as e:
            error_message = e.stderr
            if "LOW_VOLTAGE" in error_message:
                self.logger.error(
                    "Error: Low voltage detected on the target device. Please check the device's power supply."
                )
            elif "Could not connect to debug probe" in error_message:
                self.logger.info(
                    "Error: Could not connect to debug probe. Please check the connection and serial number."
                )
            else:
                self.logger.info(f"Failed due to {error_message}")
            return False, error_message

    def get_serial_for_chip(self, host_type):
        return self.chip_to_serial.get(host_type)

    def program_app(self, host_type, firmware_file):
        serial = self.get_serial_for_chip(host_type)
        if not serial:
            return False, f"No programmer found for {host_type}"
        firmware_file_path = os.path.join(FW_FILE_STORAGE_DIR, firmware_file)
        return self._run_nrfjprog(serial, firmware_file_path, modem=False)

    def program_modem(self, device: HostType, firmware_file) -> Tuple[bool, str]:
        firmware_file_path = os.path.join(FW_FILE_STORAGE_DIR, firmware_file)
        serial_number = self.get_serial_for_chip(HostType.HOST_TYPE_NRF9160_MODEM)
        return self._run_nrfjprog(serial_number, firmware_file_path, modem=True)

    def _extract_serial_number(self, device_path):
        # Use lsusb or other command to extract the serial number
        try:
            result = subprocess.check_output(["lsusb", "-D", device_path]).decode()
            serial_match = re.search(r"iSerial\s+\d+\s+(\S+)", result)
            if serial_match:
                return serial_match.group(1)
        except subprocess.CalledProcessError as e:
            self.logger.info(f"Error reading device info: {e}")
        return None
