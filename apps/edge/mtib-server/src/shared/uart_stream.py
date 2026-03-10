"""File-based UART streaming with smart batching.

Architecture:
- Single writer process per UART: reads serial port, appends to buffer file
- Multiple readers: tail the file independently via OS primitives
- Smart batching: flush on newline OR 128 bytes, whichever first

This replaces the complex threading/queue approach with simple file I/O.
"""

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import serial

# Buffer files stored in tmpfs for speed
UART_BUFFER_DIR = Path("/tmp/mtib-uart")


@dataclass
class UartConfig:
    """UART port configuration."""
    device: str
    baudrate: int = 115200
    timeout: float = 0.1  # Serial read timeout


class LineBatcher:
    """Batches bytes, flushing on newline or max size.

    Flush triggers:
    - Newline character (\\n or \\r) detected
    - Buffer reaches max_bytes (128)
    - Timeout reached (20ms) with pending data
    """

    MAX_BYTES = 128
    TIMEOUT_MS = 20
    NEWLINE_CHARS = b'\n\r'

    def __init__(self):
        self._buffer = bytearray()
        self._last_flush = time.time()

    def feed(self, data: bytes) -> Iterator[bytes]:
        """Feed data and yield complete batches."""
        if not data:
            return

        self._buffer.extend(data)

        while self._buffer:
            # Find first newline
            newline_pos = -1
            for i, byte in enumerate(self._buffer):
                if byte in self.NEWLINE_CHARS:
                    newline_pos = i
                    break

            if newline_pos >= 0:
                # Flush up to and including newline
                chunk = bytes(self._buffer[:newline_pos + 1])
                del self._buffer[:newline_pos + 1]
                self._last_flush = time.time()
                yield chunk
            elif len(self._buffer) >= self.MAX_BYTES:
                # Flush max bytes
                chunk = bytes(self._buffer[:self.MAX_BYTES])
                del self._buffer[:self.MAX_BYTES]
                self._last_flush = time.time()
                yield chunk
            else:
                # Not enough data yet
                break

    def flush_if_timeout(self) -> Optional[bytes]:
        """Flush buffer if timeout reached. Call periodically."""
        if not self._buffer:
            return None

        elapsed_ms = (time.time() - self._last_flush) * 1000
        if elapsed_ms >= self.TIMEOUT_MS:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            self._last_flush = time.time()
            return chunk
        return None

    def flush_all(self) -> Optional[bytes]:
        """Force flush everything."""
        if self._buffer:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            self._last_flush = time.time()
            return chunk
        return None


class UartWriter:
    """Writes serial data to a buffer file.

    Single instance per UART. Runs in background thread.
    Readers can independently tail the buffer file.
    """

    def __init__(self, name: str, config: UartConfig):
        self.name = name
        self.config = config
        self.buffer_path = UART_BUFFER_DIR / f"{name}.buf"

        self._serial: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._bytes_written = 0

    def start(self) -> Optional[str]:
        """Start the writer. Returns error string or None."""
        # Ensure buffer directory exists
        UART_BUFFER_DIR.mkdir(parents=True, exist_ok=True)

        # Clear old buffer
        if self.buffer_path.exists():
            self.buffer_path.unlink()
        # Create buffer file with restrictive permissions (owner read/write only)
        fd = os.open(self.buffer_path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)

        # Open serial port
        try:
            self._serial = serial.Serial(
                self.config.device,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
            )
        except Exception as e:
            return f"Failed to open {self.config.device}: {e}"

        # Start writer thread
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._writer_loop,
            daemon=True,
            name=f"uart-writer-{self.name}"
        )
        self._thread.start()
        return None

    def stop(self):
        """Stop the writer."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._serial:
            self._serial.close()
            self._serial = None

    def write_to_device(self, data: bytes) -> int:
        """Write data to the serial device (TX). Returns bytes written."""
        if not self._serial or not self._serial.is_open:
            return 0
        try:
            written = self._serial.write(data)
            self._serial.flush()
            return written
        except Exception:
            return 0

    def _writer_loop(self):
        """Background thread: read serial, append to file."""
        with open(self.buffer_path, 'ab', buffering=0) as f:
            while not self._stop.is_set():
                try:
                    # Read whatever's available
                    waiting = self._serial.in_waiting
                    if waiting > 0:
                        data = self._serial.read(min(waiting, 1024))
                        if data:
                            with self._write_lock:
                                f.write(data)
                                self._bytes_written += len(data)
                    else:
                        # Brief sleep when no data
                        time.sleep(0.001)
                except Exception:
                    if not self._stop.is_set():
                        time.sleep(0.1)

    @property
    def bytes_written(self) -> int:
        return self._bytes_written


class UartReader:
    """Reads from UART buffer file with smart batching.

    Multiple readers can exist per UART. Each maintains its own
    file position and batcher state.
    """

    def __init__(self, buffer_path: Path, start_from_end: bool = True):
        self.buffer_path = buffer_path
        self._start_from_end = start_from_end
        self._file = None
        self._batcher = LineBatcher()
        self._stop = threading.Event()

    def open(self) -> Optional[str]:
        """Open the buffer file for reading."""
        try:
            self._file = open(self.buffer_path, 'rb')
            if self._start_from_end:
                self._file.seek(0, 2)  # Seek to end (tail -f behavior)
            return None
        except Exception as e:
            return f"Failed to open buffer: {e}"

    def close(self):
        """Close the reader."""
        self._stop.set()
        if self._file:
            self._file.close()
            self._file = None

    def stop(self):
        """Signal reader to stop."""
        self._stop.set()

    def read_batched(self, timeout: float = 0.05) -> Iterator[bytes]:
        """Read and yield batched data.

        Yields complete batches (on newline or 128 bytes).
        Use in a loop for streaming.
        """
        if not self._file:
            return

        deadline = time.time() + timeout

        while not self._stop.is_set() and time.time() < deadline:
            # Read new data from file
            data = self._file.read(4096)

            if data:
                # Feed to batcher, yield complete batches
                for batch in self._batcher.feed(data):
                    yield batch
            else:
                # Check for timeout flush
                timeout_batch = self._batcher.flush_if_timeout()
                if timeout_batch:
                    yield timeout_batch
                # Brief sleep when no new data
                time.sleep(0.005)

    def read_all_available(self) -> Iterator[bytes]:
        """Read all currently available data with batching."""
        if not self._file:
            return

        # Read everything available
        data = self._file.read()
        if data:
            for batch in self._batcher.feed(data):
                yield batch

        # Flush any remaining
        remaining = self._batcher.flush_all()
        if remaining:
            yield remaining


class UartStreamManager:
    """Manages UART writers and provides reader factory.

    Usage:
        manager = UartStreamManager()

        # Start a UART (once per device)
        manager.start_uart("uart0", UartConfig("/dev/ttyUSB0"))

        # Create readers (multiple per UART)
        reader = manager.create_reader("uart0")
        for batch in reader.read_batched():
            process(batch)

        # Write to device
        manager.write("uart0", b"command\\r")
    """

    def __init__(self):
        self._writers: dict[str, UartWriter] = {}
        self._lock = threading.Lock()

    def start_uart(self, name: str, config: UartConfig) -> Optional[str]:
        """Start a UART writer. Returns error or None."""
        with self._lock:
            if name in self._writers:
                return None  # Already running

            writer = UartWriter(name, config)
            err = writer.start()
            if err:
                return err

            self._writers[name] = writer
            return None

    def stop_uart(self, name: str):
        """Stop a UART writer."""
        with self._lock:
            if name in self._writers:
                self._writers[name].stop()
                del self._writers[name]

    def stop_all(self):
        """Stop all UART writers."""
        with self._lock:
            for writer in self._writers.values():
                writer.stop()
            self._writers.clear()

    def create_reader(self, name: str, start_from_end: bool = True) -> Optional[UartReader]:
        """Create a reader for a UART. Returns None if UART not started."""
        with self._lock:
            if name not in self._writers:
                return None
            buffer_path = self._writers[name].buffer_path

        reader = UartReader(buffer_path, start_from_end)
        err = reader.open()
        if err:
            return None
        return reader

    def write(self, name: str, data: bytes) -> int:
        """Write data to a UART device (TX)."""
        with self._lock:
            if name not in self._writers:
                return 0
            return self._writers[name].write_to_device(data)

    def get_stats(self, name: str) -> dict:
        """Get stats for a UART."""
        with self._lock:
            if name not in self._writers:
                return {}
            writer = self._writers[name]
            return {
                "name": name,
                "device": writer.config.device,
                "bytes_written": writer.bytes_written,
                "buffer_path": str(writer.buffer_path),
            }


# Global manager instance
_manager: Optional[UartStreamManager] = None


def get_manager() -> UartStreamManager:
    """Get or create the global UART manager."""
    global _manager
    if _manager is None:
        _manager = UartStreamManager()
    return _manager
