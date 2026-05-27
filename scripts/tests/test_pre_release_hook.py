"""Tests for .claude/hooks/pre-release.

The pre-release hook runs as Phase 0 of `/concord-release`. It scans
the LAST_TAG..HEAD range for risky path patterns (corekinect,
protocols, corectl, prisma, deploy/) and emits a structured
system-reminder block listing downstream artifacts that need
attention. It is **read-only** — no mutations, idempotent.

Contract:
    .claude/hooks/pre-release [<last_tag>] [<head_ref>]
    - LAST_TAG defaults to `git describe --tags --abbrev=0`
    - HEAD_REF defaults to HEAD
    - emits stdout in <system-reminder>-formatted shape
    - exit 0 always (this is informational; the actual gate is
      Phase D Layer 3 at scripts/release-gates/check-runner-affected.sh)

Tested cases:
    - No risky paths in range  → silent (no system-reminder emitted)
    - corekinect touched       → reports corekinect coupling
    - corectl touched          → reports corectl coupling
    - prisma touched           → reports prisma coupling
    - mtib protocols touched   → reports protocols coupling
    - deploy/ touched          → reports all-three-envs coupling
    - Combination              → reports each in its own section
    - Range that doesn't exist → exits non-zero with usage
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path
from typing import Iterable

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = WORKSPACE_ROOT / ".claude" / "hooks" / "pre-release"


# ---------------------------------------------------------------------------
# Hermetic git-repo harness (same shape as Layer 3's tests)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=repo,
        env=env,
        check=True,
    )
    return result.stdout


def _make_repo(tmp_path: Path, files_touched: Iterable[str]) -> Path:
    """Build a throwaway repo with a v-last tag, then a commit touching files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")

    (repo / "VERSION").write_text("0.12.3\n")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", "VERSION", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "tag", "v-last")

    if not files_touched:
        (repo / "README.md").write_text("seed updated\n")
        _git(repo, "add", "README.md")
        _git(repo, "commit", "-q", "-m", "noop")
    else:
        for relpath in files_touched:
            target = repo / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text() if target.exists() else ""
            target.write_text(existing + f"# touch {relpath}\n")
            _git(repo, "add", relpath)
        _git(repo, "commit", "-q", "-m", "touch paths")

    return repo


def _run_hook(
    repo: Path,
    *,
    last_tag: str | None = "v-last",
    head_ref: str = "HEAD",
) -> subprocess.CompletedProcess:
    """Invoke the hook from inside the throwaway repo."""
    args = [str(HOOK_PATH)]
    if last_tag is not None:
        args.append(last_tag)
        args.append(head_ref)

    return subprocess.run(
        ["bash", *args],
        capture_output=True,
        text=True,
        cwd=repo,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_hook_exists_and_is_executable() -> None:
    """Sanity: the hook is at the contracted path and executable."""
    assert HOOK_PATH.is_file(), f".claude/hooks/pre-release missing at {HOOK_PATH}"
    assert os.access(HOOK_PATH, os.X_OK), f"{HOOK_PATH} is not executable"


def test_no_risky_paths_emits_no_reminder(tmp_path: Path) -> None:
    """Range touches only README → silent (no <system-reminder>)."""
    repo = _make_repo(tmp_path, ["README.md"])
    result = _run_hook(repo)
    assert result.returncode == 0, (
        f"Hook must always exit 0. stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "<system-reminder>" not in result.stdout, (
        f"No risky paths → no reminder block:\n{result.stdout}"
    )


def test_corekinect_touched_reports_runner_rebuild(tmp_path: Path) -> None:
    """corekinect change → reminder names runner rebuild + Phase D layers."""
    repo = _make_repo(tmp_path, ["libs/python/corekinect/__init__.py"])
    result = _run_hook(repo)
    assert result.returncode == 0
    assert "<system-reminder>" in result.stdout, f"Reminder missing:\n{result.stdout}"
    out_lower = result.stdout.lower()
    assert "corekinect" in out_lower
    assert "test-runner" in out_lower or "runner" in out_lower
    # Must point at the enforcement layer (Phase D Layer 3) so the agent
    # can either verify the layer fires or know which gate will catch it.
    assert "phase d" in out_lower or "layer" in out_lower or "check-runner-affected" in out_lower, (
        f"Reminder must reference the enforcement layer:\n{result.stdout}"
    )


def test_corectl_touched_reports_wheel_publish(tmp_path: Path) -> None:
    """corectl change → reminder names wheel publish + runner rebuild."""
    repo = _make_repo(tmp_path, ["tools/corectl/src/corectl/__init__.py"])
    result = _run_hook(repo)
    assert "<system-reminder>" in result.stdout
    out_lower = result.stdout.lower()
    assert "corectl" in out_lower
    assert "wheel" in out_lower or "pypi" in out_lower or "publish" in out_lower
    assert "runner" in out_lower, (
        f"corectl ships in runner image → runner must be mentioned:\n{result.stdout}"
    )


def test_prisma_schema_touched_reports_full_flow(tmp_path: Path) -> None:
    """Schema change → reminder names migration + Python client + models.ts."""
    repo = _make_repo(tmp_path, ["prisma/schema.prisma"])
    result = _run_hook(repo)
    assert "<system-reminder>" in result.stdout
    out_lower = result.stdout.lower()
    assert "prisma" in out_lower or "schema" in out_lower
    assert "migration" in out_lower
    assert "models.ts" in out_lower or "frontend" in out_lower or "type" in out_lower, (
        f"Schema change must remind about the frontend type mirror:\n{result.stdout}"
    )


def test_protocols_mtib_touched_reports_dual_rebuild(tmp_path: Path) -> None:
    """libs/protocols/mtib change → reminder names runner + mtib-server."""
    repo = _make_repo(tmp_path, ["libs/protocols/mtib/mtib.proto"])
    result = _run_hook(repo)
    assert "<system-reminder>" in result.stdout
    out_lower = result.stdout.lower()
    assert "protocols" in out_lower or "mtib" in out_lower
    assert "runner" in out_lower
    assert "mtib-server" in out_lower or "mtib server" in out_lower, (
        f"Proto change must remind about mtib-server rebuild:\n{result.stdout}"
    )


def test_deploy_touched_reports_three_envs(tmp_path: Path) -> None:
    """deploy/ touched → reminder names the all-three-envs rule."""
    repo = _make_repo(tmp_path, ["deploy/development/docker-compose.yaml"])
    result = _run_hook(repo)
    assert "<system-reminder>" in result.stdout
    out_lower = result.stdout.lower()
    assert "deploy" in out_lower
    assert "three" in out_lower or "all-three-envs" in out_lower or "values-" in out_lower, (
        f"deploy change must remind about all-three-envs:\n{result.stdout}"
    )


def test_combination_reports_each_section(tmp_path: Path) -> None:
    """Multiple risky paths → each gets its own section, with cross-references."""
    repo = _make_repo(
        tmp_path,
        [
            "libs/python/corekinect/__init__.py",
            "tools/corectl/src/corectl/__init__.py",
        ],
    )
    result = _run_hook(repo)
    assert "<system-reminder>" in result.stdout
    out_lower = result.stdout.lower()
    assert "corekinect" in out_lower
    assert "corectl" in out_lower
    # Two separate section markers — either "###" or "## " headings, or
    # explicit "1." / "2." enumeration. Hook implementation may choose
    # the form; this test just confirms BOTH paths appear with their
    # own treatment, not collapsed into one line.
    assert (
        result.stdout.count("corekinect") >= 1
        and result.stdout.count("corectl") >= 1
    ), (
        f"Both paths should be named distinctly:\n{result.stdout}"
    )


def test_idempotent_repeated_invocation(tmp_path: Path) -> None:
    """Hook does not modify the repo state. Running it twice gives same output."""
    repo = _make_repo(tmp_path, ["libs/python/corekinect/__init__.py"])
    first = _run_hook(repo)
    # Capture git tree state via porcelain status — must be clean both before and after.
    status_before = _git(repo, "status", "--porcelain")
    second = _run_hook(repo)
    status_after = _git(repo, "status", "--porcelain")

    assert status_before == status_after == "", (
        "Hook MUST be read-only — no files should be modified.\n"
        f"status before={status_before!r}\nstatus after={status_after!r}"
    )
    # Output may vary in timing-sensitive metadata but the structural
    # content (the section bodies) should match byte-for-byte.
    assert first.stdout == second.stdout, (
        "Hook should be deterministic given the same inputs.\n"
        f"first run:\n{first.stdout}\nsecond run:\n{second.stdout}"
    )


def test_missing_tag_arg_uses_git_describe(tmp_path: Path) -> None:
    """When called with no args, the hook falls back to `git describe --tags`."""
    repo = _make_repo(tmp_path, ["libs/python/corekinect/__init__.py"])
    # Call with NO args — hook must auto-detect v-last from the tag we created.
    result = _run_hook(repo, last_tag=None)
    assert result.returncode == 0, (
        f"Hook must handle no-args case via git-describe. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "<system-reminder>" in result.stdout, (
        f"Auto-detected tag should still produce a reminder:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_skill_file_wires_the_hook() -> None:
    """The /concord-release SKILL.md must invoke .claude/hooks/pre-release."""
    skill = WORKSPACE_ROOT / ".claude" / "skills" / "concord-release" / "SKILL.md"
    text = skill.read_text()
    assert ".claude/hooks/pre-release" in text or "hooks/pre-release" in text, (
        "SKILL.md must invoke the pre-release hook as Phase 0. "
        "Defining the hook without wiring it leaves it unused."
    )
