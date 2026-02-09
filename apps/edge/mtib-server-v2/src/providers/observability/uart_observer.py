"""UART observer that registers as an internal client to capture output."""

import threading
import time
from collections import deque
from queue import Empty as QueueEmpty
from typing import TYPE_CHECKING, Dict, List, Optional

from corekinect.utils import Logger

if TYPE_CHECKING:
    from src.providers.handlers.uart import UartConnection


class UartObserver:
    """Observes UART connections by registering as an internal client.

    Maintains a ring buffer of recent output lines and byte counters
    for each observed port. Background threads consume data from the
    UartConnection broadcast queues.
    """

    def __init__(self, logger: Logger, max_lines_per_port: int = 200):
        self.logger = logger
        self._max_lines = max_lines_per_port
        self._port_data: Dict[str, dict] = {}
        self._observer_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        # TX byte counters (written by handler thread, read by snapshot)
        self._tx_counts: Dict[str, int] = {}
        self._tx_lock = threading.Lock()

    def attach(self, port_name: str, uart_connection: "UartConnection") -> None:
        """Register as an internal client on a UartConnection and start consuming.

        Args:
            port_name: Logical port name (e.g. "uart0").
            uart_connection: The UartConnection to observe.
        """
        with self._lock:
            if port_name in self._observer_threads:
                return  # Already observing

            stream_id = f"_observer_{port_name}"
            rx_queue = uart_connection.register(stream_id)

            self._port_data[port_name] = {
                "port_name": port_name,
                "is_open": True,
                "baud_rate": uart_connection.port.baudrate if hasattr(uart_connection.port, "baudrate") else 0,
                "bytes_received": 0,
                "lines": deque(maxlen=self._max_lines),
                "stream_id": stream_id,
                "connection": uart_connection,
            }

            stop_event = threading.Event()
            self._stop_events[port_name] = stop_event

            thread = threading.Thread(
                target=self._consumer_loop,
                args=(port_name, rx_queue, stop_event),
                daemon=True,
                name=f"uart-observer-{port_name}",
            )
            self._observer_threads[port_name] = thread
            thread.start()

        self.logger.info(f"UartObserver: Attached to {port_name}")

    def detach(self, port_name: str) -> None:
        """Unregister from a UartConnection and stop consuming.

        Args:
            port_name: Logical port name to detach from.
        """
        with self._lock:
            stop_event = self._stop_events.pop(port_name, None)
            thread = self._observer_threads.pop(port_name, None)
            data = self._port_data.get(port_name)

        if stop_event:
            stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

        # Unregister from the connection
        if data:
            conn = data.get("connection")
            stream_id = data.get("stream_id")
            if conn and stream_id:
                conn.unregister(stream_id)

        with self._lock:
            if port_name in self._port_data:
                self._port_data[port_name]["is_open"] = False

        self.logger.info(f"UartObserver: Detached from {port_name}")

    def _consumer_loop(self, port_name: str, rx_queue, stop_event: threading.Event) -> None:
        """Background thread that reads from the RX queue and buffers lines."""
        partial_line = ""
        while not stop_event.is_set():
            try:
                data = rx_queue.get(timeout=0.5)
                if not data:
                    continue

                text = data.decode("utf-8", errors="replace")
                byte_count = len(data)

                with self._lock:
                    pd = self._port_data.get(port_name)
                    if pd is None:
                        break
                    pd["bytes_received"] += byte_count

                # Split into lines
                partial_line += text
                while "\n" in partial_line:
                    line, partial_line = partial_line.split("\n", 1)
                    line = line.rstrip("\r")
                    if line:
                        with self._lock:
                            pd = self._port_data.get(port_name)
                            if pd:
                                pd["lines"].append(line)
            except QueueEmpty:
                continue
            except Exception as e:
                if not stop_event.is_set():
                    self.logger.warning(f"UartObserver: Error on {port_name}: {e}")
                break

    def record_tx(self, port_name: str, byte_count: int) -> None:
        """Record bytes transmitted on a port.

        Args:
            port_name: Logical port name.
            byte_count: Number of bytes sent.
        """
        with self._tx_lock:
            self._tx_counts[port_name] = self._tx_counts.get(port_name, 0) + byte_count

    def get_status(self, port_name: str) -> Optional[dict]:
        """Return status for a single observed port."""
        with self._lock:
            pd = self._port_data.get(port_name)
            if pd is None:
                return None
            conn = pd.get("connection")
            with self._tx_lock:
                bytes_sent = self._tx_counts.get(port_name, 0)
            return {
                "port_name": pd["port_name"],
                "is_open": pd["is_open"],
                "baud_rate": pd["baud_rate"],
                "bytes_received": pd["bytes_received"],
                "bytes_sent": bytes_sent,
                "client_count": conn.client_count if conn else 0,
                "recent_lines": list(pd["lines"]),
            }

    def get_all_statuses(self) -> List[dict]:
        """Return status for all observed ports."""
        with self._lock:
            port_names = list(self._port_data.keys())
        return [s for name in port_names if (s := self.get_status(name)) is not None]
