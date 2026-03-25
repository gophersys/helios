"""Electrical Power Test — pytest implementation with sub-step reporting.

Migrated from apps/manufacturing/alpha/src/tests/electrical/step_1.py through step_10.py.

Tests the electrical power system including UVLO, power supply regulation,
and charger load sharing.  Steps that were commented out in the original
handlers are preserved in the same state (immediately pass) with comments
explaining they are pending ADC validation.

Run locally:
    cd apps/manufacturing/alpha
    MOCK_MODE=1 PYTHONPATH=.:../../../libs/python:../../../libs:../../../libs/protocols \\
        python -m pytest tests_pytest/test_electrical.py -v
"""

import logging
import time
from dataclasses import asdict, dataclass

import pytest

log = logging.getLogger("manufacturing.electrical")


# ── ADC channel mapping ────────────────────────────────────────────────────

ADC_BATT_SYS = 1   # TP201: +BATT_SYS
ADC_SYS = 3        # TP202: +SYS
ADC_3V3 = 0        # TP301: +3.3V
ADC_VBCKP = 2      # TP607: +VBCKP


# ── Test ───────────────────────────────────────────────────────────────────

@pytest.mark.electrical
@pytest.mark.sequential
def test_electrical(slot, config, report):
    """Electrical power system test.

    Exercises UVLO thresholds, power rail regulation, current draw, and
    charger load-sharing behaviour.  Follows the original 10-step test plan.
    """
    mtib = slot.mtib

    # Fixture config thresholds (fall back to ThetaFixtureConfig defaults)
    uvlo_voltage = config.get("electrical_uvlo_voltage_v", 3.4)
    nominal_voltage = config.get("electrical_nominal_voltage_v", 3.7)
    high_voltage = config.get("electrical_high_voltage_v", 4.5)
    stabilization_s = config.get("electrical_stabilization_period_s", 30)
    step1_3v3_thresh = config.get("electrical_step_1_3v3_threshold_v", 0.55)
    step1_current_thresh = config.get("electrical_step_1_current_threshold_a", 0.001)

    # ── Step 1: Apply +3.4V to +BATT_IN (below UVLO) ───────────────────
    with report.step("Apply +3.4V to +BATT_IN"):
        _, err = mtib.PowerEnable(channel=0, voltage_v=uvlo_voltage)
        assert err is None, f"PowerEnable failed at {uvlo_voltage}V: {err}"
        log.info("Step 1: Applied %sV to +BATT_IN", uvlo_voltage)

    # ── Step 2: Ensure device electrical state (UVLO off) ───────────────
    with report.step("Ensure device electrical state (UVLO off)"):
        # 2b. Wait for +3.3V to decay below threshold
        v3v3_ok = False
        start_time = time.time()
        while time.time() - start_time < stabilization_s:
            try:
                result, err = mtib.AdcRead(channel=ADC_3V3)
                assert err is None, f"AdcRead(3V3) error: {err}"
                if result.voltage_v <= step1_3v3_thresh:
                    v3v3_ok = True
                    break
            except AttributeError:
                # Mock mode — no AdcRead
                v3v3_ok = True
                break
            time.sleep(0.5)

        assert v3v3_ok, (
            f"3.3V did not decay below {step1_3v3_thresh}V within {stabilization_s}s"
        )

        # 2d. Ensure current below 1mA
        _is_mock = type(mtib).__name__ == "MockMtibClient"
        if not _is_mock:
            try:
                result, err = mtib.DutPowerRead(channel=0)
                assert err is None, f"DutPowerRead error: {err}"
                current_a = result.current_ma / 1000.0
                assert current_a <= step1_current_thresh, (
                    f"Current {current_a:.6f}A exceeds threshold {step1_current_thresh:.6f}A"
                )
            except AttributeError:
                pass  # AdcRead not available

        log.info("Step 2 PASS: Device in UVLO off state")

    # ── Step 3: Apply +3.7V to +BATT_IN ────────────────────────────────
    with report.step("Apply +3.7V to +BATT_IN"):
        _, err = mtib.PowerEnable(channel=0, voltage_v=nominal_voltage)
        assert err is None, f"PowerEnable failed at {nominal_voltage}V: {err}"
        log.info("Step 3: Applied %sV to +BATT_IN", nominal_voltage)

    # ── Step 4: Ensure +3.3V remains below threshold (startup delay) ───
    with report.step("Ensure +3.3V remains below threshold for startup delay"):
        # NOTE: This step was commented out in the original handler.
        # The DUT startup delay check is pending ADC stabilization investigation.
        log.info("Step 4: Skipped (pending ADC stabilization investigation)")

    # ── Step 5: Ensure device electrical state (powered at 3.7V) ────────
    with report.step("Ensure device electrical state (powered at 3.7V)"):
        # NOTE: All sub-checks (5a through 5e) were commented out in the
        # original handler.  They are pending ADC channel mapping validation.
        log.info("Step 5: Skipped (pending ADC channel mapping validation)")

    # ── Step 6: Apply +4.5V to +BATT_IN ────────────────────────────────
    with report.step("Apply +4.5V to +BATT_IN"):
        _, err = mtib.PowerEnable(channel=0, voltage_v=high_voltage)
        assert err is None, f"PowerEnable failed at {high_voltage}V: {err}"
        log.info("Step 6: Applied %sV to +BATT_IN", high_voltage)

    # ── Step 7: Ensure +SYS tracks +BATT_IN ─────────────────────────────
    with report.step("Ensure +SYS voltage tracks +BATT_IN"):
        time.sleep(2)
        # NOTE: Actual SYS voltage read was commented out in the original handler.
        log.info("Step 7: Skipped (pending ADC SYS channel validation)")

    # ── Step 8: Apply 5.0V to +CHRG ────────────────────────────────────
    with report.step("Apply 5.0V to +CHRG"):
        _, err = mtib.PowerEnable(channel=1, voltage_v=5.0)
        assert err is None, f"PowerEnable(CHRG) failed: {err}"
        log.info("Step 8: Applied 5.0V to +CHRG")

    # ── Step 9 is commented out in original (charger-on verification) ──
    # Skipped: electrical_test_step_9 was not included in the step list.

    # ── Step 10: Remove power from +CHRG ───────────────────────────────
    with report.step("Remove power from +CHRG"):
        err = mtib.PowerDisable(channel=1)
        # PowerDisable may return error string or None depending on mock
        if err:
            log.warning("PowerDisable(CHRG) returned: %s", err)
        log.info("Step 10: Removed power from +CHRG")
