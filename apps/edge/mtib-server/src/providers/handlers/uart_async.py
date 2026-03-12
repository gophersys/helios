"""Async UART stream handler with true bidirectional streaming.

This module implements LOW-LATENCY UART streaming using grpc.aio:
- TX and RX streams are fully decoupled
- Server pushes RX data immediately when available (no request-gating)
- Batching: newline OR 128 bytes OR 50ms timeout
- Target latency: <10ms from serial port to network

The key insight: gRPC bidirectional streams are INDEPENDENT. The server
can yield responses at any time, not just in response to client requests.
"""

import asyncio
import queue
import threading
import time
from typing import AsyncIterator, Optional

import grpc
import serial
from corekinect.utils import Logger

from src.shared.types import *


class AsyncUartHandler:
    """Async handler for UART streaming with true push-based RX.

    Architecture:
    - Serial RX thread: reads from serial port, feeds async queue
    - Async RX task: yields data to client immediately
    - Async TX task: consumes client requests, writes to serial port
    - Both streams run independently, maximizing throughput

    Data flow (RX - from device to client):
    1. Serial RX thread reads bytes from serial port
    2. Bytes are batched (newline/128 bytes/50ms timeout)
    3. Batched chunks are put into asyncio.Queue
    4. Async generator yields chunks immediately to client

    Data flow (TX - from client to device):
    1. Client sends request with data
    2. Async consumer puts data into TX queue
    3. Serial TX thread writes to device
    """

    # Batching config
    BATCH_MAX_BYTES = 128
    BATCH_TIMEOUT_MS = 50
    BATCH_NEWLINE_CHARS = b'\n\r'

    def __init__(self, logger: Logger):
        self.logger = logger

        # UART device paths (same as sync handler)
        self.uart_devices = {
            HostType.HOST_TYPE_NRF9160: "/dev/verdin-uart1",
            HostType.HOST_TYPE_NRF52840: "/dev/verdin-uart2",
            HostType.HOST_TYPE_NRF5340: "/dev/verdin-uart1",
            HostType.HOST_TYPE_NRF9151: "/dev/verdin-uart1",
        }

        # Active connections
        self._connections: dict[HostType, serial.Serial] = {}
        self._connection_locks: dict[HostType, threading.Lock] = {}

        # Per-target state
        self._rx_threads: dict[HostType, threading.Thread] = {}
        self._tx_threads: dict[HostType, threading.Thread] = {}
        self._stop_events: dict[HostType, threading.Event] = {}
        self._tx_queues: dict[HostType, queue.Queue] = {}

        # Async queues for RX data (bridging sync serial to async gRPC)
        self._rx_async_queues: dict[HostType, asyncio.Queue] = {}
        self._event_loops: dict[HostType, asyncio.AbstractEventLoop] = {}

    def _ensure_connection(self, target: HostType) -> Optional[str]:
        """Ensure serial connection exists. Returns error string or None."""
        if target not in self._connection_locks:
            self._connection_locks[target] = threading.Lock()

        with self._connection_locks[target]:
            if target in self._connections and self._connections[target].is_open:
                return None

            device_path = self.uart_devices.get(target)
            if not device_path:
                return f"Unknown target {target}"

            try:
                uart = serial.Serial(
                    port=device_path,
                    baudrate=115200,
                    timeout=0.01,  # 10ms read timeout for responsive polling
                    write_timeout=1,
                )
                uart.reset_input_buffer()
                uart.reset_output_buffer()
                self._connections[target] = uart
                self.logger.info(f"Opened UART {device_path} for {target}")
                return None
            except Exception as e:
                return f"Failed to open {device_path}: {e}"

    def _start_serial_threads(
        self,
        target: HostType,
        rx_async_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ):
        """Start background threads for serial I/O."""
        if target in self._stop_events:
            self._stop_events[target].set()
            if target in self._rx_threads:
                self._rx_threads[target].join(timeout=1)
            if target in self._tx_threads:
                self._tx_threads[target].join(timeout=1)

        stop_event = threading.Event()
        self._stop_events[target] = stop_event
        self._tx_queues[target] = queue.Queue()
        self._rx_async_queues[target] = rx_async_queue
        self._event_loops[target] = loop

        # RX thread with batching
        def rx_worker():
            uart = self._connections[target]
            buffer = bytearray()
            last_flush_time = time.time()

            self.logger.info(f"RX thread started for {target}")

            while not stop_event.is_set():
                try:
                    # Block until at least 1 byte arrives (up to serial timeout)
                    first = uart.read(1)
                    if first:
                        # Grab all remaining available bytes
                        in_waiting = uart.in_waiting
                        if in_waiting > 0:
                            rest = uart.read(min(in_waiting, 4096))
                            buffer.extend(first + rest)
                        else:
                            buffer.extend(first)
                    # If first is empty, serial.read timed out -- check flush

                    # Check flush conditions
                    now = time.time()
                    should_flush = False
                    flush_pos = len(buffer)

                    # Condition 1: newline found
                    for i, byte in enumerate(buffer):
                        if byte in self.BATCH_NEWLINE_CHARS:
                            flush_pos = i + 1
                            should_flush = True
                            break

                    # Condition 2: buffer full
                    if not should_flush and len(buffer) >= self.BATCH_MAX_BYTES:
                        flush_pos = self.BATCH_MAX_BYTES
                        should_flush = True

                    # Condition 3: timeout
                    if not should_flush and buffer:
                        elapsed_ms = (now - last_flush_time) * 1000
                        if elapsed_ms >= self.BATCH_TIMEOUT_MS:
                            should_flush = True

                    # Flush if needed
                    if should_flush and buffer:
                        chunk = bytes(buffer[:flush_pos])
                        del buffer[:flush_pos]
                        last_flush_time = now

                        # Put into async queue (thread-safe via loop.call_soon_threadsafe)
                        try:
                            loop.call_soon_threadsafe(
                                rx_async_queue.put_nowait, chunk
                            )
                        except asyncio.QueueFull:
                            self.logger.warning(f"RX queue full for {target}, dropping")

                except Exception as e:
                    if not stop_event.is_set():
                        self.logger.error(f"RX error for {target}: {e}")
                    break

            self.logger.info(f"RX thread stopped for {target}")

        # TX thread
        def tx_worker():
            uart = self._connections[target]
            tx_queue = self._tx_queues[target]

            self.logger.info(f"TX thread started for {target}")

            while not stop_event.is_set():
                try:
                    data = tx_queue.get(timeout=0.1)
                    if data:
                        uart.write(data)
                        uart.flush()
                except queue.Empty:
                    continue
                except Exception as e:
                    if not stop_event.is_set():
                        self.logger.error(f"TX error for {target}: {e}")
                    break

            self.logger.info(f"TX thread stopped for {target}")

        self._rx_threads[target] = threading.Thread(
            target=rx_worker, daemon=True, name=f"uart-rx-{target}"
        )
        self._tx_threads[target] = threading.Thread(
            target=tx_worker, daemon=True, name=f"uart-tx-{target}"
        )
        self._rx_threads[target].start()
        self._tx_threads[target].start()

    def _stop_serial_threads(self, target: HostType):
        """Stop serial threads for a target."""
        if target in self._stop_events:
            self._stop_events[target].set()
        if target in self._rx_threads:
            self._rx_threads[target].join(timeout=1)
        if target in self._tx_threads:
            self._tx_threads[target].join(timeout=1)
        if target in self._connections:
            try:
                self._connections[target].close()
            except:
                pass
            del self._connections[target]

    async def stream(
        self,
        request_iterator: AsyncIterator[UartStreamRequest],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[UartStreamResponse]:
        """Async bidirectional UART stream.

        This is the key difference from the sync implementation:
        - RX yields are NOT gated by client requests
        - We use asyncio.create_task to handle TX independently
        - RX data is pushed as soon as it arrives
        """
        target: Optional[HostType] = None
        rx_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        loop = asyncio.get_running_loop()

        async def tx_consumer():
            """Consume TX requests from client."""
            nonlocal target
            try:
                async for request in request_iterator:
                    if target is None:
                        target = request.target
                        self.logger.info(f"Stream started for target {target}")

                        # Establish connection
                        if err := self._ensure_connection(target):
                            await context.abort(
                                grpc.StatusCode.INTERNAL,
                                f"UART connection failed: {err}"
                            )
                            return

                        # Start serial threads
                        self._start_serial_threads(target, rx_queue, loop)

                    # Handle TX data
                    if request.data and target in self._tx_queues:
                        self._tx_queues[target].put(request.data)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"TX consumer error: {e}")

        # Start TX consumer as background task
        tx_task = asyncio.create_task(tx_consumer())

        try:
            # Wait for target to be set
            while target is None:
                await asyncio.sleep(0.01)
                if context.cancelled():
                    return

            self.logger.info(f"RX stream active for {target}")

            # Yield RX data as soon as it arrives (TRUE PUSH)
            while not context.cancelled():
                try:
                    # Wait for data with timeout (allows checking cancelled state)
                    data = await asyncio.wait_for(rx_queue.get(), timeout=0.1)
                    yield UartStreamResponse(
                        success=True,
                        target=target,
                        data=data,
                    )
                except asyncio.TimeoutError:
                    # No data, check if still active
                    continue
                except asyncio.CancelledError:
                    break

        except Exception as e:
            self.logger.error(f"RX stream error: {e}")

        finally:
            tx_task.cancel()
            try:
                await tx_task
            except asyncio.CancelledError:
                pass

            if target:
                self._stop_serial_threads(target)
                self.logger.info(f"Stream ended for {target}")


# Singleton instance
_handler: Optional[AsyncUartHandler] = None


def get_async_uart_handler(logger: Logger) -> AsyncUartHandler:
    """Get or create the async UART handler singleton."""
    global _handler
    if _handler is None:
        _handler = AsyncUartHandler(logger)
    return _handler
