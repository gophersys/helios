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
            HostType.HOST_TYPE_NRF9160_MCU: None,
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
            try:
                result = (
                    subprocess.check_output(["nrfjprog", "--snr", serial, "--deviceversion"], stderr=subprocess.STDOUT)
                    .decode()
                    .lower()
                )

                # Check for common error patterns in the output
                if "low voltage" in result or "error" in result:
                    self.logger.warning(f"J-Link {serial} detected but no device connected or low voltage condition")
                    self.unknown_serials.append(serial)
                    continue

                self.logger.info(f"J-Link serial {serial} detected with device version {result}")

                if "nrf91" in result:
                    self.chip_to_serial[HostType.HOST_TYPE_NRF9160_MCU] = serial
                elif "nrf52" in result:
                    self.chip_to_serial[HostType.HOST_TYPE_NRF52840] = serial
                elif "nrf5340" in result:
                    self.chip_to_serial[HostType.HOST_TYPE_NRF5340] = serial
                else:
                    self.logger.warning(f"Unknown device version {result} for serial {serial}")
                    self.unknown_serials.append(serial)
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                if "low voltage" in error_msg.lower():
                    self.logger.warning(f"J-Link {serial} detected but no device connected or low voltage condition")
                else:
                    self.logger.error(f"Error reading device info for J-Link {serial}: {error_msg}")
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
