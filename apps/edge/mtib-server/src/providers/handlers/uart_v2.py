"""gRPC UART handler using file-based streaming with push-based RX.

Architecture:
- One UartWriter per device (reads serial port, writes to tmpfs buffer file)
- One UartReader per gRPC client (independent file handle, tails the buffer)
- RX is fully decoupled from TX: server pushes data as soon as it arrives
  from the serial port, without waiting for client requests
- TX requests are consumed by a background thread, written to serial immediately

Previous bottleneck (FIXED):
  The old implementation used `for request in request_iterator:` as the main
  loop, meaning the server could only yield RX data in response to a client
  request. At 20Hz client polling, this capped throughput to ~20 chunks/sec.
  At 115200 baud (~11520 bytes/sec), data would accumulate faster than it
  could be delivered, causing 30-60 second lag.

Fix:
  The request iterator is now consumed by a background thread. The main
  generator loop independently yields RX data as soon as it appears in the
  rx_queue, with a short (10ms) blocking timeout to stay responsive. This
  means the server pushes data at the rate it arrives from the serial port,
  not at the client's polling rate.
"""

import queue
import threading
import time
from typing import Dict, Iterator, Optional

import grpc
from corekinect.utils import Logger

from src.shared.uart_stream import (
    UartConfig,
    UartReader,
    UartStreamManager,
    get_manager,
)
from src.shared.types import HostType, UartStreamRequest, UartStreamResponse


# Map HostType to UART device paths
UART_DEVICES = {
    HostType.HOST_TYPE_NRF9160: "/dev/verdin-uart1",
    HostType.HOST_TYPE_NRF9151: "/dev/verdin-uart1",
    HostType.HOST_TYPE_NRF52840: "/dev/verdin-uart2",
    HostType.HOST_TYPE_NRF5340: "/dev/verdin-uart1",
}


def _uart_name(target: HostType) -> str:
    """Get UART name for a target."""
    return f"uart-{target}"


class UartHandlerV2:
    """Push-based UART handler using file-based streaming.

    Architecture:
    - One UartWriter per device (started on first use)
    - One UartReader per gRPC client (independent file handle)
    - RX data is pushed to the client as soon as it arrives (not request-gated)
    - TX data from client requests is written to the serial port immediately
    - Smart batching: newline OR 256 bytes OR 20ms timeout triggers a chunk
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self._manager = get_manager()
        self._active_targets: set[HostType] = set()
        self._lock = threading.Lock()

    def _ensure_uart_started(self, target: HostType) -> Optional[str]:
        """Ensure UART writer is running for target."""
        with self._lock:
            if target in self._active_targets:
                return None

            device = UART_DEVICES.get(target)
            if not device:
                return f"Unknown target: {target}"

            name = _uart_name(target)
            config = UartConfig(device=device)

            err = self._manager.start_uart(name, config)
            if err:
                return err

            self._active_targets.add(target)
            self.logger.info(f"Started UART {name} on {device}")
            return None

    def stream(
        self,
        request_iterator: Iterator[UartStreamRequest],
        context: grpc.ServicerContext,
    ) -> Iterator[UartStreamResponse]:
        """Handle bidirectional UART streaming with push-based RX.

        Key design: RX and TX are fully decoupled.
        - A background thread consumes client requests (TX path)
        - A background thread reads serial data into rx_queue (RX path)
        - The main generator yields RX data as soon as it arrives,
          WITHOUT waiting for the next client request

        This eliminates the previous bottleneck where the server could
        only yield one response per client request (20Hz = 20 chunks/sec).
        Now the server pushes data at the rate it arrives from serial.
        """
        target: Optional[HostType] = None
        reader: Optional[UartReader] = None
        stop_event = threading.Event()

        # Event signaled once target is known and UART is ready
        target_ready = threading.Event()
        # Container for target set by tx_consumer thread
        target_container: list = [None]
        init_error: list = [None]

        # RX data queue - reader thread pushes, main generator pops
        rx_queue: queue.Queue[bytes] = queue.Queue(maxsize=2000)

        def rx_pump():
            """Background thread: read batched data from buffer file."""
            target_ready.wait(timeout=10.0)
            if stop_event.is_set():
                return

            while not stop_event.is_set() and context.is_active():
                try:
                    for batch in reader.read_batched(timeout=0.05):
                        if stop_event.is_set():
                            break
                        try:
                            rx_queue.put_nowait(batch)
                        except queue.Full:
                            # Drop oldest to make room (prevent unbounded backlog)
                            try:
                                rx_queue.get_nowait()
                            except queue.Empty:
                                pass
                            try:
                                rx_queue.put_nowait(batch)
                            except queue.Full:
                                pass
                except Exception as e:
                    if not stop_event.is_set():
                        self.logger.debug(f"RX pump error: {e}")
                    time.sleep(0.01)

        def tx_consumer():
            """Background thread: consume client requests, handle TX writes.

            This is the key change: the request iterator is consumed here
            in a background thread, NOT in the main generator loop. This
            allows the main generator to yield RX data independently.
            """
            nonlocal target, reader
            try:
                for request in request_iterator:
                    if stop_event.is_set() or not context.is_active():
                        break

                    # Initialize on first request
                    if target_container[0] is None:
                        target_container[0] = request.target
                        target = request.target
                        self.logger.info(f"UART stream for target {target}")

                        # Start UART if needed
                        err = self._ensure_uart_started(target)
                        if err:
                            init_error[0] = err
                            stop_event.set()
                            target_ready.set()
                            return

                        # Create reader for this client
                        reader = self._manager.create_reader(_uart_name(target))
                        if not reader:
                            init_error[0] = "Failed to create UART reader"
                            stop_event.set()
                            target_ready.set()
                            return

                        # Signal that target is ready
                        target_ready.set()

                    # Handle TX data (client -> device)
                    if request.data:
                        written = self._manager.write(
                            _uart_name(target_container[0]), request.data
                        )
                        if written > 0:
                            self.logger.debug(
                                f"TX {written} bytes to {target_container[0]}"
                            )

            except grpc.RpcError:
                pass  # Client disconnected
            except Exception as e:
                if not stop_event.is_set():
                    self.logger.debug(f"TX consumer error: {e}")
            finally:
                stop_event.set()
                target_ready.set()  # Unblock in case we never got a request

        rx_thread: Optional[threading.Thread] = None
        tx_thread: Optional[threading.Thread] = None

        try:
            self.logger.info("UART stream started (push-based)")

            # Start TX consumer thread to handle client requests
            tx_thread = threading.Thread(
                target=tx_consumer, daemon=True, name="uart-tx-consumer"
            )
            tx_thread.start()

            # Wait for target initialization
            target_ready.wait(timeout=10.0)
            if init_error[0]:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(init_error[0])
                return

            if stop_event.is_set():
                return

            target = target_container[0]
            if target is None:
                return

            # Start RX pump thread
            rx_thread = threading.Thread(
                target=rx_pump, daemon=True, name="uart-rx-pump"
            )
            rx_thread.start()

            # Main generator loop: yield RX data as soon as it arrives.
            # This loop is NOT gated by client requests -- it pushes data
            # to the client at the rate it arrives from the serial port.
            while not stop_event.is_set() and context.is_active():
                try:
                    # Block up to 10ms waiting for data. This short timeout
                    # keeps the loop responsive to stop_event/context changes
                    # while avoiding busy-spinning.
                    batch = rx_queue.get(timeout=0.01)
                    yield UartStreamResponse(
                        success=True,
                        message="",
                        target=target,
                        data=batch,
                    )
                except queue.Empty:
                    # No data within 10ms -- that's fine, just loop again.
                    # Do NOT yield an empty response here; that would waste
                    # bandwidth and add gRPC overhead for no benefit.
                    continue

        except grpc.RpcError as e:
            if hasattr(e, 'code') and e.code() == grpc.StatusCode.CANCELLED:
                self.logger.info("UART stream cancelled")
            else:
                self.logger.error(f"UART stream error: {e}")

        except Exception as e:
            self.logger.error(f"UART stream error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

        finally:
            stop_event.set()
            if reader:
                reader.close()
            if rx_thread:
                rx_thread.join(timeout=1.0)
            if tx_thread:
                tx_thread.join(timeout=1.0)
            self.logger.info(f"UART stream ended for {target}")

    def close_all(self):
        """Close all UART connections."""
        self._manager.stop_all()
        with self._lock:
            self._active_targets.clear()
        self.logger.info("All UARTs closed")


# Quick test
if __name__ == "__main__":
    import sys

    logging_config = {"level": "DEBUG"}

    class SimpleLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def debug(self, msg): print(f"DEBUG: {msg}")
        def warning(self, msg): print(f"WARN: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")

    logger = SimpleLogger()

    # Test the batcher
    from src.shared.uart_stream import LineBatcher

    batcher = LineBatcher()

    # Test newline batching
    test_data = b"Hello\nWorld\nThis is a test"
    print(f"Input: {test_data}")
    print("Batches:")
    for batch in batcher.feed(test_data):
        print(f"  {batch!r}")

    # Remaining (no newline yet)
    remaining = batcher.flush_all()
    if remaining:
        print(f"  (flushed) {remaining!r}")

    # Test max bytes batching
    batcher2 = LineBatcher()
    long_data = b"x" * 200  # No newlines, exceeds 128
    print(f"\nLong input ({len(long_data)} bytes, no newlines):")
    for batch in batcher2.feed(long_data):
        print(f"  {len(batch)} bytes")

    remaining = batcher2.flush_all()
    if remaining:
        print(f"  (flushed) {len(remaining)} bytes")
