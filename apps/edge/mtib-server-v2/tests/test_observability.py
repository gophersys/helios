"""Tests for the observability engine and its components."""

import sys
import threading
import time
from collections import deque
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest

# Mock gpiod and smbus before any handler import
_mock_gpiod = MagicMock()
_mock_gpiod.line.Direction.INPUT = "input"
_mock_gpiod.line.Direction.OUTPUT = "output"
_mock_gpiod.line.Value.ACTIVE = 1
_mock_gpiod.line.Value.INACTIVE = 0
sys.modules.setdefault("gpiod", _mock_gpiod)
sys.modules.setdefault("gpiod.line", _mock_gpiod.line)

_mock_smbus = MagicMock()
sys.modules.setdefault("smbus", _mock_smbus)

from src.providers.observability.gpio_tracker import GpioStateTracker
from src.providers.observability.power_monitor import PowerMonitor
from src.providers.observability.system_metrics import SystemMetricsCollector
from src.providers.observability.uart_observer import UartObserver
from src.providers.observability.engine import ObservabilityEngine
from tests.mocks.hardware import MockHardwareContext, MockLogger


# ──────────────────────────────────────────────────────────────────
#  GpioStateTracker
# ──────────────────────────────────────────────────────────────────
class TestGpioStateTracker:
    @pytest.fixture
    def tracker(self, logger):
        return GpioStateTracker(logger)

    def test_update_config_creates_state(self, tracker):
        tracker.update_config(0, 1)
        state = tracker.get_state(0)
        assert state is not None
        assert state["pin"] == 0
        assert state["direction"] == 1
        assert state["configured"] is True

    def test_update_value_creates_state(self, tracker):
        tracker.update_value(3, True)
        state = tracker.get_state(3)
        assert state is not None
        assert state["value"] is True

    def test_get_all_states(self, tracker):
        tracker.update_config(0, 0)
        tracker.update_config(1, 1)
        tracker.update_value(2, False)
        states = tracker.get_all_states()
        assert len(states) == 3

    def test_get_state_nonexistent_returns_none(self, tracker):
        assert tracker.get_state(99) is None

    def test_update_preserves_existing_fields(self, tracker):
        tracker.update_config(0, 1)
        tracker.update_value(0, True)
        state = tracker.get_state(0)
        assert state["direction"] == 1
        assert state["value"] is True
        assert state["configured"] is True


# ──────────────────────────────────────────────────────────────────
#  PowerMonitor
# ──────────────────────────────────────────────────────────────────
class TestPowerMonitor:
    def test_no_hwmon_graceful(self, logger, hardware):
        """PowerMonitor should handle no INA219 devices gracefully."""
        with patch("src.providers.observability.power_monitor.glob.glob", return_value=[]):
            monitor = PowerMonitor(logger, hardware)
        assert monitor.get_all_readings() == []

    def test_start_stop_no_hwmon(self, logger, hardware):
        """Start/stop should be safe even with no INA219."""
        with patch("src.providers.observability.power_monitor.glob.glob", return_value=[]):
            monitor = PowerMonitor(logger, hardware)
        monitor.start()  # Should be a no-op
        monitor.stop()

    def test_discover_and_read(self, logger, hardware):
        """PowerMonitor should discover INA219 and cache readings."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from tests.mocks.hardware import MockINA219
            ina0 = MockINA219(tmpdir, address=0x40, voltage_mv=4500.0, current_ma=64.0)
            ina1 = MockINA219(tmpdir, address=0x41, voltage_mv=5000.0, current_ma=6.0)

            with patch(
                "src.providers.observability.power_monitor.glob.glob",
                return_value=[ina0.path, ina1.path],
            ):
                monitor = PowerMonitor(logger, hardware, sample_rate_hz=100)

            monitor.start()
            time.sleep(0.1)  # Let at least one sample happen
            monitor.stop()

            readings = monitor.get_all_readings()
            assert len(readings) == 2

            ch0 = monitor.get_reading(0)
            assert ch0 is not None
            assert ch0["voltage_v"] == pytest.approx(4.5, abs=0.01)
            assert ch0["current_ma"] == pytest.approx(64.0, abs=0.1)

            ch1 = monitor.get_reading(1)
            assert ch1 is not None
            assert ch1["voltage_v"] == pytest.approx(5.0, abs=0.01)


# ──────────────────────────────────────────────────────────────────
#  SystemMetricsCollector
# ──────────────────────────────────────────────────────────────────
class TestSystemMetricsCollector:
    def test_initial_metrics(self, logger, hardware):
        collector = SystemMetricsCollector(logger, hardware, sample_interval_s=0.5)
        metrics = collector.get_metrics()
        assert "hostname" in metrics
        assert "server_version" in metrics
        assert metrics["server_version"] == "2.0.0"

    def test_start_stop(self, logger, hardware):
        collector = SystemMetricsCollector(logger, hardware, sample_interval_s=0.5)
        collector.start()
        time.sleep(0.2)
        collector.stop()
        metrics = collector.get_metrics()
        assert metrics["uptime_seconds"] > 0

    def test_connection_counters(self, logger, hardware):
        collector = SystemMetricsCollector(logger, hardware)
        collector.increment_connections()
        collector.increment_connections()
        collector.decrement_connections()
        collector.record_request()
        collector.record_request()
        collector.record_request()

        # Force a metrics sample
        collector.start()
        time.sleep(0.1)
        collector.stop()

        metrics = collector.get_metrics()
        assert metrics["grpc_active_connections"] == 1
        assert metrics["grpc_total_requests"] == 3

    def test_decrement_below_zero(self, logger, hardware):
        collector = SystemMetricsCollector(logger, hardware)
        collector.decrement_connections()
        collector.start()
        time.sleep(0.1)
        collector.stop()
        metrics = collector.get_metrics()
        assert metrics["grpc_active_connections"] == 0


# ──────────────────────────────────────────────────────────────────
#  UartObserver
# ──────────────────────────────────────────────────────────────────
class TestUartObserver:
    def _make_mock_connection(self):
        """Create a mock UartConnection with register/unregister support."""
        conn = MagicMock()
        conn.port = MagicMock()
        conn.port.baudrate = 115200
        queues = {}

        def register(stream_id):
            q = Queue()
            queues[stream_id] = q
            return q

        def unregister(stream_id):
            queues.pop(stream_id, None)

        conn.register = register
        conn.unregister = unregister
        conn.client_count = 1
        conn._queues = queues  # For test access
        return conn

    def test_attach_detach(self, logger):
        observer = UartObserver(logger)
        conn = self._make_mock_connection()
        observer.attach("uart0", conn)
        status = observer.get_status("uart0")
        assert status is not None
        assert status["is_open"] is True
        assert status["baud_rate"] == 115200

        observer.detach("uart0")
        status = observer.get_status("uart0")
        assert status is not None
        assert status["is_open"] is False

    def test_rx_data_captured(self, logger):
        observer = UartObserver(logger, max_lines_per_port=50)
        conn = self._make_mock_connection()
        observer.attach("uart0", conn)

        # Push data through the observer's queue
        q = conn._queues.get(f"_observer_uart0")
        assert q is not None
        q.put(b"Hello World\nSecond Line\n")
        time.sleep(0.2)  # Let consumer thread process

        status = observer.get_status("uart0")
        assert status["bytes_received"] > 0
        assert "Hello World" in status["recent_lines"]
        assert "Second Line" in status["recent_lines"]

        observer.detach("uart0")

    def test_record_tx(self, logger):
        observer = UartObserver(logger)
        conn = self._make_mock_connection()
        observer.attach("uart0", conn)

        observer.record_tx("uart0", 42)
        observer.record_tx("uart0", 8)
        status = observer.get_status("uart0")
        assert status["bytes_sent"] == 50

        observer.detach("uart0")

    def test_get_all_statuses(self, logger):
        observer = UartObserver(logger)
        conn0 = self._make_mock_connection()
        conn1 = self._make_mock_connection()
        observer.attach("uart0", conn0)
        observer.attach("uart1", conn1)

        statuses = observer.get_all_statuses()
        assert len(statuses) == 2

        observer.detach("uart0")
        observer.detach("uart1")

    def test_nonexistent_port_returns_none(self, logger):
        observer = UartObserver(logger)
        assert observer.get_status("nonexistent") is None


# ──────────────────────────────────────────────────────────────────
#  ObservabilityEngine
# ──────────────────────────────────────────────────────────────────
class TestObservabilityEngine:
    def test_snapshot_structure(self, logger, hardware):
        with patch("src.providers.observability.power_monitor.glob.glob", return_value=[]):
            engine = ObservabilityEngine(logger, hardware)

        snapshot = engine.get_snapshot()
        assert "timestamp" in snapshot
        assert "power_readings" in snapshot
        assert "gpio_states" in snapshot
        assert "uart_ports" in snapshot
        assert "system_metrics" in snapshot

    def test_start_stop(self, logger, hardware):
        with patch("src.providers.observability.power_monitor.glob.glob", return_value=[]):
            engine = ObservabilityEngine(logger, hardware)
        engine.start()
        time.sleep(0.1)
        engine.stop()

    def test_stream_yields_snapshots(self, logger, hardware):
        with patch("src.providers.observability.power_monitor.glob.glob", return_value=[]):
            engine = ObservabilityEngine(logger, hardware)

        filters = {
            "include_power": True,
            "include_gpio": True,
            "include_uart": False,
            "include_system": True,
            "include_clients": False,
            "include_uart_output": False,
        }

        count = 0
        for snapshot in engine.stream(100, filters):
            assert "timestamp" in snapshot
            assert isinstance(snapshot["power_readings"], list)
            assert isinstance(snapshot["system_metrics"], dict)
            assert snapshot["uart_ports"] == []
            count += 1
            if count >= 3:
                break

        assert count == 3

    def test_gpio_tracker_integration(self, logger, hardware):
        with patch("src.providers.observability.power_monitor.glob.glob", return_value=[]):
            engine = ObservabilityEngine(logger, hardware)

        engine.gpio_tracker.update_config(0, 1)
        engine.gpio_tracker.update_value(0, True)

        snapshot = engine.get_snapshot()
        assert len(snapshot["gpio_states"]) == 1
        assert snapshot["gpio_states"][0]["pin"] == 0
        assert snapshot["gpio_states"][0]["value"] is True


# ──────────────────────────────────────────────────────────────────
#  GPIO handler integration with tracker
# ──────────────────────────────────────────────────────────────────
class TestGpioTrackerIntegration:
    @pytest.fixture
    def tracker(self, logger):
        return GpioStateTracker(logger)

    @pytest.fixture
    def gpio_handler_with_tracker(self, logger, hardware, tracker):
        from src.providers.handlers.gpio import GpioHandler
        from tests.mocks.hardware import MockGpio
        with patch("src.providers.handlers.gpio.Gpio", MockGpio):
            handler = GpioHandler(logger, hardware, gpio_tracker=tracker)
            yield handler

    def test_config_updates_tracker(self, gpio_handler_with_tracker, tracker, context):
        from src.shared.types import GpioConfigRequest, GpioDirection
        gpio_handler_with_tracker.config(
            GpioConfigRequest(pin=0, direction=GpioDirection.GPIO_OUTPUT), context
        )
        state = tracker.get_state(0)
        assert state is not None
        assert state["configured"] is True
        assert state["direction"] == GpioDirection.GPIO_OUTPUT

    def test_write_updates_tracker(self, gpio_handler_with_tracker, tracker, context):
        from src.shared.types import GpioWriteRequest
        gpio_handler_with_tracker.write(GpioWriteRequest(pin=0, value=True), context)
        state = tracker.get_state(0)
        assert state is not None
        assert state["value"] is True

    def test_read_updates_tracker(self, gpio_handler_with_tracker, tracker, context):
        from src.shared.types import GpioReadRequest
        gpio_handler_with_tracker.read(GpioReadRequest(pin=0), context)
        state = tracker.get_state(0)
        assert state is not None
        assert state["value"] is False  # Default value
