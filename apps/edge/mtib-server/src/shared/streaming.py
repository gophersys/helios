"""Stream broadcasting infrastructure for multi-subscriber real-time streams.

This module provides low-latency broadcasting of hardware streams (UART, power, etc.)
to multiple subscribers with configurable batching strategies.

Design goals:
- Single hardware read thread per source
- O(1) subscriber add/remove
- Configurable batching (newline, byte count, timeout)
- Thread-safe subscriber management
- <100ms latency from hardware to subscriber

Usage:
    # Create a broadcaster for a UART stream
    broadcaster = StreamBroadcaster("uart0", lambda: read_uart_data())
    broadcaster.start()

    # Subscribe to receive data
    subscription = broadcaster.subscribe()
    for chunk in subscription:
        process(chunk)

    # Cleanup
    subscription.unsubscribe()
    broadcaster.stop()
"""

import queue
import threading
import time
import weakref
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Iterator, List, Optional, Set, TypeVar

from corekinect.utils import Logger


T = TypeVar("T")


class BatchStrategy(Enum):
    """Batching strategies for stream data."""

    # No batching - deliver immediately
    NONE = "none"

    # Batch until newline OR max bytes reached
    NEWLINE_OR_BYTES = "newline_or_bytes"

    # Batch until timeout OR max bytes reached
    TIMEOUT_OR_BYTES = "timeout_or_bytes"


@dataclass
class BatchConfig:
    """Configuration for stream batching."""

    strategy: BatchStrategy = BatchStrategy.NEWLINE_OR_BYTES
    max_bytes: int = 256
    timeout_ms: int = 50  # Max wait before flushing partial buffer
    newline_chars: bytes = b"\n\r"


@dataclass
class StreamStats:
    """Statistics for a stream broadcaster."""

    total_bytes_read: int = 0
    total_chunks_delivered: int = 0
    subscriber_count: int = 0
    start_time: float = field(default_factory=time.time)
    last_data_time: Optional[float] = None


class Subscription(Generic[T]):
    """A subscription to a stream broadcaster.

    Implements iterator protocol for convenient consumption.
    """

    def __init__(
        self,
        broadcaster: "StreamBroadcaster",
        data_queue: "queue.Queue[T]",
        subscriber_id: int,
    ):
        self._broadcaster = broadcaster
        self._queue = data_queue
        self._id = subscriber_id
        self._active = True

    @property
    def id(self) -> int:
        return self._id

    @property
    def active(self) -> bool:
        return self._active

    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """Get next chunk from the subscription.

        Returns None on timeout or if subscription is closed.
        """
        if not self._active:
            return None
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_nowait(self) -> Optional[T]:
        """Get next chunk without blocking."""
        if not self._active:
            return None
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def unsubscribe(self):
        """Unsubscribe from the broadcaster."""
        if self._active:
            self._active = False
            self._broadcaster._remove_subscriber(self._id)

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        while self._active:
            try:
                # Block with short timeout to check active state periodically
                data = self._queue.get(timeout=0.05)
                return data
            except queue.Empty:
                continue
        raise StopIteration

    def __enter__(self) -> "Subscription[T]":
        return self

    def __exit__(self, *args):
        self.unsubscribe()


class StreamBroadcaster:
    """Broadcasts data from a single source to multiple subscribers.

    Thread-safe management of subscribers with configurable batching.
    """

    _next_broadcaster_id = 0
    _next_subscriber_id = 0
    _id_lock = threading.Lock()

    def __init__(
        self,
        name: str,
        logger: Logger,
        batch_config: Optional[BatchConfig] = None,
    ):
        """Initialize the broadcaster.

        Args:
            name: Human-readable name for logging
            logger: Logger instance
            batch_config: Batching configuration (defaults to newline/256 bytes)
        """
        with StreamBroadcaster._id_lock:
            StreamBroadcaster._next_broadcaster_id += 1
            self._id = StreamBroadcaster._next_broadcaster_id

        self._name = name
        self._logger = logger.from_parent(f"broadcaster-{name}")
        self._batch_config = batch_config or BatchConfig()

        # Subscriber management
        self._subscribers: dict[int, queue.Queue] = {}
        self._subscriber_lock = threading.Lock()

        # Batching state
        self._buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._last_flush_time = time.time()

        # Thread control
        self._running = False
        self._source_thread: Optional[threading.Thread] = None
        self._flush_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Stats
        self._stats = StreamStats()

    @property
    def name(self) -> str:
        return self._name

    @property
    def stats(self) -> StreamStats:
        with self._subscriber_lock:
            self._stats.subscriber_count = len(self._subscribers)
        return self._stats

    @property
    def running(self) -> bool:
        return self._running

    def subscribe(self, queue_size: int = 1000) -> Subscription[bytes]:
        """Create a new subscription to this broadcaster.

        Args:
            queue_size: Max items to buffer per subscriber before dropping

        Returns:
            A Subscription object for receiving data
        """
        with StreamBroadcaster._id_lock:
            StreamBroadcaster._next_subscriber_id += 1
            sub_id = StreamBroadcaster._next_subscriber_id

        data_queue: queue.Queue[bytes] = queue.Queue(maxsize=queue_size)

        with self._subscriber_lock:
            self._subscribers[sub_id] = data_queue
            self._logger.debug(
                f"Subscriber {sub_id} added, total: {len(self._subscribers)}"
            )

        return Subscription(self, data_queue, sub_id)

    def _remove_subscriber(self, subscriber_id: int):
        """Remove a subscriber by ID."""
        with self._subscriber_lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                self._logger.debug(
                    f"Subscriber {subscriber_id} removed, total: {len(self._subscribers)}"
                )

    def _broadcast(self, data: bytes):
        """Broadcast data to all subscribers."""
        if not data:
            return

        with self._subscriber_lock:
            dead_subs = []
            for sub_id, q in self._subscribers.items():
                try:
                    q.put_nowait(data)
                except queue.Full:
                    self._logger.warning(
                        f"Subscriber {sub_id} queue full, dropping data"
                    )
                except Exception as e:
                    self._logger.debug(f"Subscriber {sub_id} error: {e}")
                    dead_subs.append(sub_id)

            # Clean up dead subscribers
            for sub_id in dead_subs:
                del self._subscribers[sub_id]

        self._stats.total_chunks_delivered += 1
        self._stats.last_data_time = time.time()

    def feed(self, data: bytes):
        """Feed raw data into the broadcaster for batching and delivery.

        This is the main entry point for source threads to push data.
        The data will be batched according to the configured strategy.
        """
        if not data:
            return

        self._stats.total_bytes_read += len(data)

        if self._batch_config.strategy == BatchStrategy.NONE:
            # No batching - deliver immediately
            self._broadcast(data)
            return

        with self._buffer_lock:
            self._buffer.extend(data)
            self._try_flush()

    def _try_flush(self):
        """Attempt to flush the buffer based on batching strategy.

        Must be called with _buffer_lock held.
        """
        if not self._buffer:
            return

        strategy = self._batch_config.strategy

        if strategy == BatchStrategy.NEWLINE_OR_BYTES:
            self._flush_newline_or_bytes()
        elif strategy == BatchStrategy.TIMEOUT_OR_BYTES:
            self._flush_timeout_or_bytes()

    def _flush_newline_or_bytes(self):
        """Flush on newline OR when buffer exceeds max_bytes.

        Must be called with _buffer_lock held.
        """
        max_bytes = self._batch_config.max_bytes
        newline_chars = self._batch_config.newline_chars

        while self._buffer:
            # Find first newline
            newline_pos = -1
            for i, byte in enumerate(self._buffer):
                if byte in newline_chars:
                    newline_pos = i
                    break

            if newline_pos >= 0:
                # Flush up to and including the newline
                chunk = bytes(self._buffer[: newline_pos + 1])
                del self._buffer[: newline_pos + 1]
                self._broadcast(chunk)
                self._last_flush_time = time.time()
            elif len(self._buffer) >= max_bytes:
                # Flush max_bytes worth
                chunk = bytes(self._buffer[:max_bytes])
                del self._buffer[:max_bytes]
                self._broadcast(chunk)
                self._last_flush_time = time.time()
            else:
                # Not enough data yet
                break

    def _flush_timeout_or_bytes(self):
        """Flush on timeout OR when buffer exceeds max_bytes.

        Must be called with _buffer_lock held.
        """
        max_bytes = self._batch_config.max_bytes
        timeout_s = self._batch_config.timeout_ms / 1000.0

        while self._buffer:
            now = time.time()
            elapsed = now - self._last_flush_time

            if len(self._buffer) >= max_bytes:
                # Flush max_bytes worth
                chunk = bytes(self._buffer[:max_bytes])
                del self._buffer[:max_bytes]
                self._broadcast(chunk)
                self._last_flush_time = now
            elif elapsed >= timeout_s:
                # Timeout reached, flush everything
                chunk = bytes(self._buffer)
                self._buffer.clear()
                self._broadcast(chunk)
                self._last_flush_time = now
            else:
                break

    def _timeout_flush_worker(self):
        """Background thread to flush partial buffers on timeout."""
        timeout_s = self._batch_config.timeout_ms / 1000.0

        while not self._stop_event.wait(timeout=timeout_s / 2):
            with self._buffer_lock:
                if self._buffer:
                    elapsed = time.time() - self._last_flush_time
                    if elapsed >= timeout_s:
                        chunk = bytes(self._buffer)
                        self._buffer.clear()
                        self._broadcast(chunk)
                        self._last_flush_time = time.time()

    def start_with_source(self, source_func: Callable[[], Optional[bytes]]):
        """Start the broadcaster with a source function.

        The source function will be called repeatedly in a background thread.
        It should return bytes when data is available, or None to indicate
        no data (will retry after short delay).

        Args:
            source_func: Function that returns bytes or None
        """
        if self._running:
            self._logger.warning("Broadcaster already running")
            return

        self._running = True
        self._stop_event.clear()
        self._stats = StreamStats()

        def source_worker():
            self._logger.info(f"Source thread started for {self._name}")
            while not self._stop_event.is_set():
                try:
                    # source_func should be blocking (e.g., serial.read with timeout)
                    # Returns None/empty if no data available within its timeout
                    data = source_func()
                    if data:
                        self.feed(data)
                    # No sleep - source_func handles blocking/timing
                except Exception as e:
                    if not self._stop_event.is_set():
                        self._logger.error(f"Source error: {e}")
                    break
            self._logger.info(f"Source thread stopped for {self._name}")

        self._source_thread = threading.Thread(
            target=source_worker, daemon=True, name=f"broadcaster-{self._name}-source"
        )
        self._source_thread.start()

        # Start timeout flush thread if using timeout-based batching
        if self._batch_config.strategy in (
            BatchStrategy.TIMEOUT_OR_BYTES,
            BatchStrategy.NEWLINE_OR_BYTES,
        ):
            self._flush_thread = threading.Thread(
                target=self._timeout_flush_worker,
                daemon=True,
                name=f"broadcaster-{self._name}-flush",
            )
            self._flush_thread.start()

    def stop(self, timeout: float = 2.0):
        """Stop the broadcaster and clean up resources."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._source_thread and self._source_thread.is_alive():
            self._source_thread.join(timeout=timeout)

        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=timeout)

        # Flush any remaining buffer
        with self._buffer_lock:
            if self._buffer:
                chunk = bytes(self._buffer)
                self._buffer.clear()
                self._broadcast(chunk)

        # Clear subscribers
        with self._subscriber_lock:
            self._subscribers.clear()

        self._logger.info(f"Broadcaster stopped: {self._name}")

    def flush_now(self):
        """Force an immediate flush of any buffered data."""
        with self._buffer_lock:
            if self._buffer:
                chunk = bytes(self._buffer)
                self._buffer.clear()
                self._broadcast(chunk)
                self._last_flush_time = time.time()


class UartBatchingMixin:
    """Mixin providing UART-specific batching logic.

    For UART streams, we want to batch until:
    - A newline character is received (complete line) - triggers immediate flush
    - OR 128 bytes accumulated (prevent unbounded buffering)
    - OR 50ms timeout (ensure partial lines like shell prompts are delivered quickly)

    This means each Zephyr log line (which ends with \n) gets sent as one
    network message, greatly reducing per-byte gRPC overhead.
    """

    UART_MAX_BATCH_BYTES = 256  # Increased to allow longer batches
    UART_BATCH_TIMEOUT_MS = 50   # 50ms timeout - fast enough for shell prompt delivery
    UART_NEWLINE_CHARS = b"\n\r"

    @staticmethod
    def create_uart_batch_config() -> BatchConfig:
        """Create the standard UART batching configuration."""
        return BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=UartBatchingMixin.UART_MAX_BATCH_BYTES,
            timeout_ms=UartBatchingMixin.UART_BATCH_TIMEOUT_MS,
            newline_chars=UartBatchingMixin.UART_NEWLINE_CHARS,
        )


class PowerStreamMixin:
    """Mixin for power stream configuration.

    Power samples are fixed-size records, so we use timeout-based batching
    to group samples together for efficiency while maintaining low latency.
    """

    POWER_BATCH_TIMEOUT_MS = 10  # 100Hz sample rate, batch every 10ms

    @staticmethod
    def create_power_batch_config() -> BatchConfig:
        """Create the standard power stream batching configuration."""
        return BatchConfig(
            strategy=BatchStrategy.TIMEOUT_OR_BYTES,
            max_bytes=4096,  # Group up to 4KB of samples
            timeout_ms=PowerStreamMixin.POWER_BATCH_TIMEOUT_MS,
        )
