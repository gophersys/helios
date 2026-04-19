"""Tests for ``corectl.commands.test_contracts``.

Each test constructs a minimal Python source representing one
scenario the validator must recognise and asserts on the resulting
``ContractViolation`` list. Source is written to a real file under
``tmp_path`` so the validator's ``Path``-based error reporting is
exercised end-to-end.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List

import pytest

from corectl.commands.test_contracts import (
    ContractViolation,
    validate_project,
    validate_test_file,
)


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip("\n"))
    return path


def _codes(violations: List[ContractViolation]) -> List[str]:
    return [v.code for v in violations]


# ────────────────────────────────────────────────────────────────────────
# Timeout-marker contract
# ────────────────────────────────────────────────────────────────────────


def test_test_with_timeout_decorator_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "ok.py", """
        import pytest

        @pytest.mark.timeout(30)
        def test_noop():
            assert True
    """)
    assert _codes(validate_test_file(path)) == []


def test_test_missing_timeout_raises_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.py", """
        def test_noop():
            assert True
    """)
    violations = validate_test_file(path)
    assert len(violations) == 1
    v = violations[0]
    assert v.code == "missing-timeout"
    assert v.severity == "error"
    assert "test_noop" in v.message
    assert v.line == 1  # at the def line


def test_multiple_tests_each_missing_timeout(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.py", """
        def test_one():
            pass

        def test_two():
            pass
    """)
    violations = validate_test_file(path)
    assert _codes(violations) == ["missing-timeout", "missing-timeout"]
    assert {v.line for v in violations} == {1, 4}


def test_non_test_function_doesnt_need_timeout(tmp_path: Path) -> None:
    path = _write(tmp_path, "helpers.py", """
        def _helper():
            pass

        def regular_function():
            pass
    """)
    assert _codes(validate_test_file(path)) == []


def test_timeout_accepts_float_and_kwarg(tmp_path: Path) -> None:
    path = _write(tmp_path, "ok.py", """
        import pytest

        @pytest.mark.timeout(30.5)
        def test_float():
            pass

        @pytest.mark.timeout(timeout=15)
        def test_kwarg():
            pass
    """)
    assert _codes(validate_test_file(path)) == []


def test_timeout_with_reference_is_accepted(tmp_path: Path) -> None:
    # We can't resolve module-level constants statically, so ``@pytest.mark.timeout(BUDGET)``
    # should pass without a violation.
    path = _write(tmp_path, "ok.py", """
        import pytest

        BUDGET = 30

        @pytest.mark.timeout(BUDGET)
        def test_const_ref():
            pass
    """)
    assert _codes(validate_test_file(path)) == []


def test_suspect_low_timeout_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "warn.py", """
        import pytest

        @pytest.mark.timeout(0.5)
        def test_too_short():
            pass
    """)
    violations = validate_test_file(path)
    assert len(violations) == 1
    assert violations[0].code == "suspect-timeout"
    assert violations[0].severity == "warning"


def test_suspect_high_timeout_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "warn.py", """
        import pytest

        @pytest.mark.timeout(900)
        def test_too_long():
            pass
    """)
    violations = validate_test_file(path)
    assert len(violations) == 1
    assert violations[0].code == "suspect-timeout"
    assert violations[0].severity == "warning"


def test_timeout_at_reasonable_boundary_passes(tmp_path: Path) -> None:
    # Exactly 1 s (lower bound) and 600 s (upper bound) must not trigger.
    path = _write(tmp_path, "ok.py", """
        import pytest

        @pytest.mark.timeout(1)
        def test_at_lower_bound():
            pass

        @pytest.mark.timeout(600)
        def test_at_upper_bound():
            pass
    """)
    assert _codes(validate_test_file(path)) == []


def test_multi_marker_stack_still_requires_timeout(tmp_path: Path) -> None:
    # Other pytest marks don't substitute for timeout.
    path = _write(tmp_path, "bad.py", """
        import pytest

        @pytest.mark.electrical
        @pytest.mark.sequential
        def test_missing_timeout():
            pass
    """)
    violations = validate_test_file(path)
    assert _codes(violations) == ["missing-timeout"]


def test_multi_marker_stack_passes_with_timeout(tmp_path: Path) -> None:
    path = _write(tmp_path, "ok.py", """
        import pytest

        @pytest.mark.electrical
        @pytest.mark.sequential
        @pytest.mark.timeout(30)
        def test_with_all_markers():
            pass
    """)
    assert _codes(validate_test_file(path)) == []


# ────────────────────────────────────────────────────────────────────────
# Empty-step contract
# ────────────────────────────────────────────────────────────────────────


def test_step_block_with_record_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "ok.py", """
        import pytest

        @pytest.mark.timeout(30)
        def test_records():
            with report.step("do thing") as step:
                step.record("value", 42, unit="ms")
    """)
    assert _codes(validate_test_file(path)) == []


def test_empty_step_block_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "warn.py", """
        import pytest

        @pytest.mark.timeout(30)
        def test_no_records():
            with report.step("empty"):
                x = 1
    """)
    violations = validate_test_file(path)
    assert len(violations) == 1
    v = violations[0]
    assert v.code == "empty-step"
    assert v.severity == "warning"


def test_step_block_with_nested_call_to_record_still_counts(tmp_path: Path) -> None:
    # ``result = step.record(...)`` is assignment-wrapped; still must count.
    path = _write(tmp_path, "ok.py", """
        import pytest

        @pytest.mark.timeout(30)
        def test_assigned_record():
            with report.step("thing") as s:
                result = s.record("key", 1)
    """)
    assert _codes(validate_test_file(path)) == []


def test_multiple_step_blocks_each_checked(tmp_path: Path) -> None:
    path = _write(tmp_path, "mixed.py", """
        import pytest

        @pytest.mark.timeout(30)
        def test_mixed():
            with report.step("first") as s:
                s.record("a", 1)
            with report.step("second"):
                pass
    """)
    violations = validate_test_file(path)
    assert _codes(violations) == ["empty-step"]
    # Second `with` is the 7th line of the dedented source (after the
    # import, blank line, decorator, def, first with, record, then second with).
    assert violations[0].line == 7


# ────────────────────────────────────────────────────────────────────────
# Project-level walk
# ────────────────────────────────────────────────────────────────────────


def test_validate_project_walks_tests_dir(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    _write(tests, "test_ok.py", """
        import pytest

        @pytest.mark.timeout(30)
        def test_good():
            pass
    """)
    _write(tests, "test_bad.py", """
        def test_missing():
            pass
    """)
    violations = validate_project(tmp_path)
    assert _codes(violations) == ["missing-timeout"]
    assert violations[0].file.name == "test_bad.py"


def test_validate_project_falls_back_to_root_when_no_tests_dir(tmp_path: Path) -> None:
    _write(tmp_path, "test_thing.py", """
        def test_missing():
            pass
    """)
    violations = validate_project(tmp_path)
    assert _codes(violations) == ["missing-timeout"]


def test_validate_project_ignores_non_test_modules_but_scans_them(tmp_path: Path) -> None:
    # A helper module with no test_ functions should produce no violations
    # even if it contains `with report.step(...)` — those aren't inside a
    # test and empty-step warnings still apply to any step block. The
    # contract is: empty step blocks are always flagged.
    tests = tmp_path / "tests"
    tests.mkdir()
    _write(tests, "conftest.py", """
        import pytest
        # no test functions here
        def _util():
            return 1
    """)
    assert _codes(validate_project(tmp_path)) == []


# ────────────────────────────────────────────────────────────────────────
# Error-path plumbing
# ────────────────────────────────────────────────────────────────────────


def test_syntax_error_surfaces_as_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, "broken.py", """
        def test_oops(:
            pass
    """)
    violations = validate_test_file(path)
    assert len(violations) == 1
    assert violations[0].code == "syntax-error"
    assert violations[0].severity == "error"
