"""AST-based test-depth validator for ``corectl test validate``.

Concord test packages are rendered by the frontend as a two-level tree:

  * top-level ``def test_*`` functions, and
  * sub-steps opened via ``with report.step("name"):`` (emitted at
    runtime by :class:`corekinect.test.reporter.StepReporter`).

The reporter's per-test thread-local step counter and the UI's step
rendering both assume this strict two-level shape. Nested or helper-
emitted steps violate the contract — they produce step indices that
don't match the UI layout and may cascade-corrupt state when the
slot-parallel runner fans items out to threads. We enforce the shape at
publish time so invalid test packages never reach the runner.

Public surface
--------------

:func:`validate_test_file(path)`
    Validate a single ``.py`` file and return a list of
    :class:`TestDepthError` describing violations.

:func:`validate_project(project_dir)`
    Walk ``project_dir/tests/`` (or the directory itself if no
    ``tests/`` subdir exists), validate every ``.py`` file, and return
    the aggregated list of errors.

Both functions are pure AST analysis — no imports, no test execution,
safe to run in CI on arbitrary repos.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

__all__ = ["TestDepthError", "validate_test_file", "validate_project"]


@dataclass(frozen=True)
class TestDepthError:
    """One violation of the two-level test-depth contract."""

    file: Path
    line: int
    message: str


# ────────────────────────────────────────────────────────────────────────
# AST helpers
# ────────────────────────────────────────────────────────────────────────


def _is_report_step_call(node: ast.expr) -> bool:
    """True iff ``node`` is a call of the form ``report.step(...)``.

    Matches the attribute chain ``<anything>.step(...)`` where the
    attribute name is ``step`` and the receiver's name contains
    ``report`` — covers the canonical ``report.step("x")`` as well as
    conservative variants like ``self.report.step(...)``. Extremely
    strict matching would miss rare legitimate uses; we err on the side
    of enforcement because false positives are cheap to fix.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "step":
        return False
    receiver = func.value
    # Accept `report.step(...)`
    if isinstance(receiver, ast.Name) and "report" in receiver.id:
        return True
    # Accept `self.report.step(...)` / `foo.report.step(...)`
    if isinstance(receiver, ast.Attribute) and "report" in receiver.attr:
        return True
    return False


def _with_has_report_step(node: ast.With) -> bool:
    """True iff any ``with`` item opens a ``report.step(...)`` context."""
    return any(_is_report_step_call(item.context_expr) for item in node.items)


def _function_opens_step(func_node: ast.AST) -> tuple[bool, int]:
    """Return (True, lineno) if the function body contains any ``with report.step(...)``.

    Only scans the function's own body — not nested function defs —
    because nested functions are a separate scope.
    """
    for child in ast.walk(func_node):
        # Skip bodies of nested function/lambda definitions so a helper
        # defined inside a test doesn't double-report.
        if child is func_node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(child, ast.With) and _with_has_report_step(child):
            return True, child.lineno
    return False, 0


# ────────────────────────────────────────────────────────────────────────
# Validators
# ────────────────────────────────────────────────────────────────────────


class _DepthVisitor(ast.NodeVisitor):
    """Walks a module AST and collects ``TestDepthError`` instances.

    Tracks whether the currently-visited function is a top-level test
    (``name.startswith('test_')``) or a helper. Keeps a ``_step_depth``
    counter that increments when entering a ``with report.step(...):``
    and decrements on exit — any increment while the counter is already
    > 0 is a nested-step violation. Helpers that contain ``report.step``
    are flagged independently.
    """

    def __init__(self, file: Path) -> None:
        self.file = file
        self.errors: List[TestDepthError] = []
        self._step_depth = 0

    # ── Function boundaries reset step-depth tracking ──

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 (pytest style)
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def _visit_function(self, node: ast.AST) -> None:
        prev_depth = self._step_depth
        self._step_depth = 0
        self._check_helper_opens_step(node)
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self._step_depth = prev_depth

    def _check_helper_opens_step(self, node: ast.AST) -> None:
        """Non-test functions must not open a ``report.step(...)``."""
        name: str = getattr(node, "name", "")
        if name.startswith("test_"):
            return
        # It's a helper (or an _underscored private helper). If it opens
        # a step anywhere in its body, that counts as a nested step when
        # called from a test — flag it at definition time to catch it
        # before any test uses it.
        opens, line = _function_opens_step(node)
        if opens:
            self.errors.append(
                TestDepthError(
                    file=self.file,
                    line=line,
                    message=(
                        f"helper function {name!r} opens a "
                        f"'with report.step(...)' block; only top-level "
                        f"test_* functions may open steps (helpers called "
                        f"from a test would effectively nest)"
                    ),
                )
            )

    # ── with-statement handling ──

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        is_step = _with_has_report_step(node)
        if is_step:
            self._step_depth += 1
            if self._step_depth > 1:
                self.errors.append(
                    TestDepthError(
                        file=self.file,
                        line=node.lineno,
                        message=(
                            "nested 'with report.step(...)' detected; "
                            "only one level of steps is supported by the "
                            "Concord reporter and the test-execution UI"
                        ),
                    )
                )
        try:
            for child in ast.iter_child_nodes(node):
                self.visit(child)
        finally:
            if is_step:
                self._step_depth -= 1


def validate_test_file(path: Path) -> List[TestDepthError]:
    """Validate a single Python file; return a list of violations.

    Syntax errors are themselves reported as a single error so the
    caller sees the problem without crashing.
    """
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            TestDepthError(
                file=path,
                line=exc.lineno or 0,
                message=f"syntax error: {exc.msg}",
            )
        ]

    visitor = _DepthVisitor(path)
    visitor.visit(tree)
    return visitor.errors


def validate_project(project_dir: Path) -> List[TestDepthError]:
    """Validate every ``.py`` file under ``project_dir/tests/``.

    Falls back to scanning the whole ``project_dir`` if no ``tests/``
    subdirectory exists, so the validator still works on flat layouts.
    """
    tests_dir = project_dir / "tests"
    root = tests_dir if tests_dir.is_dir() else project_dir
    errors: List[TestDepthError] = []
    for py_file in sorted(root.rglob("*.py")):
        errors.extend(validate_test_file(py_file))
    return errors
