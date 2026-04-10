#!/usr/bin/env python3
"""Alpha manufacturing test runner.

Entry point for manufacturing tests. Wraps pytest with:
- Preflight checks (MTIB connectivity for all slots)
- Result reporting to Concord API
- Artifact collection and upload

Usage:
    python run.py
    python run.py --preflight-only
    python run.py --run-id clxyz...

Environment variables:
    CONCORD_RUN_ID: Manufacturing session/run ID (for result reporting)
    CONCORD_API_URL: API base URL
    CONCORD_API_KEY: API key for auth
    MTIB_HOSTS: Comma-separated MTIB addresses (multi-slot)
    MTIB_HOST: Single MTIB address (single-slot)
    FIXTURE_CONFIG_PATH: Path to fixture config JSON
    PIPELINE_ID: CI pipeline ID (for firmware artifacts)
    ARTIFACTS_DIR: Directory for test artifacts
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure correct import paths
try:
    _root = Path(__file__).resolve().parents[3]
    _paths = [
        str(_root / "libs" / "python"),
        str(_root / "libs" / "protocols"),
        str(_root / "libs"),
        str(_root / "apps" / "manufacturing" / "alpha"),
    ]
    for p in _paths:
        if p not in sys.path:
            sys.path.insert(0, p)
except IndexError:
    pass  # Running in container — PYTHONPATH already configured

from corekinect.test.runner import TestRunner
from corekinect.utils import Logger

log = Logger(log_name="alpha.manufacturing")


def main():
    """Run manufacturing tests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Alpha manufacturing test runner",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("CONCORD_RUN_ID"),
        help="Run ID for result reporting",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only run preflight checks, don't run tests",
    )

    args = parser.parse_args()

    if not args.run_id:
        args.run_id = f"local-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        log.info("No run_id provided - using local ID: %s", args.run_id)

    runner = TestRunner(stage="manufacturing", run_id=args.run_id)

    log.info("=" * 60)
    log.info("Alpha Manufacturing Runner")
    log.info("=" * 60)
    log.info("Run ID:    %s", args.run_id)
    log.info("Timeout:   %ds", runner.config.timeout_s)
    log.info("Test path: %s", runner.config.test_path)
    log.info("=" * 60)

    if args.preflight_only:
        result = runner.preflight.check_all()

        print("\nPreflight Results:")
        print("-" * 40)
        for check in result.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"  [{status}] {check.check_id}: {check.message}")
        print("-" * 40)
        print(f"Overall: {'PASSED' if result.passed else 'FAILED'}")

        sys.exit(0 if result.passed else 1)

    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
