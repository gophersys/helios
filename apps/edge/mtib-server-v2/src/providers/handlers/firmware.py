import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

import grpc
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

        # Track active firmware files
        self.active_files: Dict[str, Tuple[Path, HostType]] = {}  # Maps filename to (temp file path, target)

    def _assign_jlinks(self, force_recovery: bool = False):
        """Detect and assign J-Link programmers to their respective chips."""
        try:
            serials = subprocess.check_output(["nrfjprog", "--ids"]).decode().split()
        except Exception as e:
            self.logger.error(f"Error getting J-Link serials: {e}")
            serials = []

        for serial in serials:
            # Try to get device version
            success = self._try_detect_device(serial)
            if not success:
                if force_recovery:
                    if self._try_recover_device(serial):
                        self.logger.info(f"J-Link {serial} detection failed, attempting recovery...")
                        self._try_detect_device(serial)

    def _try_detect_device(self, serial: str) -> bool:
        """Try to detect device type for a J-Link serial number. Returns True if successful."""
        try:
            result = subprocess.check_output(
                ["nrfjprog", "--snr", serial, "--deviceversion"], stderr=subprocess.STDOUT
            ).decode()

            # Log the raw output for debugging
            result_upper = result.strip().upper()

            # Check for access protection error
            if "ACCESS PROTECTION IS ENABLED" in result_upper:
                self.logger.info(f"J-Link {serial} has access protection enabled")
                return False

            # Check for other error conditions
            if "LOW VOLTAGE" in result_upper or "ERROR" in result_upper:
                self.logger.warning(f"J-Link {serial} detected but no device connected or low voltage condition")
                self.programmers[serial] = (None, False)
                return False

            # Successfully detected device
            self.logger.info(f"J-Link serial {serial} detected with device version {result}")
            self._assign_device_type(serial, result_upper)
            return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            self.logger.error(f"Error reading device info for J-Link {serial}: {error_msg}")

            # Check if this might be access protection
            if "access protection" in error_msg.lower() or "error -90" in error_msg.lower():
                self.logger.info(f"J-Link {serial} might have access protection (detected in exception)")
                return False

            self.programmers[serial] = (None, False)
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
                self.programmers[serial] = (None, False)
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"Recovery timeout for J-Link {serial}")
            self.programmers[serial] = (None, False)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during recovery for J-Link {serial}: {e}")
            self.programmers[serial] = (None, False)
            return False

    def _assign_device_type(self, serial: str, result_upper: str):
        """Assign the J-Link serial to the appropriate device type."""
        host_type = None
        if "NRF9160" in result_upper:
            host_type = HostType.HOST_TYPE_NRF9160
        elif "NRF52840" in result_upper:
            host_type = HostType.HOST_TYPE_NRF52840
        elif "NRF5340" in result_upper:
            host_type = HostType.HOST_TYPE_NRF5340
        elif "NRF9151" in result_upper or "NRF9120" in result_upper:
            host_type = HostType.HOST_TYPE_NRF9151

        if host_type:
            self.programmers[serial] = (host_type, True)
            self.logger.info(f"Assigned J-Link {serial} to host type {host_type}")
        else:
            self.logger.warning(f"Unknown device version for serial {serial}")
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
                file_path, _ = self.active_files[filename]
                file_path.unlink(missing_ok=True)
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
            for filename, (file_path, target) in self.active_files.items():
                if file_path.exists():
                    size = file_path.stat().st_size
                    sha256 = self._calculate_sha256(file_path)
                    files.append(FwFileInfo(name=filename, target=target, size_b=size, sha256_digest=sha256))
            return ListFwFilesResponse(success=True, message="", files=files)
        except Exception as e:
            self.logger.error(f"Error listing firmware files: {e}")
            return ListFwFilesResponse(success=False, message=f"Failed to list firmware files: {str(e)}", files=[])

    def upload_fw_file(
        self, request_iterator: Iterator[UploadFwFileRequest], context: grpc.ServicerContext
    ) -> UploadFwFileResponse:
        """Upload a firmware file to RAM.

        Args:
            request_iterator: Iterator of UploadFwFileRequest messages containing file chunks
            context: gRPC servicer context

        Returns:
            UploadFwFileResponse with success status and SHA256 digest
        """
        try:
            # Get the first request to get the filename
            try:
                first_request = next(request_iterator)
            except StopIteration:
                self.logger.error("UploadFwFile request stream ended before first chunk")
                return UploadFwFileResponse(
                    success=False, message="Upload stream ended before first chunk", sha256_digest=""
                )
            except grpc.RpcError as e:
                self.logger.error(f"gRPC error getting first request: {e}")
                return UploadFwFileResponse(
                    success=False, message=f"gRPC error getting first request: {str(e)}", sha256_digest=""
                )

            filename = first_request.name
            target = first_request.target
            self.logger.info(f"UploadFwFile request received for {filename} with target {target}")

            # Clean up any existing file with the same name
            self._cleanup_file(filename)

            # Create a new temporary file in RAM
            temp_file = self.ram_storage / filename
            with open(temp_file, "wb") as f:
                # Write the first chunk
                f.write(first_request.content)

                # Write remaining chunks
                try:
                    for chunk in request_iterator:
                        if not chunk.content:  # Skip empty chunks
                            continue
                        f.write(chunk.content)
                except grpc.RpcError as e:
                    self.logger.error(f"gRPC error during chunk processing: {e}")
                    # Clean up the partial file
                    self._cleanup_file(filename)
                    return UploadFwFileResponse(
                        success=False, message=f"gRPC error during chunk processing: {str(e)}", sha256_digest=""
                    )

            # Calculate SHA256 and store the file path and target
            sha256 = self._calculate_sha256(temp_file)
            self.active_files[filename] = (temp_file, target)

            return UploadFwFileResponse(success=True, message="", sha256_digest=sha256)
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
            # Re-scan and update programmer assignments before flashing
            self._assign_jlinks(force_recovery=True)

            if request.file_info.name not in self.active_files:
                return FlashFwFileResponse(
                    success=False, message=f"Firmware file {request.file_info.name} not found", time_ms=0
                )

            file_path, stored_target = self.active_files[request.file_info.name]
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
                if not is_connected:
                    continue
                # Allow NRF9160 or NRF9151 programmer for NRF9160_MODEM targets
                if request.file_info.target in [HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9160_MODEM]:
                    if host_type in [HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9151]:
                        programmer = serial
                        break
                else:
                    if host_type == request.file_info.target:
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
            # Step 1: Recover if requested
            if request.recover:
                try:
                    recover_cmd = ["nrfjprog", "--recover", "--snr", programmer]
                    self.logger.info(f"Running recover: {' '.join(recover_cmd)}")
                    subprocess.run(
                        recover_cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=60,  # 1 minute timeout
                    )
                except subprocess.TimeoutExpired:
                    error_msg = f"Recover operation timed out after 1 minute for programmer {programmer}"
                    self.logger.error(error_msg)
                    return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
                except subprocess.CalledProcessError as e:
                    error_msg = f"Failed to recover programmer {programmer}: {e.stderr if e.stderr else str(e)}"
                    if e.stdout:
                        error_msg += f"\nstdout: {e.stdout}"
                    self.logger.error(error_msg)
                    return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
                except FileNotFoundError:
                    error_msg = "nrfjprog command not found. Please ensure nRF Command Line Tools are installed."
                    self.logger.error(error_msg)
                    return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
                except Exception as e:
                    error_msg = f"Unexpected error during recover operation: {str(e)}"
                    self.logger.error(error_msg)
                    return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)

            # Step 2: Build the nrfjprog programming command
            cmd = ["nrfjprog", "--program", str(file_path), "--verify", "--snr", programmer]
            if request.sector_erase:
                cmd.append("--sectorerase")

            # Step 3: Run the programming command
            self.logger.info(f"Running program: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,  # 1 minute timeout
            )
            time_ms = int((time.time() - start_time) * 1000)

            # Step 4: Run the verify command
            cmd = ["nrfjprog", "--verify", str(file_path), "--snr", programmer]

            # Step 3: Run the programming command
            self.logger.info(f"Running program: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,  # 1 minute timeout
            )
            time_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"Successfully flashed firmware in {time_ms}ms")
            return FlashFwFileResponse(success=True, message="", time_ms=time_ms)

        except subprocess.TimeoutExpired:
            error_msg = f"Flash operation timed out after 1 minute for programmer {programmer}"
            self.logger.error(error_msg)
            return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to flash firmware: {e.stderr if e.stderr else str(e)}"
            if e.stdout:
                error_msg += f"\nstdout: {e.stdout}"
            self.logger.error(error_msg)
            return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
        except FileNotFoundError:
            error_msg = "nrfjprog command not found. Please ensure nRF Command Line Tools are installed."
            self.logger.error(error_msg)
            return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
        except Exception as e:
            self.logger.error(f"Error flashing firmware: {e}")
            return FlashFwFileResponse(success=False, message=f"Failed to flash firmware: {str(e)}", time_ms=0)

    def erase_flash(self, request: EraseFlashRequest, context: grpc.ServicerContext) -> EraseFlashResponse:
        """Erase the flash memory on a target device.

        Based on nrfjprog documentation:
        - --chiperase: Erases all available non-volatile memory and UICR
        - --recover: Erases all user flash memory, UICR, and readback protection mechanism
        """
        self.logger.info(f"EraseFlash request received for {request.target}, recover={request.recover}")
        try:
            # Re-scan and update programmer assignments before erasing flash
            # Use force_recovery=True when recover flag is set, otherwise False
            self._assign_jlinks(force_recovery=request.recover)

            # Find a suitable programmer
            programmer = None
            for serial, (host_type, is_connected) in self.programmers.items():
                if not is_connected:
                    continue
                if host_type == request.target:
                    programmer = serial
                    break

            if not programmer:
                return EraseFlashResponse(
                    success=False, message=f"No suitable programmer found for target {request.target}"
                )

            # Choose the appropriate erase command based on recover flag
            # --chiperase: Erases all non-volatile memory and UICR (when recover=False)
            # --recover: Erases everything including readback protection (when recover=True)
            if request.recover:
                cmd = ["nrfjprog", "--recover", "--snr", programmer]
                self.logger.info(f"Running recover erase: {' '.join(cmd)}")
            else:
                cmd = ["nrfjprog", "--chiperase", "--snr", programmer]
                self.logger.info(f"Running chip erase: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,  # 1 minute timeout
            )
            self.logger.info(f"Successfully erased flash (recover={request.recover})")
            return EraseFlashResponse(success=True, message="")
        except Exception as e:
            self.logger.error(f"Error erasing flash: {e}")
            return EraseFlashResponse(success=False, message=f"Failed to erase flash: {str(e)}")

    def enable_app_protect(
        self, request: EnableAppProtectRequest, context: grpc.ServicerContext
    ) -> EnableAppProtectResponse:
        """Enable App Protect."""
        self.logger.info(f"EnableAppProtect request received for {request.target}")

        try:
            # Re-scan and update programmer assignments before enabling protection
            self._assign_jlinks(False)

            # Find a suitable programmer for the target
            programmer = None
            for serial, (host_type, is_connected) in self.programmers.items():
                if not is_connected:
                    continue
                # Allow NRF9160 or NRF9151 programmer for NRF9160_MODEM targets
                if request.target in [HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9160_MODEM]:
                    if host_type in [HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9151]:
                        programmer = serial
                        break
                else:
                    if host_type == request.target:
                        programmer = serial
                        break

            if not programmer:
                return EnableAppProtectResponse(
                    success=False, message=f"No suitable programmer found for target {request.target}"
                )

            # Determine chip family and protection parameters
            if request.target in [HostType.HOST_TYPE_NRF52840, HostType.HOST_TYPE_NRF5340]:
                # NRF52 family
                family = "NRF52"
                protect_addr = "0x10001208"
                protect_val = "0xFFFFFF00"
            elif request.target in [
                HostType.HOST_TYPE_NRF9160,
                HostType.HOST_TYPE_NRF9160_MODEM,
                HostType.HOST_TYPE_NRF9151,
            ]:
                # NRF91 family
                family = "NRF91"
                protect_addr = "0x00FF8000"
                protect_val = "0"
            else:
                return EnableAppProtectResponse(
                    success=False, message=f"Unsupported target {request.target} for App Protect"
                )

            self.logger.info(f"Enabling App Protect for {family} family on programmer {programmer}")

            # Step 1: Write the App Protect value
            try:
                protect_cmd = [
                    "nrfjprog",
                    "--family",
                    family,
                    "--memwr",
                    protect_addr,
                    "--val",
                    protect_val,
                    "--snr",
                    programmer,
                ]
                self.logger.info(f"Running App Protect write: {' '.join(protect_cmd)}")
                subprocess.run(
                    protect_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,  # 30 second timeout
                )
                self.logger.info(f"Successfully wrote App Protect value {protect_val} to address {protect_addr}")
            except subprocess.TimeoutExpired:
                error_msg = f"App Protect write operation timed out after 30 seconds for programmer {programmer}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to write App Protect value: {e.stderr if e.stderr else str(e)}"
                if e.stdout:
                    error_msg += f"\nstdout: {e.stdout}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)
            except FileNotFoundError:
                error_msg = "nrfjprog command not found. Please ensure nRF Command Line Tools are installed."
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)
            except Exception as e:
                error_msg = f"Unexpected error during App Protect write: {str(e)}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)

            # Step 2: Reset MCU to apply protection
            try:
                reset_cmd = ["nrfjprog", "--reset", "--snr", programmer]
                self.logger.info(f"Running reset: {' '.join(reset_cmd)}")
                result = subprocess.run(
                    reset_cmd,
                    capture_output=True,
                    text=True,
                    check=False,  # Don't fail on non-zero exit code, check output instead
                    timeout=30,  # 30 second timeout
                )

                # Check if reset failed due to access protection
                output = result.stdout + result.stderr
                if "Access protection is enabled" in output or "readback protection" in output.lower():
                    self.logger.info("Device already has access protection enabled - skipping reset")
                    # Protection is already active, proceed to verification
                elif result.returncode == 0:
                    self.logger.info("Successfully reset MCU to apply protection")
                else:
                    error_msg = f"Failed to reset MCU: {result.stderr if result.stderr else str(result)}"
                    if result.stdout:
                        error_msg += f"\nstdout: {result.stdout}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)

            except subprocess.TimeoutExpired:
                error_msg = f"Reset operation timed out after 30 seconds for programmer {programmer}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)
            except Exception as e:
                error_msg = f"Unexpected error during reset: {str(e)}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)

            # Step 3: Wait for MCU to boot (brief delay)
            self.logger.info("Waiting for MCU to boot...")
            time.sleep(2)  # Wait 2 seconds for MCU to boot

            # Step 4: Verify protection is active
            try:
                verify_cmd = [
                    "nrfjprog",
                    "--family",
                    family,
                    "--memrd",
                    "0x00000000",
                    "--n",
                    "4",
                    "--snr",
                    programmer,
                ]
                self.logger.info(f"Running protection verification: {' '.join(verify_cmd)}")
                result = subprocess.run(
                    verify_cmd,
                    capture_output=True,
                    text=True,
                    check=False,  # Don't fail on non-zero exit code, we expect this to fail
                    timeout=30,  # 30 second timeout
                )

                # Check if the expected protection message is in the output
                output = result.stdout + result.stderr
                protection_indicators = [
                    "Can't read memory descriptors, ap-protection is enabled.",
                    "Access protection is enabled",
                    "readback protection",
                    "unavailable due to readback protection",
                ]

                protection_active = any(indicator.lower() in output.lower() for indicator in protection_indicators)

                if protection_active:
                    self.logger.info("App Protect verification successful - protection is active")
                    return EnableAppProtectResponse(success=True, message="App Protect enabled successfully")
                else:
                    # If we can read memory, protection might not be active
                    self.logger.warning("App Protect verification inconclusive - protection status unclear")
                    self.logger.debug(f"Verification output: {output}")
                    return EnableAppProtectResponse(
                        success=False, message="App Protect verification failed - protection may not be active"
                    )

            except subprocess.TimeoutExpired:
                error_msg = f"Protection verification timed out after 30 seconds for programmer {programmer}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)
            except Exception as e:
                error_msg = f"Unexpected error during protection verification: {str(e)}"
                self.logger.error(error_msg)
                return EnableAppProtectResponse(success=False, message=error_msg)

        except Exception as e:
            self.logger.error(f"Error enabling App Protect: {e}")
            return EnableAppProtectResponse(success=False, message=f"Failed to enable App Protect: {str(e)}")

    def __del__(self):
        """Cleanup all temporary files when the handler is destroyed."""
        try:
            for filename in list(self.active_files.keys()):
                self._cleanup_file(filename)
            if self.ram_storage.exists():
                self.ram_storage.rmdir()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
