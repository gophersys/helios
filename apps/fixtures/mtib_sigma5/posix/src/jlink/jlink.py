from config import config
import os
import re
import subprocess
from config import config
from config import conf
import time
from typing import Tuple, Dict
import logging
import wiringpi

from ..providers.types import *

class Jlink:
    def __init__(self):
        self.nrf9160_serial = ""
        self.nrf52840_serial = ""
        
        self.configure_gpio()

        # Initialize and find the J-Link devices
        self.initialize_and_find_jlinks()

    def initialize_and_find_jlinks(self):
        logging.info("Starting initial scan for J-Link devices.")
        self.disable_second_jlink()
        time.sleep(2)

        # Initial scan for J-Link devices
        initial_scan = self.get_jlink_serial_numbers()

        if len(initial_scan) == 1:
            logging.info(f"Found one J-Link device. Serial Number: {list(initial_scan.values())[0]}")
            # Assume the first found device is nrf9160
            self.nrf9160_serial = list(initial_scan.values())[0]

            # Use the GPIO pin to enable the second J-Link device
            self.enable_second_jlink()

            # Wait a bit for the device to be ready after enabling
            time.sleep(2)

            # Scan again for J-Link devices
            final_scan = self.get_jlink_serial_numbers()

            # Find the newly appeared device and assign it to nrf52840
            new_devices = [sn for sn in final_scan.values() if sn not in initial_scan.values()]
            if new_devices:
                logging.info(f"Found new J-Link device after enabling. Serial Number: {new_devices[0]}")
                self.nrf52840_serial = new_devices[0]
            else:
                logging.warning("No new J-Link device found after enabling the second device.")
        else:
            logging.warning(f"Initial scan did not find exactly one J-Link device, found: {len(initial_scan)}.")

    def configure_gpio(self):
        # Initialize wiringPi and set the mode to OUTPUT for USB_ENABLE_PIN
        wiringpi.pinMode(config.conf.USB_ENABLE_GPIO, wiringpi.GPIO.OUTPUT)

    def disable_second_jlink(self):
        # Drive the pin high to enable the second J-Link
        wiringpi.digitalWrite(config.conf.USB_ENABLE_GPIO, wiringpi.GPIO.LOW)

    def enable_second_jlink(self):
        # Drive the pin high to enable the second J-Link
        wiringpi.digitalWrite(config.conf.USB_ENABLE_GPIO, wiringpi.GPIO.HIGH)

    def get_jlink_serial_numbers(self) -> Dict[int, str]:
        bus_to_serial = {}
        bus_directories = [config.conf.MCU_52840_USB_BUS, config.conf.MCU_9160_USB_BUS]

        for bus_dir in bus_directories:
            if not os.path.exists(bus_dir):
                continue

            for dev_file in os.listdir(bus_dir):
                device_path = os.path.join(bus_dir, dev_file)
                serial_number = self._extract_serial_number(device_path)

                if serial_number and not serial_number.endswith('.usb'):
                    serial_number = serial_number.lstrip('0')  # Remove leading zeros
                    bus_number = int(bus_dir.split('/')[-1])
                    bus_to_serial[bus_number] = serial_number
                    logging.info(f"Detected J-Link on Bus {bus_number}: Serial Number {serial_number}")

        return bus_to_serial
    
    def _run_nrfjprog(self, serial_number, firmware_file_path, modem) -> Tuple[bool, str]:
        # Construct the nrfjprog command
        if modem is True:
            nrfjprog_command = [
                'nrfjprog',
                '-s', str(serial_number),
                '--recover',
                '--program', firmware_file_path,
                '--verify'
            ]
        else:
            nrfjprog_command = [
                'nrfjprog',
                '-s', str(serial_number),
                '--recover',
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
            return True, ""

        except subprocess.CalledProcessError as e:
            error_message = e.stderr
            if "LOW_VOLTAGE" in error_message:
                logging.error("Error: Low voltage detected on the target device. Please check the device's power supply.")
            elif "Could not connect to debug probe" in error_message:
                logging.info("Error: Could not connect to debug probe. Please check the connection and serial number.")
            else:
                logging.info(f"Failed due to {error_message}")
            return False, error_message

    def _get_serial_for_device(self, device:DeviceType):
        if device is DeviceType.DEVICE_NRF9160:
            return self.nrf9160_serial
        else:
            return self.nrf52840_serial

    def program_app(self, device:DeviceType, firmware_file) -> Tuple[bool, str]:
        firmware_file_path = os.path.join(config.conf.FW_FILE_STORAGE_DIR, firmware_file)
        serial_number = self._get_serial_for_device(device)
        return self._run_nrfjprog(serial_number, firmware_file_path, modem=False)

    def program_modem(self, device:DeviceType, firmware_file) -> Tuple[bool, str]:
        firmware_file_path = os.path.join(config.conf.FW_FILE_STORAGE_DIR, firmware_file)
        serial_number = self._get_serial_for_device(device)
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
