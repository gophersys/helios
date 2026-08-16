"""Tests for common validation assertions.

Tests the 5 assertion functions from corekinect.test.assertions using
simple mock objects instead of real hardware fixtures.
"""

from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.assertions import (
    assert_powered,
    assert_current_in_range,
    assert_cloud_message,
    assert_flash_success,
    assert_fuota_progress,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fixture(total_current_values=None, channel_current_values=None):
    """Create a mock fixture with configurable current readings.

    Args:
        total_current_values: List of values read_total_current returns in order.
        channel_current_values: List of values read_current returns in order.
    """
    fixture = MagicMock()
    if total_current_values is not None:
        fixture.read_total_current.side_effect = list(total_current_values)
    if channel_current_values is not None:
        fixture.read_current.side_effect = list(channel_current_values)
    return fixture


# ---------------------------------------------------------------------------
# assert_powered
# ---------------------------------------------------------------------------

class TestAssertPowered:
    """Tests for assert_powered()."""

    @patch("corekinect.test.assertions.time.sleep")
    def test_passes_when_current_above_threshold(self, mock_sleep):
        """Should return average current when max exceeds min_current_ma."""
        fixture = _make_fixture(total_current_values=[20.0, 25.0, 30.0])
        avg = assert_powered(fixture, min_current_ma=5.0, samples=3, interval_s=0.0)

        assert avg == pytest.approx(25.0)

    @patch("corekinect.test.assertions.time.sleep")
    def test_fails_when_current_below_threshold(self, mock_sleep):
        """Should raise AssertionError when max current is below threshold."""
        fixture = _make_fixture(total_current_values=[1.0, 2.0, 3.0])

        with pytest.raises(AssertionError, match="Device not powered"):
            assert_powered(fixture, min_current_ma=5.0, samples=3, interval_s=0.0)

    @patch("corekinect.test.assertions.time.sleep")
    def test_passes_when_single_sample_exceeds_threshold(self, mock_sleep):
        """Only the max needs to exceed threshold, not all samples."""
        fixture = _make_fixture(total_current_values=[0.1, 0.2, 10.0])
        avg = assert_powered(fixture, min_current_ma=5.0, samples=3, interval_s=0.0)

        assert avg == pytest.approx((0.1 + 0.2 + 10.0) / 3)

    @patch("corekinect.test.assertions.time.sleep")
    def test_uses_read_current_when_channel_specified(self, mock_sleep):
        """When channel is provided, should call read_current(channel=N)."""
        fixture = _make_fixture(channel_current_values=[15.0, 20.0])
        avg = assert_powered(
            fixture, min_current_ma=5.0, samples=2, interval_s=0.0, channel=1
        )

        fixture.read_current.assert_called_with(channel=1)
        assert fixture.read_total_current.call_count == 0
        assert avg == pytest.approx(17.5)

    @patch("corekinect.test.assertions.time.sleep")
    def test_uses_read_total_current_when_no_channel(self, mock_sleep):
        """When channel is None, should call read_total_current()."""
        fixture = _make_fixture(total_current_values=[10.0])
        assert_powered(fixture, min_current_ma=5.0, samples=1, interval_s=0.0)

        fixture.read_total_current.assert_called_once()
        assert fixture.read_current.call_count == 0

    @patch("corekinect.test.assertions.time.sleep")
    def test_takes_correct_number_of_samples(self, mock_sleep):
        """Should call the current read function exactly `samples` times."""
        values = [10.0] * 5
        fixture = _make_fixture(total_current_values=values)
        assert_powered(fixture, min_current_ma=5.0, samples=5, interval_s=0.0)

        assert fixture.read_total_current.call_count == 5

    @patch("corekinect.test.assertions.time.sleep")
    def test_sleeps_between_samples(self, mock_sleep):
        """Should sleep with the specified interval between samples."""
        fixture = _make_fixture(total_current_values=[10.0, 10.0, 10.0])
        assert_powered(fixture, min_current_ma=5.0, samples=3, interval_s=0.5)

        assert mock_sleep.call_count == 3
        for call in mock_sleep.call_args_list:
            assert call[0][0] == 0.5

    @patch("corekinect.test.assertions.time.sleep")
    def test_exact_threshold_passes(self, mock_sleep):
        """Max current exactly equal to threshold should pass (>=)."""
        fixture = _make_fixture(total_current_values=[5.0])
        avg = assert_powered(fixture, min_current_ma=5.0, samples=1, interval_s=0.0)

        assert avg == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# assert_current_in_range
# ---------------------------------------------------------------------------

class TestAssertCurrentInRange:
    """Tests for assert_current_in_range()."""

    def test_in_range_passes(self):
        """Current within range should not raise."""
        assert_current_in_range(15.0, min_ma=10.0, max_ma=20.0)

    def test_below_range_fails(self):
        """Current below min should raise AssertionError."""
        with pytest.raises(AssertionError, match="outside range"):
            assert_current_in_range(5.0, min_ma=10.0, max_ma=20.0)

    def test_above_range_fails(self):
        """Current above max should raise AssertionError."""
        with pytest.raises(AssertionError, match="outside range"):
            assert_current_in_range(25.0, min_ma=10.0, max_ma=20.0)

    def test_exact_min_boundary_passes(self):
        """Current exactly at min boundary should pass (<=)."""
        assert_current_in_range(10.0, min_ma=10.0, max_ma=20.0)

    def test_exact_max_boundary_passes(self):
        """Current exactly at max boundary should pass (<=)."""
        assert_current_in_range(20.0, min_ma=10.0, max_ma=20.0)

    def test_error_message_includes_name(self):
        """Error message should include the name parameter."""
        with pytest.raises(AssertionError, match="sleep current"):
            assert_current_in_range(1.0, min_ma=10.0, max_ma=20.0, name="sleep")

    def test_error_message_includes_value(self):
        """Error message should include the measured current value."""
        with pytest.raises(AssertionError, match="5.000mA"):
            assert_current_in_range(5.0, min_ma=10.0, max_ma=20.0)


# ---------------------------------------------------------------------------
# assert_cloud_message
# ---------------------------------------------------------------------------

class TestAssertCloudMessage:
    """Tests for assert_cloud_message()."""

    def test_none_message_fails(self):
        """None message should raise AssertionError."""
        with pytest.raises(AssertionError, match="got None"):
            assert_cloud_message(None, "heartbeat")

    def test_valid_message_no_fields_passes(self):
        """Non-None message with no required fields should pass."""
        msg = {"type": "heartbeat", "value": 42}
        result = assert_cloud_message(msg, "heartbeat")
        assert result is msg

    def test_missing_field_fails(self):
        """Message missing a required field should raise AssertionError."""
        msg = {"type": "heartbeat"}

        with pytest.raises(AssertionError, match="missing required field 'value'"):
            assert_cloud_message(msg, "heartbeat", {"value": 42})

    def test_wrong_value_fails(self):
        """Message with wrong field value should raise AssertionError."""
        msg = {"type": "heartbeat", "value": 99}

        with pytest.raises(AssertionError, match="expected 42"):
            assert_cloud_message(msg, "heartbeat", {"value": 42})

    def test_correct_value_passes(self):
        """Message with correct field value should pass."""
        msg = {"type": "heartbeat", "value": 42}
        result = assert_cloud_message(msg, "heartbeat", {"value": 42})
        assert result is msg

    def test_none_expected_checks_existence_only(self):
        """When expected value is None, only check that the field exists."""
        msg = {"type": "heartbeat", "value": "anything"}
        result = assert_cloud_message(msg, "heartbeat", {"value": None})
        assert result is msg

    def test_none_expected_still_fails_on_missing(self):
        """None expected should still fail if the field is missing."""
        msg = {"type": "heartbeat"}

        with pytest.raises(AssertionError, match="missing required field"):
            assert_cloud_message(msg, "heartbeat", {"value": None})

    def test_callable_validator_passes(self):
        """Callable expected value should call the function with actual value."""
        msg = {"type": "heartbeat", "value": 42}
        result = assert_cloud_message(
            msg, "heartbeat", {"value": lambda v: v > 10}
        )
        assert result is msg

    def test_callable_validator_fails(self):
        """Callable returning False should raise AssertionError."""
        msg = {"type": "heartbeat", "value": 5}

        with pytest.raises(AssertionError, match="failed validation"):
            assert_cloud_message(
                msg, "heartbeat", {"value": lambda v: v > 10}
            )

    def test_multiple_required_fields(self):
        """All required fields should be checked."""
        msg = {"a": 1, "b": 2, "c": 3}
        result = assert_cloud_message(msg, "multi", {"a": 1, "b": 2, "c": 3})
        assert result is msg

    def test_multiple_fields_one_wrong(self):
        """Should fail on the first field that doesn't match."""
        msg = {"a": 1, "b": 99}

        with pytest.raises(AssertionError):
            assert_cloud_message(msg, "multi", {"a": 1, "b": 2})

    def test_returns_message_for_chaining(self):
        """Should return the message dict for chaining assertions."""
        msg = {"x": 1}
        result = assert_cloud_message(msg, "test")
        assert result == {"x": 1}


# ---------------------------------------------------------------------------
# assert_flash_success
# ---------------------------------------------------------------------------

class TestAssertFlashSuccess:
    """Tests for assert_flash_success()."""

    def test_success_returns_time_ms(self):
        """Successful flash should return time_ms."""
        result = assert_flash_success((1500, None), "nRF52840")
        assert result == 1500

    def test_error_raises(self):
        """Flash error should raise AssertionError with target name."""
        with pytest.raises(AssertionError, match="nRF52840 flash failed"):
            assert_flash_success((None, "Write failed"), "nRF52840")

    def test_error_includes_error_message(self):
        """AssertionError should include the error string."""
        with pytest.raises(AssertionError, match="Write failed"):
            assert_flash_success((None, "Write failed"), "nRF52840")

    def test_none_time_with_no_error_returns_zero(self):
        """If time_ms is None but no error, should return 0."""
        result = assert_flash_success((None, None), "nRF52840")
        assert result == 0

    def test_zero_time_with_no_error_returns_zero(self):
        """If time_ms is 0 and no error, should return 0."""
        result = assert_flash_success((0, None), "nRF52840")
        assert result == 0

    def test_error_string_is_truthy(self):
        """Any truthy error string should cause failure."""
        with pytest.raises(AssertionError):
            assert_flash_success((500, "Verify mismatch"), "nRF9151")

    def test_empty_error_string_passes(self):
        """Empty error string (falsy) should pass."""
        result = assert_flash_success((200, ""), "nRF52840")
        assert result == 200


# ---------------------------------------------------------------------------
# assert_fuota_progress
# ---------------------------------------------------------------------------

class TestAssertFuotaProgress:
    """Tests for assert_fuota_progress()."""

    def test_none_progress_fails(self):
        """None progress should raise AssertionError."""
        with pytest.raises(AssertionError, match="FUOTA progress is None"):
            assert_fuota_progress(None)

    def test_valid_progress_passes(self):
        """Non-None progress without expected_complete should pass."""
        progress = {"percentage": 50, "isComplete": False}
        result = assert_fuota_progress(progress)
        assert result is progress

    def test_expected_complete_true_passes(self):
        """When expected_complete=True and isComplete=True, should pass."""
        progress = {"percentage": 100, "isComplete": True}
        result = assert_fuota_progress(progress, expected_complete=True)
        assert result is progress

    def test_expected_complete_true_but_not_complete_fails(self):
        """When expected_complete=True but isComplete=False, should fail."""
        progress = {"percentage": 80, "isComplete": False}

        with pytest.raises(AssertionError, match="FUOTA not complete"):
            assert_fuota_progress(progress, expected_complete=True)

    def test_expected_complete_false_does_not_check(self):
        """When expected_complete=False (default), isComplete is not checked."""
        progress = {"percentage": 50, "isComplete": False}
        result = assert_fuota_progress(progress, expected_complete=False)
        assert result is progress

    def test_expected_complete_missing_key_fails(self):
        """When expected_complete=True but isComplete key is missing, should fail."""
        progress = {"percentage": 100}

        with pytest.raises(AssertionError, match="FUOTA not complete"):
            assert_fuota_progress(progress, expected_complete=True)

    def test_returns_progress_dict(self):
        """Should return the progress dict for chaining."""
        progress = {"percentage": 75, "isComplete": False}
        result = assert_fuota_progress(progress)
        assert result == progress

    def test_none_progress_with_expected_complete_fails(self):
        """None progress should fail even when expected_complete is True."""
        with pytest.raises(AssertionError, match="FUOTA progress is None"):
            assert_fuota_progress(None, expected_complete=True)
