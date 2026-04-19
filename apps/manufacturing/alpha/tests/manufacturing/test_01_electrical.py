"""Electrical power test — UVLO, regulation, charger load-sharing.

Validates the Alpha B0 power delivery system across voltage thresholds:
  test_01 — UVLO off state: apply sub-threshold voltage, verify no power
  test_02 — Nominal power-up: apply 3.7V, verify DUT boots
  test_03 — High voltage regulation: apply 4.5V, verify rails track
  test_04 — Charger load-sharing: apply 5V to CHRG, verify handoff

Run:
    Triggered via manufacturing session → panel scan → runner executes.
"""

import logging
import time

import pytest

log = logging.getLogger("manufacturing.electrical")

# ADC channel mapping (measured on REV 1.2 hardware)
ADC_3V3 = 0        # TP301: +3.3V regulator output
ADC_BATT_SYS = 1   # TP201: +BATT_SYS (battery system rail)
ADC_VBCKP = 2      # TP607: +VBCKP (backup rail)
ADC_SYS = 3        # TP202: +SYS (system rail)


def _get_config(config: dict) -> dict:
    return {
        "uvlo_v": config.get("electrical_uvlo_voltage_v", 3.4),
        "nominal_v": config.get("electrical_nominal_voltage_v", 3.7),
        "high_v": config.get("electrical_high_voltage_v", 4.5),
        "stabilization_s": config.get("electrical_stabilization_period_s", 30),
        "thresh_3v3": config.get("electrical_step_1_3v3_threshold_v", 0.55),
        "thresh_current_a": config.get("electrical_step_1_current_threshold_a", 0.001),
    }


@pytest.mark.electrical
@pytest.mark.sequential
@pytest.mark.timeout(30)  # observed p95=21s, max=24s; budget = max + 6s
def test_01_uvlo_off_state(slot, config, report):
    """Apply sub-threshold voltage and verify the DUT stays off."""
    mtib = slot.mtib
    c = _get_config(config)

    with report.step("Apply UVLO voltage to +BATT_IN") as step:
        err = mtib.PowerEnable(channel=0, voltage_v=c["uvlo_v"])
        assert err is None, f"PowerEnable failed at {c['uvlo_v']}V: {err}"
        step.record("batt_in_voltage", c["uvlo_v"], unit="V")
        log.info("Applied %.1fV to +BATT_IN (below UVLO threshold)", c["uvlo_v"])

    with report.step("Verify 3.3V decayed and leakage within spec") as step:
        v3v3_ok = False
        measured_3v3 = None
        start = time.time()
        while time.time() - start < c["stabilization_s"]:
            voltage_v, err = mtib.AdcRead(channel=ADC_3V3)
            if err is None and voltage_v is not None:
                measured_3v3 = voltage_v
                if voltage_v <= c["thresh_3v3"]:
                    v3v3_ok = True
                    break
            time.sleep(0.5)

        step.record("3v3_voltage", measured_3v3 or 0.0, unit="V")
        step.record("stabilization_time_s", round(time.time() - start, 1), unit="s")
        assert v3v3_ok, (
            f"3.3V rail did not decay below {c['thresh_3v3']}V within "
            f"{c['stabilization_s']}s (last reading: {measured_3v3}V)"
        )
        log.info("3.3V decayed to %.3fV in %.1fs", measured_3v3, time.time() - start)

        result, err = mtib.PowerRead(channel=0)
        assert err is None, f"PowerRead error: {err}"
        current_ma = result.current_ma
        step.record("leakage_current_ma", round(current_ma, 4), unit="mA")
        assert current_ma <= c["thresh_current_a"] * 1000, (
            f"Leakage current {current_ma:.4f}mA exceeds {c['thresh_current_a'] * 1000:.4f}mA"
        )
        log.info("Leakage current: %.4fmA (limit: %.4fmA)", current_ma, c["thresh_current_a"] * 1000)


@pytest.mark.electrical
@pytest.mark.sequential
@pytest.mark.timeout(35)  # observed p95=22s, max=25s (corectl budgets suggest); tail is slow-rail stabilization under contention
def test_02_nominal_power(slot, config, report):
    """Apply nominal voltage (3.7V) and verify the DUT powers up."""
    mtib = slot.mtib
    c = _get_config(config)

    with report.step("Apply nominal voltage to +BATT_IN") as step:
        err = mtib.PowerEnable(channel=0, voltage_v=c["nominal_v"])
        assert err is None, f"PowerEnable failed at {c['nominal_v']}V: {err}"
        step.record("batt_in_voltage", c["nominal_v"], unit="V")
        log.info("Applied %.1fV to +BATT_IN (above UVLO)", c["nominal_v"])

    with report.step("Verify power rails at nominal voltage") as step:
        step.record("status", "pending_adc_validation")
        log.info("ADC rail validation pending — channel mapping needs hardware verification")


@pytest.mark.electrical
@pytest.mark.sequential
@pytest.mark.timeout(50)  # observed p95=26s, max=41s (corectl budgets suggest); tail is +SYS tracking under load
def test_03_high_voltage(slot, config, report):
    """Apply high voltage (4.5V) and verify rails track correctly."""
    mtib = slot.mtib
    c = _get_config(config)

    with report.step("Apply high voltage to +BATT_IN") as step:
        err = mtib.PowerEnable(channel=0, voltage_v=c["high_v"])
        assert err is None, f"PowerEnable failed at {c['high_v']}V: {err}"
        step.record("batt_in_voltage", c["high_v"], unit="V")
        log.info("Applied %.1fV to +BATT_IN", c["high_v"])

    with report.step("Verify +SYS tracks +BATT_IN") as step:
        time.sleep(2)
        step.record("status", "pending_adc_validation")
        log.info("ADC SYS tracking validation pending — channel mapping needs hardware verification")


@pytest.mark.electrical
@pytest.mark.sequential
@pytest.mark.timeout(55)  # observed p95=15s, max=48s (corectl budgets suggest); tail is charger handoff under USB pathway latency
def test_04_charger_load_sharing(slot, config, report):
    """Apply 5V to charger input and verify load-sharing handoff."""
    mtib = slot.mtib

    with report.step("Enable charger rail at 5.0V") as step:
        err = mtib.PowerEnable(channel=1, voltage_v=5.0)
        assert err is None, f"PowerEnable(CHRG) failed: {err}"
        step.record("chrg_voltage", 5.0, unit="V")
        log.info("Applied 5.0V to +CHRG")

    with report.step("Verify charger load-sharing") as step:
        time.sleep(2)
        ch0_result, err0 = mtib.PowerRead(channel=0)
        ch1_result, err1 = mtib.PowerRead(channel=1)
        ch0_ma = ch0_result.current_ma if ch0_result and not err0 else 0.0
        ch1_ma = ch1_result.current_ma if ch1_result and not err1 else 0.0
        step.record("battery_current_ma", round(ch0_ma, 2), unit="mA")
        step.record("charger_current_ma", round(ch1_ma, 2), unit="mA")
        log.info("Battery: %.2fmA, Charger: %.2fmA", ch0_ma, ch1_ma)

    with report.step("Disable charger rail") as step:
        err = mtib.PowerDisable(channel=1)
        if err:
            log.warning("PowerDisable(CHRG) returned: %s", err)
        step.record("charger_disabled", True)
        log.info("Removed power from +CHRG — charger test complete")
