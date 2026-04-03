"""Unit tests for the Joulescope USB driver.

Tests cover scanning, connection lifecycle, reading, statistics, and
graceful handling of disconnection. The joulescope library is fully mocked.

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_joulescope_driver.py -v
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

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
    # read() returns Nx2 ndarray [[current_a, voltage_v], ...]
    import numpy as np
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


class TestJoulescopeDriverScan(unittest.TestCase):
    """Test USB device scanning."""

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_finds_device(self, mock_js_module):
        mock_dev = _make_mock_device()
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        found = driver.scan()

        assert found is True
        mock_js_module.scan.assert_called_once()

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_no_device(self, mock_js_module):
        mock_js_module.scan.return_value = []

        driver = JoulescopeDriver(_make_logger())
        found = driver.scan()

        assert found is False

    @patch("src.drivers.joulescope.joulescope")
    def test_scan_exception_returns_false(self, mock_js_module):
        mock_js_module.scan.side_effect = RuntimeError("USB error")

        driver = JoulescopeDriver(_make_logger())
        found = driver.scan()

        assert found is False


class TestJoulescopeDriverOpen(unittest.TestCase):
    """Test device open/close lifecycle."""

    @patch("src.drivers.joulescope.joulescope")
    def test_open_success(self, mock_js_module):
        mock_dev = _make_mock_device()
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        err = driver.open()

        assert err is None
        assert driver.is_connected is True
        mock_dev.open.assert_called_once()

    @patch("src.drivers.joulescope.joulescope")
    def test_open_without_scan_fails(self, mock_js_module):
        driver = JoulescopeDriver(_make_logger())
        err = driver.open()

        assert err is not None
        assert "No device" in err
        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_open_exception_returns_error(self, mock_js_module):
        mock_dev = _make_mock_device()
        mock_dev.open.side_effect = RuntimeError("USB open failed")
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        err = driver.open()

        assert err is not None
        assert "USB open failed" in err
        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_close_after_open(self, mock_js_module):
        mock_dev = _make_mock_device()
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        driver.open()
        driver.close()

        assert driver.is_connected is False
        mock_dev.close.assert_called_once()

    @patch("src.drivers.joulescope.joulescope")
    def test_close_when_not_open_is_noop(self, mock_js_module):
        driver = JoulescopeDriver(_make_logger())
        driver.close()  # Should not raise


class TestJoulescopeDriverRead(unittest.TestCase):
    """Test single-shot readings."""

    def _open_driver(self, mock_js_module, mock_dev=None):
        if mock_dev is None:
            mock_dev = _make_mock_device()
        mock_js_module.scan.return_value = [mock_dev]
        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        driver.open()
        return driver, mock_dev

    @patch("src.drivers.joulescope.joulescope")
    def test_read_returns_voltage_current_power(self, mock_js_module):
        import numpy as np
        mock_dev = _make_mock_device()
        # Single sample: 25 mA (0.025 A), 4.5 V
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)

        driver, _ = self._open_driver(mock_js_module, mock_dev)
        err, voltage_v, current_a, power_w = driver.read()

        assert err is None
        assert abs(voltage_v - 4.5) < 0.01
        assert abs(current_a - 0.025) < 0.001
        assert abs(power_w - 0.1125) < 0.01  # 4.5V * 0.025A

    @patch("src.drivers.joulescope.joulescope")
    def test_read_not_connected_returns_error(self, mock_js_module):
        driver = JoulescopeDriver(_make_logger())
        err, v, i, p = driver.read()

        assert err is not None
        assert "not connected" in err.lower()

    @patch("src.drivers.joulescope.joulescope")
    def test_read_exception_marks_disconnected(self, mock_js_module):
        mock_dev = _make_mock_device()
        mock_dev.read.side_effect = RuntimeError("USB disconnected")

        driver, _ = self._open_driver(mock_js_module, mock_dev)
        err, v, i, p = driver.read()

        assert err is not None
        assert driver.is_connected is False

    @patch("src.drivers.joulescope.joulescope")
    def test_read_nanoamp_resolution(self, mock_js_module):
        """Joulescope reads in amps — verify sub-milliamp values survive."""
        import numpy as np
        mock_dev = _make_mock_device()
        # 500 nA = 0.0000005 A
        mock_dev.read.return_value = np.array([[0.0000005, 3.3]], dtype=np.float32)

        driver, _ = self._open_driver(mock_js_module, mock_dev)
        err, voltage_v, current_a, power_w = driver.read()

        assert err is None
        # current_a should preserve the nanoamp-level reading
        assert current_a < 0.001  # Sub-milliamp


class TestJoulescopeDriverStatistics(unittest.TestCase):
    """Test statistics collection over a duration."""

    @patch("src.drivers.joulescope.joulescope")
    def test_read_statistics_returns_stats(self, mock_js_module):
        import numpy as np
        mock_dev = _make_mock_device()
        # 5 samples: varying current at 4.5V
        mock_dev.read.return_value = np.array([
            [0.010, 4.5],
            [0.020, 4.5],
            [0.030, 4.5],
            [0.040, 4.5],
            [0.050, 4.5],
        ], dtype=np.float32)
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        driver.open()

        err, stats = driver.read_statistics(duration_s=0.1)

        assert err is None
        assert "average_a" in stats
        assert "min_a" in stats
        assert "max_a" in stats
        assert "average_v" in stats
        assert "sample_count" in stats
        assert stats["sample_count"] == 5
        assert abs(stats["average_a"] - 0.030) < 0.001
        assert abs(stats["min_a"] - 0.010) < 0.001
        assert abs(stats["max_a"] - 0.050) < 0.001

    @patch("src.drivers.joulescope.joulescope")
    def test_read_statistics_not_connected(self, mock_js_module):
        driver = JoulescopeDriver(_make_logger())
        err, stats = driver.read_statistics(1.0)

        assert err is not None
        assert stats is None


class TestJoulescopeDriverThreadSafety(unittest.TestCase):
    """Verify concurrent reads don't corrupt state."""

    @patch("src.drivers.joulescope.joulescope")
    def test_concurrent_reads(self, mock_js_module):
        import numpy as np
        mock_dev = _make_mock_device()
        mock_dev.read.return_value = np.array([[0.025, 4.5]], dtype=np.float32)
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        driver.scan()
        driver.open()

        errors = []

        def reader():
            for _ in range(10):
                err, v, i, p = driver.read()
                if err:
                    errors.append(err)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


class TestJoulescopeDriverSerial(unittest.TestCase):
    """Test serial number reporting."""

    @patch("src.drivers.joulescope.joulescope")
    def test_serial_number_available_after_scan(self, mock_js_module):
        mock_dev = _make_mock_device(serial="JS220-001998")
        mock_js_module.scan.return_value = [mock_dev]

        driver = JoulescopeDriver(_make_logger())
        driver.scan()

        assert driver.serial_number == "JS220-001998"

    @patch("src.drivers.joulescope.joulescope")
    def test_serial_number_none_before_scan(self, mock_js_module):
        driver = JoulescopeDriver(_make_logger())
        assert driver.serial_number is None


if __name__ == "__main__":
    unittest.main()
