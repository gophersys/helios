"""MTIB hardware smoke test — validates Layers 1-3 without CoreCloud.

Exercises the full FixtureController → MtibV1Client → MTIB Server chain
on live hardware. No CoreCloud credentials needed.

Run directly:
    MTIB_HOST=10.4.45.33 MTIB_PORT=50053 DEVICE_ID=70B3D584C01E1FCC \
    FIXTURE_PROFILE_PATH=libs/python/corekinect/test/validation/fixtures/alpha_b0.json \
    PYTHONPATH=libs/python:libs:libs/protocols \
    python3 -m pytest libs/python/corekinect/test/validation/tests/test_smoke_mtib.py -v -s
"""

import logging
import os
import time

import pytest

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from corekinect.test.validation.fixture_controller import FixtureController, FixtureProfile
from corekinect.test.validation.power_profiler import PowerProfiler

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def mtib():
    """Connect to MTIB server."""
    host = os.environ.get("MTIB_HOST", "10.4.45.33")
    port = int(os.environ.get("MTIB_PORT", "50053"))

    config = MtibV1Client.Config(net=NetConfig(addr=host, port=port))
    client = MtibV1Client(config)
    err = client.connect()
    assert err is None, f"MTIB connect failed: {err}"

    ready, errors, err = client.HealthCheck()
    assert err is None, f"HealthCheck failed: {err}"
    assert ready, f"MTIB not ready: {errors}"

    yield client
    client.disconnect()


@pytest.fixture(scope="module")
def fixture(mtib):
    """FixtureController with Alpha B0 profile."""
    profile_path = os.environ.get(
        "FIXTURE_PROFILE_PATH",
        "libs/python/corekinect/test/validation/fixtures/alpha_b0.json",
    )
    profile = FixtureProfile.from_json(profile_path)
    return FixtureController(mtib=mtib, profile=profile)


@pytest.fixture(scope="module")
def profiler(mtib):
    """PowerProfiler instance."""
    return PowerProfiler(mtib=mtib)


class TestMtibConnection:
    """Layer 1: MTIB gRPC connectivity."""

    def test_health_check(self, mtib):
        """MTIB server is reachable and healthy."""
        ready, errors, err = mtib.HealthCheck()
        assert err is None
        assert ready

    def test_health_check_extended(self, mtib):
        """Extended health check returns hardware info."""
        result = mtib.HealthCheckExtended()
        assert result is not None
        log.info("MTIB: hw_revision=%s", getattr(result, "hw_revision", "?"))


class TestGpio:
    """Layer 1: GPIO configuration and read-back."""

    def test_gpio_config_swd_pins(self, mtib):
        """GPIO 0+1 can be configured as output LOW (SWD enable)."""
        for gpio in (0, 1):
            err = mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
            assert err is None, f"GpioConfig({gpio}) failed: {err}"
            err = mtib.GpioWrite(gpio, False)
            assert err is None, f"GpioWrite({gpio}, LOW) failed: {err}"

    def test_gpio_read_back(self, mtib):
        """GPIO pins can be read back after write."""
        err = mtib.GpioConfig(2, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        assert err is None
        err = mtib.GpioWrite(2, True)
        assert err is None
        state, err = mtib.GpioRead(2)
        assert err is None
        assert state is True, "GPIO 2 readback should be HIGH"
        # Clean up
        err = mtib.GpioWrite(2, False)
        assert err is None


class TestPower:
    """Layer 2-3: Power on DUT and verify current draw."""

    def test_power_on_and_read(self, fixture):
        """Power on DUT at 4.5V and verify current draw (DUT is alive).

        Alpha B0 draws ~28mA during boot, settling to ~5-8mA in idle.
        Threshold at 2mA to detect "DUT is alive" vs "no firmware / disconnected".
        """
        # Disable all power first to clear any leftover state from prior sessions
        try:
            fixture.power_off()
            fixture.charger_power_off()
        except Exception:
            pass  # OK if already off
        time.sleep(2)

        fixture.power_on(voltage=4.5)

        # Sample current every second to capture boot transient
        peak_current = 0.0
        for i in range(6):
            current = fixture.read_dut_current()
            peak_current = max(peak_current, current)
            log.info("DUT t=%ds: %.1f mA (peak=%.1f mA)", i, current, peak_current)
            if i < 5:
                time.sleep(1)

        assert peak_current > 2, (
            f"DUT peak current only {peak_current:.1f}mA over 5s — "
            "expected >2mA (firmware may be wiped or DUT disconnected)"
        )

    def test_power_rails_adc(self, fixture):
        """Read ADC power rails — ch0-3 should have plausible values."""
        rails = fixture.read_power_rails()
        log.info("Power rails: %s", {k: f"{v:.2f}V" for k, v in rails.items()})

        # Ch0 should be near 4.5V (power rail) when DUT is powered
        assert rails["3v3"] > 3.0, f"Ch0 (3v3/power rail) unexpectedly low: {rails['3v3']:.2f}V"
        # Ch1 should be ~2.5V (battery divider)
        assert rails["batt_sys"] > 1.0, f"Ch1 (batt_sys) unexpectedly low: {rails['batt_sys']:.2f}V"

    def test_power_measure(self, profiler):
        """PowerMeasure RPC returns valid stats over 5 seconds."""
        result = profiler.measure(channel=0, duration_s=5)
        log.info(
            "PowerMeasure: avg=%.1fmA, peak=%.1fmA, min=%.1fmA, samples=%d",
            result.avg_current_ma, result.peak_current_ma,
            result.min_current_ma, result.samples,
        )
        assert result.samples > 0, "No samples collected"
        assert result.avg_current_ma > 0, "Average current should be >0 with DUT powered"

    def test_power_quick_read(self, profiler):
        """Quick single-shot power read returns plausible values."""
        voltage_mv, current_ma, power_mw = profiler.quick_read()
        log.info("QuickRead: %.0fmV, %.1fmA, %.1fmW", voltage_mv, current_ma, power_mw)
        assert voltage_mv > 3000, f"Voltage {voltage_mv}mV too low"
        assert current_ma >= 0, "Current should be >=0"

    def test_power_off(self, fixture):
        """Power off DUT — current should drop to ~0."""
        fixture.power_off()
        time.sleep(1)
        # Read raw power to check it's near zero
        result, err = fixture._mtib.PowerRead(channel=0)
        assert err is None
        log.info("After power off: %.1f mA", result.current_ma)
        assert result.current_ma < 5, f"DUT still drawing {result.current_ma}mA after power off"


class TestAdc:
    """Layer 1: ADC reads across all 8 channels."""

    def test_adc_read_all(self, mtib, fixture):
        """ADC ReadAll returns values for all channels."""
        # Power DUT back on for meaningful readings
        fixture.power_on()
        time.sleep(3)

        results, err = mtib.AdcReadAll()
        assert err is None, f"AdcReadAll failed: {err}"

        for ch, voltage in enumerate(results):
            log.info("ADC ch%d: %.3fV", ch, voltage)

        # At least ch0 and ch7 should have meaningful values
        assert len(results) >= 8, f"Expected 8 ADC channels, got {len(results)}"

    def test_adc_single_channel(self, mtib):
        """ADC single channel read works."""
        voltage, err = mtib.AdcRead(0)
        assert err is None, f"AdcRead(ch=0) failed: {err}"
        log.info("ADC ch0: %.3fV", voltage)
        assert voltage > 0, "ADC channel 0 should read >0V when DUT is powered"


class TestSnapshot:
    """Layer 1: GetSnapshot returns full system state."""

    def test_get_snapshot(self, mtib):
        """GetSnapshot returns aggregated system state."""
        result, err = mtib.GetSnapshot()
        assert err is None, f"GetSnapshot failed: {err}"
        assert result is not None
        log.info("Snapshot: %s", result)


class TestCleanup:
    """Always run last — power off DUT."""

    def test_power_off_final(self, fixture):
        """Ensure DUT is powered off at end of smoke test."""
        fixture.power_off()
        log.info("Smoke test cleanup: DUT powered off")
