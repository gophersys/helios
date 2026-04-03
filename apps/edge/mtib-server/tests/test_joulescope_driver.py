"""Unit tests for the Joulescope USB driver.

Tests cover scanning, connection lifecycle, reading, statistics,
graceful disconnection, edge cases, and thread safety.

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_joulescope_driver.py -v
"""

import threading
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.drivers.joulescope import JoulescopeDriver


def _make_mock_device(serial="JS220-001998", model="JS220"):
    """Build a mock joulescope.v1.device.Device."""
    dev = MagicMock()
    dev.serial_number = serial
    dev.model = model
    dev.open.return_value = None
    dev.close.return_value = None
    dev.parameter_set.return_value = None
    dev.start.return_value = None
    dev.stop.return_value = None
    dev.read.return_value = np.array([
        [0.025, 4.5],   # 25 mA, 4.5 V
        [0.024, 4.5],
        [0.026, 4.5],
    ], dtype=np.float32)
    return dev


def _make_logger():
    logger = MagicMock()
    logger.from_parent.return_value = logger
    return logger


def _open_driver(mock_js_module, mock_dev=None):
    """Scan + open helper — returns (driver, mock_dev)."""
    if mock_dev is None:
        mock_dev = _make_mock_device()
    mock_js_module.scan.return_value = [mock_dev]
    driver = JoulescopeDriver(_make_logger())
    driver.scan()
    driver.open()
    return driver, mock_dev


# ─── Scan ───────────────────────────────────────────────────────────────

class TestScan(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_finds_device(self, mock_js):
        mock_js.scan.return_value = [_make_mock_device()]
        driver = JoulescopeDriver(_make_logger())

        assert driver.scan() is True
        mock_js.scan.assert_called_once()

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_no_device(self, mock_js):
        mock_js.scan.return_value = []
        driver = JoulescopeDriver(_make_logger())

        assert driver.scan() is False

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_exception_returns_false(self, mock_js):
        mock_js.scan.side_effect = RuntimeError("USB error")
        driver = JoulescopeDriver(_make_logger())

        assert driver.scan() is False

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_picks_first_device(self, mock_js):
        """When multiple devices present, scan uses the first one."""
        dev1 = _make_mock_device(serial="JS220-001")
        dev2 = _make_mock_device(serial="JS220-002")
        mock_js.scan.return_value = [dev1, dev2]
        driver = JoulescopeDriver(_make_logger())

        assert driver.scan() is True
        assert driver.serial_number == "JS220-001"

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_after_open_replaces_device(self, mock_js):
        """Calling scan() again replaces the internal device reference."""
        dev1 = _make_mock_device(serial="JS220-OLD")
        dev2 = _make_mock_device(serial="JS220-NEW")
        mock_js.scan.return_value = [dev1]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        driver.open()
        assert driver.serial_number == "JS220-OLD"

        mock_js.scan.return_value = [dev2]
        driver.scan()
        assert driver.serial_number == "JS220-NEW"

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_device_missing_serial_number(self, mock_js):
        """Device without serial_number attribute uses None."""
        dev = MagicMock(spec=[])  # No attributes
        dev.open = MagicMock()
        mock_js.scan.return_value = [dev]
        driver = JoulescopeDriver(_make_logger())

        assert driver.scan() is True
        assert driver.serial_number is None


# ─── Open / Close ───────────────────────────────────────────────────────

class TestOpenClose(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_open_success(self, mock_js):
        mock_dev = _make_mock_device()
        mock_js.scan.return_value = [mock_dev]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()

        err = driver.open()

        assert err is None
        assert driver.is_connected is True
        mock_dev.open.assert_called_once()

    @patch("src.drivers.joulescope.joulescope")
    def test_open_sets_parameters(self, mock_js):
        """open() should attempt to configure i_range and v_range."""
        mock_dev = _make_mock_device()
        mock_js.scan.return_value = [mock_dev]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        driver.open()

        calls = [c[0] for c in mock_dev.parameter_set.call_args_list]
        assert ("i_range", "auto") in calls
        assert ("v_range", "15V") in calls

    @patch("src.drivers.joulescope.joulescope")
    def test_open_parameter_set_failure_is_nonfatal(self, mock_js):
        """If parameter_set raises, open() still succeeds."""
        mock_dev = _make_mock_device()
        mock_dev.parameter_set.side_effect = RuntimeError("unsupported param")
        mock_js.scan.return_value = [mock_dev]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()

        err = driver.open()

        assert err is None
        assert driver.is_connected is True

    @patch("src.drivers.joulescope.joulescope")
    def test_open_without_scan_fails(self, mock_js):
        driver = JoulescopeDriver(_make_logger())
        err = driver.open()

        assert err is not None
        assert "No device" in err
        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_open_exception_returns_error(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.open.side_effect = RuntimeError("USB open failed")
        mock_js.scan.return_value = [mock_dev]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()

        err = driver.open()

        assert err is not None
        assert "USB open failed" in err
        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_close_after_open(self, mock_js):
        driver, mock_dev = _open_driver(mock_js)
        driver.close()

        assert driver.is_connected is False
        mock_dev.close.assert_called_once()

    @patch("src.drivers.joulescope.joulescope")
    def test_close_when_not_open_is_noop(self, mock_js):
        driver = JoulescopeDriver(_make_logger())
        driver.close()  # Must not raise

    @patch("src.drivers.joulescope.joulescope")
    def test_close_twice_is_safe(self, mock_js):
        """Calling close() twice must not raise."""
        driver, mock_dev = _open_driver(mock_js)
        driver.close()
        driver.close()  # Must not raise

        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_close_exception_is_swallowed(self, mock_js):
        """If device.close() raises, close() still marks disconnected."""
        mock_dev = _make_mock_device()
        mock_dev.close.side_effect = RuntimeError("USB close error")
        driver, _ = _open_driver(mock_js, mock_dev)

        driver.close()  # Must not raise

        assert driver.is_connected is False


# ─── Read ───────────────────────────────────────────────────────────────

class TestRead(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_read_returns_correct_values(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, voltage_v, current_a, power_w = driver.read()

        assert err is None
        assert abs(voltage_v - 4.5) < 0.001
        assert abs(current_a - 0.025) < 0.0001
        # Power must be voltage * current
        expected_power = 4.5 * 0.025
        assert abs(power_w - expected_power) < 0.001

    @patch("src.drivers.joulescope.joulescope")
    def test_read_averages_multiple_samples(self, mock_js):
        """read() averages all samples in the window."""
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([
            [0.010, 4.0],
            [0.030, 5.0],
        ], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, voltage_v, current_a, power_w = driver.read()

        assert err is None
        assert abs(current_a - 0.020) < 0.0001  # (0.010 + 0.030) / 2
        assert abs(voltage_v - 4.5) < 0.001     # (4.0 + 5.0) / 2

    @patch("src.drivers.joulescope.joulescope")
    def test_read_passes_duration_to_device(self, mock_js):
        """Custom duration parameter is forwarded to device.read()."""
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        driver.read(duration=0.5)

        mock_dev.read.assert_called_with(duration=0.5, out_format="calibrated")

    @patch("src.drivers.joulescope.joulescope")
    def test_read_default_duration_is_10ms(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        driver.read()

        mock_dev.read.assert_called_with(duration=0.01, out_format="calibrated")

    @patch("src.drivers.joulescope.joulescope")
    def test_read_nanoamp_resolution(self, mock_js):
        """Sub-milliamp values must survive the float math."""
        mock_dev = _make_mock_device()
        # 500 nA = 5e-7 A
        mock_dev.read.return_value = np.array([[5e-7, 3.3]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, voltage_v, current_a, power_w = driver.read()

        assert err is None
        assert current_a < 1e-6  # Under 1 µA
        assert current_a > 0     # Positive
        assert abs(voltage_v - 3.3) < 0.01

    @patch("src.drivers.joulescope.joulescope")
    def test_read_negative_current(self, mock_js):
        """Negative current (reverse flow) should be returned as-is."""
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[-0.001, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, voltage_v, current_a, power_w = driver.read()

        assert err is None
        assert current_a < 0  # Negative current preserved

    @patch("src.drivers.joulescope.joulescope")
    def test_read_empty_data_returns_error(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([], dtype=np.float32).reshape(0, 2)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, v, i, p = driver.read()

        assert err is not None
        assert "No samples" in err

    @patch("src.drivers.joulescope.joulescope")
    def test_read_none_data_returns_error(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = None
        driver, _ = _open_driver(mock_js, mock_dev)

        err, v, i, p = driver.read()

        assert err is not None
        assert "No samples" in err

    @patch("src.drivers.joulescope.joulescope")
    def test_read_not_connected_returns_error(self, mock_js):
        driver = JoulescopeDriver(_make_logger())
        err, v, i, p = driver.read()

        assert err is not None
        assert "not connected" in err.lower()
        assert v == 0.0 and i == 0.0 and p == 0.0

    @patch("src.drivers.joulescope.joulescope")
    def test_read_exception_marks_disconnected(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.side_effect = RuntimeError("USB disconnected")
        driver, _ = _open_driver(mock_js, mock_dev)

        err, v, i, p = driver.read()

        assert err is not None
        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_read_after_disconnect_fails_immediately(self, mock_js):
        """After a failed read marks disconnected, next read should
        fail with 'not connected' without calling device.read()."""
        mock_dev = _make_mock_device()
        mock_dev.read.side_effect = RuntimeError("USB gone")
        driver, _ = _open_driver(mock_js, mock_dev)

        # First read triggers disconnection
        driver.read()
        assert driver.is_connected is False

        # Reset mock to detect if it's called again
        mock_dev.read.reset_mock()
        mock_dev.read.side_effect = None

        err, v, i, p = driver.read()
        assert err is not None
        assert "not connected" in err.lower()
        mock_dev.read.assert_not_called()


# ─── Statistics ─────────────────────────────────────────────────────────

class TestStatistics(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_statistics_computes_correctly(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([
            [0.010, 4.0],
            [0.020, 4.5],
            [0.030, 5.0],
            [0.040, 4.5],
            [0.050, 4.0],
        ], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, stats = driver.read_statistics(duration_s=1.0)

        assert err is None
        assert stats["sample_count"] == 5
        # Mean of [10, 20, 30, 40, 50] mA = 30 mA = 0.030 A
        assert abs(stats["average_a"] - 0.030) < 1e-6
        assert abs(stats["min_a"] - 0.010) < 1e-6
        assert abs(stats["max_a"] - 0.050) < 1e-6
        # Mean of [4.0, 4.5, 5.0, 4.5, 4.0] = 4.4 V
        assert abs(stats["average_v"] - 4.4) < 0.01
        assert stats["duration_s"] == 1.0

    @patch("src.drivers.joulescope.joulescope")
    def test_statistics_passes_duration_to_device(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        driver.read_statistics(duration_s=5.0)

        mock_dev.read.assert_called_with(duration=5.0, out_format="calibrated")

    @patch("src.drivers.joulescope.joulescope")
    def test_statistics_not_connected(self, mock_js):
        driver = JoulescopeDriver(_make_logger())
        err, stats = driver.read_statistics(1.0)

        assert err is not None
        assert stats is None

    @patch("src.drivers.joulescope.joulescope")
    def test_statistics_empty_data(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([], dtype=np.float32).reshape(0, 2)
        driver, _ = _open_driver(mock_js, mock_dev)

        err, stats = driver.read_statistics(1.0)

        assert err is not None
        assert stats is None

    @patch("src.drivers.joulescope.joulescope")
    def test_statistics_exception_marks_disconnected(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.side_effect = RuntimeError("USB error")
        driver, _ = _open_driver(mock_js, mock_dev)

        err, stats = driver.read_statistics(1.0)

        assert err is not None
        assert driver.is_connected is False


# ─── Thread Safety ──────────────────────────────────────────────────────

class TestThreadSafety(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_concurrent_reads_no_errors(self, mock_js):
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        errors = []
        values = []

        def reader():
            for _ in range(20):
                err, v, i, p = driver.read()
                if err:
                    errors.append(err)
                else:
                    values.append((v, i, p))

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        # All threads should get the same values
        assert len(values) == 80
        for v, i, p in values:
            assert abs(v - 4.5) < 0.01
            assert abs(i - 0.025) < 0.001

    @patch("src.drivers.joulescope.joulescope")
    def test_concurrent_read_and_close(self, mock_js):
        """close() during concurrent reads should not crash."""
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        driver, _ = _open_driver(mock_js, mock_dev)

        stop = threading.Event()
        exceptions = []

        def reader():
            try:
                while not stop.is_set():
                    driver.read()
            except Exception as e:
                exceptions.append(e)

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        driver.close()
        stop.set()
        t.join(timeout=2)

        assert len(exceptions) == 0


# ─── Serial Number ──────────────────────────────────────────────────────

class TestSerialNumber(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_serial_available_after_scan(self, mock_js):
        mock_js.scan.return_value = [_make_mock_device(serial="JS220-001998")]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()

        assert driver.serial_number == "JS220-001998"

    @patch("src.drivers.joulescope.joulescope")
    def test_serial_none_before_scan(self, mock_js):
        driver = JoulescopeDriver(_make_logger())
        assert driver.serial_number is None


# ─── Import Failure ─────────────────────────────────────────────────────

class TestImportFailure(unittest.TestCase):

    @patch("src.drivers.joulescope._HAS_JOULESCOPE", False)
    def test_scan_returns_false_when_lib_missing(self):
        driver = JoulescopeDriver(_make_logger())
        assert driver.scan() is False

    @patch("src.drivers.joulescope._HAS_JOULESCOPE", False)
    def test_read_fails_when_lib_missing(self):
        """Even if somehow connected, read should fail cleanly."""
        driver = JoulescopeDriver(_make_logger())
        err, v, i, p = driver.read()
        assert err is not None


# ─── Logger Without from_parent ─────────────────────────────────────────

class TestLoggerFallback(unittest.TestCase):

    @patch("src.drivers.joulescope.joulescope")
    def test_logger_without_from_parent(self, mock_js):
        """Logger without from_parent should be used directly."""
        plain_logger = MagicMock(spec=["info", "warning", "error", "debug"])
        driver = JoulescopeDriver(plain_logger)
        # Should not crash during init


if __name__ == "__main__":
    unittest.main()
