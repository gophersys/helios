from typing import Iterator, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    UartCloseRequest,
    UartConfig,
    UartOpenRequest,
    UartStreamRequest,
    UartStreamResponse,
)

from ._base import BaseClient
from ..types.uart import UartConnection


class UartMixin(BaseClient):
    """UART interface operations."""

    def uart_open(
        self,
        target_id: str,
        port_name: str = "uart0",
        baud: int = 115200,
        data_bits: int = 8,
        parity: int = 0,
        stop_bits: int = 0,
        flow_control: int = 0,
    ) -> Tuple[Optional[str], Optional[UartConnection]]:
        """Open a UART connection to a target.

        Args:
            target_id: Target device ID.
            port_name: UART port name (e.g. 'uart0', 'cdc_acm').
            baud: Baud rate.
            data_bits: Data bits (5-9).
            parity: Parity mode (0=NONE, 1=ODD, 2=EVEN).
            stop_bits: Stop bits (0=1, 1=1.5, 2=2).
            flow_control: Flow control (0=NONE, 1=RTS_CTS, 2=XON_XOFF).

        Returns:
            (error, UartConnection) tuple. error is None on success.
        """
        try:
            config = UartConfig(
                baud=baud,
                data_bits=data_bits,
                parity=parity,
                stop_bits=stop_bits,
                flow_control=flow_control,
            )
            resp = self._call(
                "UartOpen",
                UartOpenRequest(target_id=target_id, port_name=port_name, config=config),
            )
            if not resp.success:
                return resp.message, None
            return None, UartConnection(stream_id=resp.stream_id)
        except Exception as e:
            return f"uart_open error: {e}", None

    def uart_close(self, stream_id: str) -> Optional[str]:
        """Close a UART connection.

        Args:
            stream_id: UART stream ID from uart_open.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("UartClose", UartCloseRequest(stream_id=stream_id))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"uart_close error: {e}"

    def uart_stream(
        self, request_iterator: Iterator[UartStreamRequest], timeout: float = None
    ) -> Iterator[UartStreamResponse]:
        """Open a bidirectional UART data stream.

        Args:
            request_iterator: Iterator of UartStreamRequest messages to send.
            timeout: Stream timeout in seconds.

        Returns:
            Iterator of UartStreamResponse messages from the target.
        """
        return self._bidi_stream("UartStream", request_iterator, timeout=timeout)
