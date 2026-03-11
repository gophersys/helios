#!/bin/bash
# Run Stage 5 (Gate) validation tests
#
# Usage:
#   ./run_gate.sh                    # Run all gate tests
#   ./run_gate.sh --preflight-only   # Check dependencies only
#   ./run_gate.sh --collect-only     # Just collect tests (pytest mode)
#   ./run_gate.sh -k "test_01"       # Run specific test (pytest mode)
#
# Modes:
#   By default, uses the ValidationRunner which includes preflight checks,
#   result reporting, and artifact collection.
#
#   Pass pytest args (like --collect-only, -k, etc.) to use raw pytest mode.
#
# Required environment variables:
#   MTIB_ADDRESS or MTIB_HOST        # MTIB server address
#   DEVICE_SNR                       # J-Link probe serial number
#   FIXTURE_PROFILE_PATH             # Path to fixture profile JSON
#
# Optional (for FUOTA):
#   PIPELINE_ID                      # CI pipeline with firmware artifacts
#   VAL_1_0_API_KEY                  # CoreCloud API key
#   VAL_1_0_REST_SERVER_HOST_NAME    # CoreCloud REST server
#
# Optional (for Concord reporting):
#   CONCORD_RUN_ID                   # Validation run ID
#   CONCORD_API_URL                  # Concord API base URL
#   CONCORD_API_KEY                  # Concord API key

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Set PYTHONPATH
export PYTHONPATH="$REPO_ROOT/libs/python:$REPO_ROOT/libs/protocols:$REPO_ROOT/libs:$SCRIPT_DIR"

cd "$SCRIPT_DIR"

echo "=== Stage 5 (Gate) Validation ==="
echo "Working dir: $(pwd)"
echo ""

# Check required env vars
if [ -z "$MTIB_ADDRESS" ] && [ -z "$MTIB_HOST" ]; then
    echo "WARNING: MTIB_ADDRESS or MTIB_HOST not set"
fi
if [ -z "$DEVICE_SNR" ]; then
    echo "WARNING: DEVICE_SNR not set"
fi

# Check for preflight-only flag
if [[ "$1" == "--preflight-only" ]]; then
    echo "Running preflight checks..."
    python3 run.py --stage gate --preflight-only
    exit $?
fi

# If pytest-specific args are passed, use raw pytest
if [[ "$1" == "--collect-only" ]] || [[ "$1" == "-k" ]] || [[ "$1" == "--tb" ]]; then
    echo "Pytest mode (raw pytest, no preflight)"
    python3 -m pytest tests/gate/ \
        --timeout=900 \
        -v \
        "$@"
    exit $?
fi

# Default: Use ValidationRunner with preflight and reporting
echo "Using ValidationRunner..."
python3 run.py --stage gate "$@"
