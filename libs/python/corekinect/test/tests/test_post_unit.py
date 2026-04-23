"""Unit tests for POST (Power-On Self-Test) — data structures and helpers.

Tests PostResult, PostStepResult dataclasses, the _step() helper,
and summary formatting without requiring hardware or MTIB connections.
"""

from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.post import PostResult, PostStepResult, _step


# ---------------------------------------------------------------------------
# PostStepResult dataclass
# ---------------------------------------------------------------------------

class TestPostStepResult:
    """Tests for the PostStepResult dataclass."""

    def test_basic_construction(self):
        """All fields set correctly."""
        step = PostStepResult(name="GPS module", passed=True, message="comms_ok=True")
        assert step.name == "GPS module"
        assert step.passed is True
        assert step.message == "comms_ok=True"
        assert step.duration_ms == 0  # default

    def test_with_duration(self):
        """Duration is stored correctly."""
        step = PostStepResult(name="BMS", passed=False, message="timeout", duration_ms=1234)
        assert step.duration_ms == 1234

    def test_passed_false(self):
        """Failed step stores passed=False."""
        step = PostStepResult(name="Charger", passed=False, message="chip_id mismatch")
        assert step.passed is False


# ---------------------------------------------------------------------------
# PostResult dataclass
# ---------------------------------------------------------------------------

class TestPostResult:
    """Tests for the PostResult aggregate result."""

    def test_default_construction(self):
        """Default PostResult has sensible empty/zero defaults."""
        result = PostResult()
        assert result.passed is False
        assert result.steps == []
        assert result.imei is None
        assert result.iccids == []
        assert result.modem_fw_version is None
        assert result.comms_ext_flash_id is None
        assert result.app_ext_flash_id is None
        assert result.app_ble_mac is None

    def test_passed_can_be_set(self):
        """The passed field can be set to True."""
        result = PostResult(passed=True)
        assert result.passed is True

    def test_data_fields_stored(self):
        """Collected device data fields are stored correctly."""
        result = PostResult(
            imei="355025931735979",
            iccids=["89148000009808558441", "89457300000037582833"],
            modem_fw_version="1.3.6",
            comms_ext_flash_id="0xef 0x40 0x17",
            app_ext_flash_id="0xef 0x40 0x18",
            app_ble_mac="AA:BB:CC:DD:EE:FF",
        )
        assert result.imei == "355025931735979"
        assert len(result.iccids) == 2
        assert result.modem_fw_version == "1.3.6"
        assert result.comms_ext_flash_id == "0xef 0x40 0x17"
        assert result.app_ext_flash_id == "0xef 0x40 0x18"
        assert result.app_ble_mac == "AA:BB:CC:DD:EE:FF"

    def test_steps_list_independence(self):
        """Each PostResult instance has its own steps list."""
        r1 = PostResult()
        r2 = PostResult()
        r1.steps.append(PostStepResult("a", True, "ok"))
        assert len(r2.steps) == 0

    def test_iccids_list_independence(self):
        """Each PostResult instance has its own iccids list."""
        r1 = PostResult()
        r2 = PostResult()
        r1.iccids.append("12345")
        assert len(r2.iccids) == 0


# ---------------------------------------------------------------------------
# PostResult.summary()
# ---------------------------------------------------------------------------

class TestPostResultSummary:
    """Tests for the summary() formatting method."""

    def test_summary_all_pass(self):
        """Summary shows PASS for passing steps and correct count."""
        result = PostResult(passed=True)
        result.steps = [
            PostStepResult("Boot", True, "Both shells locked", 500),
            PostStepResult("GPS", True, "comms_ok=True", 200),
            PostStepResult("BMS", True, "connected=True", 100),
        ]
        summary = result.summary()
        assert "[PASS] Boot" in summary
        assert "[PASS] GPS" in summary
        assert "[PASS] BMS" in summary
        assert "3/3 steps passed" in summary

    def test_summary_with_failure(self):
        """Summary shows FAIL for failing steps and correct count."""
        result = PostResult(passed=False)
        result.steps = [
            PostStepResult("Boot", True, "ok", 500),
            PostStepResult("GPS", False, "GPS is in shutdown", 200),
            PostStepResult("BMS", True, "connected=True", 100),
        ]
        summary = result.summary()
        assert "[PASS] Boot" in summary
        assert "[FAIL] GPS" in summary
        assert "2/3 steps passed" in summary

    def test_summary_empty_steps(self):
        """Summary with no steps shows 0/0."""
        result = PostResult()
        summary = result.summary()
        assert "0/0 steps passed" in summary

    def test_summary_includes_duration(self):
        """Summary includes duration in milliseconds."""
        result = PostResult()
        result.steps = [
            PostStepResult("Modem firmware", True, "version=1.3.6", 1234),
        ]
        summary = result.summary()
        assert "1234ms" in summary

    def test_summary_includes_message(self):
        """Summary includes the step message."""
        result = PostResult()
        result.steps = [
            PostStepResult("IMEI + ICCIDs", True, "IMEI=355025931735979", 300),
        ]
        summary = result.summary()
        assert "IMEI=355025931735979" in summary

    def test_summary_all_fail(self):
        """Summary shows 0/N when all steps fail."""
        result = PostResult(passed=False)
        result.steps = [
            PostStepResult("Boot", False, "timeout", 5000),
            PostStepResult("GPS", False, "error", 0),
        ]
        summary = result.summary()
        assert "0/2 steps passed" in summary


# ---------------------------------------------------------------------------
# _step() helper
# ---------------------------------------------------------------------------

class TestStepHelper:
    """Tests for the _step() recording function."""

    def test_appends_step_to_result(self):
        """_step() appends a PostStepResult to result.steps."""
        result = PostResult()
        _step(result, "Boot", True, "Shells locked", duration_ms=500)
        assert len(result.steps) == 1
        assert result.steps[0].name == "Boot"
        assert result.steps[0].passed is True
        assert result.steps[0].message == "Shells locked"
        assert result.steps[0].duration_ms == 500

    def test_returns_passed_value(self):
        """_step() returns the passed boolean."""
        result = PostResult()
        assert _step(result, "GPS", True, "ok") is True
        assert _step(result, "BMS", False, "fail") is False

    def test_multiple_steps_accumulate(self):
        """Multiple _step() calls build up the steps list in order."""
        result = PostResult()
        _step(result, "Step 1", True, "ok")
        _step(result, "Step 2", False, "fail")
        _step(result, "Step 3", True, "ok")

        assert len(result.steps) == 3
        assert result.steps[0].name == "Step 1"
        assert result.steps[1].name == "Step 2"
        assert result.steps[2].name == "Step 3"

    def test_step_with_zero_duration(self):
        """Default duration_ms is 0."""
        result = PostResult()
        _step(result, "Skipped test", True, "Skipped")
        assert result.steps[0].duration_ms == 0

    def test_step_does_not_set_result_passed(self):
        """_step() does not modify result.passed — that's set after all steps."""
        result = PostResult()
        _step(result, "Boot", True, "ok")
        assert result.passed is False  # still default

    def test_failed_step_recorded_correctly(self):
        """A failing step is recorded with passed=False and descriptive message."""
        result = PostResult()
        _step(result, "Charger (BQ25180)", False, "Error: I2C timeout", duration_ms=3000)

        step = result.steps[0]
        assert step.passed is False
        assert step.name == "Charger (BQ25180)"
        assert "I2C timeout" in step.message
        assert step.duration_ms == 3000


# ---------------------------------------------------------------------------
# PostResult.passed computation (integration of _step + all())
# ---------------------------------------------------------------------------

class TestPassedComputation:
    """Tests for the all-steps-passed computation pattern used in run_post."""

    def test_all_pass_yields_true(self):
        """When all steps pass, computing all() over steps gives True."""
        result = PostResult()
        _step(result, "A", True, "ok")
        _step(result, "B", True, "ok")
        _step(result, "C", True, "ok")

        result.passed = all(s.passed for s in result.steps)
        assert result.passed is True

    def test_one_failure_yields_false(self):
        """When any step fails, all() gives False."""
        result = PostResult()
        _step(result, "A", True, "ok")
        _step(result, "B", False, "fail")
        _step(result, "C", True, "ok")

        result.passed = all(s.passed for s in result.steps)
        assert result.passed is False

    def test_empty_steps_all_is_true(self):
        """Edge case: all() on empty list is True (vacuous truth)."""
        result = PostResult()
        result.passed = all(s.passed for s in result.steps)
        assert result.passed is True
