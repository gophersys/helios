#!/usr/bin/env bash
# entrypoint.sh — Nightly CI runner for K8s CronJob.
#
# Replicates the developer workflow:
#   1. devcontainer start (CA certs, yarn, pip install)
#   2. nx start platform  (build images, compose up, DB setup)
#   3. nx run platform:test:e2e
#   4. nx stop platform
#
# ERROR HANDLING: No `set -e`. Every command's exit code is checked
# explicitly. Failures are logged and the step result is tracked.
# Cleanup ALWAYS runs regardless of what failed.
# All output is verbose — nothing is swallowed.

# ── Logging ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ci]${NC} $*"; }
warn() { echo -e "${YELLOW}[ci]${NC} $*"; }
err()  { echo -e "${RED}[ci]${NC} $*" >&2; }

STARTED_AT=$(date -u +%s)
COMMIT=$(git rev-parse --short HEAD)
RUN_DATE=$(date -u +%Y-%m-%d)

# Step results tracking
STEP_SETUP=1      # 0=pass, 1=not run, 2=fail
STEP_PLATFORM=1
STEP_TESTS=1
STEP_UPLOAD=1

log "${BOLD}Nightly CI — ${BRANCH:-main} @ ${COMMIT} — ${RUN_DATE}${NC}"
echo ""

# ── Resource snapshot (before) ──────────────────────────────────
log "Capturing pre-run resource snapshot..."
docker ps -q 2>/dev/null | sort > /tmp/ci-containers-before.txt || true
docker volume ls -q 2>/dev/null | sort > /tmp/ci-volumes-before.txt || true
docker network ls -q --filter type=custom 2>/dev/null | sort > /tmp/ci-networks-before.txt || true
DISK_BEFORE=$(df / --output=used 2>/dev/null | tail -1 | tr -d ' ' || echo 0)

# ── Cleanup (ALWAYS runs — best effort, never fails) ───────────
cleanup() {
  echo ""
  log "═══════════════════════════════════════════════════"
  log "CLEANUP"
  log "═══════════════════════════════════════════════════"

  # Stop platform (best effort)
  log "Stopping platform..."
  npx nx stop platform --output-style=stream 2>&1 || warn "nx stop platform failed (non-fatal)"

  # Leak detection (best effort)
  log "Checking for resource leaks..."
  local leaked=0

  docker ps -q 2>/dev/null | sort > /tmp/ci-containers-after.txt || true
  local new_containers
  new_containers=$(comm -13 /tmp/ci-containers-before.txt /tmp/ci-containers-after.txt 2>/dev/null | wc -l || echo 0)
  if [[ ${new_containers} -gt 0 ]]; then
    err "LEAK: ${new_containers} container(s) still running"
    comm -13 /tmp/ci-containers-before.txt /tmp/ci-containers-after.txt | xargs -r docker rm -f 2>/dev/null || true
    leaked=1
  fi

  docker volume ls -q 2>/dev/null | sort > /tmp/ci-volumes-after.txt || true
  local new_volumes
  new_volumes=$(comm -13 /tmp/ci-volumes-before.txt /tmp/ci-volumes-after.txt 2>/dev/null | wc -l || echo 0)
  if [[ ${new_volumes} -gt 0 ]]; then
    warn "Removing ${new_volumes} leftover volume(s)"
    comm -13 /tmp/ci-volumes-before.txt /tmp/ci-volumes-after.txt | xargs -r docker volume rm -f 2>/dev/null || true
  fi

  docker network ls -q --filter type=custom 2>/dev/null | sort > /tmp/ci-networks-after.txt || true
  local new_networks
  new_networks=$(comm -13 /tmp/ci-networks-before.txt /tmp/ci-networks-after.txt 2>/dev/null | wc -l || echo 0)
  if [[ ${new_networks} -gt 0 ]]; then
    comm -13 /tmp/ci-networks-before.txt /tmp/ci-networks-after.txt | xargs -r docker network rm 2>/dev/null || true
  fi

  local disk_after
  disk_after=$(df / --output=used 2>/dev/null | tail -1 | tr -d ' ' || echo 0)
  local disk_delta=$(( (disk_after - DISK_BEFORE) / 1024 ))
  if [[ ${disk_delta} -gt 500 ]]; then
    warn "Pruning ${disk_delta}MB of Docker cache..."
    docker system prune -f --volumes 2>/dev/null | tail -1 || true
  fi

  if [[ ${leaked} -eq 0 ]]; then
    log "Clean — no resource leaks"
  fi

  # ── Summary ──────────────────────────────────────────────────
  echo ""
  log "═══════════════════════════════════════════════════"
  log "RESULTS"
  log "═══════════════════════════════════════════════════"
  local duration=$(( $(date -u +%s) - STARTED_AT ))

  _print_step "Setup (devcontainer)" ${STEP_SETUP}
  _print_step "Platform start"      ${STEP_PLATFORM}
  _print_step "E2E tests"           ${STEP_TESTS}
  _print_step "Result upload"       ${STEP_UPLOAD}

  echo ""
  local final_exit=0
  if [[ ${STEP_SETUP} -ne 0 ]] || [[ ${STEP_PLATFORM} -ne 0 ]] || [[ ${STEP_TESTS} -ne 0 ]]; then
    final_exit=1
    err "${BOLD}FAILED${NC} in $(( duration / 60 ))m$(( duration % 60 ))s"
  else
    log "${BOLD}${GREEN}ALL PASSED${NC} in $(( duration / 60 ))m$(( duration % 60 ))s"
  fi

  exit ${final_exit}
}

_print_step() {
  local name="$1" code="$2"
  case ${code} in
    0) echo -e "  ${GREEN}✓${NC} ${name}" ;;
    1) echo -e "  ${YELLOW}○${NC} ${name} ${YELLOW}(skipped)${NC}" ;;
    2) echo -e "  ${RED}✗${NC} ${name} ${RED}(FAILED)${NC}" ;;
  esac
}

trap cleanup EXIT

# ═════════════════════════════════════════════════════════════════
# STEP 1: Devcontainer setup
# ═════════════════════════════════════════════════════════════════
log "═══════════════════════════════════════════════════"
log "STEP 1: Devcontainer setup"
log "═══════════════════════════════════════════════════"

bash .devcontainer/ctl.sh start
SETUP_EXIT=$?
if [[ ${SETUP_EXIT} -eq 0 ]]; then
  STEP_SETUP=0
  log "Devcontainer setup complete"

  # Install Claude Code CLI for AI review stages (if credentials are mounted)
  if [[ -f /root/.claude/.credentials.json ]]; then
    log "Installing Claude Code CLI for AI review stages..."
    npm install -g @anthropic-ai/claude-code@latest 2>&1 || warn "Claude Code install failed (non-fatal)"
  fi
else
  STEP_SETUP=2
  err "Devcontainer setup FAILED (exit ${SETUP_EXIT})"
  err "Cannot continue — aborting"
  exit 1  # triggers cleanup trap
fi

# Export env vars needed by docker-compose services
export CONCORD_API_KEY="ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"

# Export SSH key for docker-compose services (git-poller needs it as base64 env var)
if [[ -f /root/.ssh/id_rsa ]]; then
  export BITBUCKET_SSH_KEY
  BITBUCKET_SSH_KEY=$(base64 -w0 /root/.ssh/id_rsa)
  log "SSH key exported for docker-compose services"
fi

# ═════════════════════════════════════════════════════════════════
# STEP 2: Start development platform
# ═════════════════════════════════════════════════════════════════
echo ""
log "═══════════════════════════════════════════════════"
log "STEP 2: Start development platform"
log "═══════════════════════════════════════════════════"

npx nx start platform --output-style=stream --verbose
PLATFORM_EXIT=$?
if [[ ${PLATFORM_EXIT} -eq 0 ]]; then
  STEP_PLATFORM=0
  log "Platform started successfully"
else
  STEP_PLATFORM=2
  err "Platform start FAILED (exit ${PLATFORM_EXIT})"
  err "Cannot run tests without a running platform — aborting"
  exit 1  # triggers cleanup trap
fi

# ═════════════════════════════════════════════════════════════════
# STEP 3: Run E2E tests
# ═════════════════════════════════════════════════════════════════
echo ""
log "═══════════════════════════════════════════════════"
log "STEP 3: E2E tests"
log "═══════════════════════════════════════════════════"

npx nx run platform:test:e2e --output-style=stream --verbose 2>&1 | tee /tmp/e2e-output.log
TEST_EXIT=${PIPESTATUS[0]}
if [[ ${TEST_EXIT} -eq 0 ]]; then
  STEP_TESTS=0
  log "E2E tests passed"
else
  STEP_TESTS=2
  err "E2E tests FAILED (exit ${TEST_EXIT})"
fi

# ═════════════════════════════════════════════════════════════════
# STEP 4: Upload results to MinIO
# ═════════════════════════════════════════════════════════════════
echo ""
log "═══════════════════════════════════════════════════"
log "STEP 4: Upload results"
log "═══════════════════════════════════════════════════"

if [[ -n "${MINIO_ACCESS_KEY:-}" ]] && [[ -n "${MINIO_SECRET_KEY:-}" ]] && command -v mc &>/dev/null; then
  RESULTS_PATH="${MINIO_BUCKET}/nightly/${RUN_DATE}-${COMMIT}"

  if mc alias set cluster "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --quiet 2>&1; then
    mc mb -p "cluster/${MINIO_BUCKET}" 2>/dev/null || true

    # Upload test output
    if [[ -f /tmp/e2e-output.log ]]; then
      mc cp /tmp/e2e-output.log "cluster/${RESULTS_PATH}/output.log" --quiet 2>&1 || warn "Failed to upload output.log"
    fi

    # Upload summary
    cat > /tmp/summary.json <<EOF
{
  "date": "${RUN_DATE}",
  "commit": "${COMMIT}",
  "branch": "${BRANCH:-main}",
  "setup": ${STEP_SETUP},
  "platform": ${STEP_PLATFORM},
  "tests": ${STEP_TESTS},
  "duration_s": $(( $(date -u +%s) - STARTED_AT ))
}
EOF
    mc cp /tmp/summary.json "cluster/${RESULTS_PATH}/summary.json" --quiet 2>&1 || warn "Failed to upload summary.json"

    STEP_UPLOAD=0
    log "Results uploaded to ${RESULTS_PATH}/"
  else
    STEP_UPLOAD=2
    err "MinIO alias setup failed"
  fi
else
  warn "MinIO credentials not available — skipping upload"
fi

# Exit triggers cleanup trap which prints the summary
exit 0
