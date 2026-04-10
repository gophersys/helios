#!/usr/bin/env bash
# entrypoint.sh — Nightly CI runner for K8s CronJob.
#
# Replicates the developer workflow:
#   1. devcontainer start (CA certs, yarn install)
#   2. nx start platform  (build images, compose up, DB setup)
#   3. nx run platform:test:e2e
#   4. nx stop platform
#
# The ONLY non-Nx operation is MinIO result upload at the end.
set -euo pipefail

# ── Logging ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ci]${NC} $*"; }
err()  { echo -e "${RED}[ci]${NC} $*" >&2; }

STARTED_AT=$(date -u +%s)
EXIT_CODE=0
COMMIT=$(git rev-parse --short HEAD)
RUN_DATE=$(date -u +%Y-%m-%d)

log "Nightly CI — ${BRANCH:-main} @ ${COMMIT} — ${RUN_DATE}"

cleanup() {
  log "Stopping platform..."
  npx nx stop platform 2>/dev/null || true

  local duration=$(( $(date -u +%s) - STARTED_AT ))
  echo ""
  if [[ ${EXIT_CODE} -eq 0 ]]; then
    log "${BOLD}${GREEN}PASSED${NC} in $(( duration / 60 ))m$(( duration % 60 ))s"
  else
    err "${BOLD}${RED}FAILED${NC} in $(( duration / 60 ))m$(( duration % 60 ))s (exit ${EXIT_CODE})"
  fi
}
trap cleanup EXIT

# ── Step 1: Devcontainer setup (same as developer onboarding) ──
log "Running devcontainer start..."
bash .devcontainer/ctl.sh start

# ── Step 2: Start development platform ─────────────────────────
log "Starting platform..."
npx nx start platform --output-style=stream --verbose

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
if [[ -n "${MINIO_ACCESS_KEY:-}" ]] && [[ -n "${MINIO_SECRET_KEY:-}" ]] && command -v mc &>/dev/null; then
  log "Uploading results to MinIO..."
  RESULTS_PATH="${MINIO_BUCKET}/nightly/${RUN_DATE}-${COMMIT}"

  mc alias set cluster "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --quiet
  mc mb -p "cluster/${MINIO_BUCKET}" 2>/dev/null || true
  mc cp /tmp/e2e-output.log "cluster/${RESULTS_PATH}/output.log" --quiet 2>/dev/null || true

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
  mc cp /tmp/summary.json "cluster/${RESULTS_PATH}/summary.json" --quiet 2>/dev/null || true
  log "Results uploaded to ${RESULTS_PATH}/"
fi

exit ${EXIT_CODE}
