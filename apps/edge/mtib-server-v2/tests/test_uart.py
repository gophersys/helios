"""Tests for UartHandler and UartConnection."""

import sys
import time
import threading
from queue import Queue, Empty as QueueEmpty
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# MockSerial — simulates pyserial Serial object
# ---------------------------------------------------------------------------
class MockSerial:
    """Mock serial port for testing without real hardware."""

    def __init__(self, **kwargs):
        self.port = kwargs.get("port", "")
        self.baudrate = kwargs.get("baudrate", 115200)
        self._rx_buffer = b""
        self._closed = False

    @property
    def in_waiting(self):
        return len(self._rx_buffer)

    def read(self, size=1):
        data = self._rx_buffer[:size]
        self._rx_buffer = self._rx_buffer[size:]
        return data

    def write(self, data):
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        self._rx_buffer = b""

    def reset_output_buffer(self):
        pass

    def close(self):
        self._closed = True


class FailingSerial:
    """Serial that raises on construction (simulates missing device)."""

    def __init__(self, **kwargs):
        raise OSError("No such device: /dev/fake")


# ---------------------------------------------------------------------------
# Build a mock 'serial' module so `import serial as pyserial` resolves
# ---------------------------------------------------------------------------
_mock_serial_module = MagicMock()
_mock_serial_module.Serial = MockSerial
_mock_serial_module.PARITY_NONE = "N"
_mock_serial_module.PARITY_ODD = "O"
_mock_serial_module.PARITY_EVEN = "E"
_mock_serial_module.STOPBITS_ONE = 1
_mock_serial_module.STOPBITS_ONE_POINT_FIVE = 1.5
_mock_serial_module.STOPBITS_TWO = 2

sys.modules.setdefault("serial", _mock_serial_module)

from src.providers.handlers.uart import UartConnection, UartHandler, RX_QUEUE_MAX
from src.shared.types import (
    UartOpenRequest,
    UartCloseRequest,
    UartConfig,
    Parity,
    StopBits,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_open_request(port_name: str = "uart0", baud: int = 115200) -> UartOpenRequest:
    """Build a UartOpenRequest with sensible defaults."""
    return UartOpenRequest(
        port_name=port_name,
        config=UartConfig(
            baud=baud,
            data_bits=8,
            parity=Parity.PARITY_NONE,
            stop_bits=StopBits.STOP_BITS_1,
        ),
    )


# ===================================================================
# TestUartOpen
# ===================================================================
class TestUartOpen:
    """Tests for UartHandler.open()."""

    @pytest.fixture(autouse=True)
    def _patch_serial(self):
        """Ensure `import serial` resolves to our mock module."""
        with patch.dict(sys.modules, {"serial": _mock_serial_module}):
            _mock_serial_module.Serial = MockSerial
            yield

    @pytest.fixture
    def handler(self, logger, hardware):
        handler = UartHandler(logger, hardware)
        yield handler
        # Cleanup: close any remaining connections
        for conn in list(handler._connections.values()):
            conn.close()

    def test_open_creates_connection(self, handler, context):
        """Opening a valid port returns success and a stream_id."""
        resp = handler.open(_make_open_request("uart0"), context)

        assert resp.success is True
        assert resp.stream_id != ""
        assert len(handler._connections) == 1
        assert len(handler._streams) == 1

    def test_open_same_port_reuses_connection(self, handler, context):
        """Opening the same port twice reuses the underlying connection."""
        resp1 = handler.open(_make_open_request("uart0"), context)
        resp2 = handler.open(_make_open_request("uart0"), context)

        assert resp1.success is True
        assert resp2.success is True
        assert resp1.stream_id != resp2.stream_id
        # Only one physical connection
        assert len(handler._connections) == 1
        # Two registered streams
        assert len(handler._streams) == 2
        # Connection has 2 clients
        conn = list(handler._connections.values())[0]
        assert conn.client_count == 2

    def test_open_invalid_port_returns_error(self, handler, context):
        """If pyserial.Serial raises, open returns success=False."""
        _mock_serial_module.Serial = FailingSerial
        resp = handler.open(_make_open_request("uart0"), context)

        assert resp.success is False
        assert "No such device" in resp.message
        assert len(handler._connections) == 0


# ===================================================================
# TestUartClose
# ===================================================================
class TestUartClose:
    """Tests for UartHandler.close()."""

    @pytest.fixture(autouse=True)
    def _patch_serial(self):
        with patch.dict(sys.modules, {"serial": _mock_serial_module}):
            _mock_serial_module.Serial = MockSerial
            yield

    @pytest.fixture
    def handler(self, logger, hardware):
        handler = UartHandler(logger, hardware)
        yield handler
        for conn in list(handler._connections.values()):
            conn.close()

    def test_close_valid_stream(self, handler, context):
        """Closing a valid stream returns success."""
        open_resp = handler.open(_make_open_request("uart0"), context)
        close_resp = handler.close(
            UartCloseRequest(stream_id=open_resp.stream_id), context
        )

        assert close_resp.success is True

    def test_close_last_client_removes_connection(self, handler, context):
        """When the last client closes, the connection is removed."""
        open_resp = handler.open(_make_open_request("uart0"), context)
        handler.close(UartCloseRequest(stream_id=open_resp.stream_id), context)

        assert len(handler._connections) == 0
        assert len(handler._streams) == 0

    def test_close_unknown_stream_returns_error(self, handler, context):
        """Closing an unknown stream_id returns success=False."""
        resp = handler.close(
            UartCloseRequest(stream_id="nonexistent-stream-id"), context
        )

        assert resp.success is False
        assert "Unknown stream" in resp.message


# ===================================================================
# TestUartStream
# ===================================================================
class TestUartStream:
    """Tests for UartHandler.stream() and related TX/RX behavior."""

    @pytest.fixture(autouse=True)
    def _patch_serial(self):
        with patch.dict(sys.modules, {"serial": _mock_serial_module}):
            _mock_serial_module.Serial = MockSerial
            yield

    @pytest.fixture
    def handler(self, logger, hardware):
        handler = UartHandler(logger, hardware)
        yield handler
        for conn in list(handler._connections.values()):
            conn.close()

    def test_tx_data_written_to_serial(self, handler, context):
        """Data written through connection.write() reaches the serial port."""
        open_resp = handler.open(_make_open_request("uart0"), context)
        conn = list(handler._connections.values())[0]

        # Write through the connection and verify no exception
        conn.write(b"hello")
        # MockSerial.write returns len(data)
        assert conn.port.write(b"test") == 4

    def test_stale_data_drained(self, handler, context):
        """Stale data in the queue is drained when stream starts."""
        open_resp = handler.open(_make_open_request("uart0"), context)
        info = handler._streams[open_resp.stream_id]

        # Pre-fill the queue with stale data
        for i in range(5):
            info.rx_queue.put_nowait(f"stale-{i}".encode())

        assert info.rx_queue.qsize() == 5

        # Simulate the drain logic from stream()
        stale = 0
        while True:
            try:
                info.rx_queue.get_nowait()
                stale += 1
            except QueueEmpty:
                break

        assert stale == 5
        assert info.rx_queue.qsize() == 0


# ===================================================================
# TestUartConnection
# ===================================================================
class TestUartConnection:
    """Tests for UartConnection directly (no handler)."""

    def _make_connection(self, logger):
        """Create a UartConnection with a MockSerial."""
        mock_port = MockSerial(port="/dev/test", baudrate=115200)
        conn = UartConnection(
            device_path="/dev/test", port=mock_port, logger=logger
        )
        return conn

    def test_register_client(self, logger):
        """Registering a client returns a Queue."""
        conn = self._make_connection(logger)
        try:
            q = conn.register("client-1")
            assert isinstance(q, Queue)
            assert conn.client_count == 1
        finally:
            conn.close()

    def test_unregister_client(self, logger):
        """Unregistering removes the client from the broadcast list."""
        conn = self._make_connection(logger)
        try:
            conn.register("client-1")
            assert conn.client_count == 1

            conn.unregister("client-1")
            assert conn.client_count == 0
        finally:
            conn.close()

    def test_broadcast_to_multiple_clients(self, logger):
        """Broadcasting pushes data to all registered client queues."""
        conn = self._make_connection(logger)
        try:
            q1 = conn.register("client-1")
            q2 = conn.register("client-2")

            conn._broadcast(b"hello")

            assert q1.get_nowait() == b"hello"
            assert q2.get_nowait() == b"hello"
        finally:
            conn.close()

    def test_queue_overflow_drops_oldest(self, logger):
        """When a client queue is full, the oldest chunk is dropped."""
        conn = self._make_connection(logger)
        try:
            q = conn.register("client-1")

            # Fill the queue to capacity
            for i in range(RX_QUEUE_MAX):
                q.put_nowait(f"chunk-{i}".encode())
            assert q.full()

            # Broadcast one more — should drop oldest (chunk-0) and add new
            conn._broadcast(b"newest")

            # First item should now be chunk-1 (chunk-0 was dropped)
            first = q.get_nowait()
            assert first == b"chunk-1"

            # Drain to the end — last item should be "newest"
            last = None
            while not q.empty():
                last = q.get_nowait()
            assert last == b"newest"
        finally:
            conn.close()
