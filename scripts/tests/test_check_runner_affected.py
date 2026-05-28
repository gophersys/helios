"""Phase D Layer 3 — release-range gate: corekinect touched → runner rebuild.

The /concord-release skill must refuse to cut a release when:
  - the range $LAST_TAG..HEAD touches libs/python/corekinect/,
    libs/protocols/mtib/, or tools/corectl/, AND
  - `nx show projects --affected` for that range does NOT include
    `test-runner` (i.e., the runner image won't actually be rebuilt
    by the release's deploy step).

Escape hatch: CONCORD_FORCE_NO_RUNNER_REBUILD=1 downgrades the
hard-fail to a loud warn-and-continue.

This test file drives the standalone script
`scripts/release-gates/check-runner-affected.sh` via a hermetic
harness:
  - A throwaway git repo with synthetic commits seeds the diff range.
  - A `nx` stub on PATH returns whatever `affected` set we want.
  - The script is invoked with LAST_TAG and HEAD pointing at the
    throwaway repo.

The script is contract:
  Usage:   check-runner-affected.sh <last_tag> [<head_ref>]
  Env:     CONCORD_FORCE_NO_RUNNER_REBUILD=1 to bypass
           NX_AFFECTED_CMD (override the nx command for tests)
  Exit:    0 silent     — no paths-of-interest touched in range
           0 with info  — paths touched AND test-runner is affected
           0 with warn  — bypass via env var
           1            — paths touched AND test-runner NOT affected
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path
from typing import Iterable

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "release-gates" / "check-runner-affected.sh"


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    """Run git in `repo` and return stdout (raise on error)."""
    e = os.environ.copy()
    # Deterministic commit identities so tests don't depend on user config.
    e.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    if env:
        e.update(env)
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=repo,
        env=e,
        check=True,
    )
    return result.stdout


def _make_repo_with_range(tmp_path: Path, files_touched_in_range: Iterable[str]) -> Path:
    """Build a throwaway git repo:

        commit A: seeds VERSION + a placeholder file  (tagged 'v-last')
        commit B: touches each path in `files_touched_in_range` (HEAD)

    Returns the repo's root path. The tag 'v-last' is what tests pass
    as $LAST_TAG.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")

    # Commit A — seed
    (repo / "VERSION").write_text("0.12.3\n")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", "VERSION", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "tag", "v-last")

    # Commit B — touch the paths of interest (or unrelated paths)
    if not files_touched_in_range:
        # Make at least one commit so HEAD != tag, but touch nothing
        # relevant. The gate must treat this as "no paths of interest".
        (repo / "README.md").write_text("seed updated\n")
        _git(repo, "add", "README.md")
        _git(repo, "commit", "-q", "-m", "noop change")
    else:
        for relpath in files_touched_in_range:
            target = repo / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            # Append something deterministic
            existing = target.read_text() if target.exists() else ""
            target.write_text(existing + f"# touch {relpath}\n")
            _git(repo, "add", relpath)
        _git(repo, "commit", "-q", "-m", "touch paths")

    return repo


def _make_nx_stub(bin_dir: Path, affected_projects: Iterable[str]) -> None:
    """Write an `nx` stub that returns the given projects for `show projects --affected`.

    For all other args, the stub exits 0 with empty output (the gate
    must only depend on the `show projects --affected …` invocation).
    """
    body = textwrap.dedent(
        """
        # Stub nx — answers to `show projects --affected …` only.
        if [ "$1" = "show" ] && [ "$2" = "projects" ]; then
          # Anything after "--affected" is ignored; we emit a fixed list.
          PROJECTS="__PROJECTS__"
          for p in $PROJECTS; do
            echo "$p"
          done
          exit 0
        fi
        # Any other nx invocation is a test-author bug.
        echo "nx stub: unexpected args: $*" >&2
        exit 2
        """
    ).strip()
    body = body.replace("__PROJECTS__", " ".join(affected_projects))
    target = bin_dir / "nx"
    target.write_text("#!/usr/bin/env bash\n" + body + "\n")
    target.chmod(0o755)


def _run_gate(
    tmp_path: Path,
    *,
    files_touched_in_range: Iterable[str] = (),
    affected_projects: Iterable[str] = ("platform",),
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Build a throwaway repo + nx stub, invoke the gate script."""
    repo = _make_repo_with_range(tmp_path, files_touched_in_range)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_nx_stub(bin_dir, affected_projects)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        ["bash", str(SCRIPT_PATH), "v-last", "HEAD"],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_script_exists_and_is_executable() -> None:
    """Sanity: the gate script is at the contracted path and executable."""
    assert SCRIPT_PATH.is_file(), (
        f"Phase D Layer 3 script missing at {SCRIPT_PATH}. "
        "The /concord-release skill is supposed to call this script."
    )
    assert os.access(SCRIPT_PATH, os.X_OK), (
        f"{SCRIPT_PATH} is not executable. Run `chmod +x` and re-commit."
    )


def test_no_paths_of_interest_touched_in_range(tmp_path: Path) -> None:
    """Range touches only docs → exit 0 silent (no runner concern)."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("docs/foo.md",),
        affected_projects=("docs",),  # test-runner NOT in affected
    )
    assert result.returncode == 0, (
        f"Range with no paths of interest must pass. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    # Should not emit any failure-keywords.
    combined = result.stdout + result.stderr
    assert "FAIL" not in combined.upper() or "test-runner" not in combined.lower(), (
        f"Silent-pass case should not mention failure / test-runner:\n{combined}"
    )


def test_corekinect_touched_runner_in_affected_set(tmp_path: Path) -> None:
    """corekinect touched + test-runner is in the affected set → pass with info."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/python/corekinect/__init__.py",),
        affected_projects=("corekinect", "test-runner", "platform"),
    )
    assert result.returncode == 0, (
        f"corekinect touched + test-runner affected must pass. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    # The "OK" message must name what's about to be rebuilt so the
    # operator can confirm at a glance.
    assert "test-runner" in combined.lower(), (
        f"Info message should mention test-runner:\n{combined}"
    )
    assert "corekinect" in combined.lower() or "libs/python/corekinect" in combined.lower(), (
        f"Info message should name the touched path/project:\n{combined}"
    )


def test_corekinect_touched_runner_missing_from_affected_set(tmp_path: Path) -> None:
    """corekinect touched + test-runner NOT in affected → exit 1, name the gap."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/python/corekinect/__init__.py",),
        affected_projects=("corekinect", "platform"),  # test-runner absent
    )
    assert result.returncode == 1, (
        f"corekinect touched + test-runner missing must fail. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "test-runner" in combined.lower(), (
        f"Failure must name test-runner:\n{combined}"
    )
    assert "corekinect" in combined.lower() or "libs/python/corekinect" in combined.lower(), (
        f"Failure must name the touched path:\n{combined}"
    )
    assert "rebuild" in combined.lower(), (
        f"Failure must mention rebuild guidance:\n{combined}"
    )
    assert "CONCORD_FORCE_NO_RUNNER_REBUILD" in combined, (
        f"Failure must mention the escape-hatch env var:\n{combined}"
    )


def test_force_bypass_downgrades_failure_to_loud_warn(tmp_path: Path) -> None:
    """CONCORD_FORCE_NO_RUNNER_REBUILD=1 turns the fail-case into a pass+warn."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/python/corekinect/__init__.py",),
        affected_projects=("corekinect", "platform"),  # test-runner absent
        extra_env={"CONCORD_FORCE_NO_RUNNER_REBUILD": "1"},
    )
    assert result.returncode == 0, (
        f"Escape hatch must pass through. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "CONCORD_FORCE_NO_RUNNER_REBUILD" in combined, (
        f"Bypass usage must be logged:\n{combined}"
    )
    assert "force" in combined.lower() or "bypass" in combined.lower() or "override" in combined.lower(), (
        f"Bypass log must signal an explicit override:\n{combined}"
    )


def test_corectl_touched_runner_missing(tmp_path: Path) -> None:
    """corectl touched alone also triggers the gate."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("tools/corectl/src/corectl/__init__.py",),
        affected_projects=("corectl", "platform"),  # test-runner absent
    )
    assert result.returncode == 1, (
        f"corectl touched + test-runner missing must fail. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "test-runner" in combined.lower(), combined


def test_protocols_mtib_touched_runner_missing(tmp_path: Path) -> None:
    """libs/protocols/mtib touched alone also triggers the gate."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/protocols/mtib/mtib.proto",),
        affected_projects=("protocols", "platform"),  # test-runner absent
    )
    assert result.returncode == 1, (
        f"protocols/mtib touched + test-runner missing must fail. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "test-runner" in combined.lower(), combined
    assert "protocols" in combined.lower() or "mtib" in combined.lower(), combined


def test_protocols_mtib_touched_runner_present_mtib_server_missing(tmp_path: Path) -> None:
    """Proto changed + test-runner rebuilt BUT mtib-server NOT affected →
    fail. This is the exact gap that caused the HealthCheck/UartStream
    UNIMPLEMENTED outage: the runner was rebuilt, the edge server wasn't.
    """
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/protocols/mtib/mtib.proto",),
        affected_projects=("protocols", "test-runner", "platform"),  # mtib-server absent
    )
    assert result.returncode == 1, (
        f"proto touched + mtib-server missing must fail even when test-runner "
        f"IS rebuilt. stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "mtib-server" in combined.lower(), f"Failure must name mtib-server:\n{combined}"
    assert "CONCORD_FORCE_NO_MTIB_REBUILD" in combined, (
        f"Failure must mention the mtib escape hatch:\n{combined}"
    )


def test_protocols_mtib_touched_both_runner_and_mtib_present(tmp_path: Path) -> None:
    """Proto changed + BOTH test-runner and mtib-server affected → pass."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/protocols/mtib/mtib.proto",),
        affected_projects=("protocols", "test-runner", "mtib-server", "platform"),
    )
    assert result.returncode == 0, (
        f"proto touched + both rebuilt must pass. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "mtib-server" in combined.lower(), (
        f"OK message should confirm the mtib-server rebuild:\n{combined}"
    )


def test_mtib_force_bypass_downgrades_to_warn(tmp_path: Path) -> None:
    """CONCORD_FORCE_NO_MTIB_REBUILD=1 turns the mtib fail-case into pass+warn."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/protocols/mtib/mtib.proto",),
        affected_projects=("protocols", "test-runner", "platform"),  # mtib-server absent
        extra_env={"CONCORD_FORCE_NO_MTIB_REBUILD": "1"},
    )
    assert result.returncode == 0, (
        f"mtib escape hatch must pass through. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "CONCORD_FORCE_NO_MTIB_REBUILD" in combined, (
        f"Bypass usage must be logged:\n{combined}"
    )


def test_corekinect_only_change_does_not_require_mtib_server(tmp_path: Path) -> None:
    """A corekinect-only change (no proto) requires test-runner but NOT
    mtib-server — the mtib gate is scoped to libs/protocols/mtib/ changes.
    """
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("libs/python/corekinect/__init__.py",),
        affected_projects=("corekinect", "test-runner", "platform"),  # mtib-server absent — fine
    )
    assert result.returncode == 0, (
        f"corekinect-only + test-runner present must pass without requiring "
        f"mtib-server. stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_unrelated_path_unrelated_affected_set(tmp_path: Path) -> None:
    """A frontend-only change must not trigger the gate at all."""
    result = _run_gate(
        tmp_path,
        files_touched_in_range=("apps/frontend/app/src/lib/foo.ts",),
        affected_projects=("app",),  # test-runner NOT in affected, but gate doesn't care
    )
    assert result.returncode == 0, (
        f"Unrelated change must pass silently. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_missing_last_tag_argument(tmp_path: Path) -> None:
    """Missing $LAST_TAG arg → usage error, exit non-zero."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_nx_stub(bin_dir, [])
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode != 0, "Missing arg must error"
    assert "usage" in (result.stdout + result.stderr).lower(), (
        f"Should print usage:\n{result.stdout}\n{result.stderr}"
    )


def test_nx_failure_treated_as_inconclusive(tmp_path: Path) -> None:
    """If `nx show projects --affected` itself fails (e.g., submodule mount
    prevents git diff from running), the gate must NOT hard-fail.

    Hard-failing in that case would be a false positive: the operator
    can't tell if test-runner would have been affected or not. Instead,
    log a clear warning, pass through, and rely on Phase 9/10 visual
    verification. This mirrors Layer 2's "missing local image → warn +
    pass" behavior for consistency.
    """
    repo = _make_repo_with_range(
        tmp_path,
        ["libs/python/corekinect/__init__.py"],  # paths of interest
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # nx stub that exits non-zero with a recognizable git-error message
    failing_nx = bin_dir / "nx"
    failing_nx.write_text(
        '#!/usr/bin/env bash\n'
        'echo " NX   Command failed: git diff --name-only" >&2\n'
        'echo "fatal: not a git repository" >&2\n'
        'exit 1\n'
    )
    failing_nx.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "v-last", "HEAD"],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"Nx failure must be treated as inconclusive (pass through, not "
        f"hard fail). stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "inconclusive" in combined.lower() or "failed to run" in combined.lower(), (
        f"Inconclusive case must surface the failure clearly:\n{combined}"
    )
    # The operator-action banner must point at Phase 9/10 visual verification.
    assert "test-runner" in combined.lower() or "cmd_build" in combined.lower() or "rebuild" in combined.lower(), (
        f"Inconclusive log must tell the operator how to verify manually:\n{combined}"
    )


def test_skill_file_invokes_the_gate_script() -> None:
    """The /concord-release SKILL.md must actually CALL the script."""
    skill = WORKSPACE_ROOT / ".claude" / "skills" / "concord-release" / "SKILL.md"
    assert skill.is_file(), f"SKILL.md not found at {skill}"
    text = skill.read_text()
    assert "check-runner-affected.sh" in text, (
        ".claude/skills/concord-release/SKILL.md must invoke the gate "
        "script. Defining the script without wiring it into the skill "
        "leaves the failure mode wide open at release time."
    )
