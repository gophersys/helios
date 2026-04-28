"""Tests for stage definitions.

Stages split into two StageTypes: VALIDATION (5 stages numbered 1..5)
and MANUFACTURING (1 stage numbered 1). Stage numbers are unique
within their type, not globally.
"""

import pytest

from corekinect.stages import (
    STAGE_NAMES,
    STAGE_NUMBERS,
    STAGE_TYPES,
    Stage,
    StageType,
)


VALIDATION_STAGES = (
    Stage.SMOKE,
    Stage.DRIVER,
    Stage.INTEGRATION,
    Stage.REGRESSION,
    Stage.FUOTA,
)


class TestStageEnum:
    """Tests for the Stage enum."""

    def test_validation_stages_exist(self):
        """All five validation stages should be present."""
        for stage in VALIDATION_STAGES:
            assert stage in Stage

    def test_manufacturing_stage_exists(self):
        """The single manufacturing stage should be present."""
        assert Stage.MANUFACTURING in Stage

    def test_stage_values(self):
        """Each stage should have the correct string value."""
        assert Stage.SMOKE.value == "smoke"
        assert Stage.DRIVER.value == "driver"
        assert Stage.INTEGRATION.value == "integration"
        assert Stage.REGRESSION.value == "regression"
        assert Stage.FUOTA.value == "fuota"
        assert Stage.MANUFACTURING.value == "manufacturing"

    def test_stage_values_are_strings(self):
        """Stage values should be strings (Stage inherits from str)."""
        for stage in Stage:
            assert isinstance(stage.value, str)

    def test_stage_is_str_subclass(self):
        """Stage members should be usable as strings (str enum)."""
        assert isinstance(Stage.SMOKE, str)
        assert isinstance(Stage.FUOTA, str)
        assert isinstance(Stage.MANUFACTURING, str)

    def test_stage_string_comparison(self):
        """Stage members should compare equal to their string values."""
        assert Stage.SMOKE == "smoke"
        assert Stage.DRIVER == "driver"
        assert Stage.INTEGRATION == "integration"
        assert Stage.REGRESSION == "regression"
        assert Stage.FUOTA == "fuota"
        assert Stage.MANUFACTURING == "manufacturing"

    def test_stage_from_string(self):
        """Can construct Stage from string value."""
        assert Stage("smoke") is Stage.SMOKE
        assert Stage("fuota") is Stage.FUOTA
        assert Stage("manufacturing") is Stage.MANUFACTURING

    def test_stage_from_invalid_string_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            Stage("nonexistent")


class TestStageTypes:
    """Each Stage maps to exactly one StageType."""

    def test_every_stage_has_a_type(self):
        for stage in Stage:
            assert stage in STAGE_TYPES, (
                f"Stage {stage.value} missing from STAGE_TYPES"
            )

    def test_validation_stages_are_validation_type(self):
        for stage in VALIDATION_STAGES:
            assert STAGE_TYPES[stage] == StageType.VALIDATION

    def test_manufacturing_stage_is_manufacturing_type(self):
        assert STAGE_TYPES[Stage.MANUFACTURING] == StageType.MANUFACTURING


class TestStageNumbers:
    """Stage numbers are unique within a StageType, not globally."""

    def test_stage_numbers_maps_all_stages(self):
        for stage in Stage:
            assert stage in STAGE_NUMBERS, (
                f"Stage {stage.value} missing from STAGE_NUMBERS"
            )

    def test_validation_stage_numbers(self):
        assert STAGE_NUMBERS[Stage.SMOKE] == 1
        assert STAGE_NUMBERS[Stage.DRIVER] == 2
        assert STAGE_NUMBERS[Stage.INTEGRATION] == 3
        assert STAGE_NUMBERS[Stage.REGRESSION] == 4
        assert STAGE_NUMBERS[Stage.FUOTA] == 5

    def test_manufacturing_stage_number(self):
        assert STAGE_NUMBERS[Stage.MANUFACTURING] == 1

    def test_validation_numbers_contiguous_1_to_5(self):
        validation_numbers = sorted(
            STAGE_NUMBERS[s] for s in VALIDATION_STAGES
        )
        assert validation_numbers == [1, 2, 3, 4, 5]

    def test_no_duplicate_numbers_within_a_type(self):
        for stage_type in StageType:
            numbers = [
                STAGE_NUMBERS[s]
                for s, t in STAGE_TYPES.items()
                if t == stage_type
            ]
            assert len(numbers) == len(set(numbers)), (
                f"{stage_type.value}: duplicate stage numbers {numbers}"
            )


class TestStageNames:
    """STAGE_NAMES covers the validation stages (UI display labels)."""

    def test_stage_names_correct_values(self):
        assert STAGE_NAMES[1] == "Smoke"
        assert STAGE_NAMES[2] == "Driver"
        assert STAGE_NAMES[3] == "Integration"
        assert STAGE_NAMES[4] == "Regression"
        assert STAGE_NAMES[5] == "FUOTA"

    def test_stage_names_covers_all_validation_stages(self):
        for stage in VALIDATION_STAGES:
            number = STAGE_NUMBERS[stage]
            assert number in STAGE_NAMES, (
                f"Validation stage number {number} ({stage.value}) "
                f"missing from STAGE_NAMES"
            )

    def test_no_duplicate_names(self):
        names = list(STAGE_NAMES.values())
        assert len(names) == len(set(names)), "Duplicate stage names found"

    def test_all_names_are_strings(self):
        for name in STAGE_NAMES.values():
            assert isinstance(name, str)
