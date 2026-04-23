#!/usr/bin/env python3
"""Release gate -- bundles all preflight checks into a single go/no-go.

Usage:
    python scripts/release_gate.py [--override --reason "justification"]

Checks:
    1. Clean working tree (no uncommitted changes)
    2. On correct branch (main or release/*)
    3. VERSION file exists and is valid semver
    4. Backend tests pass
    5. Frontend typecheck passes
    6. No P0/critical open error reports
    7. Prisma schema files are in sync
    8. Helm values have all required keys for both envs

Output: JSON report with check results.
Exit: 0 = all passed (or overridden), 1 = blocked.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Optional

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    duration_ms: int = 0


@dataclass
class GateReport:
    version: str
    commit_sha: str
    checks: list[CheckResult]
    overall: str  # "passed" | "failed" | "overridden"
    override_reason: Optional[str] = None


def _run_timed(fn) -> CheckResult:
    """Run a check function and record its wall-clock duration."""
    start = time.monotonic()
    result = fn()
    elapsed_ms = int((time.monotonic() - start) * 1000)
    result.duration_ms = elapsed_ms
    return result


def check_clean_worktree() -> CheckResult:
    """Check that the git working tree has no uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            return CheckResult(
                name="clean_worktree",
                passed=False,
                message=f"Working tree is dirty: {len(result.stdout.strip().splitlines())} modified files",
            )
        return CheckResult(
            name="clean_worktree", passed=True, message="Working tree is clean"
        )
    except subprocess.CalledProcessError as e:
        return CheckResult(
            name="clean_worktree",
            passed=False,
            message=f"Git error: {e}",
        )


def check_branch() -> CheckResult:
    """Check that current branch is main or release/*."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        if branch == "main" or branch.startswith("release/"):
            return CheckResult(
                name="branch",
                passed=True,
                message=f"On allowed branch: {branch}",
            )
        return CheckResult(
            name="branch",
            passed=False,
            message=f"On branch '{branch}' -- must be 'main' or 'release/*'",
        )
    except subprocess.CalledProcessError as e:
        return CheckResult(
            name="branch", passed=False, message=f"Git error: {e}"
        )


def check_version_file(repo_root: Optional[str] = None) -> CheckResult:
    """Check that VERSION file exists and contains valid semver."""
    if repo_root is None:
        repo_root = os.getcwd()
    version_path = os.path.join(repo_root, "VERSION")
    if not os.path.isfile(version_path):
        return CheckResult(
            name="version_file",
            passed=False,
            message="VERSION file not found",
        )
    with open(version_path) as f:
        content = f.read().strip()
    if not SEMVER_PATTERN.match(content):
        return CheckResult(
            name="version_file",
            passed=False,
            message=f"VERSION file contains invalid semver: '{content}'",
        )
    return CheckResult(
        name="version_file",
        passed=True,
        message=f"VERSION: {content}",
    )


def check_backend_tests() -> CheckResult:
    """Run backend tests via nx."""
    try:
        result = subprocess.run(
            ["npx", "nx", "test", "http-api"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return CheckResult(
                name="backend_tests",
                passed=True,
                message="Backend tests passed",
            )
        return CheckResult(
            name="backend_tests",
            passed=False,
            message=f"Backend tests failed (exit {result.returncode})",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="backend_tests",
            passed=False,
            message="Backend tests timed out (300s)",
        )
    except FileNotFoundError:
        return CheckResult(
            name="backend_tests",
            passed=False,
            message="npx/nx not found -- cannot run tests",
        )


def check_frontend_typecheck() -> CheckResult:
    """Run frontend typecheck via nx."""
    try:
        result = subprocess.run(
            ["npx", "nx", "typecheck", "app"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return CheckResult(
                name="frontend_typecheck",
                passed=True,
                message="Frontend typecheck passed",
            )
        return CheckResult(
            name="frontend_typecheck",
            passed=False,
            message=f"Frontend typecheck failed (exit {result.returncode})",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="frontend_typecheck",
            passed=False,
            message="Frontend typecheck timed out (120s)",
        )
    except FileNotFoundError:
        return CheckResult(
            name="frontend_typecheck",
            passed=False,
            message="npx/nx not found -- cannot typecheck",
        )


def check_critical_bugs() -> CheckResult:
    """Check for P0/critical open issues. Placeholder -- always passes."""
    return CheckResult(
        name="critical_bugs",
        passed=True,
        message="No critical bug tracking integration configured (placeholder)",
    )


def check_schema_sync() -> CheckResult:
    """Check that Prisma schema and generated client are in sync."""
    try:
        result = subprocess.run(
            ["npx", "prisma", "migrate", "status"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return CheckResult(
                name="schema_sync",
                passed=True,
                message="Prisma schema is in sync",
            )
        return CheckResult(
            name="schema_sync",
            passed=False,
            message=f"Prisma schema out of sync: {result.stderr.strip()[:200]}",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return CheckResult(
            name="schema_sync",
            passed=False,
            message="Could not verify Prisma schema sync",
        )


def check_helm_values() -> CheckResult:
    """Check that both Helm values files exist and have required top-level keys."""
    required_keys = ["image", "httpApi", "frontend"]
    helm_dir = os.path.join("deploy", "production", "helm")
    issues = []

    for env in ["staging", "production"]:
        path = os.path.join(helm_dir, f"values-{env}.yaml")
        if not os.path.isfile(path):
            issues.append(f"Missing {path}")
            continue
        with open(path) as f:
            content = f.read()
        for key in required_keys:
            # Simple check: key appears at root level (no indent, followed by colon)
            if not re.search(rf"^{key}:", content, re.MULTILINE):
                issues.append(f"{env}: missing top-level key '{key}'")

    if issues:
        return CheckResult(
            name="helm_values",
            passed=False,
            message="; ".join(issues),
        )
    return CheckResult(
        name="helm_values",
        passed=True,
        message="Helm values files present with required keys",
    )


def get_commit_sha() -> str:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def get_version() -> str:
    """Read version from VERSION file."""
    try:
        with open("VERSION") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def run_gate(
    override: bool = False,
    reason: str = "",
    skip_slow: bool = False,
) -> GateReport:
    """Run all gate checks and produce a report.

    Args:
        override: If True and reason is provided, mark as overridden instead of failed.
        reason: Required justification when override is True.
        skip_slow: If True, skip tests and typecheck (for fast local runs).
    """
    checks = [
        _run_timed(check_clean_worktree),
        _run_timed(check_branch),
        _run_timed(check_version_file),
    ]

    if not skip_slow:
        checks.extend(
            [
                _run_timed(check_backend_tests),
                _run_timed(check_frontend_typecheck),
            ]
        )

    checks.extend(
        [
            _run_timed(check_critical_bugs),
            _run_timed(check_schema_sync),
            _run_timed(check_helm_values),
        ]
    )

    all_passed = all(c.passed for c in checks)

    if all_passed:
        overall = "passed"
    elif override and reason:
        overall = "overridden"
    else:
        overall = "failed"

    return GateReport(
        version=get_version(),
        commit_sha=get_commit_sha(),
        checks=checks,
        overall=overall,
        override_reason=reason if override and reason else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Release gate preflight checks")
    parser.add_argument(
        "--override",
        action="store_true",
        help="Override gate failures (requires --reason)",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Justification for override",
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow checks (tests, typecheck) for fast local validation",
    )
    args = parser.parse_args()

    if args.override and not args.reason:
        print("Error: --override requires --reason", file=sys.stderr)
        return 1

    report = run_gate(
        override=args.override,
        reason=args.reason,
        skip_slow=args.skip_slow,
    )

    print(json.dumps(asdict(report), indent=2))

    if report.overall == "failed":
        failed = [c for c in report.checks if not c.passed]
        print(
            f"\nGate FAILED: {len(failed)} check(s) did not pass.",
            file=sys.stderr,
        )
        return 1

    if report.overall == "overridden":
        print(
            f"\nGate OVERRIDDEN: {args.reason}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
