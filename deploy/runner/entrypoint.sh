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

# ── Step 3: Install app dependencies ──────────────────────────────────────

if [ -f /app/pyproject.toml ]; then
    echo "Installing app dependencies from pyproject.toml..."
    pip3 install --no-cache-dir -e /app/ 2>&1 | tail -5
    echo "Dependencies installed"
elif [ -f /app/setup.py ]; then
    echo "Installing app dependencies from setup.py..."
    pip3 install --no-cache-dir -e /app/ 2>&1 | tail -5
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
