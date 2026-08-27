#!/bin/bash
# Concord Test Runner — downloads test package and runs tests
#
# This is the entrypoint for the generic test runner container.
# It downloads a product-specific test package (tar.gz) from the
# Concord API, installs its dependencies, and runs tests via pytest
# or the package's run.py entry point.
set -e

echo "════════════════════════════════════════════"
echo "  Concord Test Runner v${APP_VERSION}"
echo "════════════════════════════════════════════"
echo ""

# Required env vars — TEST_PACKAGE_VERSION is now mandatory. The backend
# resolves the package id at runner-deploy time (via the unified resolver
# + stage binding + session.testPackageId), so a missing version here is
# a backend bug, not a runtime decision the runner should make on its own.
: "${PRODUCT_SLUG:?PRODUCT_SLUG is required}"
: "${STAGE:?STAGE is required}"
: "${CONCORD_API_URL:?CONCORD_API_URL is required}"
: "${CONCORD_API_KEY:?CONCORD_API_KEY is required}"
: "${TEST_PACKAGE_VERSION:?TEST_PACKAGE_VERSION is required (set by the backend at deploy time)}"

# Infer package type from stage
if [ "${TEST_PACKAGE_TYPE:-}" = "" ]; then
    if [ "$STAGE" = "manufacturing" ]; then
        TEST_PACKAGE_TYPE="MANUFACTURING"
    else
        TEST_PACKAGE_TYPE="VALIDATION"
    fi
fi

echo "Product:      ${PRODUCT_SLUG}"
echo "Stage:        ${STAGE}"
echo "Package Type: ${TEST_PACKAGE_TYPE}"
echo "Test Package: ${TEST_PACKAGE_VERSION}"
echo "Framework:    ${TEST_FRAMEWORK:-PYTEST}"
echo "API:          ${CONCORD_API_URL}"
echo "Runner:       ${GIT_COMMIT:-unknown}"
echo ""

# ── Step 1: Download test package ─────────────────────────────────────────

echo "Downloading test package..."

# Step 1b: Get presigned download URL
DOWNLOAD_API_URL="${CONCORD_API_URL}/v2/products/${PRODUCT_SLUG}/test-packages/${TEST_PACKAGE_VERSION}/download?type=${TEST_PACKAGE_TYPE}"
DOWNLOAD_JSON=$(curl -sf \
    -H "Authorization: ApiKey ${CONCORD_API_KEY}" \
    "${DOWNLOAD_API_URL}") || {
    echo "ERROR: Failed to get download URL from ${DOWNLOAD_API_URL}"
    echo "Verify PRODUCT_SLUG (${PRODUCT_SLUG}) and TEST_PACKAGE_VERSION (${TEST_PACKAGE_VERSION}) are correct."
    exit 1
}

PRESIGNED_URL=$(echo "$DOWNLOAD_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['url'])" 2>/dev/null) || {
    echo "ERROR: Failed to parse download URL from API response"
    echo "Response: ${DOWNLOAD_JSON}"
    exit 1
}

# Step 1c: Download via API proxy (avoids presigned URL hostname issues in dev)
# The API endpoint streams the file directly, so we don't need the presigned URL.
DIRECT_URL="${CONCORD_API_URL}/v2/storage/download?key=test-packages/${PRODUCT_SLUG}/${TEST_PACKAGE_TYPE,,}/${TEST_PACKAGE_VERSION}/package.tar.gz"
echo "Downloading from: ${DIRECT_URL}"

HTTP_CODE=$(curl -sf \
    -L -o /tmp/test-package.tar.gz \
    -w "%{http_code}" \
    -H "Authorization: ApiKey ${CONCORD_API_KEY}" \
    "${DIRECT_URL}") || {
    # Fallback to presigned URL if direct download fails
    echo "Direct download failed, trying presigned URL..."
    HTTP_CODE=$(curl -sf \
        -L -o /tmp/test-package.tar.gz \
        -w "%{http_code}" \
        "${PRESIGNED_URL}") || {
        echo "ERROR: Failed to download test package"
        echo "Direct URL: ${DIRECT_URL}"
        echo "Presigned URL: ${PRESIGNED_URL}"
        exit 1
    }
}

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: Storage returned HTTP ${HTTP_CODE} for test package download"
    cat /tmp/test-package.tar.gz 2>/dev/null || true
    exit 1
fi

PACKAGE_SIZE=$(du -h /tmp/test-package.tar.gz | cut -f1)
echo "Downloaded test package v${TEST_PACKAGE_VERSION} (${PACKAGE_SIZE})"

# ── Step 2: Extract test package ──────────────────────────────────────────

echo "Extracting..."
mkdir -p /app/tests
tar xzf /tmp/test-package.tar.gz -C /app/
rm /tmp/test-package.tar.gz

TEST_FILE_COUNT=$(find /app -name 'test_*.py' | wc -l)
echo "Extracted to /app/ — ${TEST_FILE_COUNT} test files"

# ── Step 2.5: Phase D Layer 4 — framework-constraint gate ─────────────────
#
# Before pytest starts, assert that the runner's bundled corekinect
# satisfies the test package's `package.framework` constraint
# (e.g., ">=0.9.0"). Semver-compatible, NOT strict-SHA. See
# .claude/knowledge/deploy/runner.md Layer 4 for the full design.
#
# Exit codes:
#   0 — constraint satisfied (or absent → warn + pass)
#   1 — constraint violated — refuse to start pytest
#   2 — usage / manifest / parse error
#
# Bypass: CONCORD_FORCE_STALE_PACKAGE=1 (loud-warn). The script logs
# the bypass usage so the operator's reason is visible in pod logs.
echo ""
if [ -f /app/concord.yaml ]; then
    if ! python3 /app/check_framework_constraint.py /app/concord.yaml; then
        gate_exit=$?
        echo ""
        echo "[runner] framework-constraint gate refused the run (exit ${gate_exit})."
        echo "[runner] Not invoking pytest. See gate output above for the fix."
        exit ${gate_exit}
    fi
else
    echo "[runner] WARNING: /app/concord.yaml not found after extract — "
    echo "[runner] skipping framework gate (legacy / non-corekinect package?)."
fi
echo ""

# ── Step 3: Install app dependencies ──────────────────────────────────────

# P3 (Phase D, branch fix/manifest-load-failure-visibility):
# install the downloaded test package NON-editable. The pre-fix
# `pip install -e /app/` fails on modern setuptools' build_meta
# because PEP 660 build_editable is not implemented for the default
# backend, surfacing a confusing
#   ERROR: Project ... has a 'pyproject.toml' and its build backend
#   is missing the 'build_editable' hook
# in every runner pod log. The runner mounts the test package
# read-only at /app/ and doesn't need editable semantics — pip
# install . is the right shape.
if [ -f /app/pyproject.toml ]; then
    echo "Installing app dependencies from pyproject.toml..."
    pip3 install --no-cache-dir /app/ 2>&1 | tail -5
    echo "Dependencies installed"
elif [ -f /app/setup.py ]; then
    echo "Installing app dependencies from setup.py..."
    pip3 install --no-cache-dir /app/ 2>&1 | tail -5
    echo "Dependencies installed"
elif [ -f /app/requirements.txt ]; then
    echo "Installing app dependencies from requirements.txt..."
    pip3 install --no-cache-dir -r /app/requirements.txt 2>&1 | tail -5
    echo "Dependencies installed"
fi

echo ""

# ── Step 4: Run tests ─────────────────────────────────────────────────────

# Persistent mode for manufacturing sessions
if [ "${RUNNER_MODE:-}" = "persistent" ]; then
    echo "[concord-runner] Starting persistent manufacturing runner..."
    echo "[concord-runner] Session: ${CONCORD_SESSION_ID}"
    exec python3 -m corekinect.test.mfg_runner \
        --session-id "${CONCORD_SESSION_ID}"
fi

# One-shot mode (default)
echo "Running ${STAGE} stage..."

# Framework dispatch — the backend sets TEST_FRAMEWORK from the
# TestPackage's framework column. When unset (legacy rows / pre-dispatch
# deploys), we behave exactly as before: run pytest via run.py or the
# direct fallback. ZTEST hands off to corekinect.test.ztest_runner.
case "${TEST_FRAMEWORK:-PYTEST}" in
    ZTEST|ztest)
        echo "Framework=ZTEST — dispatching to corekinect.test.ztest_runner"
        : "${CONCORD_RUN_ID:?CONCORD_RUN_ID is required for ztest dispatch}"
        : "${CONCORD_TARGET_ID:?CONCORD_TARGET_ID is required for ztest dispatch}"
        : "${MTIB_HOST:?MTIB_HOST is required for ztest dispatch}"
        : "${ZTEST_LABELS:?ZTEST_LABELS is required for ztest dispatch (comma-separated)}"
        exec python3 -m corekinect.test.ztest_runner \
            --run-id "${CONCORD_RUN_ID}" \
            --target-id "${CONCORD_TARGET_ID}" \
            --api-url "${CONCORD_API_URL}" \
            --api-key "${CONCORD_API_KEY}" \
            --asset-set "${ZTEST_ASSET_SET_DIR:-/app/assets}" \
            --mtib-host "${MTIB_HOST}" \
            --mtib-port "${MTIB_PORT:-50053}" \
            --labels "${ZTEST_LABELS}" \
            --timeout-s "${ZTEST_TIMEOUT_S:-600}"
        ;;
    PYTEST|pytest|"")
        # Use run.py if it exists (TestRunner with preflight + reporting)
        if [ -f /app/run.py ]; then
            exec python3 /app/run.py --stage "${STAGE}" "$@"
        else
            # Fallback to direct pytest
            exec python3 -m pytest "tests/${STAGE}/" \
                -v \
                --timeout="${TEST_TIMEOUT:-120}" \
                "$@"
        fi
        ;;
    *)
        echo "ERROR: unknown TEST_FRAMEWORK '${TEST_FRAMEWORK}' (allowed: PYTEST, ZTEST)"
        exit 2
        ;;
esac
