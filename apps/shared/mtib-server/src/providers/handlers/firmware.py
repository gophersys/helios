import grpc
import os
import time
import subprocess
import tempfile
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Tuple, Optional
from corekinect.utils import Logger
from src.shared.types import *


class FirmwareHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

        # Initialize RAM storage directory in /dev/shm
        self.ram_storage = Path("/dev/shm/mtib_fw_files")
        self.ram_storage.mkdir(exist_ok=True)

        # Initialize programmer info storage
        self.programmers: dict[str, tuple[HostType | None, bool]] = {}
        self._assign_jlinks()

        # Track active firmware files
        self.active_files: Dict[str, Path] = {}  # Maps filename to temp file path

    def _assign_jlinks(self):
        """Detect and assign J-Link programmers to their respective chips."""
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
                    self.programmers[serial] = (None, False)  # No host type, not connected
                    continue

                self.logger.info(f"J-Link serial {serial} detected with device version {result}")

                # Determine host type based on the actual device version
                host_type = None
                if "nrf91" in result:
                    host_type = HostType.HOST_TYPE_NRF9160
                elif "nrf52" in result:
                    host_type = HostType.HOST_TYPE_NRF52840
                elif "nrf53" in result:
                    host_type = HostType.HOST_TYPE_NRF5340
                elif "nrf91" in result:
                    host_type = HostType.HOST_TYPE_NRF9151

                if host_type:
                    self.programmers[serial] = (host_type, True)
                    self.logger.info(f"Assigned J-Link {serial} to host type {host_type}")
                else:
                    self.logger.warning(f"Unknown device version {result} for serial {serial}")
                    self.programmers[serial] = (None, False)

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                if "low voltage" in error_msg.lower():
                    self.logger.warning(f"J-Link {serial} detected but no device connected or low voltage condition")
                else:
                    self.logger.error(f"Error reading device info for J-Link {serial}: {error_msg}")
                self.programmers[serial] = (None, False)

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _cleanup_file(self, filename: str) -> None:
        """Clean up a temporary file."""
        if filename in self.active_files:
            try:
                self.active_files[filename].unlink(missing_ok=True)
                del self.active_files[filename]
            except Exception as e:
                self.logger.error(f"Error cleaning up file {filename}: {e}")

    def list_programmers(self, request: Empty, context: grpc.ServicerContext) -> ListProgrammersResponse:
        """List available programmers."""
        self.logger.info("ListProgrammers request received")
        try:
            programmers = []

            # Create a programmer for each detected J-Link
            for serial, (host_type, is_connected) in self.programmers.items():
                programmer = Programmer(
                    type=ProgrammerType.PROGRAMMER_TYPE_JLINK,
                    host=host_type if is_connected else HostType.HOST_TYPE_UNDEFINED,
                )
                programmers.append(programmer)

            return ListProgrammersResponse(success=True, message="", programmers=programmers)
        except Exception as e:
            self.logger.error(f"Error listing programmers: {str(e)}")
            return ListProgrammersResponse(
                success=False, message=f"Failed to list programmers: {str(e)}", programmers=[]
            )

    def list_fw_files(self, request: Empty, context: grpc.ServicerContext) -> ListFwFilesResponse:
        """List available firmware files."""
        self.logger.info("ListFwFiles request received")
        try:
            files = []
            for filename, file_path in self.active_files.items():
                if file_path.exists():
                    size = file_path.stat().st_size
                    sha256 = self._calculate_sha256(file_path)
                    files.append(FwFileInfo(name=filename, size_b=size, sha256_digest=sha256))
            return ListFwFilesResponse(success=True, message="", files=files)
        except Exception as e:
            self.logger.error(f"Error listing firmware files: {e}")
            return ListFwFilesResponse(success=False, message=f"Failed to list firmware files: {str(e)}", files=[])

    def upload_fw_file(
        self, request_iterator: grpc.ServicerContext, context: grpc.ServicerContext
    ) -> UploadFwFileResponse:
        """Upload a firmware file to RAM."""
        try:
            # Get the first request to get the filename
            first_request = next(request_iterator)
            filename = first_request.name
            self.logger.info(f"UploadFwFile request received for {filename}")

            # Clean up any existing file with the same name
            self._cleanup_file(filename)

            # Create a new temporary file in RAM
            temp_file = self.ram_storage / filename
            with open(temp_file, "wb") as f:
                # Write the first chunk
                f.write(first_request.content)

                # Write remaining chunks
                for chunk in request_iterator:
                    f.write(chunk.content)

            # Calculate SHA256 and store the file path
            sha256 = self._calculate_sha256(temp_file)
            self.active_files[filename] = temp_file

            return UploadFwFileResponse(success=True, message="", sha256_digest=sha256)
        except StopIteration:
            self.logger.error("UploadFwFile request stream ended unexpectedly")
            return UploadFwFileResponse(success=False, message="Upload stream ended unexpectedly", sha256_digest="")
        except grpc.RpcError as e:
            self.logger.error(f"gRPC error during upload: {e}")
            return UploadFwFileResponse(success=False, message=f"gRPC error during upload: {str(e)}", sha256_digest="")
        except Exception as e:
            self.logger.error(f"Error uploading firmware file: {e}")
            return UploadFwFileResponse(
                success=False, message=f"Failed to upload firmware file: {str(e)}", sha256_digest=""
            )

    def delete_fw_file(self, request: DeleteFwFileRequest, context: grpc.ServicerContext) -> DeleteFwFileResponse:
        """Delete a firmware file from RAM."""
        self.logger.info(f"DeleteFwFile request received for {request.file_info.name}")
        try:
            self._cleanup_file(request.file_info.name)
            return DeleteFwFileResponse(success=True, message="")
        except Exception as e:
            self.logger.error(f"Error deleting firmware file: {e}")
            return DeleteFwFileResponse(success=False, message=f"Failed to delete firmware file: {str(e)}")

    def flash_fw_file(self, request: FlashFwFileRequest, context: grpc.ServicerContext) -> FlashFwFileResponse:
        """Flash a firmware file from RAM."""
        self.logger.info(f"FlashFwFile request received for {request.file_info.name}")
        try:
            if request.file_info.name not in self.active_files:
                return FlashFwFileResponse(
                    success=False, message=f"Firmware file {request.file_info.name} not found", time_ms=0
                )

            file_path = self.active_files[request.file_info.name]
            if not file_path.exists():
                return FlashFwFileResponse(
                    success=False, message=f"Firmware file {request.file_info.name} no longer exists", time_ms=0
                )

            # Verify SHA256 if provided
            if request.file_info.sha256_digest:
                current_sha256 = self._calculate_sha256(file_path)
                if current_sha256 != request.file_info.sha256_digest:
                    return FlashFwFileResponse(success=False, message="SHA256 digest mismatch", time_ms=0)

            # Find a suitable programmer
            programmer = None
            for serial, (host_type, is_connected) in self.programmers.items():
                if is_connected and host_type == request.file_info.target:
                    programmer = serial
                    break

            if not programmer:
                return FlashFwFileResponse(
                    success=False,
                    message=f"No suitable programmer found for target {request.file_info.target}",
                    time_ms=0,
                )

            # Flash the firmware
            start_time = time.time()
            try:
                result = subprocess.run(
                    ["nrfjprog", "--program", str(file_path), "--verify", "--snr", programmer],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                time_ms = int((time.time() - start_time) * 1000)
                return FlashFwFileResponse(success=True, message="", time_ms=time_ms)
            except subprocess.CalledProcessError as e:
                return FlashFwFileResponse(success=False, message=f"Failed to flash firmware: {e.stderr}", time_ms=0)

        except Exception as e:
            self.logger.error(f"Error flashing firmware: {e}")
            return FlashFwFileResponse(success=False, message=f"Failed to flash firmware: {str(e)}", time_ms=0)

    def __del__(self):
        """Cleanup all temporary files when the handler is destroyed."""
        try:
            for filename in list(self.active_files.keys()):
                self._cleanup_file(filename)
            if self.ram_storage.exists():
                self.ram_storage.rmdir()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
