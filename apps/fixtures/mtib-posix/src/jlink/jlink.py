from config import config
import os
import re
import subprocess
from config import config
import time
from pynrfjprog import HighLevel

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

                    # Print the detected J-Link device
                    print(f"Detected J-Link on Bus {bus_number}: Serial Number {serial_number}")

        # Print final mapping
        for bus, serial in bus_to_serial.items():
            print(f"Bus {bus}: Serial Number {serial}")

        return bus_to_serial

    def program_app(self, serial_number, firmware_file):
        try:
            # Construct path
            file_path = os.path.join(config.conf.FW_FILE_STORAGE_DIR, firmware_file)
            
            # Convert serial number to integer
            serial_number_int = int(serial_number)

            # Start the programming process
            start = time.time()
            with HighLevel.API() as api:
                print("Establishing board connection")
                with HighLevel.IPCDFUProbe(api, serial_number_int, HighLevel.CoProcessor.CP_APPLICATION, None, True, None, 8000) as probe:
                    program_options = HighLevel.ProgramOptions(
                        erase_action=HighLevel.EraseAction.ERASE_SECTOR,
                        reset=HighLevel.ResetAction.RESET_SYSTEM,
                        verify=HighLevel.VerifyAction.VERIFY_READ
                    )
                    print(f"Programming '{firmware_file}' to board {serial_number}")
                    probe.program(file_path, program_options)
                    print("Programming complete")

                    # Verification step
                    print("Verifying")
                    probe.verify(file_path)
                    print("Verification complete")

                print(f"Completed in {time.time() - start} seconds")
                return True

        except Exception as e:
            error_message = str(e)
            if "LOW_VOLTAGE" in error_message:
                print("Error: Low voltage detected on the target device. Please check the device's power supply.")
            elif "Could not connect to debug probe" in error_message:
                print("Error: Could not connect to debug probe. Please check the connection and serial number.")
            else:
                print(f"Failed due to {error_message}")
            return False

    def program_modem(self, serial_number, firmware_file):
        try:
            # Construct path
            file_path = os.path.join(config.conf.FW_FILE_STORAGE_DIR, firmware_file)
            
            # Convert serial number to integer
            serial_number_int = int(serial_number)

            # Start the programming process
            start = time.time()
            with HighLevel.API() as api:
                print("Establishing board connection")
                with HighLevel.IPCDFUProbe(api, serial_number_int, HighLevel.CoProcessor.CP_APPLICATION, None, True, None, 8000) as probe:
                    program_options = HighLevel.ProgramOptions(
                        erase_action=HighLevel.EraseAction.ERASE_ALL,
                        reset=HighLevel.ResetAction.RESET_SYSTEM,
                        verify=HighLevel.VerifyAction.VERIFY_NONE
                    )
                    print(f"Programming '{firmware_file}' to board {serial_number}")
                    probe.program(file_path, program_options)
                    print("Programming complete")

                    # Verification step
                    print("Verifying")
                    probe.verify(file_path)
                    print("Verification complete")

                print(f"Completed in {time.time() - start} seconds")
                return True

        except Exception as e:
            error_message = str(e)
            if "LOW_VOLTAGE" in error_message:
                print("Error: Low voltage detected on the target device. Please check the device's power supply.")
            elif "Could not connect to debug probe" in error_message:
                print("Error: Could not connect to debug probe. Please check the connection and serial number.")
            else:
                print(f"Failed due to {error_message}")
            return False

    def _extract_serial_number(self, device_path):
        # Use lsusb or other command to extract the serial number
        try:
            result = subprocess.check_output(['lsusb', '-D', device_path]).decode()
            serial_match = re.search(r'iSerial\s+\d+\s+(\S+)', result)
            if serial_match:
                return serial_match.group(1)
        except subprocess.CalledProcessError as e:
            print(f"Error reading device info: {e}")
        return None
