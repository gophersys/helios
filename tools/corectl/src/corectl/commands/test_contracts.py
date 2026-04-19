"""AST-based contract validators for ``corectl test validate``.

Beyond the two-level step-depth shape enforced in
:mod:`corectl.commands.test_depth`, the Concord runner relies on a
handful of **conventions** every test package must respect. These are
captured here as independent validators so we can fail fast at
``corectl upload`` time rather than discover them at run-time in
production.

Current contracts
-----------------

:func:`validate_timeout_markers` (ERROR)
    Every ``def test_*`` function must declare an explicit
    ``@pytest.mark.timeout(N)`` with a positive integer or float.
    Missing timeouts let a single bad slot drag the wall-clock of a
    whole panel run — the parallel runner budgets off each test's
    declared timeout. An implicit session-wide timeout is not enough
    because it applies to the whole run, not each test.

:func:`validate_step_records` (WARN)
    Every ``with report.step(...):`` block should call ``step.record(...)``
    at least once. Empty steps render as blank cards in the UI and
    indicate a test that isn't capturing measurements — probably a
    bug in the test itself.

Public surface
--------------

:func:`validate_test_file(path, *, stage_markers=...)`
    Run all contracts against a single file and return a list of
    :class:`ContractViolation`.

:func:`validate_project(project_dir, *, stage_markers=...)`
    Walk ``project_dir/tests/``, run every contract, aggregate.

All validators are pure AST analysis — no imports, no test execution.

Design notes
------------

* Violations carry a ``severity`` of ``"error"`` or ``"warning"`` so the
  caller can decide whether to block upload.
* A single AST walk collects all contract violations in one pass — we
  don't reparse per-check.
* Contracts are additive: new contracts go in the same ``_Visitor``
  without changing the public surface.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

__all__ = [
    "ContractViolation",
    "validate_test_file",
    "validate_project",
    "validate_files",
]


# ────────────────────────────────────────────────────────────────────────
# Violation type
# ────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ContractViolation:
    """One violation of a package contract.

    ``severity`` is ``"error"`` (blocks upload under ``--strict``) or
    ``"warning"`` (surfaces as a yellow warning, non-blocking).

    ``code`` is a short stable identifier so CI can pin/grep
    violations by type (e.g. ``missing-timeout``).
    """

    file: Path
    line: int
    code: str
    severity: str  # "error" | "warning"
    message: str


# ────────────────────────────────────────────────────────────────────────
# Decorator / call helpers
# ────────────────────────────────────────────────────────────────────────


def _decorator_path(node: ast.expr) -> Optional[str]:
    """Flatten a decorator expression to a dotted path, or return None.

    ``@pytest.mark.timeout(30)`` → ``"pytest.mark.timeout"``
    ``@pytest.mark.sequential``  → ``"pytest.mark.sequential"``
    ``@some_decorator``          → ``"some_decorator"``
    """
    target = node.func if isinstance(node, ast.Call) else node
    parts: List[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    else:
        return None
    return ".".join(reversed(parts))


def _timeout_seconds(node: ast.Call) -> Optional[float]:
    """Extract the numeric argument from ``@pytest.mark.timeout(N)``.

    Accepts positional ``N`` or keyword ``timeout=N``. Returns the
    numeric value or ``None`` if the argument isn't a literal number
    (e.g. a reference like ``@pytest.mark.timeout(LONG_TIMEOUT)`` —
    we can't statically verify those).
    """
    arg: Optional[ast.expr] = None
    if node.args:
        arg = node.args[0]
    else:
        for kw in node.keywords:
            if kw.arg == "timeout":
                arg = kw.value
                break
    if arg is None:
        return None
    if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
        return float(arg.value)
    return None


def _is_step_record_call(node: ast.expr) -> bool:
    """True iff ``node`` is ``<anything>.record(...)`` on a step-like name.

    Matches ``step.record(...)`` and similar — we accept any receiver
    because tests often bind the step to various names via
    ``with report.step(...) as step:`` / ``as s:`` / ``as power_step:``.
    The call is the signal; we don't need to reason about the binding.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    return func.attr == "record"


def _with_opens_step(node: ast.With) -> bool:
    """True iff any ``with`` item is ``report.step(...)``-shaped."""
    for item in node.items:
        expr = item.context_expr
        if not isinstance(expr, ast.Call):
            continue
        func = expr.func
        if not isinstance(func, ast.Attribute) or func.attr != "step":
            continue
        # Accept anything ending in `.step(...)` where receiver mentions
        # report — mirrors test_depth's matcher so the two stay in sync.
        recv = func.value
        if isinstance(recv, ast.Name) and "report" in recv.id:
            return True
        if isinstance(recv, ast.Attribute) and "report" in recv.attr:
            return True
    return False


def _step_block_has_record(with_node: ast.With) -> bool:
    """True iff the body of a ``with report.step(...)`` block calls ``*.record(...)``.

    Only scans direct body (including nested blocks); skips function
    definitions inside the block — a helper-emitted record is a
    separate concern.
    """
    for child in ast.walk(with_node):
        if child is with_node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(child, ast.Expr) and _is_step_record_call(child.value):
            return True
        if isinstance(child, ast.Call) and _is_step_record_call(child):
            # covers ``result = step.record(...)`` patterns
            return True
    return False


# ────────────────────────────────────────────────────────────────────────
# Visitor
# ────────────────────────────────────────────────────────────────────────


_UPPER_TIMEOUT_S = 600.0   # tests taking >10 min almost certainly indicate
                           # a broken wait — the session-level timeout is 30 min
_LOWER_TIMEOUT_S = 1.0     # < 1 s is a typo (e.g. timeout=0.5 when meant 30)


class _Visitor(ast.NodeVisitor):
    """Walks a module AST collecting all contract violations in one pass."""

    def __init__(self, file: Path) -> None:
        self.file = file
        self.violations: List[ContractViolation] = []

    # ── Tests must declare a pytest.mark.timeout(N) ──

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def _visit_function(self, node: ast.AST) -> None:
        name: str = getattr(node, "name", "")
        if name.startswith("test_"):
            self._check_timeout_marker(node)
        # descend — nested functions + step blocks
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def _check_timeout_marker(self, node: ast.AST) -> None:
        """Emit missing-timeout / suspect-timeout violations for a test function."""
        decorators: Sequence[ast.expr] = getattr(node, "decorator_list", ()) or ()
        timeout_call: Optional[ast.Call] = None
        for dec in decorators:
            path = _decorator_path(dec)
            if path == "pytest.mark.timeout" and isinstance(dec, ast.Call):
                timeout_call = dec
                break

        if timeout_call is None:
            self.violations.append(
                ContractViolation(
                    file=self.file,
                    line=node.lineno,
                    code="missing-timeout",
                    severity="error",
                    message=(
                        f"test {node.name!r} has no "
                        f"'@pytest.mark.timeout(N)' — every test must "
                        f"declare a per-test timeout so a stuck slot "
                        f"can't drag the whole parallel run's wall clock"
                    ),
                )
            )
            return

        seconds = _timeout_seconds(timeout_call)
        if seconds is None:
            # Non-literal (e.g. a constant reference) — accept; we can't
            # verify statically and flagging would be noisy.
            return

        if seconds < _LOWER_TIMEOUT_S:
            self.violations.append(
                ContractViolation(
                    file=self.file,
                    line=timeout_call.lineno,
                    code="suspect-timeout",
                    severity="warning",
                    message=(
                        f"test {node.name!r} has timeout={seconds}s "
                        f"(< {_LOWER_TIMEOUT_S}s) — likely a typo; a "
                        f"sub-second budget will always expire under "
                        f"normal hardware latency"
                    ),
                )
            )
        elif seconds > _UPPER_TIMEOUT_S:
            self.violations.append(
                ContractViolation(
                    file=self.file,
                    line=timeout_call.lineno,
                    code="suspect-timeout",
                    severity="warning",
                    message=(
                        f"test {node.name!r} has timeout={seconds}s "
                        f"(> {_UPPER_TIMEOUT_S}s) — tests that long "
                        f"usually hide a broken wait; the parallel "
                        f"runner's panel budget assumes tight per-test "
                        f"ceilings"
                    ),
                )
            )

    # ── Step blocks should record at least one measurement ──

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        if _with_opens_step(node) and not _step_block_has_record(node):
            self.violations.append(
                ContractViolation(
                    file=self.file,
                    line=node.lineno,
                    code="empty-step",
                    severity="warning",
                    message=(
                        "'with report.step(...)' block has no "
                        "'step.record(...)' call — the step will render "
                        "as an empty card in the UI with no captured data"
                    ),
                )
            )
        for child in ast.iter_child_nodes(node):
            self.visit(child)


# ────────────────────────────────────────────────────────────────────────
# Public surface
# ────────────────────────────────────────────────────────────────────────


def validate_test_file(path: Path) -> List[ContractViolation]:
    """Run all contracts against a single ``.py`` file.

    Returns every violation in source order. Syntax errors surface as
    a single ``syntax-error`` violation so the caller sees the problem
    instead of crashing.
    """
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            ContractViolation(
                file=path,
                line=exc.lineno or 0,
                code="syntax-error",
                severity="error",
                message=f"syntax error: {exc.msg}",
            )
        ]

    visitor = _Visitor(path)
    visitor.visit(tree)
    return visitor.violations


def validate_project(project_dir: Path) -> List[ContractViolation]:
    """Walk ``project_dir/tests/`` and aggregate every contract violation.

    Falls back to scanning the whole directory if no ``tests/``
    subdirectory exists, so the validator works on flat layouts.

    Prefer :func:`validate_files` when the caller knows exactly which
    files will be executed by the runner (from the manifest stages) —
    it avoids flagging harness / E2E test modules that live alongside
    but are never scheduled by the runner.
    """
    tests_dir = project_dir / "tests"
    root = tests_dir if tests_dir.is_dir() else project_dir
    return validate_files(sorted(root.rglob("*.py")))


def validate_files(paths: Iterable[Path]) -> List[ContractViolation]:
    """Run contracts against an explicit list of files.

    Missing files are skipped silently — the caller is assumed to have
    already reported unresolved stage modules. This keeps contract
    validation focused on files that actually exist.
    """
    violations: List[ContractViolation] = []
    for path in paths:
        if path.is_file():
            violations.extend(validate_test_file(path))
    return violations
