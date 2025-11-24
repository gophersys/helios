import os
import time
import zipfile
from typing import Optional, List, Dict
from corekinect.mtib_client.v1 import MtibV1Client
from corekinect.utils.logx import Logger
from corekinect.mtib_client.v1 import HostType, FwFileInfo
from minio import Minio

from services.mtib import get_mtib_client
from services.storage import get_storage_client


# -----------------------------------------------
#                                  Firmware Service
# ---------------------------------------------*/
def download_firmware_from_storage(
    logger: Logger, storage_client: Minio, file_path: str
) -> tuple[Optional[str], Optional[str]]:
    try:
        # Extract filename from the bucket path for local storage
        firmware_filename = file_path.split("/")[-1]
        local_file_path = f"/tmp/{firmware_filename}"

        logger.info(f"Downloading firmware from path: {file_path}")
        logger.info(f"Local file path: {local_file_path}")

        # Download firmware from the specific path in the bucket
        storage_client.fget_object(
            bucket_name="firmware",
            object_name=file_path,
            file_path=local_file_path,
        )
        logger.info(f"Successfully downloaded firmware to: {local_file_path}")

        # Unzip the firmware file
        extract_dir = "/tmp/firmware_extracted"
        os.makedirs(extract_dir, exist_ok=True)

        logger.info(f"Extracting firmware to: {extract_dir}")
        with zipfile.ZipFile(local_file_path, "r") as zip_ref:
            # Test if zip file is valid
            zip_ref.testzip()
            # Extract all files
            zip_ref.extractall(extract_dir)

        logger.info(f"Successfully extracted firmware to: {extract_dir}")
        return extract_dir, None

    except Exception as e:
        logger.error(f"Failed to download firmware: {e}")
        return None, f"Failed to download firmware from storage: {e}"


def discover_firmware_files(logger: Logger, firmware_extract_path: str) -> tuple[List[Dict], Optional[str]]:
    """Discover and categorize firmware files for sigma5 product"""
    try:
        firmware_files = []

        logger.info("Discovering firmware files:")
        logger.info("=" * 60)

        # Walk through the extracted firmware directory
        for root, _, files in os.walk(firmware_extract_path):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, firmware_extract_path)

                # Map files to their types based on sigma5 specific patterns
                if file.startswith("mfw_nrf") and file.endswith(".zip"):
                    # nRF9160 modem firmware (mfw_nrf_*.zip)
                    firmware_files.append(
                        {
                            "file_path": file_path,
                            "target": HostType.HOST_TYPE_NRF9160_MODEM,
                        }
                    )
                elif file.startswith("sigma_comm") and file.endswith(".hex") and "signed.encrypted" not in file_path:
                    # Communication coprocessor firmware for nRF9160 (sigma_comm_*.hex) - exclude encrypted
                    firmware_files.append(
                        {
                            "file_path": file_path,
                            "target": HostType.HOST_TYPE_NRF9160,
                        }
                    )
                elif file.startswith("sigma_app") and file.endswith(".hex") and "signed.encrypted" not in file_path:
                    # Application firmware for nRF52840 (sigma_app_*.hex) - exclude encrypted
                    firmware_files.append(
                        {
                            "file_path": file_path,
                            "target": HostType.HOST_TYPE_NRF52840,
                        }
                    )

        # Log discovered firmware files
        logger.info("Discovered firmware files:")
        for fw_info in firmware_files:
            logger.info(f" - {fw_info['file_path']} -> {fw_info['target']}")
        logger.info(f"\nTotal firmware files found: {len(firmware_files)}")
        logger.info("=" * 60)

        return firmware_files, None

    except Exception as e:
        return [], f"Failed to discover firmware files: {e}"


def upload_firmware_to_mtib(logger: Logger, mtib_client: MtibV1Client, firmware_files: List[Dict]) -> Optional[str]:
    try:
        logger.info("Uploading firmware files to MTIB:")

        # Upload each firmware file
        for fw_info in firmware_files:
            logger.info(f"Uploading {fw_info['target']} firmware: {fw_info['file_path']}")
            error = mtib_client.UploadFwFile(file_path=fw_info["file_path"], target=fw_info["target"])
            if error:
                logger.error(f"Could not upload fw file {fw_info['file_path']}: {error}")
                return f"Could not upload fw file {fw_info['file_path']}: {error}"
            logger.info(f"Successfully uploaded {fw_info['target']} firmware")

        logger.info("All firmware files uploaded successfully!")
        return None
    except Exception as e:
        return f"Failed to upload firmware files to MTIB: {str(e)}"


def flash_firmware_to_dut(
    logger: Logger, mtib_client: MtibV1Client, firmware_files: List[Dict], voltage_v: float = 3.7
) -> Optional[str]:
    dut_powered_on = False

    try:
        logger.info("Flashing firmware files to DUT:")

        # Power on the DUT
        error = mtib_client.DutPowerEnable(voltage_v=voltage_v)
        if error:
            logger.error(f"Could not power on DUT: {error}")
            return f"Could not power on DUT: {error}"
        dut_powered_on = True
        logger.info("Successfully powered on DUT")

        # Flash each firmware file
        for fw_info in firmware_files:
            filename = os.path.basename(fw_info["file_path"])
            logger.info(f"Flashing {fw_info['target']} firmware: {filename}")

            file_info = FwFileInfo(name=filename, target=fw_info["target"])
            time_ms, error = mtib_client.FlashFwFile(file_info=file_info, sector_erase=True, recover=True)
            if error:
                logger.error(f"Could not flash fw file {filename}: {error}")
                return f"Could not flash fw file {filename}: {error}"
            logger.info(f"Successfully flashed {fw_info['target']} firmware in {time_ms}ms")

        logger.info("All firmware files flashed successfully!")
        return None

    except Exception as e:
        return f"Failed to flash firmware to DUT: {str(e)}"

    finally:
        # Always power off the DUT if we powered it on
        if dut_powered_on:
            error = mtib_client.DutPowerDisable()
            if error:
                logger.error(f"Could not power off DUT: {error}")
            else:
                logger.info("Successfully powered off DUT")


def flash_firmware_from_storage(logger: Logger, firmware_file_path: str, voltage_v: float = 3.7) -> Optional[str]:
    mtib_client = get_mtib_client()
    storage_client = get_storage_client()

    extract_dir, error = download_firmware_from_storage(logger, storage_client, firmware_file_path)
    if error:
        return error

    firmware_files, error = discover_firmware_files(logger, extract_dir)
    if error:
        return error

    if not firmware_files:
        return "No firmware files found in extracted archive"

    error = upload_firmware_to_mtib(logger, mtib_client, firmware_files)
    if error:
        return error

    error = flash_firmware_to_dut(logger, mtib_client, firmware_files, voltage_v)
    if error:
        return error

    return None
