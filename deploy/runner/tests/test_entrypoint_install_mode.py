"""P3 — runner entrypoint installs test packages NON-editable.

The pre-fix entrypoint did `pip3 install --no-cache-dir -e /app/`
against the downloaded test package. Modern setuptools' default
`build_meta` backend doesn't expose `build_editable` (PEP 660), so
this fails with::

    ERROR: Project file:///app has a 'pyproject.toml' and its build
    backend is missing the 'build_editable' hook.

The fix is trivial — drop the `-e` flag. The test package is read-only
at runtime; the runner doesn't need editable-install semantics. Switch
to `pip install .` (non-editable).

This file pins the contract going forward: entrypoint.sh MUST NOT pip-
install with `-e` on the downloaded test package. Any future
hand-edit that re-introduces `-e` triggers the test.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = WORKSPACE_ROOT / "deploy" / "runner" / "entrypoint.sh"


def _non_comment_lines(text: str) -> list[str]:
    """Return entrypoint.sh lines with comments and blank lines stripped.

    The forbid-`-e` check would otherwise false-positive on comment
    lines that name the old behaviour for context (e.g., a
    "pip install -e /app/ was the bug" explanatory block).
    """
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(raw)
    return out


def test_entrypoint_does_not_use_editable_install() -> None:
    """pip3 install -e against /app/ would hit PEP 660 build_editable errors.

    Allow `pip install -e` against OTHER paths (we don't have any
    today, but the test should be narrow). Specifically forbid
    `pip install -e /app/` on a CODE line (comments may reference
    the old shape).
    """
    assert ENTRYPOINT.is_file()
    forbidden = re.compile(r"pip3?\s+install[^\n]*\s-e\s+/app/")
    offenders = [
        line for line in _non_comment_lines(ENTRYPOINT.read_text())
        if forbidden.search(line)
    ]
    assert not offenders, (
        "deploy/runner/entrypoint.sh must NOT use `pip install -e /app/`. "
        "Modern setuptools' build_meta does not implement PEP 660 "
        "build_editable, and the runner does not need editable semantics. "
        f"Offending lines:\n" + "\n".join(offenders)
    )


def test_entrypoint_uses_non_editable_install() -> None:
    """At least one `pip install /app/` (non-editable) line must exist.

    Catches a future regression where someone deletes the install
    section entirely.
    """
    non_editable = re.compile(r"pip3?\s+install[^\n]*\s/app/?\b")
    matches = [
        line for line in _non_comment_lines(ENTRYPOINT.read_text())
        if non_editable.search(line) and " -e " not in line
    ]
    assert matches, (
        "deploy/runner/entrypoint.sh should install the downloaded test "
        "package non-editably with `pip install /app/`. None found."
    )


def test_entrypoint_still_uses_no_cache_dir() -> None:
    """The `--no-cache-dir` flag prevents wheel-cache bloat in the pod's
    ephemeral storage; preserve it across the editable→non-editable
    change.
    """
    install_lines = [
        line for line in _non_comment_lines(ENTRYPOINT.read_text())
        if re.search(r"pip3?\s+install[^\n]*/app", line)
    ]
    assert install_lines, "no pip-install-into-/app lines found"
    for line in install_lines:
        assert "--no-cache-dir" in line, (
            f"Each /app pip-install must keep --no-cache-dir: {line!r}"
        )
