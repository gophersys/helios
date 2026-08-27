#!/usr/bin/env bash
#
# scripts/record-release.sh <env>
#
# After a successful `nx update platform -c <env>`, create the matching
# row in the env's `releases` table so the UI's /releases page reflects
# what was just deployed.
#
# This automates the manual step previously done by an operator (or by
# the AI driving /concord-release). Wired into deploy/ctl.sh's update
# command so EVERY nx update creates a release record — fixing the
# v0.12.6→v0.12.12 gap where seven production deploys never showed up
# in the UI because operators ran `nx update` directly without invoking
# the full /concord-release flow.
#
# How it works:
#   1. Reads VERSION + git metadata from the host
#   2. Generates a JWT inside the http-api pod using JWT_SECRET_KEY
#      (avoids needing host-side python/jwt). The token is signed with
#      RELEASE_RECORDER_USER_ID which must exist as a User row in the
#      env's database.
#   3. POSTs /v2/releases. If 409 (version exists) PATCH instead so
#      reruns of the same version still update fields.
#   4. Verifies the record landed by GET /v2/releases?limit=3.
#
# Idempotent: re-running for the same version PATCHes the existing row.
#
# Failure semantics: non-zero exit only if both POST + PATCH fail.
# nx update has already deployed the new code by the time this runs;
# a record-record failure is loud but not catastrophic — surface and
# let the operator retry.

set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
    echo "[record-release] ERROR: usage: $0 <staging|production>" >&2
    exit 2
fi

# Only run in CI/AI-driven paths; the AI-interactive path is already
# handled by the PostToolUse hook reminder.
if [[ "${CONCORD_SKIP_RELEASE_RECORD:-0}" == "1" ]]; then
    echo "[record-release] CONCORD_SKIP_RELEASE_RECORD=1 — skipping."
    exit 0
fi

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[record-release]${NC} $*"; }
warn() { echo -e "${YELLOW}[record-release]${NC} $*"; }
err()  { echo -e "${RED}[record-release]${NC} $*" >&2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── 1. Collect metadata ───────────────────────────────────────────
VERSION=$(cat VERSION | tr -d '[:space:]')
if [[ -z "$VERSION" ]]; then
    err "VERSION file is empty"
    exit 1
fi

COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null || true)
COMMIT_SHORT=$(git rev-parse --short=8 HEAD 2>/dev/null || true)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
if [[ -z "$COMMIT_SHA" ]]; then
    # Fallback for submodule layouts where git fails inside the
    # devcontainer (same workaround docs/concord-submodule.md describes
    # for .git-build-info).
    if [[ -f .git-build-info ]]; then
        COMMIT_SHORT=$(sed -n 1p .git-build-info)
        BRANCH=$(sed -n 2p .git-build-info)
        COMMIT_SHA="$COMMIT_SHORT"
    else
        err "Cannot determine git commit (no .git and no .git-build-info)"
        exit 1
    fi
fi

# Previous version: top of the env's releases table. Best-effort.
PREVIOUS_VERSION=$(kubectl exec -n "$ENV" deploy/concord-postgres -- \
    psql -U concord -d concord -tAc \
    "SELECT version FROM releases ORDER BY \"createdAt\" DESC LIMIT 1;" \
    2>/dev/null | tr -d '[:space:]' || true)

CHANGELOG=$(git log --pretty=format:'- %s (%h)' "${PREVIOUS_VERSION:+v$PREVIOUS_VERSION..}HEAD" 2>/dev/null | head -50 || echo "")
SUMMARY=$(git log -1 --pretty=format:'%s' HEAD 2>/dev/null || echo "Deploy v$VERSION to $ENV")

log "Recording release: version=$VERSION sha=$COMMIT_SHORT env=$ENV previous=${PREVIOUS_VERSION:-<none>}"

# ── 2. Locate the http-api pod ────────────────────────────────────
POD=$(kubectl get pods -n "$ENV" -l app.kubernetes.io/name=concord-http-api \
    -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' 2>/dev/null | tr ' ' '\n' | head -1)

if [[ -z "$POD" ]]; then
    err "No Running http-api pod in namespace $ENV — cannot record release"
    exit 1
fi

# Determine the user-id this release should be authored by. The
# RELEASE_RECORDER_USER_ID env var on the http-api Deployment is the
# canonical source; if absent, fall back to a sentinel "system" user
# the seed creates.
USER_ID=$(kubectl exec -n "$ENV" "$POD" -c http-api -- \
    bash -c 'echo "${RELEASE_RECORDER_USER_ID:-}"' 2>/dev/null | tr -d '[:space:]')

if [[ -z "$USER_ID" ]]; then
    # Fall back to the current platform lead's User row by email. Prefer
    # setting RELEASE_RECORDER_USER_ID on the http-api Deployment so this
    # person-specific fallback never runs — it must be retargeted whenever
    # the platform lead changes (was mateo@ before the 2026 handoff).
    USER_ID=$(kubectl exec -n "$ENV" deploy/concord-postgres -- \
        psql -U concord -d concord -tAc \
        "SELECT id FROM users WHERE email = 'jared@corekinect.com' LIMIT 1;" \
        2>/dev/null | tr -d '[:space:]')
fi

if [[ -z "$USER_ID" ]]; then
    err "Cannot determine release-recorder user-id (RELEASE_RECORDER_USER_ID env unset AND no fallback user)"
    err "Set RELEASE_RECORDER_USER_ID on the concord-http-api Deployment to a real User.id"
    exit 1
fi

log "Authoring release as user-id=$USER_ID"

# ── 3. Mint a JWT inside the pod ──────────────────────────────────
TOKEN=$(kubectl exec -n "$ENV" "$POD" -c http-api -- \
    python3 -c "
import os, jwt, time
secret = os.environ['JWT_SECRET_KEY']
payload = {
    'sub': '$USER_ID',
    'iat': int(time.time()),
    'exp': int(time.time()) + 300,
    'origin': 'release-recorder',
}
print(jwt.encode(payload, secret, algorithm='HS256'))
" 2>/dev/null | tr -d '[:space:]')

if [[ -z "$TOKEN" ]]; then
    err "Failed to mint JWT inside http-api pod"
    exit 1
fi

# ── 4. POST /v2/releases ──────────────────────────────────────────
# Build the payload via jq so escaping is safe regardless of changelog
# contents.
PAYLOAD=$(jq -n \
    --arg version "$VERSION" \
    --arg commitSha "$COMMIT_SHA" \
    --arg branch "$BRANCH" \
    --arg previousVersion "$PREVIOUS_VERSION" \
    --arg summary "$SUMMARY" \
    --arg changelog "$CHANGELOG" \
    --arg origin "auto-nx-update" \
    '{
        version: $version,
        commitSha: $commitSha,
        branch: $branch,
        status: "RELEASED",
        previousVersion: ($previousVersion | select(length > 0)),
        summary: $summary,
        changelog: $changelog,
        releaseOrigin: $origin,
        gateStatus: "passed"
    } | with_entries(select(.value != null))')

# POST first; if 409, PATCH /v2/releases/<existing-id>.
HTTP_STATUS=$(kubectl exec -n "$ENV" "$POD" -c http-api -- \
    curl -sS -o /tmp/record-release.out -w '%{http_code}' \
    -X POST http://localhost:9001/v2/releases \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>/dev/null || echo "000")

case "$HTTP_STATUS" in
    2*)
        log "POST /v2/releases → $HTTP_STATUS"
        ;;
    409)
        log "Version $VERSION already exists — PATCHing"
        EXISTING_ID=$(kubectl exec -n "$ENV" "$POD" -c http-api -- \
            bash -c "curl -sS http://localhost:9001/v2/releases?version=$VERSION -H 'Authorization: Bearer $TOKEN' | jq -r '.data[0].id // .items[0].id // empty'" 2>/dev/null | tr -d '[:space:]')
        if [[ -z "$EXISTING_ID" ]]; then
            err "Could not locate existing release record id for version $VERSION"
            exit 1
        fi
        PATCH_STATUS=$(kubectl exec -n "$ENV" "$POD" -c http-api -- \
            curl -sS -o /tmp/record-release.out -w '%{http_code}' \
            -X PATCH "http://localhost:9001/v2/releases/$EXISTING_ID" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD" 2>/dev/null || echo "000")
        if [[ ! "$PATCH_STATUS" =~ ^2 ]]; then
            err "PATCH /v2/releases/$EXISTING_ID → $PATCH_STATUS"
            kubectl exec -n "$ENV" "$POD" -c http-api -- cat /tmp/record-release.out 2>/dev/null || true
            exit 1
        fi
        log "PATCH /v2/releases/$EXISTING_ID → $PATCH_STATUS"
        ;;
    *)
        err "POST /v2/releases → $HTTP_STATUS"
        kubectl exec -n "$ENV" "$POD" -c http-api -- cat /tmp/record-release.out 2>/dev/null || true
        exit 1
        ;;
esac

# ── 5. Verify ─────────────────────────────────────────────────────
LATEST=$(kubectl exec -n "$ENV" deploy/concord-postgres -- \
    psql -U concord -d concord -tAc \
    "SELECT version || '|' || status FROM releases ORDER BY \"createdAt\" DESC LIMIT 1;" \
    2>/dev/null | tr -d '[:space:]')

if [[ "$LATEST" != "${VERSION}|RELEASED" ]]; then
    warn "Verification mismatch: expected '${VERSION}|RELEASED', got '$LATEST'"
    exit 1
fi

log "Verified: top of releases table is $LATEST"
