"""Unit tests for power handler.

Tests PowerEnable, PowerDisable, PowerRead, PowerMeasure, and snapshot.
INA219 and GPIO drivers are mocked — no hardware required.

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_power_handler.py -v
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from src.shared.types import (
    PowerChannel,
    PowerDisableRequest,
    PowerEnableRequest,
    PowerMeasureRequest,
    PowerReadRequest,
)
from src.handlers.power import PowerHandler


def _make_handler(ina_read_returns=None):
    """Construct a PowerHandler with all hardware mocked.

    ina_read_returns: list of (error, voltage_v, current_ma, power_mw) tuples
                      returned by successive _read_ina219 calls.
                      Defaults to a healthy reading: (None, 4.5, 25.0, 112.5).
    """
    default_reading = (None, 4.5, 25.0, 112.5)
    if ina_read_returns is None:
        ina_read_returns = [default_reading]

    logger = MagicMock()
    logger.from_parent.return_value = logger

    mcp4017 = MagicMock()

    # Mock the GPIO class at the point where PowerHandler imports it.
    # dut_pwr_en and dut_chg_en are both Gpio objects; we need init() and write()
    # to succeed.
    mock_gpio_instance = MagicMock()
    mock_gpio_instance.init.return_value = None   # None == no error
    mock_gpio_instance.write.return_value = None  # None == no error

    # Mock INA219 — patch its __init__ to skip sysfs discovery.
    with patch("src.handlers.power.Gpio", return_value=mock_gpio_instance), \
         patch("src.handlers.power.INA219") as mock_ina_cls:
        mock_ina = MagicMock()
        mock_ina_cls.return_value = mock_ina

        # Side-effect list so we can sequence multiple reads.
        mock_ina.read.side_effect = list(ina_read_returns)
        if not ina_read_returns:
            mock_ina.read.return_value = default_reading

        handler = PowerHandler(logger=logger, mcp4017=mcp4017)
        # Store mocks on handler for assertion access in tests
        handler._mock_ina = mock_ina
        handler._mock_gpio = mock_gpio_instance
        handler._mock_mcp4017 = mcp4017

    return handler


class TestPowerEnable(unittest.TestCase):
    """Test PowerEnable RPC logic."""

    def _make_ctx(self):
        ctx = MagicMock()
        ctx.is_active.return_value = True
        return ctx

    def test_enable_dut_channel_success(self):
        """PowerEnable on DUT channel writes GPIO high."""
        # Voltage 0 → skip voltage control, just enable GPIO
        handler = _make_handler()
        handler._mock_gpio.write.return_value = None

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=0.0)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is True
        assert "DUT" in resp.message

    def test_enable_charger_channel_success(self):
        handler = _make_handler()
        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_CHARGER, voltage_v=0.0)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is True
        assert "charger" in resp.message

    def test_enable_sets_enabled_state(self):
        handler = _make_handler()
        assert handler._is_enabled(PowerChannel.POWER_CHANNEL_DUT) is False

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=0.0)
        handler.power_enable(req, self._make_ctx())

        assert handler._is_enabled(PowerChannel.POWER_CHANNEL_DUT) is True

    def test_enable_voltage_out_of_range_rejected(self):
        """Voltages outside 0–5.5 V must be rejected before touching hardware."""
        handler = _make_handler()
        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=6.0)

        # Reset the write call count accumulated during __init__ (which disables both GPIOs)
        handler._mock_gpio.write.reset_mock()

        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is False
        assert "6.0" in resp.message or "safe range" in resp.message
        # GPIO must not have been driven after the range check
        handler._mock_gpio.write.assert_not_called()

    def test_enable_negative_voltage_rejected(self):
        handler = _make_handler()
        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=-1.0)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is False

    def test_enable_gpio_write_failure_returns_error(self):
        handler = _make_handler()
        handler._mock_gpio.write.return_value = "gpio fault"

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=0.0)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is False
        assert "gpio fault" in resp.message

    def test_enable_with_voltage_invokes_mcp4017(self):
        """When voltage_v > 0 on DUT channel, binary search must call mcp4017.set_step."""
        # INA219 readings simulate successful voltage convergence:
        # first call returns 4.5 V which is within 0.05 V of target 4.5 V.
        readings = [(None, 4.5, 25.0, 112.5)] * 5
        handler = _make_handler(ina_read_returns=readings)

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=4.5)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is True
        handler._mock_mcp4017.set_step.assert_called()

    def test_enable_voltage_control_failure_returns_error(self):
        """If voltage can't converge, PowerEnable fails."""
        # Return a fixed voltage far from target on every iteration.
        readings = [(None, 2.0, 0.0, 0.0)] * 15  # always 2 V, target 4.5 V
        handler = _make_handler(ina_read_returns=readings)

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=4.5)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is False
        assert "voltage" in resp.message.lower() or "final" in resp.message.lower()

    def test_enable_voltage_control_ina_error_returns_error(self):
        """If INA219 errors during voltage control, PowerEnable fails."""
        readings = [("ina read error", 0.0, 0.0, 0.0)] * 5
        handler = _make_handler(ina_read_returns=readings)

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_DUT, voltage_v=4.5)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is False


class TestPowerDisable(unittest.TestCase):
    """Test PowerDisable RPC logic."""

    def _make_ctx(self):
        ctx = MagicMock()
        ctx.is_active.return_value = True
        return ctx

    def test_disable_dut_channel_success(self):
        handler = _make_handler()
        # First enable so state is True
        handler._pwr_enabled = True

        req = PowerDisableRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        resp = handler.power_disable(req, self._make_ctx())

        assert resp.success is True
        assert "DUT" in resp.message

    def test_disable_clears_enabled_state(self):
        handler = _make_handler()
        handler._pwr_enabled = True

        req = PowerDisableRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        handler.power_disable(req, self._make_ctx())

        assert handler._is_enabled(PowerChannel.POWER_CHANNEL_DUT) is False

    def test_disable_charger_channel(self):
        handler = _make_handler()
        handler._chg_enabled = True

        req = PowerDisableRequest(channel=PowerChannel.POWER_CHANNEL_CHARGER)
        resp = handler.power_disable(req, self._make_ctx())

        assert resp.success is True
        assert handler._is_enabled(PowerChannel.POWER_CHANNEL_CHARGER) is False

    def test_disable_gpio_failure_returns_error(self):
        handler = _make_handler()
        handler._mock_gpio.write.return_value = "write error"

        req = PowerDisableRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        resp = handler.power_disable(req, self._make_ctx())

        assert resp.success is False
        assert "write error" in resp.message

    def test_disable_does_not_read_ina219(self):
        """Disabling power must never read INA219."""
        handler = _make_handler()
        req = PowerDisableRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        handler.power_disable(req, self._make_ctx())

        handler._mock_ina.read.assert_not_called()


class TestPowerRead(unittest.TestCase):
    """Test PowerRead RPC logic."""

    def _make_ctx(self):
        return MagicMock()

    def test_read_dut_channel_success(self):
        readings = [(None, 4.5, 25.0, 112.5)]
        handler = _make_handler(ina_read_returns=readings)
        handler._pwr_enabled = True

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is True
        assert resp.enabled is True
        assert abs(resp.voltage_v - 4.5) < 0.001
        assert abs(resp.current_ma - 25.0) < 0.001
        assert abs(resp.power_mw - 112.5) < 0.001

    def test_read_reflects_disabled_state(self):
        readings = [(None, 4.5, 0.0, 0.0)]
        handler = _make_handler(ina_read_returns=readings)
        handler._pwr_enabled = False

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is True
        assert resp.enabled is False

    def test_read_charger_channel(self):
        readings = [(None, 5.0, 30.0, 150.0)]
        handler = _make_handler(ina_read_returns=readings)
        handler._chg_enabled = True

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_CHARGER)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is True
        assert abs(resp.voltage_v - 5.0) < 0.001
        assert abs(resp.current_ma - 30.0) < 0.001

    def test_read_ina219_error_returns_failure(self):
        readings = [("sysfs read error", 0.0, 0.0, 0.0)]
        handler = _make_handler(ina_read_returns=readings)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_DUT)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False
        assert "sysfs read error" in resp.message

    def test_read_invalid_channel_returns_failure(self):
        """A channel value with no INA219 mapping should fail gracefully."""
        handler = _make_handler()
        # Inject an unmapped channel value directly
        req = PowerReadRequest(channel=99)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False


class TestPowerMeasure(unittest.TestCase):
    """Test PowerMeasure RPC logic."""

    def _make_ctx(self, active=True):
        ctx = MagicMock()
        ctx.is_active.return_value = active
        return ctx

    def test_measure_returns_statistics(self):
        """Measure over a short duration and verify stats computation."""
        # Three INA219 samples: currents 10, 20, 30 mA; voltages 4.5 V each
        readings = [
            (None, 4.5, 10.0, 45.0),
            (None, 4.5, 20.0, 90.0),
            (None, 4.5, 30.0, 135.0),
        ] * 10  # enough samples for a short duration
        handler = _make_handler(ina_read_returns=readings)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=0.05)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is True
        assert resp.sample_count > 0
        assert resp.min_ma <= resp.average_ma <= resp.max_ma
        assert resp.average_mv > 0

    def test_measure_averages_correctly(self):
        """All samples at same current → average equals that current."""
        readings = [(None, 4.5, 25.0, 112.5)] * 20
        handler = _make_handler(ina_read_returns=readings)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=0.05)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is True
        assert abs(resp.average_ma - 25.0) < 0.1
        assert abs(resp.min_ma - 25.0) < 0.1
        assert abs(resp.max_ma - 25.0) < 0.1

    def test_measure_min_max_correct(self):
        """Verify min/max are correctly identified across samples."""
        readings = [
            (None, 4.5, 5.0, 22.5),
            (None, 4.5, 50.0, 225.0),
            (None, 4.5, 25.0, 112.5),
        ] * 10
        handler = _make_handler(ina_read_returns=readings)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=0.05)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is True
        assert abs(resp.min_ma - 5.0) < 0.1
        assert abs(resp.max_ma - 50.0) < 0.1

    def test_measure_skips_bad_samples(self):
        """INA219 errors during measure are skipped; good samples still counted."""
        readings = [
            ("transient error", 0.0, 0.0, 0.0),
            (None, 4.5, 25.0, 112.5),
            ("transient error", 0.0, 0.0, 0.0),
            (None, 4.5, 25.0, 112.5),
        ] * 5
        handler = _make_handler(ina_read_returns=readings)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=0.05)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is True
        assert resp.sample_count > 0

    def test_measure_all_samples_fail_returns_error(self):
        """If every INA219 read fails, measure must fail with 'No samples'."""
        # Use a callable so the side_effect never exhausts regardless of call count
        handler = _make_handler(ina_read_returns=None)
        handler._mock_ina.read.side_effect = lambda addr: ("always fails", 0.0, 0.0, 0.0)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=0.05)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is False
        assert "No samples" in resp.message

    def test_measure_invalid_channel_returns_failure(self):
        handler = _make_handler()
        req = PowerMeasureRequest(channel=99, duration_s=0.1)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is False

    def test_measure_stops_when_context_inactive(self):
        """Measure exits early if gRPC context becomes inactive."""
        readings = [(None, 4.5, 25.0, 112.5)] * 5
        handler = _make_handler(ina_read_returns=readings)

        # Context immediately inactive
        ctx = self._make_ctx(active=False)
        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=10.0)

        start = time.monotonic()
        resp = handler.power_measure(req, ctx)
        elapsed = time.monotonic() - start

        # Should return quickly, not run for 10 seconds
        assert elapsed < 1.0


class TestPowerSnapshot(unittest.TestCase):
    """Test get_snapshot_data helper."""

    def test_snapshot_returns_both_channels(self):
        # Two channels: DUT (0x40) and CHARGER (0x41)
        readings = [
            (None, 4.5, 25.0, 112.5),  # DUT
            (None, 5.0, 10.0, 50.0),   # CHARGER
        ]
        handler = _make_handler(ina_read_returns=readings)
        handler._pwr_enabled = True
        handler._chg_enabled = False

        data = handler.get_snapshot_data()

        assert len(data) == 2
        channels = {d.channel for d in data}
        assert PowerChannel.POWER_CHANNEL_DUT in channels
        assert PowerChannel.POWER_CHANNEL_CHARGER in channels

    def test_snapshot_skips_failed_channels(self):
        """If INA219 read fails for a channel, it's omitted from snapshot."""
        readings = [
            ("ina error", 0.0, 0.0, 0.0),  # DUT fails
            (None, 5.0, 10.0, 50.0),        # CHARGER ok
        ]
        handler = _make_handler(ina_read_returns=readings)
        data = handler.get_snapshot_data()

        assert len(data) == 1
        assert data[0].channel == PowerChannel.POWER_CHANNEL_CHARGER

    def test_snapshot_reflects_enabled_state(self):
        readings = [
            (None, 4.5, 25.0, 112.5),
            (None, 5.0, 10.0, 50.0),
        ]
        handler = _make_handler(ina_read_returns=readings)
        handler._pwr_enabled = True
        handler._chg_enabled = False

        data = handler.get_snapshot_data()
        by_channel = {d.channel: d for d in data}

        assert by_channel[PowerChannel.POWER_CHANNEL_DUT].enabled is True
        assert by_channel[PowerChannel.POWER_CHANNEL_CHARGER].enabled is False


class TestPowerInternalHelpers(unittest.TestCase):
    """Test internal helper methods."""

    def test_get_ina_addr_dut(self):
        handler = _make_handler()
        assert handler._get_ina_addr(PowerChannel.POWER_CHANNEL_DUT) == 0x40

    def test_get_ina_addr_charger(self):
        handler = _make_handler()
        assert handler._get_ina_addr(PowerChannel.POWER_CHANNEL_CHARGER) == 0x41

    def test_get_ina_addr_invalid_returns_none(self):
        handler = _make_handler()
        assert handler._get_ina_addr(99) is None

    def test_is_enabled_tracks_per_channel(self):
        handler = _make_handler()
        handler._pwr_enabled = True
        handler._chg_enabled = False

        assert handler._is_enabled(PowerChannel.POWER_CHANNEL_DUT) is True
        assert handler._is_enabled(PowerChannel.POWER_CHANNEL_CHARGER) is False

    def test_set_enabled_updates_correct_channel(self):
        handler = _make_handler()
        handler._set_enabled(PowerChannel.POWER_CHANNEL_DUT, True)
        handler._set_enabled(PowerChannel.POWER_CHANNEL_CHARGER, True)

        assert handler._pwr_enabled is True
        assert handler._chg_enabled is True

        handler._set_enabled(PowerChannel.POWER_CHANNEL_DUT, False)
        assert handler._pwr_enabled is False
        assert handler._chg_enabled is True  # unaffected


def _make_mock_joulescope(read_returns=None):
    """Build a mock JoulescopeDriver."""
    js = MagicMock()
    js.is_connected = True
    js.serial_number = "JS220-001998"
    if read_returns is None:
        js.read.return_value = (None, 4.5, 0.000025, 0.0001125)  # 25 µA, 4.5 V
    else:
        js.read.side_effect = list(read_returns)
    js.read_statistics.return_value = (None, {
        "average_a": 0.000025,
        "min_a": 0.00001,
        "max_a": 0.00005,
        "average_v": 4.5,
        "sample_count": 1000,
        "duration_s": 1.0,
    })
    return js


def _make_handler_with_joulescope(joulescope=None, ina_read_returns=None):
    """Construct a PowerHandler with Joulescope support."""
    handler = _make_handler(ina_read_returns=ina_read_returns)
    handler._joulescope = joulescope
    return handler


class TestPowerEnableJoulescope(unittest.TestCase):
    """Test PowerEnable/Disable for Joulescope channel (always-on no-op)."""

    def _make_ctx(self):
        ctx = MagicMock()
        ctx.is_active.return_value = True
        return ctx

    def test_enable_joulescope_is_noop(self):
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, voltage_v=0.0)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is True
        assert "always-on" in resp.message.lower()

    def test_enable_joulescope_with_voltage_still_noop(self):
        """Voltage parameter is ignored for Joulescope — still a no-op."""
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, voltage_v=4.5)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is True
        assert "always-on" in resp.message.lower()
        # Must NOT have called voltage control or GPIO
        handler._mock_mcp4017.set_step.assert_not_called()

    def test_enable_joulescope_without_driver_still_succeeds(self):
        """Enable on Joulescope channel succeeds even without driver (no-op before check)."""
        handler = _make_handler_with_joulescope(joulescope=None)

        req = PowerEnableRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, voltage_v=0.0)
        resp = handler.power_enable(req, self._make_ctx())

        assert resp.success is True

    def test_disable_joulescope_is_noop(self):
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerDisableRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_disable(req, self._make_ctx())

        assert resp.success is True
        assert "always-on" in resp.message.lower()


class TestPowerReadJoulescope(unittest.TestCase):
    """Test PowerRead for Joulescope channel."""

    def _make_ctx(self):
        return MagicMock()

    def test_read_joulescope_success(self):
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is True
        assert resp.enabled is True  # Joulescope always reports enabled
        assert abs(resp.voltage_v - 4.5) < 0.001
        # 25 µA = 0.000025 A → current_ma = 0.025, current_na = 25000
        assert abs(resp.current_ma - 0.025) < 0.001
        assert abs(resp.current_na - 25000.0) < 1.0
        # power_mw = power_w * 1000 = 0.0001125 * 1000 = 0.1125
        assert abs(resp.power_mw - 0.1125) < 0.01

    def test_read_joulescope_unit_conversion_math(self):
        """Verify all unit conversions from amps to mA, nA, and mW."""
        # 1.5 mA = 0.0015 A at 3.3V
        js = _make_mock_joulescope(read_returns=[
            (None, 3.3, 0.0015, 0.00495)  # 1.5 mA, 3.3 V, 4.95 mW
        ])
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is True
        assert abs(resp.current_ma - 1.5) < 0.001        # 0.0015 * 1000
        assert abs(resp.current_na - 1500000.0) < 1.0    # 0.0015 * 1e9
        assert abs(resp.power_mw - 4.95) < 0.01          # 0.00495 * 1000
        assert abs(resp.voltage_v - 3.3) < 0.001

    def test_read_joulescope_not_connected(self):
        js = _make_mock_joulescope()
        js.is_connected = False
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False
        assert "not connected" in resp.message.lower()

    def test_read_joulescope_none(self):
        """No Joulescope driver at all."""
        handler = _make_handler_with_joulescope(joulescope=None)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False

    def test_read_joulescope_driver_error(self):
        js = _make_mock_joulescope(read_returns=[("USB disconnected", 0.0, 0.0, 0.0)])
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False
        assert "USB disconnected" in resp.message

    def test_read_joulescope_exception_caught(self):
        """Exception raised by driver (not error tuple) must be caught."""
        js = _make_mock_joulescope()
        js.read.side_effect = RuntimeError("segfault in USB driver")
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False
        assert "segfault" in resp.message

    def test_read_joulescope_none_returns_not_connected(self):
        """With no driver, error message mentions 'not connected'."""
        handler = _make_handler_with_joulescope(joulescope=None)

        req = PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE)
        resp = handler.power_read(req, self._make_ctx())

        assert resp.success is False
        assert "not connected" in resp.message.lower()


class TestPowerMeasureJoulescope(unittest.TestCase):
    """Test PowerMeasure for Joulescope channel."""

    def _make_ctx(self, active=True):
        ctx = MagicMock()
        ctx.is_active.return_value = active
        return ctx

    def test_measure_joulescope_success(self):
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, duration_s=1.0)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is True
        assert resp.sample_count == 1000
        assert resp.duration_s == 1.0
        # 25 µA = 0.000025 A → 0.025 mA average
        assert abs(resp.average_ma - 0.025) < 0.001
        assert abs(resp.min_ma - 0.01) < 0.001       # 10 µA
        assert abs(resp.max_ma - 0.05) < 0.001       # 50 µA
        # voltage: 4.5 V → 4500 mV
        assert abs(resp.average_mv - 4500.0) < 1.0
        # nA fields
        assert abs(resp.average_na - 25000.0) < 1.0  # 0.000025 * 1e9
        assert abs(resp.min_na - 10000.0) < 1.0      # 0.00001 * 1e9
        assert abs(resp.max_na - 50000.0) < 1.0      # 0.00005 * 1e9

    def test_measure_joulescope_not_connected(self):
        js = _make_mock_joulescope()
        js.is_connected = False
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, duration_s=1.0)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is False

    def test_measure_joulescope_driver_error(self):
        js = _make_mock_joulescope()
        js.read_statistics.return_value = ("USB error", None)
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, duration_s=1.0)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is False

    def test_measure_joulescope_exception_caught(self):
        """Exception from read_statistics must be caught."""
        js = _make_mock_joulescope()
        js.read_statistics.side_effect = RuntimeError("device yanked")
        handler = _make_handler_with_joulescope(joulescope=js)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, duration_s=1.0)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is False
        assert "device yanked" in resp.message

    def test_measure_joulescope_none_returns_not_connected(self):
        handler = _make_handler_with_joulescope(joulescope=None)

        req = PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_JOULESCOPE, duration_s=1.0)
        resp = handler.power_measure(req, self._make_ctx())

        assert resp.success is False
        assert "not connected" in resp.message.lower()


class TestPowerSnapshotJoulescope(unittest.TestCase):
    """Test snapshot includes Joulescope when connected."""

    def test_snapshot_includes_joulescope(self):
        readings = [
            (None, 4.5, 25.0, 112.5),  # DUT
            (None, 5.0, 10.0, 50.0),   # CHARGER
        ]
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js, ina_read_returns=readings)

        data = handler.get_snapshot_data()

        assert len(data) == 3
        by_ch = {d.channel: d for d in data}
        assert PowerChannel.POWER_CHANNEL_JOULESCOPE in by_ch

        js_snap = by_ch[PowerChannel.POWER_CHANNEL_JOULESCOPE]
        assert js_snap.enabled is True
        assert abs(js_snap.voltage_v - 4.5) < 0.001
        # 0.000025 A → 0.025 mA
        assert abs(js_snap.current_ma - 0.025) < 0.001

    def test_snapshot_joulescope_read_error_excluded(self):
        """If Joulescope read fails during snapshot, it's silently excluded."""
        readings = [
            (None, 4.5, 25.0, 112.5),
            (None, 5.0, 10.0, 50.0),
        ]
        js = _make_mock_joulescope(read_returns=[("USB error", 0.0, 0.0, 0.0)])
        handler = _make_handler_with_joulescope(joulescope=js, ina_read_returns=readings)

        data = handler.get_snapshot_data()

        assert len(data) == 2  # Only INA219 channels

    def test_snapshot_excludes_joulescope_when_not_connected(self):
        readings = [
            (None, 4.5, 25.0, 112.5),
            (None, 5.0, 10.0, 50.0),
        ]
        js = _make_mock_joulescope()
        js.is_connected = False
        handler = _make_handler_with_joulescope(joulescope=js, ina_read_returns=readings)

        data = handler.get_snapshot_data()

        assert len(data) == 2

    def test_snapshot_excludes_joulescope_when_none(self):
        readings = [
            (None, 4.5, 25.0, 112.5),
            (None, 5.0, 10.0, 50.0),
        ]
        handler = _make_handler_with_joulescope(joulescope=None, ina_read_returns=readings)

        data = handler.get_snapshot_data()

        assert len(data) == 2


class TestJoulescopeAvailableProperty(unittest.TestCase):
    """Test joulescope_available property."""

    def test_available_when_connected(self):
        js = _make_mock_joulescope()
        handler = _make_handler_with_joulescope(joulescope=js)
        assert handler.joulescope_available is True

    def test_not_available_when_disconnected(self):
        js = _make_mock_joulescope()
        js.is_connected = False
        handler = _make_handler_with_joulescope(joulescope=js)
        assert handler.joulescope_available is False

    def test_not_available_when_none(self):
        handler = _make_handler_with_joulescope(joulescope=None)
        assert handler.joulescope_available is False


if __name__ == "__main__":
    unittest.main()
