"""gRPC UART handler using file-based streaming.

This replaces the complex uart.py with a simple wrapper around UartStreamManager.
Each gRPC client gets an independent UartReader that tails the buffer file.
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
    """Simplified UART handler using file-based streaming.

    Architecture:
    - One UartWriter per device (started on first use)
    - One UartReader per gRPC client (independent file handle)
    - Smart batching: newline OR 128 bytes triggers send
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
        """Handle bidirectional UART streaming.

        Each client gets an independent reader. Data is batched before sending.
        """
        target: Optional[HostType] = None
        reader: Optional[UartReader] = None
        stop_event = threading.Event()

        # RX data queue - reader thread pushes, main loop pops
        rx_queue: queue.Queue[bytes] = queue.Queue(maxsize=1000)

        def rx_pump():
            """Background thread: read batched data from file."""
            while not stop_event.is_set() and context.is_active():
                try:
                    for batch in reader.read_batched(timeout=0.05):
                        if stop_event.is_set():
                            break
                        try:
                            rx_queue.put_nowait(batch)
                        except queue.Full:
                            self.logger.warning("RX queue full, dropping batch")
                except Exception as e:
                    if not stop_event.is_set():
                        self.logger.debug(f"RX pump error: {e}")
                    time.sleep(0.01)

        rx_thread: Optional[threading.Thread] = None

        try:
            self.logger.info("UART stream started")

            for request in request_iterator:
                if not context.is_active():
                    break

                # Initialize on first request
                if target is None:
                    target = request.target
                    self.logger.info(f"UART stream for target {target}")

                    # Start UART if needed
                    err = self._ensure_uart_started(target)
                    if err:
                        context.set_code(grpc.StatusCode.INTERNAL)
                        context.set_details(err)
                        return

                    # Create reader for this client
                    reader = self._manager.create_reader(_uart_name(target))
                    if not reader:
                        context.set_code(grpc.StatusCode.INTERNAL)
                        context.set_details("Failed to create UART reader")
                        return

                    # Start RX pump thread
                    rx_thread = threading.Thread(target=rx_pump, daemon=True)
                    rx_thread.start()

                # Handle TX (client -> device)
                if request.data:
                    written = self._manager.write(_uart_name(target), request.data)
                    self.logger.debug(f"TX {written} bytes to {target}")

                # Yield all available RX data
                yielded = False
                while True:
                    try:
                        batch = rx_queue.get_nowait()
                        yield UartStreamResponse(
                            success=True,
                            message="",
                            target=target,
                            data=batch,
                        )
                        yielded = True
                    except queue.Empty:
                        break

                # Keep stream alive if no data
                if not yielded:
                    yield UartStreamResponse(
                        success=True,
                        message="",
                        target=target,
                    )

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.CANCELLED:
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
