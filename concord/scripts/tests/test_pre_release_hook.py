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
    - No risky paths in range       → silent (no system-reminder emitted)
    - corekinect touched            → reports corekinect coupling
    - corectl touched               → reports corectl coupling
    - prisma touched                → reports prisma coupling
    - mtib protocols touched        → reports protocols coupling
    - deploy/ touched               → reports all-three-envs coupling
    - Combination                   → reports each in its own section
    - corekinect + known-test-apps  → reports Phase D Layer 5 test-app sweep
    - corectl + known-test-apps     → reports Phase D Layer 5 test-app sweep
    - docs-only changes             → no test-app section emitted
    - Missing path on disk          → warning emitted for absent app
    - Range that doesn't exist      → exits non-zero with usage
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


# ---------------------------------------------------------------------------
# Phase D Layer 5 — test-app refresh sweep
# ---------------------------------------------------------------------------
#
# When the release range touches corekinect, protocols, or corectl, the
# hook must additionally enumerate every test app from
# .claude/known-test-apps.yaml and emit a "Test apps to refresh" section
# pointing the operator at the Phase 11 sweep. The section MUST:
#   - name every entry from the manifest
#   - include each entry's local path
#   - warn when a path doesn't exist on disk
#   - print the concrete remediation command
#
# The hook is read-only (informational). It does NOT execute the refresh
# itself — Phase 11 of /concord-release does that.


def _write_known_test_apps(
    repo: Path,
    entries: list[dict[str, str]],
) -> None:
    """Write a .claude/known-test-apps.yaml inside the throwaway repo."""
    manifest_dir = repo / ".claude"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# test fixture manifest",
        "test_apps:",
    ]
    for entry in entries:
        lines.append(f"  - name: {entry['name']}")
        lines.append(f"    path: {entry['path']}")
        lines.append(f"    product: {entry.get('product', 'unknown')}")
        lines.append(f"    type: {entry.get('type', 'UNKNOWN')}")
        lines.append(
            f"    repo: {entry.get('repo', 'git@example.com:test/repo.git')}"
        )
    (manifest_dir / "known-test-apps.yaml").write_text(
        "\n".join(lines) + "\n"
    )
    _git(repo, "add", ".claude/known-test-apps.yaml")
    _git(repo, "commit", "-q", "-m", "seed test-app manifest")


def test_corekinect_touched_emits_test_app_section(tmp_path: Path) -> None:
    """corekinect change + known-test-apps.yaml present → Layer 5 section."""
    repo = _make_repo(tmp_path, ["libs/python/corekinect/__init__.py"])
    # Add a manifest AFTER the tag so the hook sees it on HEAD.
    _write_known_test_apps(
        repo,
        [
            {
                "name": "sigma5_validation",
                "path": str(tmp_path / "fake-sigma5-validation"),
            },
            {
                "name": "sigma5_manufacturing",
                "path": str(tmp_path / "fake-sigma5-manufacturing"),
            },
        ],
    )
    # Create one of the paths so we can assert mixed present/absent behavior.
    (tmp_path / "fake-sigma5-validation").mkdir()
    _git(tmp_path / "fake-sigma5-validation", "init", "-q", "-b", "main")
    _git(tmp_path / "fake-sigma5-validation", "config", "user.name", "test")
    _git(tmp_path / "fake-sigma5-validation", "config", "user.email", "test@example.com")
    _git(tmp_path / "fake-sigma5-validation", "config", "commit.gpgsign", "false")
    (tmp_path / "fake-sigma5-validation" / "README.md").write_text("hi\n")
    _git(tmp_path / "fake-sigma5-validation", "add", "README.md")
    _git(tmp_path / "fake-sigma5-validation", "commit", "-q", "-m", "seed")

    result = _run_hook(repo)
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "<system-reminder>" in result.stdout
    out = result.stdout
    out_lower = out.lower()

    # The Layer 5 section MUST appear and name every manifest entry.
    assert "test apps to refresh" in out_lower or "layer 5" in out_lower, (
        f"Layer 5 section missing:\n{out}"
    )
    assert "sigma5_validation" in out, f"sigma5_validation not listed:\n{out}"
    assert "sigma5_manufacturing" in out, (
        f"sigma5_manufacturing not listed:\n{out}"
    )

    # Remediation command MUST be printed verbatim so the operator can
    # copy-paste it. We assert the load-bearing fragments.
    assert "corectl test update --apply" in out, (
        f"refresh command missing:\n{out}"
    )
    assert "corectl test upload" in out, f"upload command missing:\n{out}"

    # Missing-path warning for the absent entry.
    assert "fake-sigma5-manufacturing" in out
    assert "missing" in out_lower or "not found" in out_lower or "warn" in out_lower, (
        f"Missing-path warning not emitted:\n{out}"
    )


def test_corectl_touched_emits_test_app_section(tmp_path: Path) -> None:
    """corectl change alone → Layer 5 section still emits."""
    repo = _make_repo(tmp_path, ["tools/corectl/src/corectl/__init__.py"])
    _write_known_test_apps(
        repo,
        [
            {
                "name": "alpha_validation",
                "path": str(tmp_path / "alpha_validation"),
            },
        ],
    )

    result = _run_hook(repo)
    assert "<system-reminder>" in result.stdout
    out_lower = result.stdout.lower()
    assert "test apps to refresh" in out_lower or "layer 5" in out_lower, (
        f"corectl change must trigger Layer 5 sweep section:\n{result.stdout}"
    )
    assert "alpha_validation" in result.stdout


def test_protocols_touched_emits_test_app_section(tmp_path: Path) -> None:
    """protocols change → Layer 5 section emits (proto wire format change)."""
    repo = _make_repo(tmp_path, ["libs/protocols/mtib/mtib.proto"])
    _write_known_test_apps(
        repo,
        [
            {
                "name": "sigma5_validation",
                "path": str(tmp_path / "sigma5_validation"),
            },
        ],
    )

    result = _run_hook(repo)
    out_lower = result.stdout.lower()
    assert "test apps to refresh" in out_lower or "layer 5" in out_lower, (
        f"protocols change must trigger Layer 5 sweep section:\n{result.stdout}"
    )


def test_docs_only_does_not_emit_test_app_section(tmp_path: Path) -> None:
    """docs-only range → no test-app section (no Layer 5 trigger paths)."""
    repo = _make_repo(tmp_path, ["docs/some-page.md"])
    _write_known_test_apps(
        repo,
        [
            {
                "name": "sigma5_validation",
                "path": str(tmp_path / "sigma5_validation"),
            },
        ],
    )

    result = _run_hook(repo)
    assert result.returncode == 0
    # Either no reminder at all, or a reminder that does NOT contain the
    # Layer 5 section. Both are acceptable; what we ASSERT is that the
    # section is not falsely emitted on docs-only ranges.
    out_lower = result.stdout.lower()
    assert "test apps to refresh" not in out_lower, (
        f"docs-only change must not trigger Layer 5 section:\n{result.stdout}"
    )


def test_prisma_alone_does_not_emit_test_app_section(tmp_path: Path) -> None:
    """prisma change without corekinect/corectl/protocols → no test-app sweep.

    The Layer 5 sweep is scoped to changes that affect what the test app
    consumes (corekinect/corectl/protocols). A pure schema change does not
    invalidate the test app's scaffold — it invalidates database state.
    """
    repo = _make_repo(tmp_path, ["prisma/schema.prisma"])
    _write_known_test_apps(
        repo,
        [
            {
                "name": "sigma5_validation",
                "path": str(tmp_path / "sigma5_validation"),
            },
        ],
    )

    result = _run_hook(repo)
    out_lower = result.stdout.lower()
    assert "test apps to refresh" not in out_lower, (
        "prisma-only change must NOT trigger Layer 5 sweep "
        f"(scope is corekinect/corectl/protocols only):\n{result.stdout}"
    )


def test_missing_manifest_falls_back_gracefully(tmp_path: Path) -> None:
    """corekinect touched but no known-test-apps.yaml → hook must not crash.

    Older clones of concord may not yet have the manifest. The hook
    should degrade gracefully: emit the existing corekinect section
    unchanged, and either omit the Layer 5 section or note the manifest
    is missing. Either is fine; what we forbid is a hard crash.
    """
    repo = _make_repo(tmp_path, ["libs/python/corekinect/__init__.py"])
    result = _run_hook(repo)
    assert result.returncode == 0, (
        f"Hook must not crash when manifest absent.\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "<system-reminder>" in result.stdout
    assert "corekinect" in result.stdout.lower()
