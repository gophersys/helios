"""Common assertions for validation tests.

These assertions provide consistent error messages and are used
across all validation stages. They are product-agnostic — any product's
validation app can import and use them.

Two layers:

* **Coarse helpers** (``assert_powered``, ``assert_current_in_range``,
  ``assert_cloud_message``, ``assert_flash_success``,
  ``assert_fuota_progress``) — built around the validation
  ``ctx.fixture`` / cloud-client surfaces.

* **Test-author DSL** (``assert_and_record``, ``assert_adc_settles``,
  ``assert_current_settles``) — the three-call patterns that recur
  across every alpha manufacturing test, collapsed into one call
  each. Pair an assertion with a reporter ``step.record`` and
  encapsulate the "poll an MTIB reading until it settles" loop so
  test bodies stay focused on what they're verifying.

Usage:
    from corekinect.test.assertions import (
        assert_powered, assert_current_in_range,
        assert_and_record, assert_adc_settles, assert_current_settles,
    )

    assert_powered(ctx.fixture, min_current_ma=5.0)
    assert_current_in_range(current_ma, min_ma=0.05, max_ma=0.1, name="sleep")

    # In a manufacturing test:
    with report.step("Verify 3.3V rail UVLO") as step:
        v = assert_adc_settles(mtib, channel=0, threshold=0.55,
                                timeout_s=15, op="<=")
        assert_and_record(step, "3v3_voltage", v, "V", lambda x: x <= 0.55)
"""

import time
from typing import Any, Callable, Dict, Optional, Tuple

# Operators we accept for the ``settle`` helpers below. Map symbol →
# (predicate, human-readable name) so the failure message reads naturally.
_SETTLE_OPS: Dict[str, Tuple[Callable[[float, float], bool], str]] = {
    "<=": (lambda v, t: v <= t, "≤"),
    ">=": (lambda v, t: v >= t, "≥"),
    "<":  (lambda v, t: v < t,  "<"),
    ">":  (lambda v, t: v > t,  ">"),
}


def assert_powered(
    fixture,
    min_current_ma: float = 5.0,
    samples: int = 10,
    interval_s: float = 0.5,
    channel: Optional[int] = None,
) -> float:
    """Assert device is drawing current (powered on).

    Takes multiple samples to handle modem burst variability.

    Args:
        fixture: FixtureController instance.
        min_current_ma: Minimum current to consider "powered".
        samples: Number of samples to take.
        interval_s: Interval between samples.
        channel: Power channel (None = auto based on fixture profile).

    Returns:
        Average current in mA.

    Raises:
        AssertionError: If max current is below threshold.
    """
    readings = []
    for _ in range(samples):
        if channel is not None:
            current = fixture.read_current(channel=channel)
        else:
            current = fixture.read_total_current()
        readings.append(current)
        time.sleep(interval_s)

    max_current = max(readings)
    avg_current = sum(readings) / len(readings)

    assert max_current >= min_current_ma, (
        f"Device not powered: max={max_current:.2f}mA < {min_current_ma}mA "
        f"(samples: {[f'{r:.2f}' for r in readings]})"
    )

    return avg_current


def assert_current_in_range(
    current_ma: float,
    min_ma: float,
    max_ma: float,
    name: str = "current",
) -> None:
    """Assert current is within expected range.

    Args:
        current_ma: Measured current in mA.
        min_ma: Minimum expected current.
        max_ma: Maximum expected current.
        name: Name for error message (e.g., "sleep", "active").

    Raises:
        AssertionError: If current is outside range.
    """
    assert min_ma <= current_ma <= max_ma, (
        f"{name} current {current_ma:.3f}mA outside range "
        f"[{min_ma:.3f}, {max_ma:.3f}]mA"
    )


def assert_cloud_message(
    message: Optional[Dict[str, Any]],
    message_type: str,
    required_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assert a cloud message was received and has expected fields.

    Args:
        message: Message dict (or None if not received).
        message_type: Expected message type (for error message).
        required_fields: Dict of field_name -> expected_value.
            If value is None, just checks field exists.
            If value is a callable, calls it with the actual value.

    Returns:
        The message dict (for chaining).

    Raises:
        AssertionError: If message is None or fields don't match.
    """
    assert message is not None, f"Expected {message_type} message, got None"

    if required_fields:
        for field, expected in required_fields.items():
            assert field in message, (
                f"{message_type} missing required field '{field}'. "
                f"Got: {list(message.keys())}"
            )
            actual = message[field]

            if expected is None:
                continue  # Just checking existence
            elif callable(expected):
                assert expected(actual), (
                    f"{message_type}.{field} failed validation: {actual}"
                )
            else:
                assert actual == expected, (
                    f"{message_type}.{field} = {actual}, expected {expected}"
                )

    return message


def assert_flash_success(
    result: Tuple[Optional[int], Optional[str]],
    target: str,
) -> int:
    """Assert flash operation succeeded.

    Args:
        result: Tuple of (time_ms, error) from FlashFwFile.
        target: Target name for error message (e.g., "nRF52840").

    Returns:
        Flash time in ms.

    Raises:
        AssertionError: If flash failed.
    """
    time_ms, err = result
    assert not err, f"{target} flash failed: {err}"
    return time_ms or 0


def assert_fuota_progress(
    progress: Optional[Dict[str, Any]],
    expected_complete: bool = False,
) -> Dict[str, Any]:
    """Assert FUOTA progress is valid.

    Args:
        progress: Progress dict from get_progress().
        expected_complete: If True, assert isComplete is True.

    Returns:
        The progress dict.

    Raises:
        AssertionError: If progress is invalid or completion doesn't match.
    """
    assert progress is not None, "FUOTA progress is None"

    if expected_complete:
        assert progress.get("isComplete") is True, (
            f"FUOTA not complete: {progress}"
        )

    return progress


# ────────────────────────────────────────────────────────────────────────
# Test-author DSL — Phase 3
# ────────────────────────────────────────────────────────────────────────


def assert_and_record(
    step,
    name: str,
    value: Any,
    unit: str = "",
    predicate: Optional[Callable[[Any], bool]] = None,
    msg: Optional[str] = None,
):
    """Record ``value`` to the reporter step, then assert ``predicate(value)``.

    The record lands BEFORE the assertion fires so the operator sees
    the actual reading in the reporter timeline even when the test
    fails. Without this helper test authors had to write the same
    three lines (record, assert, hand-format error) in every step.

    ``predicate`` is optional — pass ``None`` to record-only and
    skip the assertion (useful when the value is informational).

    Returns the value so callers can chain (e.g. ``v = assert_and_record(...)``).

        with report.step("Read 3.3V rail") as step:
            v = mtib.read_adc(0)
            assert_and_record(step, "3v3_voltage", v, "V", lambda x: x >= 3.0)
    """
    step.record(name, value, unit=unit) if unit else step.record(name, value)
    if predicate is not None and not predicate(value):
        if msg is None:
            msg = f"{name} predicate failed: value={value}{(' ' + unit) if unit else ''}"
        raise AssertionError(msg)
    return value


def assert_adc_settles(
    mtib,
    channel: int,
    threshold: float,
    *,
    timeout_s: float,
    op: str = "<=",
    poll_s: float = 0.5,
) -> float:
    """Poll ``mtib.AdcRead(channel)`` until ``op(value, threshold)`` holds.

    Replaces the 11-line "while time.time() - start < ...; sleep; check"
    boilerplate that appears in every electrical test in
    ``apps/manufacturing/alpha/tests/manufacturing/test_01_electrical.py``.

    Tolerates transient gRPC read errors (returns ``(None, err)``) by
    skipping the sample and trying again on the next poll cycle. The
    timeout is hard-real — once the deadline passes, raises with the
    last successful reading included so the operator can see how far
    off the rail was.

    Returns the first value that satisfies the predicate.

        v3v3 = assert_adc_settles(mtib, channel=0, threshold=0.55,
                                   timeout_s=15, op="<=")
    """
    if op not in _SETTLE_OPS:
        raise ValueError(
            f"assert_adc_settles op must be one of {sorted(_SETTLE_OPS)}, got {op!r}"
        )
    pred, sym = _SETTLE_OPS[op]
    deadline = time.time() + timeout_s
    last_val: Optional[float] = None
    while time.time() < deadline:
        v, err = mtib.AdcRead(channel=channel)
        if err is None and v is not None:
            last_val = v
            if pred(v, threshold):
                return v
        time.sleep(poll_s)
    raise AssertionError(
        f"ADC channel {channel} did not settle {sym} {threshold} within "
        f"{timeout_s}s (last reading: {last_val})"
    )


def assert_current_settles(
    mtib,
    channel: int,
    threshold: float,
    *,
    timeout_s: float,
    op: str = "<=",
    poll_s: float = 0.5,
) -> float:
    """Same shape as :func:`assert_adc_settles` but for ``mtib.PowerRead``.

    Reads ``current_ma`` from the ``PowerRead`` result tuple. Useful
    for "device entered low-power" (op="<=") and "device booted and
    is drawing nominal current" (op=">=") gates.
    """
    if op not in _SETTLE_OPS:
        raise ValueError(
            f"assert_current_settles op must be one of {sorted(_SETTLE_OPS)}, got {op!r}"
        )
    pred, sym = _SETTLE_OPS[op]
    deadline = time.time() + timeout_s
    last_val: Optional[float] = None
    while time.time() < deadline:
        result, err = mtib.PowerRead(channel=channel)
        if err is None and result is not None:
            i = float(getattr(result, "current_ma", 0.0))
            last_val = i
            if pred(i, threshold):
                return i
        time.sleep(poll_s)
    raise AssertionError(
        f"Current on channel {channel} did not settle {sym} {threshold} mA within "
        f"{timeout_s}s (last reading: {last_val} mA)"
    )
