"""Tests for base timing utilities.

Tests CommonTiming defaults, the COMMON singleton, the timeout decorator,
wait_with_progress behavior, and frozen dataclass immutability.
"""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.timing import CommonTiming, COMMON, timeout, wait_with_progress


# ---------------------------------------------------------------------------
# CommonTiming
# ---------------------------------------------------------------------------

class TestCommonTimingDefaults:
    """Tests for CommonTiming default field values."""

    def test_power_cycle_off(self):
        t = CommonTiming()
        assert t.POWER_CYCLE_OFF == 2.0

    def test_power_cycle_on(self):
        t = CommonTiming()
        assert t.POWER_CYCLE_ON == 10.0

    def test_uart_settle(self):
        t = CommonTiming()
        assert t.UART_SETTLE == 0.5

    def test_mtib_connect(self):
        t = CommonTiming()
        assert t.MTIB_CONNECT == 10

    def test_field_types(self):
        """Timing fields should have the expected numeric types."""
        t = CommonTiming()
        assert isinstance(t.POWER_CYCLE_OFF, float)
        assert isinstance(t.POWER_CYCLE_ON, float)
        assert isinstance(t.UART_SETTLE, float)
        assert isinstance(t.MTIB_CONNECT, int)


class TestCommonTimingFrozen:
    """Tests that CommonTiming is a frozen (immutable) dataclass."""

    def test_cannot_modify_power_cycle_off(self):
        t = CommonTiming()
        with pytest.raises(FrozenInstanceError):
            t.POWER_CYCLE_OFF = 99.0

    def test_cannot_modify_power_cycle_on(self):
        t = CommonTiming()
        with pytest.raises(FrozenInstanceError):
            t.POWER_CYCLE_ON = 99.0

    def test_cannot_modify_uart_settle(self):
        t = CommonTiming()
        with pytest.raises(FrozenInstanceError):
            t.UART_SETTLE = 99.0

    def test_cannot_modify_mtib_connect(self):
        t = CommonTiming()
        with pytest.raises(FrozenInstanceError):
            t.MTIB_CONNECT = 99

    def test_cannot_add_new_attribute(self):
        t = CommonTiming()
        with pytest.raises(FrozenInstanceError):
            t.NEW_FIELD = 42


# ---------------------------------------------------------------------------
# COMMON singleton
# ---------------------------------------------------------------------------

class TestCommonSingleton:
    """Tests for the COMMON module-level instance."""

    def test_common_is_common_timing_instance(self):
        assert isinstance(COMMON, CommonTiming)

    def test_common_matches_default_values(self):
        """COMMON should have the same values as a fresh CommonTiming()."""
        fresh = CommonTiming()
        assert COMMON.POWER_CYCLE_OFF == fresh.POWER_CYCLE_OFF
        assert COMMON.POWER_CYCLE_ON == fresh.POWER_CYCLE_ON
        assert COMMON.UART_SETTLE == fresh.UART_SETTLE
        assert COMMON.MTIB_CONNECT == fresh.MTIB_CONNECT

    def test_common_equals_default(self):
        """COMMON should be equal to a new CommonTiming() via dataclass __eq__."""
        assert COMMON == CommonTiming()


# ---------------------------------------------------------------------------
# timeout decorator
# ---------------------------------------------------------------------------

class TestTimeoutDecorator:
    """Tests for the timeout() decorator."""

    def test_applies_pytest_timeout_marker(self):
        """Decorated function should have pytest.mark.timeout applied."""

        @timeout(300)
        def test_example():
            pass

        markers = list(test_example.pytestmark)
        timeout_markers = [m for m in markers if m.name == "timeout"]
        assert len(timeout_markers) == 1
        assert timeout_markers[0].args == (300,)

    def test_different_timeout_values(self):
        """Different timeout values should be reflected in the marker."""

        @timeout(60)
        def test_quick():
            pass

        @timeout(900)
        def test_slow():
            pass

        quick_markers = [m for m in test_quick.pytestmark if m.name == "timeout"]
        slow_markers = [m for m in test_slow.pytestmark if m.name == "timeout"]

        assert quick_markers[0].args == (60,)
        assert slow_markers[0].args == (900,)

    def test_decorated_function_is_still_callable(self):
        """The decorated function should still be callable."""

        @timeout(10)
        def test_callable():
            return 42

        assert test_callable() == 42

    def test_preserves_function_name(self):
        """Decorated function should retain its original __name__
        (pytest.mark does not change the function name)."""

        @timeout(10)
        def test_my_func():
            pass

        assert test_my_func.__name__ == "test_my_func"


# ---------------------------------------------------------------------------
# wait_with_progress
# ---------------------------------------------------------------------------

class TestWaitWithProgress:
    """Tests for wait_with_progress()."""

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_completes_after_duration(self, mock_time, mock_sleep):
        """Should complete after the specified duration."""
        # Simulate time advancing: start=0, then after each sleep
        mock_time.side_effect = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0]
        logger = MagicMock()

        wait_with_progress(20.0, message="Test", interval_s=5.0, logger=logger)

        # Should have logged progress messages
        assert logger.info.call_count >= 2

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_logs_progress_messages(self, mock_time, mock_sleep):
        """Should log messages including elapsed/remaining time."""
        mock_time.side_effect = [0.0, 10.0, 20.0, 30.0]
        logger = MagicMock()

        wait_with_progress(20.0, message="Waiting", interval_s=10.0, logger=logger)

        # Logger uses %-style formatting: info(format_str, message, ...)
        # The message is the second positional arg (index [0][1])
        first_call_args = logger.info.call_args_list[0]
        assert first_call_args[0][1] == "Waiting"

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_logs_completion_message(self, mock_time, mock_sleep):
        """Should log a completion message at the end."""
        mock_time.side_effect = [0.0, 10.0, 20.0]
        logger = MagicMock()

        wait_with_progress(10.0, message="Done", interval_s=10.0, logger=logger)

        last_call_args = logger.info.call_args_list[-1]
        assert "complete" in last_call_args[0][0]

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_sleeps_min_of_interval_and_remaining(self, mock_time, mock_sleep):
        """sleep() should be called with min(interval_s, remaining)."""
        # Duration=15, interval=10: first sleep=10, second sleep=5 (remaining)
        mock_time.side_effect = [0.0, 10.0, 15.0]
        logger = MagicMock()

        wait_with_progress(15.0, interval_s=10.0, logger=logger)

        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == 10.0
        assert sleep_calls[1] == 5.0

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_uses_module_logger_when_no_logger_given(self, mock_time, mock_sleep):
        """When logger is None, should use the module-level _log."""
        # The Logger (via stdlib logging) also calls time.time() internally
        # for log record timestamps, so we need a generous side_effect list.
        mock_time.side_effect = [0.0] + [2.0] * 20

        # Should not raise; exercises the default logger path
        wait_with_progress(1.0, interval_s=1.0)

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_zero_duration_completes_immediately(self, mock_time, mock_sleep):
        """Duration of 0 should complete immediately (no sleep calls in loop)."""
        mock_time.side_effect = [0.0]
        logger = MagicMock()

        wait_with_progress(0.0, logger=logger)

        # The while loop condition (elapsed < duration_s) is False immediately
        mock_sleep.assert_not_called()

    @patch("corekinect.test.timing.time.sleep")
    @patch("corekinect.test.timing.time.time")
    def test_custom_message_appears_in_logs(self, mock_time, mock_sleep):
        """Custom message should appear in progress log entries."""
        mock_time.side_effect = [0.0, 5.0]
        logger = MagicMock()

        wait_with_progress(1.0, message="Rebooting", interval_s=1.0, logger=logger)

        all_messages = [call[0][1] for call in logger.info.call_args_list]
        assert any("Rebooting" in str(m) for m in all_messages)
