"""Tests for the test-author DSL helpers added in Phase 3.

The DSL collapses the three patterns that recur across every alpha
manufacturing test into one call each:

  * ``assert_and_record(step, name, value, unit, predicate, msg)`` —
    couples a measurement record with the assertion that gates it,
    so the value lands on the reporter even when the assert fails.
  * ``assert_adc_settles(mtib, channel, threshold, *, timeout_s, op, poll_s)``
    — the 11-line "poll the ADC, sleep, check, time-out" pattern in
    ``test_01_electrical.py`` becomes one line.
  * ``assert_current_settles(mtib, channel, threshold, *, timeout_s, op, poll_s)``
    — same shape for current readings.

These tests use a fake MTIB stub (no hardware) so we can drive the
helper through every interesting branch deterministically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

import pytest

from corekinect.test.assertions import (
    assert_adc_settles,
    assert_and_record,
    assert_current_settles,
)


# ────────────────────────────────────────────────────────────────────────
# Fakes
# ────────────────────────────────────────────────────────────────────────


@dataclass
class _RecordedStep:
    """Minimal stand-in for ``ConcordReporter.StepReporter`` records."""

    records: List[tuple] = field(default_factory=list)

    def record(self, name: str, value: Any, unit: str = "") -> None:
        self.records.append((name, value, unit))


@dataclass
class _FakeMtib:
    """Drives ``AdcRead`` / ``PowerRead`` from a queue of pre-canned readings.

    Each call pops the next reading; ``readings`` may include strings
    or ``Exception`` instances to model partial failures and the
    helpers' tolerance for transient gRPC errors.
    """

    adc_readings: List[Optional[float]] = field(default_factory=list)
    power_readings: List[Optional[float]] = field(default_factory=list)

    def AdcRead(self, channel: int) -> tuple:
        if not self.adc_readings:
            return None, "no more readings configured"
        v = self.adc_readings.pop(0)
        if isinstance(v, Exception):
            return None, str(v)
        return v, None

    def PowerRead(self, channel: int) -> tuple:
        if not self.power_readings:
            return None, "no more readings configured"
        r = self.power_readings.pop(0)
        if isinstance(r, Exception):
            return None, str(r)
        # PowerRead returns a (current_ma, voltage_v, power_w, error)
        # tuple per the mtib_client v1 contract.
        return type("R", (), {"current_ma": r, "voltage_v": 4.5, "power_w": 0.0})(), None


# ────────────────────────────────────────────────────────────────────────
# assert_and_record
# ────────────────────────────────────────────────────────────────────────


class TestAssertAndRecord:
    """``assert_and_record`` records the value before the assertion fires."""

    def test_records_when_assertion_passes(self) -> None:
        step = _RecordedStep()
        assert_and_record(step, "voltage", 4.5, "V", lambda v: v >= 3.3)
        assert step.records == [("voltage", 4.5, "V")]

    def test_records_then_raises_when_assertion_fails(self) -> None:
        step = _RecordedStep()
        with pytest.raises(AssertionError) as excinfo:
            assert_and_record(step, "voltage", 2.0, "V", lambda v: v >= 3.3)
        # The record must land BEFORE the AssertionError so the operator
        # sees the actual reading in the reporter even though the test
        # failed.
        assert step.records == [("voltage", 2.0, "V")]
        assert "voltage" in str(excinfo.value)
        assert "2.0" in str(excinfo.value)

    def test_custom_message_overrides_default(self) -> None:
        step = _RecordedStep()
        with pytest.raises(AssertionError) as excinfo:
            assert_and_record(
                step, "voltage", 2.0, "V", lambda v: v >= 3.3,
                msg="3.3V rail did not reach nominal",
            )
        assert "3.3V rail did not reach nominal" in str(excinfo.value)

    def test_returns_value_for_chained_assertions(self) -> None:
        step = _RecordedStep()
        v = assert_and_record(step, "voltage", 4.5, "V", lambda v: v >= 3.3)
        assert v == 4.5

    def test_no_predicate_records_without_asserting(self) -> None:
        step = _RecordedStep()
        v = assert_and_record(step, "voltage", 4.5, "V")
        assert v == 4.5
        assert step.records == [("voltage", 4.5, "V")]


# ────────────────────────────────────────────────────────────────────────
# assert_adc_settles
# ────────────────────────────────────────────────────────────────────────


class TestAssertAdcSettles:
    """``assert_adc_settles`` replaces the 11-line poll loop with one call."""

    def test_returns_immediately_when_first_reading_satisfies(self) -> None:
        mtib = _FakeMtib(adc_readings=[0.4])
        v = assert_adc_settles(mtib, channel=0, threshold=0.55,
                               timeout_s=5, op="<=", poll_s=0.05)
        assert v == 0.4

    def test_polls_until_value_settles(self) -> None:
        # First two readings above threshold; third meets it.
        mtib = _FakeMtib(adc_readings=[3.2, 1.5, 0.5])
        v = assert_adc_settles(mtib, channel=0, threshold=0.55,
                               timeout_s=5, op="<=", poll_s=0.05)
        assert v == 0.5

    def test_raises_when_never_settles(self) -> None:
        mtib = _FakeMtib(adc_readings=[3.0, 3.0, 3.0, 3.0, 3.0, 3.0])
        with pytest.raises(AssertionError) as excinfo:
            assert_adc_settles(mtib, channel=0, threshold=0.55,
                               timeout_s=0.2, op="<=", poll_s=0.05)
        msg = str(excinfo.value)
        assert "channel" in msg.lower() or "0" in msg
        assert "0.55" in msg

    def test_op_geq_polls_for_voltage_to_rise(self) -> None:
        mtib = _FakeMtib(adc_readings=[0.1, 1.0, 3.5])
        v = assert_adc_settles(mtib, channel=7, threshold=3.0,
                               timeout_s=5, op=">=", poll_s=0.05)
        assert v == 3.5

    def test_tolerates_transient_read_errors_until_timeout(self) -> None:
        # First two reads error out, then a good one arrives.
        mtib = _FakeMtib(adc_readings=[Exception("grpc transient"),
                                        Exception("grpc transient"),
                                        0.4])
        v = assert_adc_settles(mtib, channel=0, threshold=0.55,
                               timeout_s=5, op="<=", poll_s=0.05)
        assert v == 0.4

    def test_invalid_op_raises_immediately(self) -> None:
        mtib = _FakeMtib(adc_readings=[0.4])
        with pytest.raises(ValueError):
            assert_adc_settles(mtib, channel=0, threshold=0.55,
                               timeout_s=5, op="==", poll_s=0.05)


# ────────────────────────────────────────────────────────────────────────
# assert_current_settles
# ────────────────────────────────────────────────────────────────────────


class TestAssertCurrentSettles:
    """Same shape as ``assert_adc_settles`` but for ``PowerRead.current_ma``."""

    def test_returns_when_current_drops_under_threshold(self) -> None:
        mtib = _FakeMtib(power_readings=[60.0, 30.0, 5.0])
        i = assert_current_settles(mtib, channel=0, threshold=10.0,
                                    timeout_s=5, op="<=", poll_s=0.05)
        assert i == 5.0

    def test_geq_for_boot_complete_detection(self) -> None:
        # Steady-state current rises above 5 mA after boot.
        mtib = _FakeMtib(power_readings=[0.0, 0.5, 6.0])
        i = assert_current_settles(mtib, channel=0, threshold=5.0,
                                    timeout_s=5, op=">=", poll_s=0.05)
        assert i == 6.0

    def test_raises_with_last_reading_in_message(self) -> None:
        mtib = _FakeMtib(power_readings=[40.0, 30.0, 25.0, 20.0, 18.0])
        with pytest.raises(AssertionError) as excinfo:
            assert_current_settles(mtib, channel=0, threshold=5.0,
                                    timeout_s=0.2, op="<=", poll_s=0.05)
        msg = str(excinfo.value)
        assert "5.0" in msg  # threshold
        # Last reading should appear so the operator can see how far off we were.
        assert "18" in msg or "20" in msg
