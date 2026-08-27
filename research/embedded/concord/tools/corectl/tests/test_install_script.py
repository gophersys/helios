"""Tests for the corectl install script.

Two concerns:
  1. The script served to users at /corectl/install.sh (the static file in the
     frontend app) must always be identical to the canonical source at
     tools/corectl/install.sh. They are kept in sync by the
     ``corectl:sync-install-script`` Nx target, which runs before every
     frontend containerize build. These tests catch any drift between the two.

  2. The canonical script itself must use pipx (not bare ``pip install``), so
     it works on Python 3.12+ systems with PEP 668 externally-managed
     environments.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repo root: tools/corectl/tests/test_install_script.py → [3] parents up
_REPO_ROOT = Path(__file__).resolve().parents[3]

CANONICAL = _REPO_ROOT / "tools" / "corectl" / "install.sh"
SERVED = _REPO_ROOT / "apps" / "frontend" / "app" / "static" / "corectl" / "install.sh"


# ── Existence guards ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def canonical_text() -> str:
    assert CANONICAL.exists(), f"Canonical install script missing: {CANONICAL}"
    return CANONICAL.read_text()


@pytest.fixture(scope="module")
def served_text() -> str:
    assert SERVED.exists(), (
        f"Served install script missing: {SERVED}\n"
        f"Run: nx run corectl:sync-install-script"
    )
    return SERVED.read_text()


# ── Identity ─────────────────────────────────────────────────────────────────


def test_served_script_matches_canonical(canonical_text: str, served_text: str) -> None:
    """The static file served to users must be byte-for-byte identical to the
    canonical source.  If this fails, run:

        nx run corectl:sync-install-script

    then commit both files together.
    """
    assert served_text == canonical_text, (
        "apps/frontend/app/static/corectl/install.sh has drifted from "
        "tools/corectl/install.sh.\n"
        "Fix: nx run corectl:sync-install-script"
    )


# ── Canonical script content ──────────────────────────────────────────────────


def test_canonical_uses_pipx_to_install_corectl(canonical_text: str) -> None:
    """The install script must use pipx so it works on Python 3.12+ systems
    with PEP 668 externally-managed-environment protection.
    """
    assert "pipx install" in canonical_text, (
        "tools/corectl/install.sh must use 'pipx install' to install corectl. "
        "Bare 'pip install' breaks on Python 3.12+ (PEP 668)."
    )


def test_canonical_does_not_use_pip_user_for_corectl(canonical_text: str) -> None:
    """The broken pattern that caused the PEP 668 failure must not reappear.

    The old script used ``pip install --user ... corectl corekinect``.
    If this pattern ever reappears (e.g., as a fallback branch), the test
    catches it before it ships.
    """
    lines = canonical_text.splitlines()
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comment lines — they may document what NOT to do.
        if stripped.startswith("#"):
            continue
        if "pip install" in line and ("corectl" in line or "corekinect" in line):
            pytest.fail(
                f"tools/corectl/install.sh line {lineno} uses 'pip install' "
                f"to install corectl/corekinect directly:\n\n  {line.rstrip()}\n\n"
                "Use 'pipx install' instead (PEP 668 compliance)."
            )


def test_canonical_checks_python_version(canonical_text: str) -> None:
    """The script must gate on Python >= 3.10 before attempting the install."""
    assert "3.10" in canonical_text, (
        "tools/corectl/install.sh must enforce a minimum Python version (>=3.10). "
        "Missing version check."
    )
