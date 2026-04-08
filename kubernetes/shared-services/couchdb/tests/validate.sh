#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------
# CouchDB + Obsidian LiveSync — Deployment Validation
# ------------------------------------------------------------------
# Runs CouchDB in Docker with the same config used in the Helm chart,
# then validates health, CORS, auth, and LiveSync database readiness.
#
# Usage:
#   ./tests/validate.sh              # local Docker test
#   ./tests/validate.sh --live URL   # test a live deployment
#
# Example:
#   ./tests/validate.sh --live https://notes.mateosegura.com
# ------------------------------------------------------------------

CONTAINER_NAME="couchdb-validation-test"
TEST_USER="admin"
TEST_PASS="testpass123"
LIVE_URL=""
CLEANUP=true
PASS=0
FAIL=0

# Parse arguments
if [[ "${1:-}" == "--live" ]]; then
    LIVE_URL="${2:?Usage: $0 --live <url>}"
    echo "Testing live deployment at: ${LIVE_URL}"
    echo "Note: set COUCHDB_USER and COUCHDB_PASSWORD env vars for auth"
    TEST_USER="${COUCHDB_USER:-admin}"
    TEST_PASS="${COUCHDB_PASSWORD:?Set COUCHDB_PASSWORD for live testing}"
    CLEANUP=false
fi

cleanup() {
    if [[ "$CLEANUP" == "true" ]]; then
        echo ""
        echo "Cleaning up..."
        docker rm -f "$CONTAINER_NAME" &>/dev/null || true
        [[ -n "${CONFIG_DIR:-}" && "$CONFIG_DIR" == /tmp/* ]] && rm -rf "$CONFIG_DIR" || true
    fi
}
trap cleanup EXIT

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

get_base_url() {
    if [[ -n "$LIVE_URL" ]]; then
        echo "$LIVE_URL"
    else
        echo "http://localhost:5984"
    fi
}

# ── Start local CouchDB (skip if testing live) ──────────────────

if [[ -z "$LIVE_URL" ]]; then
    CONFIG_DIR="$(mktemp -d)"

    # Generate local.ini from the Helm chart's configmap (matches production)
    cat > "$CONFIG_DIR/local.ini" <<'INI'
[couchdb]
single_node=true
max_document_size = 50000000

[chttpd]
require_valid_user = true
max_http_request_size = 4294967296
enable_cors = true
bind_address = 0.0.0.0
port = 5984

[chttpd_auth]
require_valid_user = true
authentication_redirect = /_utils/session.html

[httpd]
WWW-Authenticate = Basic realm="couchdb"
bind_address = 0.0.0.0

[cors]
origins = *
credentials = true
methods = GET, PUT, POST, HEAD, DELETE
headers = accept, authorization, content-type, origin, referer, x-csrf-token

[log]
level = warn
INI

    echo "Starting CouchDB container..."
    docker rm -f "$CONTAINER_NAME" &>/dev/null || true
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p 5984:5984 \
        -e COUCHDB_USER="$TEST_USER" \
        -e COUCHDB_PASSWORD="$TEST_PASS" \
        -v "$CONFIG_DIR/local.ini:/opt/couchdb/etc/local.d/local.ini" \
        couchdb:3 >/dev/null

    echo "Waiting for CouchDB to start..."
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:5984/_up" -u "$TEST_USER:$TEST_PASS" &>/dev/null; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "ERROR: CouchDB failed to start within 30s"
            docker logs "$CONTAINER_NAME"
            exit 1
        fi
        sleep 1
    done
    echo "CouchDB is up."
fi

BASE_URL="$(get_base_url)"
AUTH="$TEST_USER:$TEST_PASS"
echo ""

# ── Test Suite ───────────────────────────────────────────────────

echo "=== 1. Health & Readiness ==="

# 1a. /_up endpoint (used by liveness/readiness probes)
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/_up" -u "$AUTH" 2>/dev/null || echo "000")
if [[ "$STATUS" == "200" ]]; then
    pass "/_up returns 200"
else
    fail "/_up returned $STATUS (expected 200)"
fi

# 1b. Root endpoint returns CouchDB version
VERSION=$(curl -sf "$BASE_URL/" -u "$AUTH" 2>/dev/null | grep -o '"version":"[^"]*"' || echo "none")
if [[ "$VERSION" != "none" ]]; then
    pass "CouchDB responding — $VERSION"
else
    fail "Root endpoint did not return version info"
fi

echo ""
echo "=== 2. Authentication ==="

# 2a. Unauthenticated request should be rejected
UNAUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/" 2>/dev/null)
if [[ "$UNAUTH_STATUS" == "401" ]]; then
    pass "Unauthenticated requests rejected (401)"
else
    fail "Unauthenticated request returned $UNAUTH_STATUS (expected 401)"
fi

# 2b. Authenticated request should succeed
AUTH_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/" -u "$AUTH" 2>/dev/null || echo "000")
if [[ "$AUTH_STATUS" == "200" ]]; then
    pass "Authenticated requests succeed (200)"
else
    fail "Authenticated request returned $AUTH_STATUS (expected 200)"
fi

echo ""
echo "=== 3. CORS Configuration ==="

# 3a. Preflight OPTIONS request
CORS_HEADERS=$(curl -sf -I -X OPTIONS \
    -H "Origin: https://obsidian.md" \
    -H "Access-Control-Request-Method: PUT" \
    -H "Access-Control-Request-Headers: authorization,content-type" \
    "$BASE_URL/" -u "$AUTH" 2>/dev/null || echo "")

if echo "$CORS_HEADERS" | grep -qi "access-control-allow-origin"; then
    pass "CORS Access-Control-Allow-Origin header present"
else
    fail "CORS Access-Control-Allow-Origin header missing"
fi

if echo "$CORS_HEADERS" | grep -qi "access-control-allow-credentials"; then
    pass "CORS Access-Control-Allow-Credentials header present"
else
    fail "CORS Access-Control-Allow-Credentials header missing"
fi

if echo "$CORS_HEADERS" | grep -qi "access-control-allow-methods"; then
    pass "CORS Access-Control-Allow-Methods header present"
else
    fail "CORS Access-Control-Allow-Methods header missing"
fi

echo ""
echo "=== 4. System Databases ==="

# CouchDB requires _users and _replicator to exist for single-node mode
# Create them if they don't exist (matches the post-deploy init step)
for DB in _users _replicator _global_changes; do
    curl -sf -X PUT "$BASE_URL/$DB" -u "$AUTH" &>/dev/null || true
done

for DB in _users _replicator _global_changes; do
    DB_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/$DB" -u "$AUTH" 2>/dev/null || echo "000")
    if [[ "$DB_STATUS" == "200" ]]; then
        pass "System database $DB exists"
    else
        fail "System database $DB not found ($DB_STATUS)"
    fi
done

echo ""
echo "=== 5. LiveSync Database ==="

# Create the obsidian-livesync database
DB_NAME="obsidian-livesync"
curl -sf -X PUT "$BASE_URL/$DB_NAME" -u "$AUTH" &>/dev/null || true

LS_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/$DB_NAME" -u "$AUTH" 2>/dev/null || echo "000")
if [[ "$LS_STATUS" == "200" ]]; then
    pass "LiveSync database '$DB_NAME' created and accessible"
else
    fail "LiveSync database returned $LS_STATUS"
fi

# 5b. Test write and read (simulates LiveSync sync operation)
DOC_ID="test-note-$(date +%s)"
WRITE_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X PUT "$BASE_URL/$DB_NAME/$DOC_ID" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d '{"type":"plain","data":"# Test Note\nThis is a sync test."}' 2>/dev/null || echo "000")

if [[ "$WRITE_STATUS" == "201" ]]; then
    pass "Document write to LiveSync database succeeded"
else
    fail "Document write returned $WRITE_STATUS (expected 201)"
fi

READ_BODY=$(curl -sf "$BASE_URL/$DB_NAME/$DOC_ID" -u "$AUTH" 2>/dev/null || echo "")
if echo "$READ_BODY" | grep -q "Test Note"; then
    pass "Document read from LiveSync database succeeded"
else
    fail "Document read did not return expected content"
fi

# 5c. Test _changes feed (LiveSync relies on this for real-time sync)
CHANGES_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    "$BASE_URL/$DB_NAME/_changes?limit=1" -u "$AUTH" 2>/dev/null || echo "000")
if [[ "$CHANGES_STATUS" == "200" ]]; then
    pass "_changes feed accessible (required for LiveSync)"
else
    fail "_changes feed returned $CHANGES_STATUS"
fi

# Cleanup test doc
REV=$(echo "$READ_BODY" | grep -o '"_rev":"[^"]*"' | cut -d'"' -f4)
if [[ -n "$REV" ]]; then
    curl -sf -X DELETE "$BASE_URL/$DB_NAME/$DOC_ID?rev=$REV" -u "$AUTH" &>/dev/null || true
fi

echo ""
echo "=== 6. Max Document Size ==="

# LiveSync chunks large notes; verify the server accepts reasonable payloads
TMPFILE=$(mktemp)
python3 -c "import json; print(json.dumps({'data': 'x' * 1000000}))" > "$TMPFILE" 2>/dev/null
LARGE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT "$BASE_URL/$DB_NAME/size-test" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d @"$TMPFILE" 2>/dev/null)
rm -f "$TMPFILE"

if [[ "$LARGE_STATUS" == "201" ]]; then
    pass "1MB document write accepted (large note support)"
    # Cleanup
    REV=$(curl -sf "$BASE_URL/$DB_NAME/size-test" -u "$AUTH" 2>/dev/null | grep -o '"_rev":"[^"]*"' | cut -d'"' -f4)
    curl -sf -X DELETE "$BASE_URL/$DB_NAME/size-test?rev=$REV" -u "$AUTH" &>/dev/null || true
else
    fail "1MB document write returned $LARGE_STATUS (expected 201)"
fi

echo ""
echo "=== 7. Config Verification ==="

# Verify CouchDB config via API
CONFIG=$(curl -sf "$BASE_URL/_node/nonode@nohost/_config/chttpd/enable_cors" -u "$AUTH" 2>/dev/null || echo "")
if [[ "$CONFIG" == '"true"' ]]; then
    pass "CORS enabled in CouchDB config"
else
    fail "CORS config check returned: $CONFIG (expected \"true\")"
fi

SINGLE=$(curl -sf "$BASE_URL/_node/nonode@nohost/_config/couchdb/single_node" -u "$AUTH" 2>/dev/null || echo "")
if [[ "$SINGLE" == '"true"' ]]; then
    pass "Single-node mode enabled"
else
    fail "Single-node mode check returned: $SINGLE (expected \"true\")"
fi

echo ""
echo "════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "════════════════════════════════════════"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
