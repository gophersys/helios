#!/usr/bin/env bash
# entrypoint.sh — Nightly CI runner for K8s CronJob.
#
# Replicates the developer workflow:
#   1. devcontainer start (CA certs, yarn, pip install)
#   2. nx start platform  (build images, compose up, DB setup)
#   3. nx run platform:test:e2e
#   4. nx stop platform
#
# Resource tracking: snapshots Docker state before/after to ensure
# clean teardown with no leaked containers, volumes, or networks.
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

# ── Resource snapshot (before) ──────────────────────────────────
log "Capturing pre-run resource snapshot..."
docker ps -q 2>/dev/null | sort > /tmp/ci-containers-before.txt || true
docker volume ls -q 2>/dev/null | sort > /tmp/ci-volumes-before.txt || true
docker network ls -q --filter type=custom 2>/dev/null | sort > /tmp/ci-networks-before.txt || true
DISK_BEFORE=$(df / --output=used 2>/dev/null | tail -1 | tr -d ' ' || echo 0)

cleanup() {
  log "Stopping platform..."
  npx nx stop platform 2>/dev/null || true

  # ── Resource snapshot (after) + leak detection ──────────────
  log "Checking for resource leaks..."
  local leaked=0

  # Containers
  docker ps -q 2>/dev/null | sort > /tmp/ci-containers-after.txt || true
  local new_containers
  new_containers=$(comm -13 /tmp/ci-containers-before.txt /tmp/ci-containers-after.txt | wc -l)
  if [[ ${new_containers} -gt 0 ]]; then
    err "LEAK: ${new_containers} container(s) still running after cleanup"
    docker ps --filter "id=$(comm -13 /tmp/ci-containers-before.txt /tmp/ci-containers-after.txt | head -5 | tr '\n' '|' | sed 's/|$//')" --format "  {{.Names}} ({{.Image}})" 2>/dev/null || true
    # Force cleanup
    comm -13 /tmp/ci-containers-before.txt /tmp/ci-containers-after.txt | xargs -r docker rm -f 2>/dev/null || true
    leaked=1
  fi

  # Volumes
  docker volume ls -q 2>/dev/null | sort > /tmp/ci-volumes-after.txt || true
  local new_volumes
  new_volumes=$(comm -13 /tmp/ci-volumes-before.txt /tmp/ci-volumes-after.txt | wc -l)
  if [[ ${new_volumes} -gt 0 ]]; then
    err "LEAK: ${new_volumes} volume(s) left behind"
    comm -13 /tmp/ci-volumes-before.txt /tmp/ci-volumes-after.txt | head -5 | sed 's/^/  /'
    # Force cleanup
    comm -13 /tmp/ci-volumes-before.txt /tmp/ci-volumes-after.txt | xargs -r docker volume rm -f 2>/dev/null || true
    leaked=1
  fi

  # Networks
  docker network ls -q --filter type=custom 2>/dev/null | sort > /tmp/ci-networks-after.txt || true
  local new_networks
  new_networks=$(comm -13 /tmp/ci-networks-before.txt /tmp/ci-networks-after.txt | wc -l)
  if [[ ${new_networks} -gt 0 ]]; then
    err "LEAK: ${new_networks} network(s) left behind"
    comm -13 /tmp/ci-networks-before.txt /tmp/ci-networks-after.txt | xargs -r docker network rm 2>/dev/null || true
    leaked=1
  fi

  # Disk
  local disk_after
  disk_after=$(df / --output=used 2>/dev/null | tail -1 | tr -d ' ' || echo 0)
  local disk_delta=$(( (disk_after - DISK_BEFORE) / 1024 ))
  if [[ ${disk_delta} -gt 500 ]]; then
    err "LEAK: ${disk_delta}MB disk not reclaimed — running docker system prune"
    docker system prune -f --volumes 2>/dev/null || true
  fi

  if [[ ${leaked} -eq 0 ]]; then
    log "Clean — no resource leaks detected"
  fi

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

# Export SSH key for docker-compose services (git-poller needs it as base64 env var)
if [[ -f /root/.ssh/id_rsa ]]; then
  export BITBUCKET_SSH_KEY
  BITBUCKET_SSH_KEY=$(base64 -w0 /root/.ssh/id_rsa)
  log "SSH key exported for docker-compose services"
fi

# ── Step 2: Start development platform ─────────────────────────
log "Starting platform..."
npx nx start platform --output-style=stream --verbose

# ── Step 3: Run E2E tests ──────────────────────────────────────
log "Running E2E tests..."
npx nx run platform:test:e2e --output-style=stream --verbose 2>&1 | tee /tmp/e2e-output.log || EXIT_CODE=$?

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
