"""Common assertions for validation tests.

These assertions provide consistent error messages and are used
across all validation stages. They are product-agnostic — any product's
validation app can import and use them.

Usage:
    from corekinect.test.assertions import assert_powered, assert_current_in_range

    assert_powered(ctx.fixture, min_current_ma=5.0)
    assert_current_in_range(current_ma, min_ma=0.05, max_ma=0.1, name="sleep")
"""

import time
from typing import Any, Dict, Optional, Tuple


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
