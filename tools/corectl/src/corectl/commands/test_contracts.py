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
from typing import Iterable, List, Optional, Sequence, Tuple

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
    """True iff ``node`` records a measurement onto a step.

    Matches:
      * ``<anything>.record(...)`` — direct method call. We accept any
        receiver because tests bind the step to various names via
        ``with report.step(...) as step:`` / ``as s:`` / ``as power_step:``.
      * ``assert_and_record(step, ...)`` and any other ``assert_*`` helper
        from ``corekinect.test.assertions`` — these wrap a predicate AND
        record on the step in one call. Treating them as both an assertion
        and a record is the whole point of the helper; the validator has
        to mirror that or every canonical mfg test trips empty-step.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "record":
        return True
    if isinstance(func, ast.Name) and func.id.startswith("assert_"):
        return True
    return False


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


# ── Helpers for the Phase 5 checks ──────────────────────────────────────


def _function_has_verification(node: ast.AST) -> bool:
    """True iff a function body asserts, records, or raises something.

    A test that verifies nothing — no ``assert``, no ``step.record``,
    no ``raise``, no ``pytest.fail/.exit/.skip`` — is dead weight at
    best and a false-positive at worst. We deliberately accept any of
    these as evidence of intent so the check never flags a
    legitimately-shaped test.
    """
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # Don't descend into nested helpers — their assertions
            # don't count toward the parent test's verification.
            continue
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Raise):
            return True
        if isinstance(child, ast.Call):
            if _is_step_record_call(child):
                return True
            # ``pytest.fail(...)``, ``pytest.skip(...)``, ``pytest.exit(...)``
            func = child.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "pytest" and func.attr in ("fail", "skip", "exit"):
                    return True
    return False


def _arg_names(node: ast.AST) -> List[str]:
    """Names of every argument (positional + keyword-only) on a function."""
    args = getattr(node, "args", None)
    if args is None:
        return []
    out: List[str] = []
    out.extend(a.arg for a in args.args)
    out.extend(a.arg for a in args.kwonlyargs)
    return out


def _function_uses_name(node: ast.AST, name: str) -> bool:
    """True iff anywhere inside ``node``'s body references ``name``."""
    body = getattr(node, "body", [])
    for stmt in body:
        for child in ast.walk(stmt):
            if isinstance(child, ast.Name) and child.id == name:
                return True
            # ``slot.mtib`` — the receiver is a Name node we'll catch above,
            # so attributes don't need their own case.
    return False


def _is_environ_subscript_without_default(node: ast.AST) -> Optional[str]:
    """Return the env-var name if ``node`` is ``os.environ["X"]``-shaped.

    Returns ``None`` for ``os.environ.get("X", default)`` and other
    safe forms. We only flag the bare-subscript form because that's
    the one that crashes at import time.
    """
    if not isinstance(node, ast.Subscript):
        return None
    value = node.value
    # Match ``os.environ`` and the bare ``environ`` (after ``from os
    # import environ``).
    is_environ = False
    if isinstance(value, ast.Attribute) and value.attr == "environ":
        if isinstance(value.value, ast.Name) and value.value.id == "os":
            is_environ = True
    elif isinstance(value, ast.Name) and value.id == "environ":
        is_environ = True
    if not is_environ:
        return None
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return "<dynamic>"


def _shared_data_keys(node: ast.AST) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(written_key, read_key)`` if ``node`` touches ``slot.shared_data["X"]``.

    Only one of the pair is non-None per call (a node is either a
    write target or a read site, not both). Returns ``(None, None)``
    for nodes that aren't shared_data accesses.
    """
    if not isinstance(node, ast.Subscript):
        return None, None
    value = node.value
    if not (isinstance(value, ast.Attribute) and value.attr == "shared_data"):
        return None, None
    slice_node = node.slice
    if not (isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str)):
        return None, None
    return slice_node.value, None  # caller distinguishes write vs read by ast.Store/Load


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
        # ``shared_data["X"]`` keys collected file-wide so we can flag
        # write-only and read-only orphans after the visit completes.
        self._shared_data_writes: dict = {}  # key -> first lineno
        self._shared_data_reads: dict = {}   # key -> first lineno
        # Whether we're currently inside a function body (controls
        # severity of env-var-no-default).
        self._function_depth = 0

    # ── Tests must declare a pytest.mark.timeout(N) ──

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def _visit_function(self, node: ast.AST) -> None:
        name: str = getattr(node, "name", "")
        if name.startswith("test_"):
            self._check_timeout_marker(node)
            self._check_has_verification(node)
            self._check_unused_fixture_params(node)
        # descend — nested functions + step blocks. Track depth so
        # ``visit_Subscript`` can vary env-var severity by scope.
        self._function_depth += 1
        try:
            for child in ast.iter_child_nodes(node):
                self.visit(child)
        finally:
            self._function_depth -= 1

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

    # ── Phase 5 checks ───────────────────────────────────────────────

    def _check_has_verification(self, node: ast.AST) -> None:
        """Flag tests that don't ``assert``, ``record``, or ``raise`` anything."""
        if _function_has_verification(node):
            return
        self.violations.append(
            ContractViolation(
                file=self.file,
                line=node.lineno,
                code="missing-assertion",
                severity="error",
                message=(
                    f"test {getattr(node, 'name', '?')!r} contains no "
                    f"assert / step.record / raise / pytest.fail — the test "
                    f"verifies nothing and will pass even when the device "
                    f"is broken"
                ),
            )
        )

    def _check_unused_fixture_params(self, node: ast.AST) -> None:
        """Flag fixture args declared on a test but never referenced in its body.

        Skips ``self`` / ``cls`` (class-based tests) and any param
        prefixed with ``_`` (the standard "intentionally unused"
        Python convention).
        """
        unused: List[str] = []
        for name in _arg_names(node):
            if name in ("self", "cls") or name.startswith("_"):
                continue
            if not _function_uses_name(node, name):
                unused.append(name)
        if not unused:
            return
        self.violations.append(
            ContractViolation(
                file=self.file,
                line=node.lineno,
                code="unused-fixture-param",
                severity="warning",
                message=(
                    f"test {getattr(node, 'name', '?')!r} declares fixture "
                    f"param(s) {', '.join(repr(n) for n in unused)} but "
                    f"never references them — unused fixtures still pay "
                    f"setup cost and usually mean the test was renamed or "
                    f"the fixture is the wrong one"
                ),
            )
        )

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        # env-var-no-default
        env_name = _is_environ_subscript_without_default(node)
        if env_name is not None:
            severity = "warning" if self._function_depth > 0 else "error"
            scope = "function" if self._function_depth > 0 else "module"
            self.violations.append(
                ContractViolation(
                    file=self.file,
                    line=node.lineno,
                    code="env-var-no-default",
                    severity=severity,
                    message=(
                        f"environ[{env_name!r}] read at {scope} scope without "
                        f"a default — use os.environ.get({env_name!r}, ...) "
                        f"so a missing var doesn't crash "
                        f"{'at import time' if severity == 'error' else 'mid-test'}"
                    ),
                )
            )

        # shared-data-orphan: collect read/write sites for cross-test analysis
        key, _ = _shared_data_keys(node)
        if key is not None:
            ctx = getattr(node, "ctx", None)
            if isinstance(ctx, ast.Store):
                self._shared_data_writes.setdefault(key, node.lineno)
            elif isinstance(ctx, ast.Load):
                self._shared_data_reads.setdefault(key, node.lineno)

        # Descend into children — index expressions like
        # ``a[b[c]]`` need recursion to flag the inner ``b[c]`` too.
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def finalize(self) -> None:
        """Cross-test analysis that runs after the AST walk completes.

        Today: emit ``shared-data-orphan`` for any key written-only or
        read-only across the file. Visitor-time analysis can't do this
        because writes and reads can live in different functions.
        """
        for key, lineno in self._shared_data_writes.items():
            if key not in self._shared_data_reads:
                self.violations.append(
                    ContractViolation(
                        file=self.file,
                        line=lineno,
                        code="shared-data-orphan",
                        severity="warning",
                        message=(
                            f"slot.shared_data[{key!r}] is written but never "
                            f"read in this file — either the consumer was "
                            f"removed (delete the write) or the consumer "
                            f"reads under a different key"
                        ),
                    )
                )
        for key, lineno in self._shared_data_reads.items():
            if key not in self._shared_data_writes:
                self.violations.append(
                    ContractViolation(
                        file=self.file,
                        line=lineno,
                        code="shared-data-orphan",
                        severity="warning",
                        message=(
                            f"slot.shared_data[{key!r}] is read but never "
                            f"written in this file — the producer is "
                            f"missing or the read uses the wrong key, "
                            f"raising KeyError at runtime"
                        ),
                    )
                )


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
    visitor.finalize()  # cross-test checks (shared-data-orphan, ...)
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
