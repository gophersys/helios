from typing import List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    FlashEraseRequest,
    FlashInfoRequest,
    FlashProgramRequest,
    FlashWriteRequest,
)

from ._base import BaseClient
from ..types.flash import FlashInfo, FlashProgramResult, FlashRegion, FlashWriteResult


class FlashMixin(BaseClient):
    """Flash programming operations."""

    def flash_info(self, session_id: str) -> Tuple[Optional[str], Optional[FlashInfo]]:
        """Get flash memory layout information.

        Args:
            session_id: Active debug session ID.

        Returns:
            (error, FlashInfo) tuple. error is None on success.
        """
        try:
            resp = self._call("FlashInfo", FlashInfoRequest(session_id=session_id))
            if not resp.success:
                return resp.message, None
            regions = [
                FlashRegion(
                    start=r.start, size=r.size, sector_size=r.sector_size, writable=r.writable
                )
                for r in resp.regions
            ]
            return None, FlashInfo(regions=regions)
        except Exception as e:
            return f"flash_info error: {e}", None

    def flash_erase(
        self,
        session_id: str = "",
        address: int = 0,
        size: int = 0,
        *,
        target_id: str = "",
        probe_id: str = "",
    ) -> Optional[str]:
        """Erase flash memory.

        Two modes supported:
        - Session-based: Provide session_id from debug_connect()
        - Direct: Provide target_id and probe_id directly (no session needed)

        Args:
            session_id: Active debug session ID (Option A).
            address: Start address (0 for full chip erase).
            size: Size to erase (0 for full chip erase).
            target_id: Direct target specification, e.g., "nrf52840" (Option B).
            probe_id: Direct probe specification, e.g., "821009543" or "auto" (Option B).

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "FlashErase",
                FlashEraseRequest(
                    session_id=session_id,
                    address=address,
                    size=size,
                    target_id=target_id,
                    probe_id=probe_id,
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"flash_erase error: {e}"

    def flash_write(
        self, session_id: str, address: int, data: bytes, verify: bool = True
    ) -> Tuple[Optional[str], Optional[FlashWriteResult]]:
        """Write data to flash memory.

        Args:
            session_id: Active debug session ID.
            address: Flash address to write to.
            data: Data to write.
            verify: Whether to verify after writing.

        Returns:
            (error, FlashWriteResult) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "FlashWrite",
                FlashWriteRequest(
                    session_id=session_id, address=address, data=data, verify=verify
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, FlashWriteResult(bytes_written=resp.bytes_written, time_ms=resp.time_ms)
        except Exception as e:
            return f"flash_write error: {e}", None

    def flash_program(
        self,
        filename: str,
        session_id: str = "",
        erase_before: bool = True,
        verify_after: bool = True,
        reset_after: bool = True,
        *,
        target_id: str = "",
        probe_id: str = "",
    ) -> Tuple[Optional[str], Optional[FlashProgramResult]]:
        """Program a firmware file to flash.

        Two modes supported:
        - Session-based: Provide session_id from debug_connect()
        - Direct: Provide target_id and probe_id directly (no session needed)

        Args:
            filename: Name of the previously uploaded firmware file.
            session_id: Active debug session ID (Option A).
            erase_before: Whether to run --recover before programming.
            verify_after: Whether to verify after programming.
            reset_after: Whether to reset the target after programming.
            target_id: Direct target specification, e.g., "nrf52840" (Option B).
            probe_id: Direct probe specification, e.g., "821009543" or "auto" (Option B).

        Returns:
            (error, FlashProgramResult) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "FlashProgram",
                FlashProgramRequest(
                    session_id=session_id,
                    filename=filename,
                    erase_before=erase_before,
                    verify_after=verify_after,
                    reset_after=reset_after,
                    target_id=target_id,
                    probe_id=probe_id,
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, FlashProgramResult(
                bytes_programmed=resp.bytes_programmed, time_ms=resp.time_ms
            )
        except Exception as e:
            return f"flash_program error: {e}", None
