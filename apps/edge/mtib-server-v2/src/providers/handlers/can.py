"""CAN bus handler for V2 protocol."""

import time
from typing import TYPE_CHECKING, Iterator

from corekinect.utils import Logger
from src.shared.types import (
    CanConfig,
    CanFrame,
    CanReceiveResponse,
    CanSendRequest,
    CanSetFilterRequest,
    Empty,
    Response,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class CanHandler:
    """Handles CAN bus RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._bus = None
        self._filters: list = []

    def configure(self, request: CanConfig, context) -> Response:
        """Configure CAN bus."""
        try:
            import can

            interface = f"can{request.bus}" if request.bus >= 0 else "can0"
            self._bus = can.interface.Bus(
                channel=interface,
                interface="socketcan",
                bitrate=request.bitrate or 500000,
                fd=request.fd_enabled,
                data_bitrate=request.fd_data_bitrate or request.bitrate or 500000,
            )
            self.logger.info(f"CAN bus configured: {interface} @ {request.bitrate}bps")
            return Response(success=True, message="CAN configured")
        except ImportError:
            return Response(success=False, message="python-can not available")
        except Exception as e:
            return Response(success=False, message=str(e))

    def send(self, request: CanSendRequest, context) -> Response:
        """Send a CAN frame."""
        if self._bus is None:
            return Response(success=False, message="CAN bus not configured")
        try:
            import can

            frame = request.frame
            msg = can.Message(
                arbitration_id=frame.id,
                is_extended_id=frame.extended_id,
                is_fd=frame.fd,
                bitrate_switch=frame.brs,
                data=frame.data,
            )
            self._bus.send(msg)
            return Response(success=True, message="Frame sent")
        except Exception as e:
            return Response(success=False, message=str(e))

    def set_filter(self, request: CanSetFilterRequest, context) -> Response:
        """Set CAN receive filters."""
        if self._bus is None:
            return Response(success=False, message="CAN bus not configured")
        try:
            filters = []
            for f in request.filters:
                filters.append({
                    "can_id": f.id,
                    "can_mask": f.mask,
                    "extended": f.extended,
                })
            self._bus.set_filters(filters)
            return Response(success=True, message="Filters set")
        except Exception as e:
            return Response(success=False, message=str(e))

    def receive(self, request: Empty, context) -> Iterator[CanReceiveResponse]:
        """Server-streaming CAN frame receiver."""
        if self._bus is None:
            yield CanReceiveResponse(success=False, message="CAN bus not configured")
            return

        self.logger.info("CAN receive stream started")
        try:
            while context.is_active():
                msg = self._bus.recv(timeout=0.1)
                if msg is not None:
                    now = time.time()
                    frame = CanFrame(
                        id=msg.arbitration_id,
                        extended_id=msg.is_extended_id,
                        fd=msg.is_fd,
                        brs=msg.bitrate_switch,
                        data=bytes(msg.data),
                        timestamp=Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9)),
                    )
                    yield CanReceiveResponse(success=True, message="", frame=frame)
        except Exception as e:
            self.logger.error(f"CAN receive error: {e}")
        finally:
            self.logger.info("CAN receive stream ended")
