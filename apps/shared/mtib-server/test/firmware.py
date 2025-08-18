# Standard includes
import os
import sys
import time

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client
from corekinect.mtib_client.v1.client.types import HostType, ProgrammerType
from test.helper import run_sample

def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Demonstrate the firmware-related functions of the MTIB client.
    """
    if len(sys.argv) != 2:
        logger.error("Usage: python3 firmware.py <firmware_file_path>")
        return

    fw_path = sys.argv[1]
    fw_name = os.path.basename(fw_path)

    logger.info(f"Testing firmware functions with file: {fw_path}")

    # Check if file exists
    if not os.path.exists(fw_path):
        logger.error(f"Firmware file not found at {fw_path}")
        return

    # List available programmers
    programmers, err = client.ListProgrammers()
    if err:
        logger.error(f"Failed to list programmers: {err}")
        return
    if not programmers:
        logger.error("No programmers available")
        return

    # Print each programmer with its type and host as strings
    for p in programmers:
        host_status = "Connected" if p.host != 0 else "Not Connected"
        logger.info(f"Programmer: {ProgrammerType(p.type).name} - Status: {host_status}")

    # Find a programmer with a valid host type
    valid_programmer = None
    for p in programmers:
        if p.host != 0:  # 0 is HOST_TYPE_UNDEFINED
            valid_programmer = p
            break

    if not valid_programmer:
        logger.error("No connected devices found. Please connect a device to a programmer and try again.")
        # return

    # List firmware files before upload
    fw_files, err = client.ListFwFiles()
    if err:
        logger.error(f"Failed to list firmware files: {err}")
        return
    logger.info(f"Available firmware files before upload: {[f.name for f in fw_files]}")

    # Upload the firmware file
    err = client.UploadFwFile(fw_path, HostType.HOST_TYPE_NRF52840)
    if err:
        logger.error(f"Failed to upload firmware file: {err}")
        return
    logger.info(f"Successfully uploaded firmware file: {fw_name}")

    # List firmware files after upload to verify
    fw_files, err = client.ListFwFiles()
    if err:
        logger.error(f"Failed to list firmware files: {err}")
        return
    if not any(f.name == fw_name for f in fw_files):
        logger.error(f"Uploaded file {fw_name} not found in server's firmware files")
        return
    logger.info(f"Available firmware files after upload: {[f.name for f in fw_files]}")

    # Find the uploaded file info for flashing
    uploaded_file = None
    for f in fw_files:
        if f.name == fw_name:
            uploaded_file = f
            break
    
    if not uploaded_file:
        logger.error(f"Could not find uploaded file {fw_name} for flashing")
        return

    # Flash the firmware using the uploaded file info
    time_ms, err = client.FlashFwFile(uploaded_file)
    if err:
        logger.error(f"Failed to flash firmware: {err}")
        return
    logger.info(f"Successfully flashed firmware to {HostType(valid_programmer.host).name} device in {time_ms}ms")

    # Delete the firmware file after flashing
    err = client.DeleteFwFile(uploaded_file)
    if err:
        logger.error(f"Failed to delete firmware file: {err}")
        return
    logger.info(f"Successfully deleted firmware file: {fw_name}")


if __name__ == "__main__":
    run_sample(sample, "firmware")
