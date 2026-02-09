"""Tests for PowerHandler."""

import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

# Mock gpiod and smbus before any handler import can trigger them
_mock_gpiod = MagicMock()
_mock_gpiod.line.Direction.INPUT = "input"
_mock_gpiod.line.Direction.OUTPUT = "output"
_mock_gpiod.line.Value.ACTIVE = 1
_mock_gpiod.line.Value.INACTIVE = 0
sys.modules.setdefault("gpiod", _mock_gpiod)
sys.modules.setdefault("gpiod.line", _mock_gpiod.line)

_mock_smbus = MagicMock()
sys.modules.setdefault("smbus", _mock_smbus)

from src.shared.types import (
    PowerChannel,
    PowerConfig,
    PowerDisableRequest,
    PowerEnableRequest,
    PowerMeasureRequest,
    PowerStatusRequest,
    PowerStreamRequest,
    Response,
)
from tests.mocks.hardware import MockGpio, MockINA219, MockMCP4017


@pytest.fixture
def hwmon_dir():
    """Create a temporary hwmon directory with INA219 sysfs files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def ina_main(hwmon_dir):
    """Create mock INA219 at 0x40 (DUT power) with typical readings."""
    return MockINA219(hwmon_dir, address=0x40, voltage_mv=4500.0, current_ma=64.0)


@pytest.fixture
def ina_chg(hwmon_dir):
    """Create mock INA219 at 0x41 (charge power) with typical readings."""
    return MockINA219(hwmon_dir, address=0x41, voltage_mv=5000.0, current_ma=6.0)


@pytest.fixture
def power_handler(logger, hardware, hwmon_dir, ina_main, ina_chg):
    """Create a PowerHandler with mocked hardware dependencies."""
    hwmon_paths = [ina_main.path, ina_chg.path]

    with (
        patch("src.providers.handlers.power.glob.glob", return_value=hwmon_paths),
        patch("src.providers.handlers.power.Gpio", MockGpio),
        patch("src.providers.handlers.power.MCP4017", MockMCP4017),
    ):
        from src.providers.handlers.power import PowerHandler

        handler = PowerHandler(logger, hardware)
        yield handler


# ──────────────────────────────────────────────────────────────────
#  PowerEnable
# ──────────────────────────────────────────────────────────────────
class TestPowerEnable:
    def test_enable_main_sets_gpio_high(self, power_handler, context):
        """Enabling POWER_MAIN should set the power-enable GPIO high."""
        req = PowerEnableRequest(
            config=PowerConfig(channel=PowerChannel.POWER_MAIN, voltage_v=0)
        )
        resp = power_handler.enable(req, context)

        assert resp.success is True
        assert power_handler._pwr_enabled is True
        assert power_handler._pwr_en._value == 1

    def test_enable_vbat_sets_gpio_high(self, power_handler, context):
        """Enabling POWER_VBAT should set the charge-enable GPIO high."""
        req = PowerEnableRequest(
            config=PowerConfig(channel=PowerChannel.POWER_VBAT)
        )
        resp = power_handler.enable(req, context)

        assert resp.success is True
        assert power_handler._chg_enabled is True
        assert power_handler._chg_en._value == 1

    def test_enable_with_voltage_calls_feedback_loop(self, power_handler, context):
        """Enabling with a non-zero voltage should invoke _set_voltage."""
        with patch.object(power_handler, "_set_voltage", return_value=None) as mock_sv:
            req = PowerEnableRequest(
                config=PowerConfig(channel=PowerChannel.POWER_MAIN, voltage_v=4.5)
            )
            resp = power_handler.enable(req, context)

            assert resp.success is True
            mock_sv.assert_called_once_with(4.5)

    def test_enable_unsupported_channel_returns_error(self, power_handler, context):
        """An unrecognised channel value should return success=False."""
        req = PowerEnableRequest(
            config=PowerConfig(channel=999)
        )
        resp = power_handler.enable(req, context)

        assert resp.success is False
        assert "Unsupported" in resp.message or "channel" in resp.message.lower()


# ──────────────────────────────────────────────────────────────────
#  PowerDisable
# ──────────────────────────────────────────────────────────────────
class TestPowerDisable:
    def test_disable_main_sets_gpio_low(self, power_handler, context):
        """Disabling POWER_MAIN should set the power-enable GPIO low."""
        power_handler._pwr_en.write(True)
        power_handler._pwr_enabled = True

        req = PowerDisableRequest(channel=PowerChannel.POWER_MAIN)
        resp = power_handler.disable(req, context)

        assert resp.success is True
        assert power_handler._pwr_enabled is False
        assert power_handler._pwr_en._value == 0

    def test_disable_vbat_sets_gpio_low(self, power_handler, context):
        """Disabling POWER_VBAT should set the charge-enable GPIO low."""
        power_handler._chg_en.write(True)
        power_handler._chg_enabled = True

        req = PowerDisableRequest(channel=PowerChannel.POWER_VBAT)
        resp = power_handler.disable(req, context)

        assert resp.success is True
        assert power_handler._chg_enabled is False
        assert power_handler._chg_en._value == 0

    def test_disable_unsupported_channel_returns_error(self, power_handler, context):
        """Disabling an unknown channel should return an error."""
        req = PowerDisableRequest(channel=999)
        resp = power_handler.disable(req, context)

        assert resp.success is False


# ──────────────────────────────────────────────────────────────────
#  PowerStatus
# ──────────────────────────────────────────────────────────────────
class TestPowerStatus:
    def test_reads_ina219_values(self, power_handler, context):
        """Status should return voltage, current, power from INA219 sysfs."""
        req = PowerStatusRequest(channel=PowerChannel.POWER_MAIN)
        resp = power_handler.status(req, context)

        assert resp.success is True
        # MockINA219 was created with voltage_mv=4500, current_ma=64
        assert resp.voltage_v == pytest.approx(4.5, abs=0.01)
        assert resp.current_ma == pytest.approx(64.0, abs=0.1)
        assert resp.power_mw > 0

    def test_returns_enabled_state(self, power_handler, context):
        """Status should reflect the enabled/disabled state of the channel."""
        # Initially disabled
        req = PowerStatusRequest(channel=PowerChannel.POWER_MAIN)
        resp = power_handler.status(req, context)
        assert resp.enabled is False

        # Enable main power
        power_handler._pwr_enabled = True
        resp = power_handler.status(req, context)
        assert resp.enabled is True

    def test_unknown_channel_returns_error(self, power_handler, context):
        """Querying status on an unknown channel should fail."""
        req = PowerStatusRequest(channel=999)
        resp = power_handler.status(req, context)

        assert resp.success is False
        assert "INA219" in resp.message or "channel" in resp.message.lower()


# ──────────────────────────────────────────────────────────────────
#  PowerStream
# ──────────────────────────────────────────────────────────────────
class TestPowerStream:
    def test_yields_samples_at_rate(self, power_handler, context):
        """Stream should yield PowerStreamResponse with samples."""
        req = PowerStreamRequest(
            channel=PowerChannel.POWER_MAIN, sample_rate_hz=100
        )

        samples_collected = []
        for resp in power_handler.stream(req, context):
            assert resp.success is True
            assert len(resp.samples) == 1
            samples_collected.append(resp.samples[0])
            if len(samples_collected) >= 3:
                context.cancel()

        assert len(samples_collected) >= 3
        for s in samples_collected:
            assert s.voltage_mv == pytest.approx(4500.0, abs=1.0)
            assert s.current_ua == pytest.approx(64000.0, abs=100.0)

    def test_stops_when_context_inactive(self, power_handler, context):
        """Stream should stop yielding when context becomes inactive."""
        req = PowerStreamRequest(
            channel=PowerChannel.POWER_MAIN, sample_rate_hz=1000
        )

        # Cancel immediately
        context.cancel()

        results = list(power_handler.stream(req, context))
        assert len(results) == 0


# ──────────────────────────────────────────────────────────────────
#  PowerMeasure
# ──────────────────────────────────────────────────────────────────
class TestPowerMeasure:
    def test_collects_samples_computes_stats(self, power_handler, context):
        """Measure should collect samples and compute min/max/avg/energy."""
        req = PowerMeasureRequest(
            channel=PowerChannel.POWER_MAIN,
            sample_rate_hz=200,
            duration_s=0.05,
        )
        resp = power_handler.measure(req, context)

        assert resp.success is True
        assert resp.sample_count >= 1
        assert resp.duration_s > 0
        # With constant 64mA = 64000uA readings
        assert resp.average_ua == pytest.approx(64000.0, abs=100.0)
        assert resp.min_ua == pytest.approx(64000.0, abs=100.0)
        assert resp.max_ua == pytest.approx(64000.0, abs=100.0)
        assert resp.energy_uj > 0
        assert len(resp.samples) == resp.sample_count

    def test_zero_duration_no_samples(self, power_handler, context):
        """A zero-duration measurement should return no samples."""
        req = PowerMeasureRequest(
            channel=PowerChannel.POWER_MAIN,
            sample_rate_hz=100,
            duration_s=0.0,
        )
        resp = power_handler.measure(req, context)

        assert resp.success is False
        assert "No samples" in resp.message


# ──────────────────────────────────────────────────────────────────
#  Voltage Feedback Loop
# ──────────────────────────────────────────────────────────────────
class TestVoltageLoop:
    def test_binary_search_converges(self, power_handler, context):
        """The _set_voltage feedback loop should converge to the target."""
        call_count = 0

        def mock_read_ina219(path):
            nonlocal call_count
            call_count += 1
            step = power_handler.mcp4017.step
            # Higher step = higher resistance = lower output voltage
            simulated_v = 5.0 - (step / 127.0) * 2.0
            return simulated_v, 64.0, simulated_v * 64.0

        with (
            patch.object(power_handler, "_read_ina219", side_effect=mock_read_ina219),
            patch("src.providers.handlers.power.time.sleep"),
        ):
            err = power_handler._set_voltage(4.5)

        assert err is None, f"Voltage loop failed: {err}"
        assert call_count <= 10
