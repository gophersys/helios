#!/bin/bash
# Concord Validation Runner — downloads test package and runs tests
set -e

echo "════════════════════════════════════════════"
echo "  Concord Validation Runner v${APP_VERSION}"
echo "════════════════════════════════════════════"
echo ""

# Required env vars
: "${PRODUCT_SLUG:?PRODUCT_SLUG is required}"
: "${STAGE:?STAGE is required}"
: "${CONCORD_API_URL:?CONCORD_API_URL is required}"
: "${CONCORD_API_KEY:?CONCORD_API_KEY is required}"

# Optional — defaults to "latest"
TEST_PACKAGE_VERSION="${TEST_PACKAGE_VERSION:-latest}"

echo "Product:      ${PRODUCT_SLUG}"
echo "Stage:        ${STAGE}"
echo "Test Package: ${TEST_PACKAGE_VERSION}"
echo "API:          ${CONCORD_API_URL}"
echo ""

# ── Step 1: Download test package ──
echo "Downloading test package..."

if [ "$TEST_PACKAGE_VERSION" = "latest" ]; then
    DOWNLOAD_URL="${CONCORD_API_URL}/v2/products/${PRODUCT_SLUG}/test-packages/latest"
else
    DOWNLOAD_URL="${CONCORD_API_URL}/v2/products/${PRODUCT_SLUG}/test-packages/${TEST_PACKAGE_VERSION}/download"
fi

# Get the download URL (may be a redirect to MinIO presigned URL)
PACKAGE_URL=$(curl -sf \
    -H "Authorization: ApiKey ${CONCORD_API_KEY}" \
    -L -o /tmp/test-package.tar.gz \
    -w "%{url_effective}" \
    "${DOWNLOAD_URL}" 2>/dev/null) || {
    echo "ERROR: Failed to download test package from ${DOWNLOAD_URL}"
    echo "Verify PRODUCT_SLUG and TEST_PACKAGE_VERSION are correct."
    exit 1
}

echo "Downloaded test package ($(du -h /tmp/test-package.tar.gz | cut -f1))"

# ── Step 2: Extract test package ──
echo "Extracting..."
mkdir -p /app/tests
tar xzf /tmp/test-package.tar.gz -C /app/
rm /tmp/test-package.tar.gz

echo "Test package extracted to /app/"
echo "Files: $(find /app -name 'test_*.py' | wc -l) test files"
echo ""

# ── Step 3: Run validation ──
echo "Running ${STAGE} stage..."

# Use run.py if it exists (full ValidationRunner with preflight + reporting)
if [ -f /app/run.py ]; then
    exec python3 /app/run.py --stage "${STAGE}" "$@"
else
    # Fallback to direct pytest
    exec python3 -m pytest "tests/${STAGE}/" \
        -v \
        --timeout="${TEST_TIMEOUT:-120}" \
        "$@"
fi
