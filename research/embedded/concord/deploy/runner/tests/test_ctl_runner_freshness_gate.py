"""Phase D Layer 2 — ctl.sh baked-SHA gate for the runner image.

Before `cmd_update` deploys, the runner image's bundled corekinect git
SHA must match the workspace's HEAD for `libs/python/corekinect/`. If
they diverge, the running pods would execute stale corekinect against
freshly published test packages — the v0.12.0->0.12.3 skew failure mode.

Contract pinned by this test file:

  1. `_corekinect_sha` produces a deterministic SHA for the
     `libs/python/corekinect/` tree at HEAD.
  2. `_check_runner_corekinect_freshness <env>` is a function in
     `deploy/ctl.sh`.
  3. Gate behavior:
     a. Baked SHA == workspace SHA  → pass silently.
     b. Baked SHA != workspace SHA  → fail (exit 1) with a clear
                                       message naming the diff.
     c. No baked SHA in image      → warn loudly, pass through
                                       (legacy image, opt-in until
                                       v0.12.4 rebuilds everywhere).
     d. Image not present locally   → warn, pass through (push from
                                       another node).
     e. With CONCORD_FORCE_STALE_RUNNER=1, the diverged case still
        passes but logs the escape-hatch usage prominently.

Tests drive the gate via a sourcing harness that stubs `docker`,
`git`, and `kubectl` so the gate runs hermetic against a fake image.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
CTL_SH = WORKSPACE_ROOT / "deploy" / "ctl.sh"


# ---------------------------------------------------------------------------
# Test harness — invoke the gate function from ctl.sh with stubs in PATH
# ---------------------------------------------------------------------------

HARNESS_SOURCE = """
# Source ctl.sh in library mode — its dispatcher is guarded by a
# BASH_SOURCE check + the CONCORD_CTL_NO_DISPATCH sentinel.
export CONCORD_CTL_NO_DISPATCH=1
set +e
set +u
set +o pipefail

source __CTL_SH__

# Drop strict mode for the harness body so a failing gate doesn't kill
# the script before we print GATE_EXIT.
set +e
set +u
set +o pipefail

# The gate's call site:
_check_runner_corekinect_freshness "__ENV__"
echo "GATE_EXIT=$?"
"""


def _make_stub(path: Path, name: str, body: str) -> None:
    """Write an executable shell stub at `path/name` with the given body."""
    target = path / name
    target.write_text("#!/usr/bin/env bash\n" + body + "\n")
    target.chmod(0o755)


def _run_gate(
    tmp_path: Path,
    *,
    env_name: str = "staging",
    workspace_sha: str = "abc123",
    baked_sha: str | None = "abc123",
    image_present: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the gate via a harness shell with stubs in PATH.

    `baked_sha=None` simulates the legacy-image case (env var absent).
    `image_present=False` simulates `docker image inspect` returning
    non-zero (image not on the local node).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)

    # `git` stub: respond to `rev-parse HEAD libs/python/corekinect`
    # and `ls-tree -d HEAD libs/python/corekinect` consistently.
    _make_stub(
        bin_dir,
        "git",
        textwrap.dedent(
            f"""
            # Args: $@
            case "$1 $2" in
              "rev-parse HEAD")
                # Used by other helpers in ctl.sh; return a fake repo SHA.
                echo "repohead00000000"
                ;;
              "rev-parse --short")
                echo "repohead"
                ;;
              "rev-parse --abbrev-ref")
                echo "test-branch"
                ;;
              "log -1")
                # `git log -1 --format=%H -- libs/python/corekinect/`
                echo "{workspace_sha}"
                ;;
              "ls-tree -d")
                # `git ls-tree -d HEAD libs/python/corekinect`
                echo "040000 tree {workspace_sha}\tlibs/python/corekinect"
                ;;
              "status --porcelain")
                ;;
              *)
                # Fall through silently — gate must not depend on unmocked args.
                ;;
            esac
            exit 0
            """
        ).strip(),
    )

    # `docker` stub: respond to `image inspect`.
    if image_present:
        if baked_sha is None:
            # Legacy image — no COREKINECT_GIT_SHA env var present.
            inspect_output = (
                '[{"Config":{"Env":["GIT_COMMIT=oldrunner","APP_VERSION=0.12.3"]}}]'
            )
        else:
            inspect_output = (
                '[{"Config":{"Env":['
                '"GIT_COMMIT=runnerbuild",'
                f'"COREKINECT_GIT_SHA={baked_sha}",'
                '"APP_VERSION=0.12.4"'
                ']}}]'
            )
        _make_stub(
            bin_dir,
            "docker",
            textwrap.dedent(
                f"""
                if [ "$1" = "image" ] && [ "$2" = "inspect" ]; then
                  cat <<'JSON'
{inspect_output}
JSON
                  exit 0
                fi
                exit 0
                """
            ).strip(),
        )
    else:
        _make_stub(
            bin_dir,
            "docker",
            'if [ "$1" = "image" ] && [ "$2" = "inspect" ]; then exit 1; fi\nexit 0',
        )

    # `kubectl` stub — not directly used by the gate but ctl.sh imports
    # may call it during sourcing. Return harmless success.
    _make_stub(bin_dir, "kubectl", "exit 0")

    # `helm` stub for the same reason.
    _make_stub(bin_dir, "helm", "exit 0")

    # Compose the harness script.
    harness = HARNESS_SOURCE.replace("__CTL_SH__", str(CTL_SH)).replace(
        "__ENV__", env_name
    )
    harness_path = tmp_path / "harness.sh"
    harness_path.write_text(harness)

    # PATH: stubs first, then the real PATH so common utilities (sed, awk,
    # date, etc.) still resolve.
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        ["bash", str(harness_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ctl_sh_exists() -> None:
    """Sanity: ctl.sh is where we expect it."""
    assert CTL_SH.is_file(), f"ctl.sh not found at {CTL_SH}"


def test_corekinect_sha_helper_defined_in_ctl_sh() -> None:
    """The helper that computes the workspace's corekinect SHA must exist."""
    content = CTL_SH.read_text()
    assert "_corekinect_sha()" in content or "_corekinect_sha ()" in content, (
        "deploy/ctl.sh must define a `_corekinect_sha` shell function that "
        "returns a deterministic SHA for libs/python/corekinect/ at HEAD."
    )


def test_runner_freshness_gate_function_defined() -> None:
    """The freshness-gate function must exist by the contracted name."""
    content = CTL_SH.read_text()
    assert "_check_runner_corekinect_freshness" in content, (
        "deploy/ctl.sh must define `_check_runner_corekinect_freshness <env>`."
    )


def test_gate_passes_when_shas_match(tmp_path: Path) -> None:
    """Baked SHA == workspace SHA → exit 0, no warning chatter."""
    sha = "deadbeef" * 5  # 40-char fake SHA
    result = _run_gate(tmp_path, workspace_sha=sha, baked_sha=sha)
    assert "GATE_EXIT=0" in result.stdout, (
        f"Gate must pass when SHAs match. stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    # No "diverged" complaints in the matched case.
    combined = result.stdout + result.stderr
    assert "diverged" not in combined.lower(), (
        f"Matching-SHA case should not log divergence:\n{combined}"
    )


def test_gate_fails_when_shas_diverge(tmp_path: Path) -> None:
    """Baked SHA != workspace SHA → exit 1, message names the drift."""
    result = _run_gate(
        tmp_path,
        workspace_sha="newsha" + "0" * 34,
        baked_sha="oldsha" + "0" * 34,
    )
    assert "GATE_EXIT=1" in result.stdout, (
        f"Gate must fail when SHAs diverge. stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "stale" in combined.lower() or "drift" in combined.lower() or "diverged" in combined.lower(), (
        f"Failure message must signal drift/stale state:\n{combined}"
    )
    # Must mention the escape hatch so the operator knows how to bypass.
    assert "CONCORD_FORCE_STALE_RUNNER" in combined, (
        f"Failure message must reference the escape-hatch env var:\n{combined}"
    )


def test_gate_warns_then_passes_on_legacy_image(tmp_path: Path) -> None:
    """Image with no COREKINECT_GIT_SHA env var (pre-v0.12.4) → warn + pass.

    This is the SAFETY-CRITICAL case: the currently deployed runner at
    v0.12.3 does not have the SHA baked in. The gate must NOT block the
    first v0.12.4 update on this image — it must warn and pass through.
    """
    result = _run_gate(tmp_path, workspace_sha="any" + "0" * 37, baked_sha=None)
    assert "GATE_EXIT=0" in result.stdout, (
        f"Legacy image (no baked SHA) must pass through. stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "legacy" in combined.lower() or "no baked" in combined.lower() or "missing" in combined.lower(), (
        f"Legacy case must log a warning so it's visible:\n{combined}"
    )


def test_gate_warns_then_passes_when_image_not_present(tmp_path: Path) -> None:
    """`docker image inspect` failure → warn + pass.

    The image may live only on the registry / another node. The gate is
    a best-effort check at the local node — don't refuse the deploy just
    because the image isn't cached locally.
    """
    result = _run_gate(tmp_path, image_present=False)
    assert "GATE_EXIT=0" in result.stdout, (
        f"Missing-local-image case must pass through. stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )


def test_force_stale_runner_escape_hatch(tmp_path: Path) -> None:
    """CONCORD_FORCE_STALE_RUNNER=1 must convert a hard fail to a loud warn."""
    result = _run_gate(
        tmp_path,
        workspace_sha="new" + "0" * 37,
        baked_sha="old" + "0" * 37,
        extra_env={"CONCORD_FORCE_STALE_RUNNER": "1"},
    )
    assert "GATE_EXIT=0" in result.stdout, (
        f"Escape hatch must downgrade failure to a pass. stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    # The bypass must be screamingly obvious in logs.
    assert "CONCORD_FORCE_STALE_RUNNER" in combined, (
        f"Escape-hatch usage must be logged:\n{combined}"
    )
    assert "force" in combined.lower() or "bypass" in combined.lower() or "override" in combined.lower(), (
        f"Escape-hatch log must signal that a guardrail was bypassed:\n{combined}"
    )


def test_gate_invoked_from_cmd_update() -> None:
    """The gate must actually be called by `cmd_update`, not defined and ignored."""
    content = CTL_SH.read_text()
    # Extract the cmd_update function body — `cmd_update() { ... }` block.
    start = content.find("cmd_update() {")
    assert start >= 0, "cmd_update function not found in ctl.sh"
    # Find the matching closing brace at column 0 (function-level).
    end = content.find("\n}\n", start)
    assert end > start, "cmd_update body not delimited as expected"
    body = content[start:end]
    assert "_check_runner_corekinect_freshness" in body, (
        "cmd_update must invoke `_check_runner_corekinect_freshness` before "
        "deploying. Defining the gate function without calling it leaves "
        "the failure mode wide open."
    )
