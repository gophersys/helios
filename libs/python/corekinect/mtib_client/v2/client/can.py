from typing import Iterator, List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    CanConfig,
    CanFilterConfig,
    CanFrame as CanFrameProto,
    CanSendRequest,
    CanSetFilterRequest,
    Empty,
)

from ._base import BaseClient
from ..types.bus import CanFrame


class CanMixin(BaseClient):
    """CAN bus operations."""

    def can_configure(
        self,
        bus: int = 0,
        bitrate: int = 500000,
        fd_enabled: bool = False,
        fd_data_bitrate: int = 0,
    ) -> Optional[str]:
        """Configure a CAN bus interface.

        Args:
            bus: CAN bus number.
            bitrate: Nominal bitrate (125000, 250000, 500000, 1000000).
            fd_enabled: Enable CAN FD mode.
            fd_data_bitrate: CAN FD data phase bitrate.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "CanConfigure",
                CanConfig(
                    bus=bus,
                    bitrate=bitrate,
                    fd_enabled=fd_enabled,
                    fd_data_bitrate=fd_data_bitrate,
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"can_configure error: {e}"

    def can_send(
        self,
        bus: int,
        frame_id: int,
        data: bytes,
        extended_id: bool = False,
        fd: bool = False,
        brs: bool = False,
    ) -> Optional[str]:
        """Send a CAN frame.

        Args:
            bus: CAN bus number.
            frame_id: CAN frame ID.
            data: Frame payload data.
            extended_id: Use 29-bit extended ID.
            fd: Send as CAN FD frame.
            brs: Enable bit rate switch (CAN FD).

        Returns:
            Error message string, or None on success.
        """
        try:
            frame = CanFrameProto(
                id=frame_id, extended_id=extended_id, fd=fd, brs=brs, data=data
            )
            resp = self._call("CanSend", CanSendRequest(bus=bus, frame=frame))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"can_send error: {e}"

    def can_set_filter(
        self, bus: int, filters: List[Tuple[int, int, bool]]
    ) -> Optional[str]:
        """Set CAN receive filters.

        Args:
            bus: CAN bus number.
            filters: List of (id, mask, extended) filter tuples.

        Returns:
            Error message string, or None on success.
        """
        try:
            filter_configs = [
                CanFilterConfig(id=f[0], mask=f[1], extended=f[2]) for f in filters
            ]
            resp = self._call(
                "CanSetFilter", CanSetFilterRequest(bus=bus, filters=filter_configs)
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"can_set_filter error: {e}"

    def can_receive(self, timeout: float = None) -> Iterator[CanFrame]:
        """Stream received CAN frames.

        Args:
            timeout: Stream timeout in seconds.

        Yields:
            CanFrame objects for each received frame.
        """
        stream = self._server_stream("CanReceive", Empty(), timeout=timeout)
        for resp in stream:
            if not resp.success:
                continue
            f = resp.frame
            yield CanFrame(
                id=f.id,
                extended_id=f.extended_id,
                fd=f.fd,
                brs=f.brs,
                data=f.data,
                timestamp_s=f.timestamp.seconds if f.timestamp else 0,
                timestamp_ns=f.timestamp.nanos if f.timestamp else 0,
            )
