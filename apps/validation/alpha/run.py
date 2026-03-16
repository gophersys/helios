#!/usr/bin/env python3
"""Alpha validation test runner.

Unified entry point for all validation stages. Wraps pytest with:
- Preflight checks (MTIB, storage, device, fixture, firmware)
- Result reporting to Concord API
- Artifact collection and upload
- Consistent error handling and cleanup

Usage:
    # Run FUOTA tests (Stage 5 — merge blocker)
    python run.py --stage fuota

    # Run Nightly tests
    python run.py --stage nightly

    # Preflight only (check dependencies without running tests)
    python run.py --stage fuota --preflight-only

    # With Concord run ID (enables result reporting)
    python run.py --stage fuota --run-id clxyz...

Environment variables (all optional with defaults):
    CONCORD_RUN_ID: Validation run ID (for result reporting)
    CONCORD_API_URL: API base URL
    CONCORD_API_KEY: API key for auth
    STAGE: Test stage (default: fuota)
    MTIB_ADDRESS: MTIB server address (host:port)
    DEVICE_SNR: J-Link probe serial number
    FIXTURE_PROFILE_PATH: Path to fixture profile JSON
    PIPELINE_ID: CI pipeline ID (for firmware artifacts)
    ARTIFACTS_DIR: Directory for test artifacts
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure correct import paths
# In repo: apps/validation/alpha/run.py → parents[3] = repo root
# In container: /app/run.py → parents[3] doesn't exist (PYTHONPATH already set)
try:
    _root = Path(__file__).resolve().parents[3]
    _paths = [
        str(_root / "libs" / "python"),
        str(_root / "libs" / "protocols"),
        str(_root / "libs"),
        str(_root / "apps" / "validation" / "alpha"),
    ]
    for p in _paths:
        if p not in sys.path:
            sys.path.insert(0, p)
except IndexError:
    pass  # Running in container — PYTHONPATH already configured

from corekinect.test.runner import ValidationRunner
from corekinect.utils import Logger

log = Logger(log_name="alpha.runner")


def main():
    """Run validation tests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Alpha validation test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--stage",
        default=os.environ.get("STAGE", "fuota"),
        choices=["smoke", "silicon", "integration", "nightly", "fuota"],
        help="Test stage to run (default: fuota)",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("CONCORD_RUN_ID"),
        help="Validation run ID for result reporting",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only run preflight checks, don't run tests",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Generate a local run ID if not provided
    if not args.run_id:
        args.run_id = f"local-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        log.info("No run_id provided - using local ID: %s", args.run_id)

    # Create runner
    runner = ValidationRunner(stage=args.stage, run_id=args.run_id)

    # Print banner
    log.info("=" * 60)
    log.info("Alpha Validation Runner")
    log.info("=" * 60)
    log.info("Stage:     %s", args.stage)
    log.info("Run ID:    %s", args.run_id)
    log.info("Timeout:   %ds", runner.config.timeout_s)
    log.info("Test path: %s", runner.config.test_path)
    log.info("=" * 60)

    # Preflight only mode
    if args.preflight_only:
        log.info("Running preflight checks only...")
        result = runner.preflight.check_all()

        print("\nPreflight Results:")
        print("-" * 40)
        for check in result.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"  [{status}] {check.check_id}: {check.message}")
        print("-" * 40)
        print(f"Overall: {'PASSED' if result.passed else 'FAILED'}")

        sys.exit(0 if result.passed else 1)

    # Run full validation
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
