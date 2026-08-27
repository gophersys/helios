"""Phase D Layer 4 — runner-side framework-constraint gate.

The runner image bakes a specific corekinect version. The downloaded
test package's concord.yaml declares a `package.framework` constraint
(e.g., ">=0.9.0"). Before pytest invocation, the runner asserts that
its bundled corekinect satisfies the constraint. If not, pytest must
NOT start — the run would otherwise silently skip every test or
produce undefined behavior.

The check is **semver-compatible**, NOT strict-SHA. The active session
on panel 0AW2 (cmpn99zoa0088i6ahaxcz0tcq) ships a test package with
`framework: ">=0.9.0"`. The v0.12.4 runner has corekinect 0.12.4 →
0.12.4 satisfies >=0.9.0 → gate MUST pass.

The gate is implemented as a standalone Python script
deploy/runner/check_framework_constraint.py so it is unit-testable
without bash subprocess gymnastics. entrypoint.sh invokes it
post-extract, pre-pytest.

Contract:
    python3 check_framework_constraint.py <path-to-concord.yaml>

Inputs:
    - argv[1]: path to the extracted test package's concord.yaml
    - corekinect.__version__ (read by importing the module)
    - env CONCORD_FORCE_STALE_PACKAGE=1: escape hatch

Exits:
    0 — constraint satisfied (or missing/empty: warn + pass)
    1 — constraint violated
    2 — usage / manifest read / parse error
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = WORKSPACE_ROOT / "deploy" / "runner" / "check_framework_constraint.py"


# ---------------------------------------------------------------------------
# Harness — write a concord.yaml, invoke the script with a fake corekinect
# version via PYTHONPATH-injected shim.
# ---------------------------------------------------------------------------


def _make_corekinect_shim(tmp_path: Path, version: str) -> Path:
    """Create a throwaway `corekinect` package on PYTHONPATH that just
    exports `__version__`. The script imports `corekinect` to read
    `__version__`; this lets each test pin a specific version without
    rebuilding the real package.
    """
    shim_root = tmp_path / "pypath"
    shim_root.mkdir(exist_ok=True)
    pkg = shim_root / "corekinect"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n')
    return shim_root


def _write_concord_yaml(tmp_path: Path, *, framework: str | None = None, extras: str = "") -> Path:
    """Write a minimal concord.yaml at tmp_path/concord.yaml."""
    parts = ['schema: "1.0"', "", "package:"]
    parts.append('  type: manufacturing')
    parts.append('  version: "0.1.0"')
    if framework is not None:
        # Use a single-quoted YAML scalar to preserve operator chars.
        parts.append(f'  framework: "{framework}"')
    if extras:
        parts.append(extras)
    yaml_path = tmp_path / "concord.yaml"
    yaml_path.write_text("\n".join(parts) + "\n")
    return yaml_path


def _run_gate(
    tmp_path: Path,
    *,
    framework: str | None,
    runner_version: str,
    extra_env: dict[str, str] | None = None,
    yaml_path: Path | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the gate script with a stubbed corekinect on PYTHONPATH."""
    shim_root = _make_corekinect_shim(tmp_path, runner_version)
    if yaml_path is None:
        yaml_path = _write_concord_yaml(tmp_path, framework=framework)

    env = os.environ.copy()
    # Prepend the shim so it wins over any system-installed corekinect.
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{shim_root}{os.pathsep}{existing_pp}" if existing_pp else str(shim_root)
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(yaml_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_script_exists_and_is_executable() -> None:
    """Sanity: the gate script is at the contracted path."""
    assert SCRIPT_PATH.is_file(), f"Phase D Layer 4 script missing at {SCRIPT_PATH}"


def test_constraint_satisfied_passes(tmp_path: Path) -> None:
    """Standard pass: runner 0.12.4 satisfies >=0.9.0."""
    result = _run_gate(tmp_path, framework=">=0.9.0", runner_version="0.12.4")
    assert result.returncode == 0, (
        f"runner 0.12.4 must satisfy >=0.9.0. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "0.12.4" in combined or "0.12" in combined, (
        f"Pass message should name the runner version:\n{combined}"
    )
    assert ">=0.9.0" in combined, (
        f"Pass message should name the constraint:\n{combined}"
    )


def test_active_session_emulation_must_pass(tmp_path: Path) -> None:
    """SAFETY-CRITICAL: this is the tonight-manufacturing case.

    The active session's package has framework: ">=0.9.0" and the
    runner that will deploy with v0.12.4 has corekinect 0.12.4.
    If this test fails, the implementation is wrong — DO NOT COMMIT.
    """
    # Use the literal value from the live sigma5_manufacturing concord.yaml
    # (verified via Read of /home/mateo/work/manufacturing/sigma5_manufacturing/concord.yaml)
    result = _run_gate(tmp_path, framework=">=0.9.0", runner_version="0.12.4")
    assert result.returncode == 0, (
        "ACTIVE-SESSION EMULATION FAILED. "
        "framework='>=0.9.0' + runner 0.12.4 MUST PASS — this is what "
        "tonight's manufacturing depends on. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_constraint_violated_fails_with_error(tmp_path: Path) -> None:
    """Runner 0.8.0 vs >=1.0: gate must refuse."""
    result = _run_gate(tmp_path, framework=">=1.0", runner_version="0.8.0")
    assert result.returncode == 1, (
        f"runner 0.8.0 must NOT satisfy >=1.0. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    # The error message must include:
    #   the constraint (what was required)
    #   the runner version (what we have)
    #   the operator's next step
    assert ">=1.0" in combined, f"Error must name the constraint:\n{combined}"
    assert "0.8.0" in combined, f"Error must name the runner version:\n{combined}"
    assert (
        "refresh-framework" in combined
        or "rebuild" in combined.lower()
        or "upload" in combined.lower()
    ), f"Error must point at the fix (refresh-framework + upload):\n{combined}"


def test_runner_too_new_violates_upper_bound(tmp_path: Path) -> None:
    """Runner 1.0.0 vs <1.0,>=0.9: still a violation (upper bound)."""
    result = _run_gate(tmp_path, framework="<1.0,>=0.9", runner_version="1.0.0")
    assert result.returncode == 1, (
        f"runner 1.0.0 must NOT satisfy <1.0,>=0.9. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_compatible_release_operator_violates(tmp_path: Path) -> None:
    """~=0.12.0 means >=0.12.0,<0.13. Runner 0.13.0 fails."""
    result = _run_gate(tmp_path, framework="~=0.12.0", runner_version="0.13.0")
    assert result.returncode == 1, (
        f"runner 0.13.0 must NOT satisfy ~=0.12.0. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_force_stale_package_escape_hatch(tmp_path: Path) -> None:
    """CONCORD_FORCE_STALE_PACKAGE=1 converts a hard fail to a loud warn."""
    result = _run_gate(
        tmp_path,
        framework=">=1.0",
        runner_version="0.8.0",
        extra_env={"CONCORD_FORCE_STALE_PACKAGE": "1"},
    )
    assert result.returncode == 0, (
        f"Escape hatch must convert failure to pass. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "CONCORD_FORCE_STALE_PACKAGE" in combined, (
        f"Bypass usage must be logged:\n{combined}"
    )
    assert "override" in combined.lower() or "bypass" in combined.lower() or "force" in combined.lower(), (
        f"Bypass log must signal an explicit override:\n{combined}"
    )


def test_missing_constraint_warns_and_passes(tmp_path: Path) -> None:
    """No framework: key in concord.yaml (legacy schema-1.0 manifests).

    Warn + pass — we don't know the constraint, fall back to
    permissive. Documented in the knowledge file.
    """
    result = _run_gate(tmp_path, framework=None, runner_version="0.12.4")
    assert result.returncode == 0, (
        f"Missing constraint must warn + pass. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert (
        "no" in combined.lower() and "constraint" in combined.lower()
    ) or "missing" in combined.lower() or "absent" in combined.lower(), (
        f"Missing-constraint case must log a clear warning:\n{combined}"
    )


def test_malformed_constraint_errors(tmp_path: Path) -> None:
    """Bogus constraint string → exit 2 with parse error."""
    result = _run_gate(
        tmp_path,
        framework="hilarious garbage",
        runner_version="0.12.4",
    )
    assert result.returncode == 2, (
        f"Malformed constraint must exit 2. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "parse" in combined.lower() or "invalid" in combined.lower() or "malformed" in combined.lower(), (
        f"Parse-failure message must signal what went wrong:\n{combined}"
    )


def test_missing_manifest_errors(tmp_path: Path) -> None:
    """concord.yaml does not exist at the given path → exit 2."""
    shim_root = _make_corekinect_shim(tmp_path, "0.12.4")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(shim_root)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(tmp_path / "nonexistent.yaml")],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 2, (
        f"Missing manifest must exit 2. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_missing_argv_errors(tmp_path: Path) -> None:
    """No path argument → exit 2 with usage."""
    shim_root = _make_corekinect_shim(tmp_path, "0.12.4")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(shim_root)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "usage" in combined.lower(), f"Should print usage:\n{combined}"


def test_real_sigma5_manufacturing_concord_yaml(tmp_path: Path) -> None:
    """End-to-end against the literal sigma5_manufacturing concord.yaml.

    Copies the actual live manifest from
    /home/mateo/work/manufacturing/sigma5_manufacturing/concord.yaml,
    runs the gate against it with a stubbed corekinect 0.12.4. MUST pass.

    If this is skipped (manifest path doesn't exist), we still have
    test_active_session_emulation_must_pass covering the same case
    with a synthesized manifest.
    """
    live_yaml = Path("/home/mateo/work/manufacturing/sigma5_manufacturing/concord.yaml")
    if not live_yaml.is_file():
        pytest.skip(f"Live manifest not available at {live_yaml}")
    target = tmp_path / "concord.yaml"
    target.write_text(live_yaml.read_text())
    result = _run_gate(
        tmp_path,
        framework=None,  # ignored — we're using a real yaml_path
        runner_version="0.12.4",
        yaml_path=target,
    )
    assert result.returncode == 0, (
        "Real live sigma5_manufacturing concord.yaml must satisfy a v0.12.4 "
        "runner. If this fails, the manifest parser or the gate logic is "
        f"broken.\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert ">=0.9.0" in combined or "0.9.0" in combined, (
        f"Pass message should reflect the live manifest's constraint:\n{combined}"
    )


def test_entrypoint_invokes_the_gate() -> None:
    """The runner entrypoint must actually CALL the gate before pytest."""
    entrypoint = WORKSPACE_ROOT / "deploy" / "runner" / "entrypoint.sh"
    assert entrypoint.is_file()
    text = entrypoint.read_text()
    assert "check_framework_constraint.py" in text, (
        "deploy/runner/entrypoint.sh must invoke "
        "check_framework_constraint.py after the test package is "
        "extracted and BEFORE pytest is invoked. Defining the script "
        "without wiring it leaves the failure mode wide open."
    )


def test_entrypoint_invokes_gate_before_pytest() -> None:
    """The gate call must be positioned BEFORE the pytest exec, not after.

    Anchored on the actual pytest invocation (`python3 -m pytest` or
    `exec ... pytest`), not on any of the earlier comments / find
    invocations that incidentally contain the word "pytest".
    """
    import re

    entrypoint = WORKSPACE_ROOT / "deploy" / "runner" / "entrypoint.sh"
    text = entrypoint.read_text()
    gate_idx = text.find("check_framework_constraint.py")
    assert gate_idx >= 0, "gate not invoked at all (covered by other test)"

    # The real pytest invocation in entrypoint.sh is either:
    #   exec python3 -m pytest ...     (one-shot mode)
    #   python3 /app/run.py ...        (corekinect TestRunner that
    #                                   internally drives pytest)
    # Pick the earliest of those two — that's the boundary the gate
    # must precede.
    invocation_re = re.compile(r"(exec\s+python3\s+-m\s+pytest|exec\s+python3\s+/app/run\.py)")
    matches = [m.start() for m in invocation_re.finditer(text)]
    assert matches, (
        "could not locate the pytest / run.py invocation in entrypoint.sh "
        "— either the entrypoint shape changed or the test pattern is out "
        "of date."
    )
    first_invocation = min(matches)
    assert gate_idx < first_invocation, (
        "check_framework_constraint.py must run BEFORE the pytest / run.py "
        f"invocation (gate_idx={gate_idx}, first_invocation={first_invocation}). "
        "Otherwise a violating constraint still lets the tests start "
        "silently. Move the gate call up."
    )
