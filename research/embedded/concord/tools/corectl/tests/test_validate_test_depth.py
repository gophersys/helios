"""Tests for the 2-level test-depth validator in ``corectl test validate``.

The frontend renders test runs as a two-level tree: top-level tests and
sub-steps emitted by ``with report.step(...)``. The reporter's per-test
thread-local state also assumes this structure — nested steps would
corrupt the step indices. This validator enforces the shape at publish
time so malformed test packages never reach the runner.

Violations caught:
  * ``with report.step(...)`` nested inside another ``with report.step(...)``
  * Helper functions that call ``report.step(...)`` — indirectly nest
    when called from a test that itself opens a step.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Tiny helper that writes a fake test package module
# ─────────────────────────────────────────────────────────────────────────────


def _write_test_file(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(body))
    return p


# ─────────────────────────────────────────────────────────────────────────────
# The validator under test
# ─────────────────────────────────────────────────────────────────────────────


def test_accepts_flat_two_level_depth(tmp_path: Path) -> None:
    """Top-level test with top-level `with report.step(...)` is valid."""
    from corectl.commands.test_depth import validate_test_file

    path = _write_test_file(tmp_path, "test_ok.py", """
        def test_something(slot, report):
            with report.step("Apply voltage"):
                slot.mtib.PowerEnable(0, 4.5)
            with report.step("Verify rail") as step:
                step.record("voltage_3v3", 3.3, unit="V")
                assert True
    """)
    errors = validate_test_file(path)
    assert errors == []


def test_rejects_nested_step(tmp_path: Path) -> None:
    """with report.step inside another with report.step is invalid."""
    from corectl.commands.test_depth import validate_test_file

    path = _write_test_file(tmp_path, "test_nested.py", """
        def test_something(slot, report):
            with report.step("Outer"):
                with report.step("Inner"):
                    pass
    """)
    errors = validate_test_file(path)
    assert errors, "expected at least one error for nested step"
    err = errors[0]
    assert "nested" in err.message.lower()
    assert err.file == path
    assert err.line > 0


def test_rejects_helper_that_opens_step(tmp_path: Path) -> None:
    """Helper functions called from a test must not open their own step."""
    from corectl.commands.test_depth import validate_test_file

    path = _write_test_file(tmp_path, "test_helper.py", """
        def _do_work(report):
            with report.step("Inner from helper"):
                pass

        def test_something(slot, report):
            with report.step("Outer"):
                _do_work(report)
    """)
    errors = validate_test_file(path)
    assert errors, "expected error for helper opening a step"
    # Error should name the helper and its file/line
    helper_errors = [e for e in errors if "_do_work" in e.message or "helper" in e.message.lower()]
    assert helper_errors, f"helper-specific error missing: got {errors}"


def test_accepts_step_record_inside_step(tmp_path: Path) -> None:
    """`step.record(...)` inside a `with` block is fine (not a step open)."""
    from corectl.commands.test_depth import validate_test_file

    path = _write_test_file(tmp_path, "test_record.py", """
        def test_something(slot, report):
            with report.step("Measure") as step:
                step.record("voltage", 3.3, unit="V")
                step.record_dict({"current": {"value": 0.02, "unit": "A"}})
    """)
    errors = validate_test_file(path)
    assert errors == []


def test_reports_file_and_line_for_violation(tmp_path: Path) -> None:
    """Error entries carry the source file and the offending line number."""
    from corectl.commands.test_depth import validate_test_file

    path = _write_test_file(tmp_path, "test_line_info.py", """
        def test_a(slot, report):
            with report.step("Outer"):
                pass

        def test_b(slot, report):
            with report.step("Outer"):
                with report.step("Bad"):
                    pass
    """)
    errors = validate_test_file(path)
    assert len(errors) == 1
    assert errors[0].file == path
    # The inner `with report.step("Bad")` is on the line AFTER the outer one.
    # Exact line number depends on dedent; just require line > 5.
    assert errors[0].line > 5


def test_ignores_non_test_files(tmp_path: Path) -> None:
    """validate_test_file should still parse any .py file but only flag violations."""
    from corectl.commands.test_depth import validate_test_file

    path = _write_test_file(tmp_path, "helpers.py", """
        def make_payload():
            return {"foo": "bar"}
    """)
    errors = validate_test_file(path)
    assert errors == []


def test_validate_project_dir_walks_tests_directory(tmp_path: Path) -> None:
    """Top-level project validator walks tests/ and aggregates errors."""
    from corectl.commands.test_depth import validate_project

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_good.py").write_text(textwrap.dedent("""
        def test_a(slot, report):
            with report.step("ok"):
                pass
    """))
    (tests_dir / "test_bad.py").write_text(textwrap.dedent("""
        def test_b(slot, report):
            with report.step("outer"):
                with report.step("inner"):
                    pass
    """))

    errors = validate_project(tmp_path)
    assert len(errors) == 1
    assert errors[0].file.name == "test_bad.py"
