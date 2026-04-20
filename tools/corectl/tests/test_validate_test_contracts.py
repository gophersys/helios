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
            assert True

        def test_two():
            assert True
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
            assert True

        @pytest.mark.timeout(timeout=15)
        def test_kwarg():
            assert True
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
            assert True
    """)
    assert _codes(validate_test_file(path)) == []


def test_suspect_low_timeout_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "warn.py", """
        import pytest

        @pytest.mark.timeout(0.5)
        def test_too_short():
            assert True
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
            assert True
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
            assert True

        @pytest.mark.timeout(600)
        def test_at_upper_bound():
            assert True
    """)
    assert _codes(validate_test_file(path)) == []


def test_multi_marker_stack_still_requires_timeout(tmp_path: Path) -> None:
    # Other pytest marks don't substitute for timeout.
    path = _write(tmp_path, "bad.py", """
        import pytest

        @pytest.mark.electrical
        @pytest.mark.sequential
        def test_missing_timeout():
            assert True
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
            assert True
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
                assert True  # avoid tripping missing-assertion separately
    """)
    violations = validate_test_file(path)
    empty_step = [v for v in violations if v.code == "empty-step"]
    assert len(empty_step) == 1
    v = empty_step[0]
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
            assert True
    """)
    _write(tests, "test_bad.py", """
        def test_missing():
            assert True
    """)
    violations = validate_project(tmp_path)
    assert _codes(violations) == ["missing-timeout"]
    assert violations[0].file.name == "test_bad.py"


def test_validate_project_falls_back_to_root_when_no_tests_dir(tmp_path: Path) -> None:
    _write(tmp_path, "test_thing.py", """
        def test_missing():
            assert True
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


# ════════════════════════════════════════════════════════════════════════
# Phase 5 — additional static checks
# ════════════════════════════════════════════════════════════════════════


# ── missing-assertion: a test that asserts nothing (no assert / record / raise)


def test_missing_assertion_in_test_function_errors(tmp_path: Path) -> None:
    path = _write(tmp_path, "noop.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_does_nothing():
            x = 1 + 1
            y = "hello"
    """)
    codes = _codes(validate_test_file(path))
    assert "missing-assertion" in codes


def test_assert_statement_satisfies_assertion_check(tmp_path: Path) -> None:
    path = _write(tmp_path, "ok_assert.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_with_assert():
            assert 1 + 1 == 2
    """)
    codes = _codes(validate_test_file(path))
    assert "missing-assertion" not in codes


def test_step_record_call_satisfies_assertion_check(tmp_path: Path) -> None:
    """Recording a measurement counts as a checkpoint even without ``assert``.

    The reporter step name + recorded value is itself a verification
    artifact (operators inspect it post-run); a test that records but
    never asserts is still meaningful.
    """
    path = _write(tmp_path, "ok_record.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_records_only(report):
            with report.step("Probe") as step:
                step.record("voltage", 4.5, "V")
    """)
    codes = _codes(validate_test_file(path))
    assert "missing-assertion" not in codes


def test_raise_statement_satisfies_assertion_check(tmp_path: Path) -> None:
    """A test that conditionally raises is still verifying something."""
    path = _write(tmp_path, "ok_raise.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_raises_on_bad_state():
            err = None
            if err:
                raise RuntimeError("bad state")
    """)
    codes = _codes(validate_test_file(path))
    assert "missing-assertion" not in codes


def test_pytest_fail_call_satisfies_assertion_check(tmp_path: Path) -> None:
    """``pytest.fail(...)`` is a deliberate verification path."""
    path = _write(tmp_path, "ok_fail.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_fails_loudly():
            pytest.fail("expected this branch unreachable")
    """)
    codes = _codes(validate_test_file(path))
    assert "missing-assertion" not in codes


# ── unused-fixture-param: fixture arg declared but body never references it


def test_unused_fixture_param_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "unused.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_unused(slot, report, mfg_assets):
            assert 1 == 1
            report.step("noop")
            # ``slot`` and ``mfg_assets`` are declared but never used in the body.
    """)
    codes = _codes(validate_test_file(path))
    assert "unused-fixture-param" in codes
    # The violation message should name which params are unused.
    msgs = [v.message for v in validate_test_file(path) if v.code == "unused-fixture-param"]
    joined = " ".join(msgs)
    assert "slot" in joined
    assert "mfg_assets" in joined
    assert "report" not in joined  # report IS used


def test_used_fixture_param_does_not_warn(tmp_path: Path) -> None:
    path = _write(tmp_path, "used.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_uses_all(slot, config):
            mtib = slot.mtib
            threshold = config["thresh"]
            assert mtib is not None
            assert threshold > 0
    """)
    codes = _codes(validate_test_file(path))
    assert "unused-fixture-param" not in codes


def test_self_fixture_param_is_ignored(tmp_path: Path) -> None:
    """Class-based tests have ``self`` as the first arg — never flag it."""
    path = _write(tmp_path, "selfok.py", """
        import pytest

        class TestThing:
            @pytest.mark.timeout(5)
            def test_self_only(self):
                assert 1 == 1
    """)
    codes = _codes(validate_test_file(path))
    assert "unused-fixture-param" not in codes


# ── env-var-no-default: os.environ["X"] without a fallback


def test_env_var_no_default_at_module_scope_errors(tmp_path: Path) -> None:
    path = _write(tmp_path, "envbad.py", """
        import os

        # Module-scope read with no fallback — crashes at import time
        # if the env var is missing.
        SECRET = os.environ["MY_SECRET"]
    """)
    codes = _codes(validate_test_file(path))
    assert "env-var-no-default" in codes


def test_env_var_with_get_default_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "envok.py", """
        import os

        SECRET = os.environ.get("MY_SECRET", "fallback")
        OTHER = os.environ.get("OTHER")  # explicit None default is fine
    """)
    codes = _codes(validate_test_file(path))
    assert "env-var-no-default" not in codes


def test_env_var_no_default_inside_function_warns_not_errors(tmp_path: Path) -> None:
    """Reading without default inside a function is recoverable (raises
    KeyError at call time, not at import) — warning, not error."""
    path = _write(tmp_path, "envfunc.py", """
        import os
        import pytest

        @pytest.mark.timeout(5)
        def test_reads_env():
            value = os.environ["MY_SECRET"]
            assert value
    """)
    violations = validate_test_file(path)
    env_vs = [v for v in violations if v.code == "env-var-no-default"]
    assert env_vs, "expected env-var-no-default violation"
    assert env_vs[0].severity == "warning"


# ── shared-data-orphan: slot.shared_data["X"] written but never read (or vice versa)


def test_shared_data_written_but_never_read_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "shared.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_a(slot):
            slot.shared_data["app_shell"] = "foo"
            assert slot is not None

        @pytest.mark.timeout(5)
        def test_b(slot):
            assert slot is not None
    """)
    codes = _codes(validate_test_file(path))
    assert "shared-data-orphan" in codes
    msgs = [v.message for v in validate_test_file(path) if v.code == "shared-data-orphan"]
    assert any("app_shell" in m for m in msgs)


def test_shared_data_read_but_never_written_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, "shared2.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_a(slot):
            value = slot.shared_data["never_set"]
            assert value
    """)
    codes = _codes(validate_test_file(path))
    assert "shared-data-orphan" in codes


def test_shared_data_written_and_read_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "shared3.py", """
        import pytest

        @pytest.mark.timeout(5)
        def test_a(slot):
            slot.shared_data["imei"] = "359..."
            assert True

        @pytest.mark.timeout(5)
        def test_b(slot):
            value = slot.shared_data["imei"]
            assert value
    """)
    codes = _codes(validate_test_file(path))
    assert "shared-data-orphan" not in codes
