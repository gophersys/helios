"""Flash programming handler with per-probe locking for parallel flash.

Integrates with the debug handler for session/probe tracking, with
ProbeManager for auto probe resolution and MUX switching, and uses
per-probe locks so that two nrfjprog processes targeting different
USB probes can run in parallel.
"""

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from corekinect.utils import Logger
from src.shared.types import (
    FlashEraseRequest,
    FlashInfoRequest,
    FlashInfoResponse,
    FlashProgramRequest,
    FlashProgramResponse,
    FlashRegion,
    FlashWriteRequest,
    FlashWriteResponse,
    Response,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext
    from .debug import DebugHandler
    from .target import ProbeManager

# Target ID → nrfjprog --family flag
TARGET_FAMILY_MAP = {
    "nrf52840": "NRF52",
    "nrf52": "NRF52",
    "nrf9160": "NRF91",
    "nrf9151": "NRF91",
    "nrf91": "NRF91",
    "nrf5340": "NRF53",
    "nrf53": "NRF53",
}


class FlashHandler:
    """Handles flash programming RPCs with per-probe parallel support."""

    JLINK_CLOCKSPEED_KHZ = 4000  # 4 MHz — stable through pogo pins

    def __init__(self, logger: Logger, hardware: "HardwareContext", assets_dir: str):
        self.logger = logger
        self.hardware = hardware
        self.assets_dir = assets_dir
        self._debug_handler: Optional["DebugHandler"] = None
        self._probe_manager: Optional["ProbeManager"] = None

    def set_debug_handler(self, debug_handler: "DebugHandler") -> None:
        """Set reference to debug handler for session lookups."""
        self._debug_handler = debug_handler

    def set_probe_manager(self, pm: "ProbeManager") -> None:
        """Set reference to ProbeManager for probe locking and MUX."""
        self._probe_manager = pm

    def info(self, request: FlashInfoRequest, context) -> FlashInfoResponse:
        """Get flash memory info for the connected target."""
        regions = [
            FlashRegion(start=0x00000000, size=0x100000, sector_size=4096, writable=True),
        ]
        return FlashInfoResponse(success=True, message="", regions=regions)

    def erase(self, request: FlashEraseRequest, context) -> Response:
        """Erase flash memory.

        Supports two modes:
        - Session-based: Provide session_id from DebugConnect
        - Direct: Provide target_id and probe_id directly (no session needed)
        """
        try:
            probe_id, target_id = self._resolve_target(
                session_id=request.session_id,
                target_id=getattr(request, "target_id", ""),
                probe_id=getattr(request, "probe_id", ""),
            )

            if not target_id:
                return Response(
                    success=False,
                    message="target_id required (via session_id or direct)",
                )

            # Set MUX via ProbeManager
            self._prepare_mux(target_id, probe_id)

            if request.address == 0 and request.size == 0:
                cmd = ["nrfjprog", "--chiperase"]
                cmd.extend(self._build_nrfjprog_flags_direct(probe_id, target_id))

                # Per-probe lock
                lock = self._get_probe_lock(probe_id)
                self.logger.info(f"Running chip erase: {' '.join(cmd)}")
                with lock:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    return Response(success=False, message=f"Erase failed: {result.stderr}")
                return Response(success=True, message="Chip erased")
            else:
                return Response(success=False, message="Sector erase not yet implemented")
        except FileNotFoundError:
            return Response(success=False, message="nrfjprog not found")
        except subprocess.TimeoutExpired:
            return Response(success=False, message="Erase operation timed out")
        except Exception as e:
            return Response(success=False, message=str(e))

    def write(self, request: FlashWriteRequest, context) -> FlashWriteResponse:
        """Write raw data to flash memory."""
        try:
            start_time = time.time()
            elapsed_ms = int((time.time() - start_time) * 1000)
            return FlashWriteResponse(
                success=False,
                message="Raw flash write requires active debug session (TODO: pyocd)",
                bytes_written=0,
                time_ms=elapsed_ms,
            )
        except Exception as e:
            return FlashWriteResponse(success=False, message=str(e), bytes_written=0, time_ms=0)

    def _resolve_target(
        self,
        session_id: str = "",
        target_id: str = "",
        probe_id: str = "",
    ) -> tuple:
        """Resolve target_id and probe_id from session or direct specification.

        Args:
            session_id: Debug session ID (Option A)
            target_id: Direct target specification (Option B)
            probe_id: Direct probe specification (Option B)

        Returns:
            (probe_id, target_id) tuple. Both may be None if unresolvable.

        Priority: Direct specification > Session lookup
        """
        # Option B: Direct specification takes priority
        if target_id or probe_id:
            resolved_probe = probe_id if probe_id else "auto"
            resolved_target = target_id if target_id else None
            return resolved_probe, resolved_target

        # Option A: Session lookup
        if session_id and self._debug_handler:
            session = self._debug_handler._sessions.get(session_id)
            if session:
                return session.probe_id, session.target_id

        return None, None

    def _build_nrfjprog_flags_direct(
        self,
        probe_id: Optional[str],
        target_id: Optional[str],
        include_family: bool = True,
    ) -> list:
        """Build nrfjprog flags from direct probe/target IDs."""
        flags = []
        if include_family and target_id:
            family = TARGET_FAMILY_MAP.get(target_id)
            if family:
                flags.extend(["--family", family])
        if probe_id and probe_id != "auto":
            flags.extend(["--snr", probe_id])
        flags.extend(["--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)])
        return flags

    def _get_probe_lock(self, probe_id: Optional[str]):
        """Get per-probe lock from ProbeManager, or a no-op context manager."""
        if self._probe_manager and probe_id and probe_id != "auto":
            return self._probe_manager.get_probe_lock(probe_id)
        return _NoOpLock()

    def _prepare_mux(self, target_id: Optional[str], probe_id: Optional[str]) -> None:
        """Set MUX position via ProbeManager if available."""
        if self._probe_manager and target_id and probe_id and probe_id != "auto":
            mux_err = self._probe_manager.prepare_mux_for_target(target_id, probe_id)
            if mux_err:
                self.logger.warning(f"MUX warning during flash: {mux_err}")

    def program(self, request: FlashProgramRequest, context) -> FlashProgramResponse:
        """Program a firmware file to flash.

        Supports two modes:
        - Session-based: Provide session_id from DebugConnect
        - Direct: Provide target_id and probe_id directly (no session needed)

        When erase_before is set, runs nrfjprog --recover first to clear
        APPROTECT and erase all flash/UICR before programming.

        Uses per-probe locking so that two parallel flash requests
        targeting different probes can run concurrently.
        """
        try:
            start_time = time.time()
            probe_id, target_id = self._resolve_target(
                session_id=request.session_id,
                target_id=getattr(request, "target_id", ""),
                probe_id=getattr(request, "probe_id", ""),
            )

            if not target_id:
                return FlashProgramResponse(
                    success=False,
                    message="target_id required (via session_id or direct)",
                    bytes_programmed=0,
                    time_ms=0,
                )

            # Resolve firmware file path
            fw_path = Path(self.assets_dir) / request.filename
            if not fw_path.exists():
                fw_path = Path("/dev/shm/mtib_fw_files") / request.filename
                if not fw_path.exists():
                    return FlashProgramResponse(
                        success=False,
                        message=f"Firmware file not found: {request.filename}",
                        bytes_programmed=0,
                        time_ms=0,
                    )

            # Set MUX position (outside lock — MUX is shared, but in dual
            # mode it stays NORMAL and in single mode requests are serialized
            # through the same probe lock anyway)
            self._prepare_mux(target_id, probe_id)

            nrfjprog_flags = self._build_nrfjprog_flags_direct(probe_id, target_id)
            lock = self._get_probe_lock(probe_id)

            # Acquire per-probe lock for the entire flash sequence
            # (recover → program → reset).  Different probes can run
            # in parallel since they have separate locks.
            with lock:
                # Step 1: Recover (erase + remove APPROTECT)
                if request.erase_before:
                    recover_flags = self._build_nrfjprog_flags_direct(
                        probe_id, target_id, include_family=False,
                    )
                    recover_cmd = ["nrfjprog", "--recover"]
                    recover_cmd.extend(recover_flags)

                    for attempt in range(2):
                        self.logger.info(
                            f"Recover (attempt {attempt + 1}): {' '.join(recover_cmd)}"
                        )
                        result = subprocess.run(
                            recover_cmd, capture_output=True, text=True, timeout=60,
                        )
                        if result.returncode == 0:
                            break
                        if attempt == 0:
                            self.logger.warning(
                                f"Recover attempt 1 failed, retrying in 3s: "
                                f"{result.stderr.strip()}"
                            )
                            time.sleep(3)
                        else:
                            return FlashProgramResponse(
                                success=False,
                                message=f"Recover failed: {result.stderr}",
                                bytes_programmed=0,
                                time_ms=int((time.time() - start_time) * 1000),
                            )

                # Step 2: Program the firmware
                cmd = ["nrfjprog", "--program", str(fw_path)]
                cmd.extend(nrfjprog_flags)
                if request.erase_before:
                    cmd.append("--sectorerase")
                if request.verify_after:
                    cmd.append("--verify")

                self.logger.info(f"Flashing: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120,
                )

                if result.returncode != 0:
                    return FlashProgramResponse(
                        success=False,
                        message=f"Flash failed: {result.stderr}",
                        bytes_programmed=0,
                        time_ms=int((time.time() - start_time) * 1000),
                    )

                # Step 3: Reset after programming
                if request.reset_after:
                    reset_cmd = ["nrfjprog", "--reset"]
                    reset_cmd.extend(nrfjprog_flags)
                    subprocess.run(
                        reset_cmd, capture_output=True, text=True, timeout=10,
                    )

            elapsed_ms = int((time.time() - start_time) * 1000)
            file_size = fw_path.stat().st_size

            return FlashProgramResponse(
                success=True,
                message="",
                bytes_programmed=file_size,
                time_ms=elapsed_ms,
            )
        except FileNotFoundError:
            return FlashProgramResponse(
                success=False, message="nrfjprog not found",
                bytes_programmed=0, time_ms=0,
            )
        except subprocess.TimeoutExpired:
            return FlashProgramResponse(
                success=False, message="Flash operation timed out",
                bytes_programmed=0, time_ms=0,
            )
        except Exception as e:
            return FlashProgramResponse(
                success=False, message=str(e),
                bytes_programmed=0, time_ms=0,
            )


class _NoOpLock:
    """Context manager that does nothing — used when no probe lock is needed."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
