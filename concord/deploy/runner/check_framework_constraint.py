#!/usr/bin/env python3
"""Phase D Layer 4 — runner-side framework-constraint gate.

The test runner Docker image bakes a specific corekinect version. The
downloaded test package's concord.yaml declares a
`package.framework` constraint (e.g., ">=0.9.0"). Before pytest is
invoked, this script asserts that the bundled corekinect satisfies
the constraint. If not, pytest must NOT start — the run would
otherwise silently skip every test or produce undefined behaviour.

The check is **semver-compatible**, NOT strict-SHA. The active
manufacturing session ships a package with
`framework: ">=0.9.0"`; a v0.12.4 runner with `corekinect.__version__
== "0.12.4"` satisfies that constraint and must pass through.

Usage:
    python3 check_framework_constraint.py <path-to-concord.yaml>

Env:
    CONCORD_FORCE_STALE_PACKAGE=1   bypass the gate (loud-warn)

Exits:
    0 — constraint satisfied (or missing/empty: warn + pass)
    1 — constraint violated
    2 — usage / manifest read / parse error

The full design is in .claude/knowledge/deploy/runner.md (Layer 4).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ANSI colours mirror deploy/ctl.sh so the operator's terminal looks
# consistent across the four layers. Disable when not on a TTY (e.g.,
# when the runner pod's logs are scraped by fluentd).
if sys.stderr.isatty():
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"
else:
    RED = GREEN = YELLOW = CYAN = NC = ""


def _err(msg: str) -> None:
    print(f"{RED}[framework-gate]{NC} {msg}", file=sys.stderr, flush=True)


def _warn(msg: str) -> None:
    print(f"{YELLOW}[framework-gate]{NC} {msg}", flush=True)


def _info(msg: str) -> None:
    print(f"{CYAN}[framework-gate]{NC} {msg}", flush=True)


def _ok(msg: str) -> None:
    print(f"{GREEN}[framework-gate]{NC} {msg}", flush=True)


# Exit codes — keep in sync with the test file.
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_ERROR = 2

# Fix-instruction text — appears in both the failure path and the
# bypass-banner so operators always see what to do.
REMEDIATION = (
    "  To fix: re-publish the test package against the new framework:\n"
    "    corectl test refresh-framework\n"
    "    corectl test upload\n"
    "  Then redeploy the runner image so the new package's runs pick"
    " up the satisfied constraint."
)


def _usage(error: str = "") -> int:
    if error:
        _err(error)
    print(
        "Usage: check_framework_constraint.py <path-to-concord.yaml>\n"
        "\n"
        "Asserts that the runner's bundled corekinect version satisfies\n"
        "the test package's package.framework constraint. Run AFTER\n"
        "extracting the test package and BEFORE invoking pytest.\n"
        "\n"
        "Env:\n"
        "  CONCORD_FORCE_STALE_PACKAGE=1   bypass the gate (loud-warn)\n",
        file=sys.stderr,
    )
    return EXIT_ERROR


def _load_constraint(manifest_path: Path) -> str | None:
    """Return the `package.framework` constraint string from concord.yaml,
    or None if absent / empty. Raises RuntimeError on a malformed file.
    """
    try:
        import yaml  # PyYAML — already in runner requirements.txt
    except ImportError as exc:  # pragma: no cover — would only trigger if requirements drift
        raise RuntimeError(
            "PyYAML is not installed in the runner image. Add 'pyyaml' to "
            "deploy/runner/requirements.txt."
        ) from exc

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"failed to load {manifest_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"{manifest_path}: top-level YAML must be a mapping, got "
            f"{type(data).__name__}"
        )

    package = data.get("package")
    if package is None:
        return None
    if not isinstance(package, dict):
        raise RuntimeError(
            f"{manifest_path}: `package` must be a mapping, got "
            f"{type(package).__name__}"
        )

    constraint = package.get("framework")
    if constraint is None:
        # Older v1 manifests didn't have this key. Treat as absent.
        return None
    if not isinstance(constraint, str):
        raise RuntimeError(
            f"{manifest_path}: `package.framework` must be a string, got "
            f"{type(constraint).__name__}"
        )
    stripped = constraint.strip()
    return stripped or None


def _read_runner_version() -> str:
    """Return `corekinect.__version__` from the runner-image-baked package.

    Raises RuntimeError if corekinect can't be imported (e.g., the runner
    is fundamentally broken).
    """
    try:
        import corekinect  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "corekinect cannot be imported. The runner image is misbuilt; "
            "see Phase D Layer 1 (deploy/runner/project.json "
            "implicitDependencies) and Layer 2 (ctl.sh runner SHA gate)."
        ) from exc

    version = getattr(corekinect, "__version__", None)
    if not isinstance(version, str) or not version:
        raise RuntimeError(
            f"corekinect.__version__ is missing or invalid (got "
            f"{version!r}). The runner image's baked corekinect package "
            "is broken."
        )
    return version


def _parse_specifier(spec_str: str):
    """Parse a PEP 440 specifier set. Raises ValueError on garbage."""
    try:
        from packaging.specifiers import SpecifierSet, InvalidSpecifier
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "packaging is not installed in the runner image. Add "
            "'packaging>=21.0' to deploy/runner/requirements.txt."
        ) from exc

    try:
        return SpecifierSet(spec_str)
    except InvalidSpecifier as exc:
        raise ValueError(
            f"package.framework value {spec_str!r} is not a valid PEP 440 "
            f"specifier set: {exc}"
        ) from exc


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _usage("missing required argument: <path-to-concord.yaml>")

    manifest_path = Path(argv[1])
    if not manifest_path.is_file():
        _err(f"concord.yaml not found at {manifest_path}")
        _err(
            "  This is invoked AFTER the test package is extracted. If "
            "the file isn't there, the extract step (Step 2 in "
            "entrypoint.sh) failed or wrote to a different location."
        )
        return EXIT_ERROR

    # Read the runner-baked corekinect version first; if corekinect is
    # missing entirely the rest of the run is moot.
    try:
        runner_version = _read_runner_version()
    except RuntimeError as exc:
        _err(str(exc))
        return EXIT_ERROR

    # Read the constraint from the manifest.
    try:
        constraint = _load_constraint(manifest_path)
    except RuntimeError as exc:
        _err(f"manifest parse error: {exc}")
        return EXIT_ERROR

    if constraint is None:
        _warn(
            f"no framework constraint declared in {manifest_path.name} "
            f"(package.framework absent or empty)."
        )
        _warn(
            "  Legacy v1 manifests didn't carry this field. Falling back "
            "to permissive — running pytest with whatever corekinect the "
            f"runner image baked in ({runner_version})."
        )
        _warn(
            "  To enable the gate for this package, add "
            "`package.framework: \">=X.Y.Z\"` to its concord.yaml and "
            "re-upload."
        )
        return EXIT_OK

    # Parse the constraint.
    try:
        spec = _parse_specifier(constraint)
    except ValueError as exc:
        _err(f"malformed framework constraint: {exc}")
        return EXIT_ERROR
    except RuntimeError as exc:  # pragma: no cover
        _err(str(exc))
        return EXIT_ERROR

    # Evaluate. `packaging.specifiers.SpecifierSet.contains` ignores
    # pre-releases by default; pass `prereleases=True` so a runner like
    # "0.12.4rc1" would still be evaluated. We don't ship pre-releases
    # today but the policy choice matters.
    if spec.contains(runner_version, prereleases=True):
        _ok(
            f"test package framework constraint {constraint!r} satisfied "
            f"by corekinect {runner_version}"
        )
        return EXIT_OK

    # Violation. Either escape-hatch or fail.
    if os.environ.get("CONCORD_FORCE_STALE_PACKAGE", "0") == "1":
        _warn("═══════════════════════════════════════════════════════════════════")
        _warn("  CONCORD_FORCE_STALE_PACKAGE=1 — bypassing framework gate")
        _warn(f"  test package requires corekinect {constraint!r}")
        _warn(f"  runner has corekinect {runner_version}")
        _warn("  This is an explicit override. The test run WILL execute against")
        _warn("  a corekinect version that the package was not validated against.")
        _warn("  You have been warned.")
        _warn("═══════════════════════════════════════════════════════════════════")
        return EXIT_OK

    _err(
        f"runner-side framework constraint violated: test package requires "
        f"corekinect {constraint!r}, runner has {runner_version}."
    )
    _err("")
    _err(
        "  Running pytest now would either silently skip every test "
        "(corekinect.test.autoconf.load_manifest no-op path) or "
        "produce undefined behaviour. Refusing to start."
    )
    _err("")
    _err(REMEDIATION)
    _err("")
    _err(
        "  Or, if you intentionally want to run anyway "
        "(e.g., emergency triage), set:"
    )
    _err("    CONCORD_FORCE_STALE_PACKAGE=1")
    _err("  Loud warning will be logged.")
    return EXIT_VIOLATION


if __name__ == "__main__":
    sys.exit(main(sys.argv))
