#!/usr/bin/env bash
# entrypoint.sh — Nightly CI runner for K8s CronJob.
# Called after the CronJob inline bootstrap has already:
#   1. Waited for the DinD sidecar
#   2. Cloned the repo to /workspace/concord
#
# This script runs from the repo root. It uses ONLY Nx commands
# against the development environment.
#
# Expected env vars (from ConfigMap + Secret):
#   MINIO_ENDPOINT   — http://concord-minio.staging.svc:9000
#   MINIO_BUCKET     — ci
#   MINIO_ACCESS_KEY — MinIO access key (from ci-minio-upload secret)
#   MINIO_SECRET_KEY — MinIO secret key (from ci-minio-upload secret)
#   BRANCH           — main
set -euo pipefail

# ── Logging ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ci]${NC} $*"; }
info() { echo -e "${CYAN}[ci]${NC} $*"; }
err()  { echo -e "${RED}[ci]${NC} $*" >&2; }

STARTED_AT=$(date -u +%s)
EXIT_CODE=0
COMMIT=$(git rev-parse --short HEAD)
RUN_DATE=$(date -u +%Y-%m-%d)

log "Nightly CI — ${BRANCH:-main} @ ${COMMIT} — ${RUN_DATE}"

cleanup() {
  log "Cleaning up..."
  npx nx stop platform 2>/dev/null || true

  local ended_at=$(date -u +%s)
  local duration=$(( ended_at - STARTED_AT ))
  local minutes=$(( duration / 60 ))
  local seconds=$(( duration % 60 ))

  echo ""
  if [[ ${EXIT_CODE} -eq 0 ]]; then
    log "${BOLD}${GREEN}PASSED${NC} in ${minutes}m${seconds}s"
  else
    err "${BOLD}${RED}FAILED${NC} in ${minutes}m${seconds}s (exit ${EXIT_CODE})"
  fi
}
trap cleanup EXIT

# ── Step 1: Install dependencies ──────────────────────────────
log "Installing dependencies..."
yarn install --immutable
npx prisma generate

# ── Step 2: Start development environment ──────────────────────
log "Starting development platform..."
npx nx start platform --output-style=stream --verbose

log "Waiting for platform ready..."
npx nx run platform:ready --output-style=stream --verbose

# ── Step 3: Run E2E tests ──────────────────────────────────────
log "Running E2E tests..."
set +e
npx nx run platform:test:e2e --output-style=stream --verbose 2>&1 | tee /tmp/e2e-output.log
EXIT_CODE=${PIPESTATUS[0]}
set -e

if [[ ${EXIT_CODE} -eq 0 ]]; then
  log "E2E tests passed"
else
  err "E2E tests failed (exit ${EXIT_CODE})"
fi

# ── Step 4: Upload results to MinIO ────────────────────────────
if [[ -n "${MINIO_ACCESS_KEY:-}" ]] && [[ -n "${MINIO_SECRET_KEY:-}" ]]; then
  log "Uploading results to MinIO..."
  mc alias set cluster "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --quiet

  RESULTS_PATH="${MINIO_BUCKET}/nightly/${RUN_DATE}-${COMMIT}"

  # Ensure bucket exists
  mc mb -p "cluster/${MINIO_BUCKET}" 2>/dev/null || true

  # Upload test output
  mc cp /tmp/e2e-output.log "cluster/${RESULTS_PATH}/output.log" --quiet

  # Upload JUnit XML if pytest generated it
  if ls test-results/*.xml 1>/dev/null 2>&1; then
    mc cp --recursive test-results/ "cluster/${RESULTS_PATH}/junit/" --quiet
  fi

  # Write summary metadata
  cat > /tmp/summary.json <<EOF
{
  "date": "${RUN_DATE}",
  "commit": "${COMMIT}",
  "branch": "${BRANCH:-main}",
  "result": $([ ${EXIT_CODE} -eq 0 ] && echo '"pass"' || echo '"fail"'),
  "exit_code": ${EXIT_CODE},
  "duration_s": $(( $(date -u +%s) - STARTED_AT ))
}
EOF
  mc cp /tmp/summary.json "cluster/${RESULTS_PATH}/summary.json" --quiet

  log "Results uploaded to ${RESULTS_PATH}/"
else
  info "MINIO_ACCESS_KEY not set — skipping result upload"
fi

exit ${EXIT_CODE}
