from config import config
import os
import re
import subprocess
from config import config
import time
import logging

class Jlink:
    def get_jlink_serial_numbers(self) -> dict:
        bus_to_serial = {}
        bus_directories = [config.conf.MCU_52840_USB_BUS, config.conf.MCU_9160_USB_BUS]

        for bus_dir in bus_directories:
            if not os.path.exists(bus_dir):
                continue

            # List all device files in the bus directory
            for dev_file in os.listdir(bus_dir):
                device_path = os.path.join(bus_dir, dev_file)
                serial_number = self._extract_serial_number(device_path)

                if serial_number and not serial_number.endswith('.usb'):
                    # Remove leading zeros from the serial number
                    serial_number = serial_number.lstrip('0')
                    bus_number = int(bus_dir.split('/')[-1])
                    bus_to_serial[bus_number] = serial_number

                    # logging.info the detected J-Link device
                    logging.info(f"Detected J-Link on Bus {bus_number}: Serial Number {serial_number}")

        # logging.info final mapping
        for bus, serial in bus_to_serial.items():
            logging.info(f"Bus {bus}: Serial Number {serial}")

        return bus_to_serial

    def _run_nrfjprog(self, serial_number, firmware_file_path, modem):
        # Construct the nrfjprog command
        nrfjprog_command = [
            'nrfjprog',
            '-s', str(serial_number),
            '--program', firmware_file_path,
            '--verify'
        ]
    
        try:
            # Start the programming process
            start = time.time()
            logging.info(f"Programming '{firmware_file_path}' to board on programmer {serial_number}")

            # Run the nrfjprog command
            result = subprocess.run(nrfjprog_command, capture_output=True, text=True, check=True)
            
            # logging.info the output from nrfjprog
            logging.info(result.stdout)
            
            logging.info(f"Programming complete in {time.time() - start} seconds")
            return True

        except subprocess.CalledProcessError as e:
            error_message = e.stderr
            if "LOW_VOLTAGE" in error_message:
                logging.error("Error: Low voltage detected on the target device. Please check the device's power supply.")
            elif "Could not connect to debug probe" in error_message:
                logging.info("Error: Could not connect to debug probe. Please check the connection and serial number.")
            else:
                logging.info(f"Failed due to {error_message}")
            return False

    def program_app(self, serial_number, firmware_file):
        # Construct path to firmware file
        firmware_file_path = os.path.join(config.conf.FW_FILE_STORAGE_DIR, firmware_file)
        return self._run_nrfjprog(serial_number, firmware_file_path, modem=False)

    def program_modem(self, serial_number, firmware_file):
        # Construct path to firmware file
        firmware_file_path = os.path.join(config.conf.FW_FILE_STORAGE_DIR, firmware_file)
        return self._run_nrfjprog(serial_number, firmware_file_path, modem=True)

    def _extract_serial_number(self, device_path):
        # Use lsusb or other command to extract the serial number
        try:
            result = subprocess.check_output(['lsusb', '-D', device_path]).decode()
            serial_match = re.search(r'iSerial\s+\d+\s+(\S+)', result)
            if serial_match:
                return serial_match.group(1)
        except subprocess.CalledProcessError as e:
            logging.info(f"Error reading device info: {e}")
        return None
