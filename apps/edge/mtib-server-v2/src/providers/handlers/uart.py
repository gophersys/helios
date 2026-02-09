"""UART handler for V2 protocol.

Provides real-time, event-driven UART communication with multi-client
support.  Architecture mirrors the proven V1 UART handler:

- UartConnection: Shared serial port per physical device.  A background
  RX thread continuously reads bytes and broadcasts them to every
  registered client queue — zero polling delay.
- UartHandler: Manages the connection pool, client registration, and
  the three gRPC RPCs (Open / Close / Stream).
- Stream RPC: TX runs in a background thread (so client writes never
  block the RX path).  The main generator thread yields RX data the
  instant it arrives in the per-client queue — true event-driven
  delivery with no added latency.

Multiple clients can subscribe to the same physical port simultaneously.
Data flows as fast as the UART produces it.
"""

import threading
import time
import uuid
from queue import Empty as QueueEmpty, Full as QueueFull, Queue
from typing import TYPE_CHECKING, Dict, Iterator, Optional

from corekinect.utils import Logger
from src.shared.types import (
    Parity as ProtoParity,
    FlowControl as ProtoFlowControl,
    Response,
    StopBits as ProtoStopBits,
    Timestamp,
    UartCloseRequest,
    UartOpenRequest,
    UartOpenResponse,
    UartStreamRequest,
    UartStreamResponse,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext
    from src.providers.observability.uart_observer import UartObserver

# Known UART device mappings
UART_DEVICE_MAP = {
    "uart0": "/dev/verdin-uart1",
    "uart1": "/dev/verdin-uart2",
    "cdc_acm": "/dev/ttyACM0",
}

# Maximum queued RX chunks per client before dropping the oldest.
RX_QUEUE_MAX = 10000


# ---------------------------------------------------------------------------
# UartConnection — shared serial port with broadcast RX
# ---------------------------------------------------------------------------
class UartConnection:
    """Shared serial port with background RX broadcasting.

    One RX thread reads from the physical UART and pushes every chunk to
    every registered client queue.  Multiple gRPC clients can share the
    same underlying serial port without interference.
    """

    def __init__(self, device_path: str, port, logger: Logger):
        self.device_path = device_path
        self.port = port
        self.logger = logger
        self._clients: Dict[str, Queue] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._rx_thread = threading.Thread(
            target=self._rx_loop, daemon=True, name=f"uart-rx-{device_path}"
        )
        self._rx_thread.start()

    # -- RX ------------------------------------------------------------------

    def _rx_loop(self) -> None:
        """Continuously read UART and broadcast to all clients."""
        while not self._stop.is_set():
            try:
                data = self.port.read(1)
                if data:
                    # Grab everything else already buffered
                    more = self.port.read(self.port.in_waiting)
                    if more:
                        data += more
                    self._broadcast(data)
                else:
                    time.sleep(0.001)  # Prevent busy-wait on timeout-read
            except Exception as e:
                if not self._stop.is_set():
                    self.logger.error(f"UART RX error on {self.device_path}: {e}")
                break

    def _broadcast(self, data: bytes) -> None:
        """Push *data* to every registered client queue."""
        with self._lock:
            for q in self._clients.values():
                try:
                    q.put_nowait(data)
                except QueueFull:
                    # Client not consuming fast enough — drop oldest chunk
                    try:
                        q.get_nowait()
                        q.put_nowait(data)
                    except (QueueEmpty, QueueFull):
                        pass

    # -- TX ------------------------------------------------------------------

    def write(self, data: bytes) -> None:
        """Write data to the serial port (thread-safe via pyserial lock)."""
        self.port.write(data)
        self.port.flush()

    # -- Client management ---------------------------------------------------

    def register(self, stream_id: str) -> Queue:
        """Register a client and return its dedicated RX queue."""
        q: Queue = Queue(maxsize=RX_QUEUE_MAX)
        with self._lock:
            self._clients[stream_id] = q
        return q

    def unregister(self, stream_id: str) -> None:
        """Remove a client from the broadcast list."""
        with self._lock:
            self._clients.pop(stream_id, None)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Stop RX thread and close the serial port."""
        self._stop.set()
        if self._rx_thread.is_alive():
            self._rx_thread.join(timeout=2.0)
        try:
            self.port.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# UartHandler — gRPC RPC implementation
# ---------------------------------------------------------------------------
class UartHandler:
    """Handles V2 UART RPCs with shared connections and multi-client broadcast."""

    def __init__(self, logger: Logger, hardware: "HardwareContext", uart_observer: Optional["UartObserver"] = None):
        self.logger = logger
        self.hardware = hardware
        self._connections: Dict[str, UartConnection] = {}  # device_path → conn
        self._streams: Dict[str, "_StreamInfo"] = {}       # stream_id  → info
        self._port_names: Dict[str, str] = {}              # device_path → port_name
        self._lock = threading.Lock()
        self._observer = uart_observer

    # -- Helpers -------------------------------------------------------------

    def _resolve_parity(self, parity: int) -> str:
        import serial
        mapping = {
            ProtoParity.PARITY_NONE: serial.PARITY_NONE,
            ProtoParity.PARITY_ODD: serial.PARITY_ODD,
            ProtoParity.PARITY_EVEN: serial.PARITY_EVEN,
        }
        return mapping.get(parity, serial.PARITY_NONE)

    def _resolve_stopbits(self, stop_bits: int) -> float:
        import serial
        mapping = {
            ProtoStopBits.STOP_BITS_1: serial.STOPBITS_ONE,
            ProtoStopBits.STOP_BITS_1_5: serial.STOPBITS_ONE_POINT_FIVE,
            ProtoStopBits.STOP_BITS_2: serial.STOPBITS_TWO,
        }
        return mapping.get(stop_bits, serial.STOPBITS_ONE)

    # -- RPCs ----------------------------------------------------------------

    def open(self, request: UartOpenRequest, context) -> UartOpenResponse:
        """Open a UART connection (reuses existing connection for same port)."""
        try:
            import serial as pyserial

            port_name = request.port_name
            device_path = UART_DEVICE_MAP.get(port_name, port_name)
            config = request.config
            baudrate = config.baud if config.baud > 0 else 115200

            with self._lock:
                # Reuse existing connection or create a new one
                conn = self._connections.get(device_path)
                if conn is None:
                    data_bits = config.data_bits if config.data_bits > 0 else 8
                    ser = pyserial.Serial(
                        port=device_path,
                        baudrate=baudrate,
                        bytesize=data_bits,
                        parity=self._resolve_parity(config.parity),
                        stopbits=self._resolve_stopbits(config.stop_bits),
                        xonxoff=False,
                        rtscts=False,
                        dsrdtr=False,
                        timeout=1,
                        write_timeout=1,
                    )
                    # Reset buffers on open (matches V1 behavior)
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    conn = UartConnection(
                        device_path=device_path, port=ser, logger=self.logger
                    )
                    self._connections[device_path] = conn
                    self._port_names[device_path] = port_name
                    self.logger.info(
                        f"UART opened: {device_path} @ {baudrate}bps"
                    )

                    if self._observer:
                        self._observer.attach(port_name, conn)

                stream_id = str(uuid.uuid4())
                rx_queue = conn.register(stream_id)
                self._streams[stream_id] = _StreamInfo(
                    device_path=device_path, rx_queue=rx_queue
                )

            self.logger.info(
                f"UART client registered: stream={stream_id[:8]}… "
                f"on {device_path} ({conn.client_count} client(s))"
            )
            return UartOpenResponse(success=True, message="", stream_id=stream_id)

        except Exception as e:
            self.logger.error(f"Failed to open UART: {e}")
            return UartOpenResponse(success=False, message=str(e), stream_id="")

    def close(self, request: UartCloseRequest, context) -> Response:
        """Close a UART client stream.  Closes device when last client leaves."""
        with self._lock:
            info = self._streams.pop(request.stream_id, None)
            if info is None:
                return Response(
                    success=False,
                    message=f"Unknown stream: {request.stream_id}",
                )

            conn = self._connections.get(info.device_path)
            if conn:
                conn.unregister(request.stream_id)
                remaining = conn.client_count
                if remaining == 0:
                    port_name = self._port_names.pop(info.device_path, None)
                    if self._observer and port_name:
                        self._observer.detach(port_name)
                    conn.close()
                    del self._connections[info.device_path]
                    self.logger.info(
                        f"UART device closed: {info.device_path} (last client)"
                    )
                else:
                    self.logger.info(
                        f"UART client removed: {info.device_path} "
                        f"({remaining} client(s) remaining)"
                    )

        return Response(success=True, message="UART closed")

    def stream(
        self,
        request_iterator: Iterator[UartStreamRequest],
        context,
    ) -> Iterator[UartStreamResponse]:
        """Bidirectional UART streaming — event-driven, real-time.

        TX: A background thread consumes the client request iterator and
            writes data to the serial port immediately.
        RX: The main thread blocks on the per-client queue and yields a
            response the instant data arrives — no polling delay.
        """
        info: Optional[_StreamInfo] = None
        conn: Optional[UartConnection] = None
        stop = threading.Event()
        init_error: list = []

        # -- TX background thread --------------------------------------------
        def tx_worker():
            nonlocal info, conn
            try:
                for request in request_iterator:
                    if not context.is_active() or stop.is_set():
                        break

                    # Resolve stream on first request
                    if info is None:
                        with self._lock:
                            info = self._streams.get(request.stream_id)
                            if info:
                                conn = self._connections.get(info.device_path)
                        if info is None:
                            init_error.append(
                                f"Unknown stream: {request.stream_id}"
                            )
                            return

                    # Write TX data to UART
                    if request.data and conn:
                        try:
                            conn.write(request.data)
                            if self._observer and info:
                                port_name = self._port_names.get(info.device_path)
                                if port_name:
                                    self._observer.record_tx(port_name, len(request.data))
                        except Exception as e:
                            self.logger.error(f"UART write error: {e}")
            except Exception as e:
                if not stop.is_set():
                    self.logger.error(f"UART TX worker error: {e}")
            finally:
                stop.set()

        tx_thread = threading.Thread(target=tx_worker, daemon=True, name="uart-tx")
        tx_thread.start()

        try:
            # Wait for the TX thread to resolve the stream info
            deadline = time.time() + 5.0
            while info is None and not stop.is_set() and time.time() < deadline:
                if init_error:
                    yield UartStreamResponse(
                        success=False, message=init_error[0]
                    )
                    return
                time.sleep(0.01)

            if info is None:
                msg = init_error[0] if init_error else "Stream resolution timeout"
                yield UartStreamResponse(success=False, message=msg)
                return

            # Drain stale data accumulated between stream calls.
            # This matches V1's behavior where data between streams is
            # dropped (no registered clients).  Without this drain, the
            # client would receive old data queued since the last stream
            # closed, which breaks prompt-based completion detection.
            stale = 0
            while True:
                try:
                    info.rx_queue.get_nowait()
                    stale += 1
                except QueueEmpty:
                    break
            if stale:
                self.logger.debug(
                    f"Drained {stale} stale RX chunks from queue"
                )

            # -- RX event loop -----------------------------------------------
            # Block on the client queue and yield data the instant it arrives.
            while context.is_active() and not stop.is_set():
                try:
                    data = info.rx_queue.get(timeout=0.5)
                    now = time.time()
                    yield UartStreamResponse(
                        success=True,
                        message="",
                        data=data,
                        timestamp=Timestamp(
                            seconds=int(now), nanos=int((now % 1) * 1e9)
                        ),
                    )
                except QueueEmpty:
                    # Yield empty keepalive to flush gRPC HTTP/2 write
                    # buffer.  Without this, server-side responses can
                    # be held in the HTTP/2 framing buffer until the
                    # next client-to-server frame triggers a flush —
                    # causing multi-second latency on UART data delivery.
                    yield UartStreamResponse(
                        success=True, message="", data=b""
                    )
                    continue

        except Exception as e:
            self.logger.error(f"UART stream error: {e}")
        finally:
            stop.set()
            tx_thread.join(timeout=2.0)
            self.logger.debug("UART stream ended")


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------
class _StreamInfo:
    """Per-client bookkeeping."""

    __slots__ = ("device_path", "rx_queue")

    def __init__(self, device_path: str, rx_queue: Queue):
        self.device_path = device_path
        self.rx_queue = rx_queue
