"""Tests for validation stage definitions.

Tests the Stage enum, STAGE_NUMBERS mapping, and STAGE_NAMES mapping
from corekinect.test.stages.
"""

import pytest

from corekinect.stages import Stage, STAGE_NUMBERS, STAGE_NAMES


class TestStageEnum:
    """Tests for the Stage enum."""

    def test_all_five_stages_exist(self):
        """Stage enum should have exactly 5 members."""
        assert len(Stage) == 5

    def test_stage_values(self):
        """Each stage should have the correct string value."""
        assert Stage.SMOKE.value == "smoke"
        assert Stage.DRIVER.value == "driver"
        assert Stage.INTEGRATION.value == "integration"
        assert Stage.REGRESSION.value == "regression"
        assert Stage.FUOTA.value == "fuota"

    def test_stage_values_are_strings(self):
        """Stage values should be strings (Stage inherits from str)."""
        for stage in Stage:
            assert isinstance(stage.value, str)

    def test_stage_is_str_subclass(self):
        """Stage members should be usable as strings (str enum)."""
        assert isinstance(Stage.SMOKE, str)
        assert isinstance(Stage.FUOTA, str)

    def test_stage_string_comparison(self):
        """Stage members should compare equal to their string values."""
        assert Stage.SMOKE == "smoke"
        assert Stage.DRIVER == "driver"
        assert Stage.INTEGRATION == "integration"
        assert Stage.REGRESSION == "regression"
        assert Stage.FUOTA == "fuota"

    def test_stage_from_string(self):
        """Can construct Stage from string value."""
        assert Stage("smoke") is Stage.SMOKE
        assert Stage("fuota") is Stage.FUOTA

    def test_stage_from_invalid_string_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            Stage("nonexistent")


class TestStageNumbers:
    """Tests for the STAGE_NUMBERS mapping."""

    def test_stage_numbers_maps_all_stages(self):
        """STAGE_NUMBERS should have an entry for every Stage member."""
        for stage in Stage:
            assert stage in STAGE_NUMBERS, (
                f"Stage {stage.value} missing from STAGE_NUMBERS"
            )

    def test_stage_numbers_correct_values(self):
        """Each stage should map to its expected number."""
        assert STAGE_NUMBERS[Stage.SMOKE] == 1
        assert STAGE_NUMBERS[Stage.DRIVER] == 2
        assert STAGE_NUMBERS[Stage.INTEGRATION] == 3
        assert STAGE_NUMBERS[Stage.REGRESSION] == 4
        assert STAGE_NUMBERS[Stage.FUOTA] == 5

    def test_stage_numbers_no_extra_entries(self):
        """STAGE_NUMBERS should have exactly 5 entries (no extras)."""
        assert len(STAGE_NUMBERS) == 5

    def test_no_duplicate_numbers(self):
        """No two stages should share the same number."""
        numbers = list(STAGE_NUMBERS.values())
        assert len(numbers) == len(set(numbers)), "Duplicate stage numbers found"

    def test_no_gaps_in_numbering(self):
        """Stage numbers should be contiguous 1..5 with no gaps."""
        numbers = sorted(STAGE_NUMBERS.values())
        assert numbers == [1, 2, 3, 4, 5]


class TestStageNames:
    """Tests for the STAGE_NAMES mapping."""

    def test_stage_names_correct_values(self):
        """Each number should map to the expected display name."""
        assert STAGE_NAMES[1] == "Smoke"
        assert STAGE_NAMES[2] == "Driver"
        assert STAGE_NAMES[3] == "Integration"
        assert STAGE_NAMES[4] == "Regression"
        assert STAGE_NAMES[5] == "FUOTA"

    def test_stage_names_has_all_five(self):
        """STAGE_NAMES should have exactly 5 entries."""
        assert len(STAGE_NAMES) == 5

    def test_stage_names_and_numbers_are_consistent(self):
        """Every number in STAGE_NUMBERS should have a name in STAGE_NAMES."""
        for stage, number in STAGE_NUMBERS.items():
            assert number in STAGE_NAMES, (
                f"Stage number {number} ({stage.value}) missing from STAGE_NAMES"
            )

    def test_no_duplicate_names(self):
        """No two numbers should share the same display name."""
        names = list(STAGE_NAMES.values())
        assert len(names) == len(set(names)), "Duplicate stage names found"

    def test_all_names_are_strings(self):
        """All display names should be strings."""
        for name in STAGE_NAMES.values():
            assert isinstance(name, str)
