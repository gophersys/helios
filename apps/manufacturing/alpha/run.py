#!/usr/bin/env python3
"""Alpha manufacturing test runner.

Wraps pytest with preflight checks, result reporting, and artifact collection.

Usage:
    python run.py
    python run.py --preflight-only
    python run.py --run-id clxyz...

Environment variables:
    CONCORD_RUN_ID      Manufacturing session/run ID (activates reporting)
    CONCORD_API_URL     API base URL
    CONCORD_API_KEY     API key for auth
    MTIB_HOSTS          Comma-separated MTIB addresses (multi-slot)
    MTIB_HOST           Single MTIB address (single-slot)
    FIXTURE_CONFIG_PATH Path to fixture config JSON
    BUILD_RUN_ID        Build run ID (firmware artifact resolution)
    ARTIFACTS_DIR       Directory for test artifacts
    MOCK_MODE           Set to "1" for offline testing
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure correct import paths when running outside a container
_root = Path(__file__).resolve().parents[3]
for _p in [
    _root / "libs" / "python",
    _root / "libs" / "protocols",
    _root / "libs",
    Path(__file__).resolve().parent,
]:
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from corekinect.test.runner import TestRunner
from corekinect.utils import Logger

log = Logger(log_name="alpha.manufacturing")


def main():
    """Run manufacturing tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Alpha manufacturing test runner")
    parser.add_argument(
        "--run-id",
        default=os.environ.get("CONCORD_RUN_ID"),
        help="Run ID for result reporting",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only run preflight checks, skip tests",
    )
    args = parser.parse_args()

    if not args.run_id:
        args.run_id = f"local-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        log.info("No run_id provided — using local ID: %s", args.run_id)

    runner = TestRunner(stage="manufacturing", run_id=args.run_id)

    log.info("=" * 60)
    log.info("Alpha Manufacturing Runner")
    log.info("  Run ID:    %s", args.run_id)
    log.info("  Timeout:   %ds", runner.config.timeout_s)
    log.info("  Test path: %s", runner.config.test_path)
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
