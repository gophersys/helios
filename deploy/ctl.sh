#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# Concord Platform CLI
# ───────────────────────────────────────────────────────────────
# Single entry point for all platform lifecycle operations across
# development, staging, and production environments.
#
# Usage:
#   ./deploy/ctl.sh <environment> <action> [args...]
#
# Environments:
#   development   Docker Compose (local containers)
#   staging       Kubernetes staging namespace
#   production    Kubernetes production namespace
#
# Lifecycle:
#   start         Full 0→running (idempotent)
#   update        Rebuild + redeploy (fast, cached)
#   stop          Teardown app workloads (safe)
#   status        Show what's running
#   logs          Tail component logs
# ───────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

COMPOSE="docker compose -f deploy/development/docker-compose.yaml"
HELM_DIR="${SCRIPT_DIR}/production/helm"

REGISTRY="containers.ad.corekinect.com"
REGISTRY_API="${REGISTRY}/concord-http-api"
REGISTRY_FRONTEND="${REGISTRY}/concord-frontend"
REGISTRY_GIT_POLLER="${REGISTRY}/concord-git-poller"
REGISTRY_BUILD_SERVICE="${REGISTRY}/concord-build-service"
REGISTRY_DOCS="${REGISTRY}/concord-docs"
REGISTRY_TEST_RUNNER="${REGISTRY}/concord-test-runner"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[concord]${NC} $*"; }
warn() { echo -e "${YELLOW}[concord]${NC} $*"; }
err()  { echo -e "${RED}[concord]${NC} $*" >&2; }
info() { echo -e "${CYAN}[concord]${NC} $*"; }
step() { echo -e "\n${CYAN}▸${NC} $*"; }

TIMER_START=0
timer_start() { TIMER_START=$(date +%s%N); }
timer_end() {
  local elapsed_ms=$(( ($(date +%s%N) - TIMER_START) / 1000000 ))
  if (( elapsed_ms > 60000 )); then
    info "  ${1}: ${BOLD}$(( elapsed_ms / 1000 ))s${NC}"
  else
    info "  ${1}: ${BOLD}${elapsed_ms}ms${NC}"
  fi
}

# ═════════════════════════════════════════════════════════════════
# Shared helpers
# ═════════════════════════════════════════════════════════════════

get_version() {
  local tag
  tag=$(git describe --tags --exact-match 2>/dev/null || true)
  if [[ -n "${tag}" ]]; then
    echo "${tag}"
  else
    local pkg_version sha
    pkg_version=$(node -p "require('./apps/frontend/app/package.json').version" 2>/dev/null || echo "0.0.1")
    sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    echo "${pkg_version}-${sha}"
  fi
}

_preflight() {
  # Verify cluster access for staging/production operations
  if ! kubectl cluster-info &>/dev/null; then
    err "Cannot reach Kubernetes cluster"
    err "Check your kubeconfig: kubectl cluster-info"
    exit 1
  fi
  if ! command -v helm &>/dev/null; then
    err "helm not found — install: https://helm.sh/docs/intro/install/"
    exit 1
  fi
}

_prisma_schema_hash() {
  sha256sum prisma/schema.prisma 2>/dev/null | awk '{print $1}'
}

_db_setup() {
  # Prisma generate + push + seed (shared by dev start and dev update)
  local db_url="postgresql://concord:concord@localhost:5433/concord"
  cd prisma
  if [[ "${CI:-false}" == "true" ]]; then
    yarn prisma generate 2>&1
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      yarn prisma db push --accept-data-loss --skip-generate 2>&1
  else
    yarn prisma generate 2>&1 | grep -E "^✔|Generated" || true
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      yarn prisma db push --accept-data-loss --skip-generate 2>&1 | grep -E "^🚀|Your database" || true
  fi
  if [[ "${CI:-false}" == "true" ]]; then
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      PYTHONPATH=../libs/python:../libs:../libs/protocols \
      python3 -m seed.main 2>&1
  else
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      PYTHONPATH=../libs/python:../libs:../libs/protocols \
      python3 -m seed.main 2>&1 | grep -E "^===|Product access:" | head -5 || true
  fi
  cd ..
}

# ═════════════════════════════════════════════════════════════════
# Build (shared by dev + staging + production)
# ═════════════════════════════════════════════════════════════════

cmd_build() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend" "git-poller" "build-service" "docs")

  # In CI, stream docker build output instead of suppressing it
  local build_redirect="/dev/null"
  if [[ "${CI:-false}" == "true" ]]; then
    build_redirect="/dev/stdout"
  fi

  local version
  version=$(get_version)

  log "Building  version=${BOLD}${version}${NC}  env=${BOLD}${env}${NC}  targets=${BOLD}${targets[*]}${NC}"

  export APP_VERSION="${version}"
  export PUBLIC_APP_VERSION="${version}"
  export ENVIRONMENT="${env}"
  export PUBLIC_APP_ENVIRONMENT="${env}"
  export GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  export GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  export GIT_DIRTY="$([ -n "$(git status --porcelain 2>/dev/null)" ] && echo true || echo false)"
  export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  export BUILD_HOST="$(hostname)"

  info "  commit=${GIT_COMMIT} branch=${GIT_BRANCH} dirty=${GIT_DIRTY}"

  for target in "${targets[@]}"; do
    case "${target}" in
      api|http-api|backend)
        timer_start
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/http-api/deploy/Dockerfile \
          --tag "${REGISTRY_API}:${env}" \
          --load . > "${build_redirect}" 2>&1
        timer_end "API build"
        ;;
      frontend|fe|app|ui)
        timer_start
        docker buildx build \
          --build-arg PUBLIC_APP_ENVIRONMENT="${env}" \
          --build-arg PUBLIC_APP_VERSION="${version}" \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/frontend/app/deploy/Dockerfile \
          --tag "${REGISTRY_FRONTEND}:${env}" \
          --load . > "${build_redirect}" 2>&1
        timer_end "Frontend build"
        ;;
      git-poller|poller)
        timer_start
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/git-poller/deploy/Dockerfile \
          --tag "${REGISTRY_GIT_POLLER}:${env}" \
          --load . > "${build_redirect}" 2>&1
        timer_end "Git-poller build"
        ;;
      runner|test-runner)
        timer_start
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file deploy/runner/Dockerfile \
          --tag "${REGISTRY_TEST_RUNNER}:${env}" \
          --tag "${REGISTRY_TEST_RUNNER}:${env}-${GIT_COMMIT}" \
          --load . > "${build_redirect}" 2>&1
        timer_end "Test runner build"
        ;;
      build-service)
        timer_start
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/build-service/deploy/Dockerfile \
          --tag "${REGISTRY_BUILD_SERVICE}:${env}" \
          --load . > "${build_redirect}" 2>&1
        timer_end "Build-service build"
        ;;
      docs)
        timer_start
        docker buildx build \
          --file apps/frontend/docs/deploy/Dockerfile \
          --tag "${REGISTRY_DOCS}:${env}" \
          --load . > "${build_redirect}" 2>&1
        timer_end "Docs build"
        ;;
      *)
        err "Unknown build target: ${target}"
        err "Valid: api, frontend, git-poller, runner, build-service, docs"
        exit 1
        ;;
    esac
  done
  log "Build complete."
}

# ═════════════════════════════════════════════════════════════════
# Push / Helm (staging + production)
# ═════════════════════════════════════════════════════════════════

_push_images() {
  local env="$1"
  shift
  local targets=("$@")

  if command -v k3s &>/dev/null; then
    log "Importing images into K3s..."
    for target in "${targets[@]}"; do
      case "${target}" in
        api|http-api|backend)     docker save "${REGISTRY_API}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
        frontend|fe|app|ui)       docker save "${REGISTRY_FRONTEND}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
        git-poller|poller)        docker save "${REGISTRY_GIT_POLLER}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
        runner|test-runner)       docker save "${REGISTRY_TEST_RUNNER}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
        build-service)            docker save "${REGISTRY_BUILD_SERVICE}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
        docs)                     docker save "${REGISTRY_DOCS}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
      esac
    done
  else
    log "Pushing images to registry..."
    timer_start
    for target in "${targets[@]}"; do
      case "${target}" in
        api|http-api|backend)     docker push "${REGISTRY_API}:${env}" > /dev/null 2>&1 || true ;;
        frontend|fe|app|ui)       docker push "${REGISTRY_FRONTEND}:${env}" > /dev/null 2>&1 || true ;;
        git-poller|poller)        docker push "${REGISTRY_GIT_POLLER}:${env}" > /dev/null 2>&1 || true ;;
        runner|test-runner)       docker push "${REGISTRY_TEST_RUNNER}:${env}" > /dev/null 2>&1 || true ;;
        build-service)            docker push "${REGISTRY_BUILD_SERVICE}:${env}" > /dev/null 2>&1 || true ;;
        docs)                     docker push "${REGISTRY_DOCS}:${env}" > /dev/null 2>&1 || true ;;
      esac
    done
    timer_end "Push"
  fi
}

_helm_deploy() {
  local env="$1"
  local helm_args=(
    upgrade --install concord
    "${HELM_DIR}/concord"
    -n "${env}" --create-namespace
    -f "${HELM_DIR}/values-${env}.yaml"
    --set "httpApi.image.tag=${env}"
    --set "frontend.image.tag=${env}"
    --set "gitPoller.image.tag=${env}"
  )

  if [[ -f "${HELM_DIR}/values-${env}-secrets.yaml" ]]; then
    helm_args+=(-f "${HELM_DIR}/values-${env}-secrets.yaml")
  fi

  timer_start
  helm "${helm_args[@]}" --wait --rollback-on-failure --timeout 600s
  timer_end "Helm upgrade"
}

_verify_rollout() {
  local env="$1"
  info "Verifying rollout..."
  local deployments
  deployments=$(kubectl get deployments -n "${env}" --no-headers -o custom-columns=":metadata.name" 2>/dev/null || true)
  local all_ok=true
  for dep in ${deployments}; do
    if kubectl rollout status "deployment/${dep}" -n "${env}" --timeout=180s &>/dev/null; then
      info "  ✓ ${dep}"
    else
      warn "  ✗ ${dep} not ready"
      all_ok=false
    fi
  done
  $all_ok || warn "Some deployments did not reach Ready state"
}

_smoke_test() {
  local env="$1"
  info "Running smoke tests..."
  local all_ok=true

  # Get an http-api pod to exec from (it has Python for HTTP checks)
  local api_pod
  api_pod=$(kubectl get pods -n "${env}" -l app.kubernetes.io/name=concord-http-api \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

  if [[ -z "${api_pod}" ]]; then
    warn "  ✗ No running http-api pod found for smoke tests"
    return 1
  fi

  # Smoke test each service endpoint from inside the cluster
  local -A checks=(
    ["http-api|concord-http-api:9001/v2/docs"]="API docs"
    ["frontend|concord-frontend:80/"]="Frontend"
    ["docs|concord-docs:80/"]="Docs"
  )

  for key in "${!checks[@]}"; do
    local label="${checks[$key]}"
    local url="http://${key#*|}"
    local svc="${key%%|*}"

    local status
    status=$(kubectl exec -n "${env}" "${api_pod}" -- \
      python3 -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('${url}', timeout=10)
    print(r.status)
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null || echo "ERR:exec-failed")

    if [[ "${status}" =~ ^2[0-9][0-9]$ ]]; then
      info "  ✓ ${label} → ${status}"
    else
      warn "  ✗ ${label} → ${status}"
      all_ok=false
    fi
  done

  # Build-service has no K8s Service (it's a worker, not an endpoint).
  # Check that the pod is running and healthy via its liveness probe.
  local bs_ready
  bs_ready=$(kubectl get pods -n "${env}" -l app.kubernetes.io/name=concord-build-service \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
  if [[ "${bs_ready}" -gt 0 ]]; then
    info "  ✓ Build service pod running"
  else
    warn "  ✗ Build service pod not running"
    all_ok=false
  fi

  if $all_ok; then
    info "Smoke tests passed"
    return 0
  else
    warn "Smoke tests FAILED"
    return 1
  fi
}

_rollback_on_failure() {
  local env="$1"
  warn "Rolling back to previous release..."

  local prev_rev
  prev_rev=$(helm history concord -n "${env}" -o json 2>/dev/null \
    | python3 -c "
import sys, json
h = json.load(sys.stdin)
deployed = [r for r in h if r.get('status') == 'deployed']
print(deployed[-1]['revision'] if deployed else '')
" 2>/dev/null || echo "")

  if [[ -z "${prev_rev}" ]]; then
    err "No previous revision to rollback to"
    return 1
  fi

  info "Rolling back to revision ${prev_rev}..."
  helm rollback concord "${prev_rev}" -n "${env}" --wait --timeout 300s

  # Verify rollback
  _verify_rollout "${env}"

  info "Rollback complete. Investigate and fix before re-deploying."
  return 0
}

# ═════════════════════════════════════════════════════════════════
# Deploy (staging/production) — build + push + helm
# ═════════════════════════════════════════════════════════════════

cmd_deploy() {
  local env="$1"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend" "git-poller" "build-service" "docs")

  local version
  version=$(get_version)
  local total_start
  total_start=$(date +%s)

  log "Deploying to ${BOLD}${env}${NC}  version=${BOLD}${version}${NC}  targets=${BOLD}${targets[*]}${NC}"
  echo ""

  cmd_build "${env}" "${targets[@]}"
  echo ""

  _push_images "${env}" "${targets[@]}"
  echo ""

  log "Helm upgrade..."
  _helm_deploy "${env}"

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Deployed in ${total_elapsed}s${NC}"
}

# ═════════════════════════════════════════════════════════════════
# Quick deploy (staging/production) — build + push + restart
# ═════════════════════════════════════════════════════════════════

_restart_targets() {
  local env="$1"
  shift
  local targets=("$@")
  local restart_args=""
  for target in "${targets[@]}"; do
    case "${target}" in
      api|http-api|backend)     restart_args="${restart_args} deployment/concord-http-api" ;;
      frontend|fe|app|ui)       restart_args="${restart_args} deployment/concord-frontend" ;;
      git-poller|poller)        restart_args="${restart_args} deployment/concord-git-poller" ;;
    esac
  done
  if [[ -n "${restart_args}" ]]; then
    timer_start
    kubectl rollout restart ${restart_args} -n "${env}" > /dev/null 2>&1
    for target in "${targets[@]}"; do
      case "${target}" in
        api|http-api|backend) kubectl rollout status deployment/concord-http-api -n "${env}" --timeout=90s > /dev/null 2>&1 ;;
        frontend|fe|app|ui)   kubectl rollout status deployment/concord-frontend -n "${env}" --timeout=30s > /dev/null 2>&1 ;;
        git-poller|poller)    kubectl rollout status deployment/concord-git-poller -n "${env}" --timeout=30s > /dev/null 2>&1 ;;
        docs)                 kubectl rollout status deployment/concord-docs -n "${env}" --timeout=30s > /dev/null 2>&1 ;;
      esac
    done
    timer_end "Rollout"
  fi
}

cmd_quick() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend")
  local total_start
  total_start=$(date +%s)
  log "Quick deploy  env=${BOLD}${env}${NC}  targets=${BOLD}${targets[*]}${NC}"
  echo ""
  cmd_build "${env}" "${targets[@]}"
  echo ""
  _push_images "${env}" "${targets[@]}"
  echo ""
  _restart_targets "${env}" "${targets[@]}"
  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Quick deploy done in ${total_elapsed}s${NC}"
}

# ═════════════════════════════════════════════════════════════════
# Status / Logs / Diff
# ═════════════════════════════════════════════════════════════════

cmd_status() {
  local env="${1:-staging}"
  echo ""
  echo -e "${BOLD}=== ${env} Pods ===${NC}"
  kubectl get pods -n "${env}" --no-headers 2>/dev/null | grep -v Terminating || echo "  No pods found"
  echo ""
  echo -e "${BOLD}=== ${env} Services ===${NC}"
  kubectl get svc -n "${env}" 2>/dev/null || echo "  No services found"
}

cmd_logs() {
  local env="${1:-staging}"
  local component="${2:-http-api}"
  kubectl logs -n "${env}" -l "app.kubernetes.io/name=concord-${component}" -f --tail=100 2>/dev/null || \
    kubectl logs -n "${env}" -l "app=concord-${component}" -f --tail=100
}

cmd_restart() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend")
  _restart_targets "${env}" "${targets[@]}"
  log "Restart complete."
}

cmd_diff() {
  local env="${1:-staging}"
  local values_file="${HELM_DIR}/values-${env}.yaml"
  [[ ! -f "${values_file}" ]] && { err "No values file for: ${env}"; exit 1; }
  local helm_args=(diff upgrade concord "${HELM_DIR}/concord" -n "${env}" -f "${values_file}")
  [[ -f "${HELM_DIR}/values-${env}-secrets.yaml" ]] && helm_args+=(-f "${HELM_DIR}/values-${env}-secrets.yaml")
  helm "${helm_args[@]}" 2>/dev/null || warn "Install helm-diff: helm plugin install https://github.com/databus23/helm-diff"
}

# ═════════════════════════════════════════════════════════════════
# DEVELOPMENT — start / update / stop / status / logs / ready
# ═════════════════════════════════════════════════════════════════

cmd_dev_start() {
  local total_start
  total_start=$(date +%s)
  log "${BOLD}Starting development platform${NC}"

  # Protobuf
  step "Generating protobuf code"
  bash libs/protocols/ctl.sh generate 2>&1 | grep -E "^(Generating|Processing)" || true
  info "  ✓ protobuf"

  # Build service images (parallel via Nx)
  step "Building service images"
  timer_start
  if [[ "${CI:-false}" == "true" ]]; then
    npx nx run-many -t build -p http-api git-poller build-service -c development --output-style=stream --verbose 2>&1
  else
    npx nx run-many -t build -p http-api git-poller build-service -c development 2>&1 | tail -5
  fi
  timer_end "Image builds"

  # Start infrastructure first
  step "Starting infrastructure"
  $COMPOSE up -d db minio pypi 2>&1 | grep -v "^$"
  info "  ✓ postgres, minio, pypi"

  # Wait for DB
  step "Waiting for postgres"
  until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
  info "  ✓ postgres ready"

  # Database setup
  step "Database setup (generate → push → seed)"
  _db_setup
  info "  ✓ schema pushed, data seeded"

  # Start all services
  step "Starting backend services"
  $COMPOSE up -d 2>&1 | grep -v "^$"
  info "  ✓ all services up"

  # Summary
  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Platform running${NC}  (${total_elapsed}s)"
  echo -e "  ${DIM}http-api       ${NC} localhost:9001"
  echo -e "  ${DIM}build-service  ${NC} localhost:9002"
  echo -e "  ${DIM}git-poller     ${NC} running"
  echo -e "  ${DIM}postgres       ${NC} localhost:5433"
  echo -e "  ${DIM}minio          ${NC} localhost:8675 ${DIM}(console: 8676)${NC}"
  echo -e "  ${DIM}pypi           ${NC} localhost:8091"
  echo ""
  echo -e "Start the UI:  ${CYAN}npx nx serve app${NC}  → localhost:4200"
}

cmd_dev_update() {
  local total_start
  total_start=$(date +%s)
  log "${BOLD}Updating development platform${NC}"

  # Rebuild + restart — --no-cache guarantees fresh source in images
  step "Rebuilding containers"
  timer_start
  $COMPOSE build --no-cache --parallel http-api git-poller build-service 2>&1 | tail -5
  timer_end "Image builds"

  step "Restarting containers"
  $COMPOSE up -d --force-recreate --no-build 2>&1 | grep -v "^$"
  info "  ✓ containers updated"

  # Check if schema changed — if so, push + seed
  local local_hash
  local_hash=$(_prisma_schema_hash)
  local cache_file="${REPO_ROOT}/.nx/prisma-schema-hash-dev"
  local cached_hash=""
  [[ -f "${cache_file}" ]] && cached_hash=$(cat "${cache_file}" 2>/dev/null)
  if [[ "${local_hash}" != "${cached_hash}" ]]; then
    step "Prisma schema changed — updating database"
    # Wait for DB to be ready (might have just restarted)
    until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
    _db_setup
    mkdir -p "$(dirname "${cache_file}")"
    echo "${local_hash}" > "${cache_file}"
    info "  ✓ schema pushed, data seeded"
  fi

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Update complete${NC}  (${total_elapsed}s)"
}

cmd_dev_stop() {
  log "${BOLD}Stopping development platform${NC}"
  $COMPOSE down 2>&1 | grep -v "^$"
  log "Platform stopped."
}

cmd_dev_status() {
  $COMPOSE ps
}

cmd_dev_logs() {
  local component="${1:-}"
  if [[ -n "${component}" ]]; then
    $COMPOSE logs -f --tail=50 "${component}"
  else
    $COMPOSE logs -f --tail=50
  fi
}

cmd_dev_ready() {
  # Re-migrate + re-seed without restarting containers
  step "Waiting for postgres"
  until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
  info "  ✓ postgres ready"

  step "Database setup (generate → push → seed)"
  _db_setup
  info "  ✓ schema pushed, data seeded"
}

# ═════════════════════════════════════════════════════════════════
# STAGING / PRODUCTION — start / update / stop
# ═════════════════════════════════════════════════════════════════

cmd_start() {
  local env="$1"
  local total_start
  total_start=$(date +%s)

  log "${BOLD}Starting platform: ${env}${NC}"
  echo ""

  # Preflight
  step "Preflight checks"
  _preflight
  info "  ✓ cluster reachable, helm available"

  # Bootstrap infrastructure (idempotent)
  step "Ensuring infrastructure"
  bash infrastructure/ctl.sh office bootstrap
  echo ""

  # Sync secrets for this namespace
  step "Syncing secrets (${env})"
  bash infrastructure/clusters/office/secrets/create-all.sh "${env}"
  echo ""

  # Build + push + helm deploy
  step "Deploying applications"
  cmd_deploy "${env}"
  echo ""

  # Verify
  step "Verifying rollout"
  _verify_rollout "${env}"

  # Smoke test — rollback on failure
  step "Smoke testing"
  if ! _smoke_test "${env}"; then
    _rollback_on_failure "${env}"
    exit 1
  fi

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Platform started: ${env}${NC}  (${total_elapsed}s)"
}

cmd_update() {
  local env="$1"
  local total_start
  total_start=$(date +%s)

  log "${BOLD}Updating platform: ${env}${NC}"
  echo ""

  # Preflight
  step "Preflight checks"
  _preflight
  info "  ✓ cluster reachable, helm available"

  # Sync secrets (catches newly added .env values)
  step "Syncing secrets (${env})"
  bash infrastructure/clusters/office/secrets/create-all.sh "${env}"
  echo ""

  # Build + push + helm deploy
  step "Deploying applications"
  cmd_deploy "${env}"
  echo ""

  # Verify
  step "Verifying rollout"
  _verify_rollout "${env}"

  # Smoke test — rollback on failure
  step "Smoke testing"
  if ! _smoke_test "${env}"; then
    _rollback_on_failure "${env}"
    exit 1
  fi

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Platform updated: ${env}${NC}  (${total_elapsed}s)"
}

cmd_stop() {
  local env="$1"

  # Production safety gate — require explicit confirmation
  if [[ "${env}" == "production" ]]; then
    if [[ "${2:-}" != "--confirm-delete" ]]; then
      err "Refusing to stop production without explicit confirmation."
      echo ""
      echo "  Production stop will:"
      echo "    • Remove all application pods (http-api, frontend, etc.)"
      echo "    • PVCs are protected (helm.sh/resource-policy: keep)"
      echo "    • Database and MinIO data survive on disk"
      echo ""
      echo "  If you are sure, run:"
      echo "    ./deploy/ctl.sh production stop --confirm-delete"
      echo ""
      exit 1
    fi
    warn "Production stop confirmed. Proceeding..."
  fi

  log "${BOLD}Stopping platform: ${env}${NC}"

  _preflight

  # Check if release exists
  if helm list -n "${env}" --short 2>/dev/null | grep -q "^concord$"; then
    log "Removing Helm release from ${env}..."
    helm uninstall concord -n "${env}" --wait 2>&1 | sed 's/^/  /'
    log "${BOLD}Platform stopped: ${env}${NC}"
    info "PVCs preserved — data is safe. Run 'nx start platform -c ${env}' to redeploy."
  else
    info "Nothing to stop — no Helm release 'concord' in namespace ${env}"
  fi
}

# ═════════════════════════════════════════════════════════════════
# Help
# ═════════════════════════════════════════════════════════════════

usage() {
  cat <<EOF

${BOLD}Concord Platform CLI${NC}

${BOLD}Usage:${NC}
  ./deploy/ctl.sh <environment> <action> [args...]

${BOLD}Environments:${NC}
  ${GREEN}development${NC}    Docker Compose (local containers)
  ${GREEN}staging${NC}        Kubernetes staging namespace
  ${GREEN}production${NC}     Kubernetes production namespace

${BOLD}Lifecycle:${NC}
  ${GREEN}start${NC}          Full 0→running setup (idempotent, safe to run twice)
  ${GREEN}update${NC}         Rebuild changed images + redeploy (fast, cached)
  ${GREEN}stop${NC}           Teardown app workloads (keeps infrastructure)

${BOLD}Operations:${NC}
  ${GREEN}status${NC}         Show what's running
  ${GREEN}logs [comp]${NC}    Tail component logs
  ${GREEN}deploy${NC}         Build + push + helm upgrade (staging/prod)
  ${GREEN}quick${NC}          Build + push + restart, skip helm (staging/prod)
  ${GREEN}restart${NC}        Rolling restart (staging/prod)
  ${GREEN}ready${NC}          Re-migrate + re-seed DB (development)
  ${GREEN}diff${NC}           Preview Helm changes (staging/prod)

${BOLD}Examples:${NC}
  ./deploy/ctl.sh development start       Full dev startup
  ./deploy/ctl.sh development update      Fast rebuild + restart changed
  ./deploy/ctl.sh development stop        Compose down

  ./deploy/ctl.sh staging start           Bootstrap + build + deploy
  ./deploy/ctl.sh staging update          Rebuild + redeploy (cached)
  ./deploy/ctl.sh staging stop            Helm uninstall
  ./deploy/ctl.sh staging status          Show pods + services

  ./deploy/ctl.sh production start        Full production deploy
  ./deploy/ctl.sh production update       Update production
  ./deploy/ctl.sh production stop         Remove production workloads

${BOLD}Nx shortcuts:${NC}
  nx start platform                       → development start
  nx update platform                      → development update
  nx stop platform                        → development stop
  nx start platform -c staging            → staging start
  nx update platform -c staging           → staging update
  nx run platform:status -c staging       → staging status

EOF
}

# ═════════════════════════════════════════════════════════════════
# Main dispatch
# ═════════════════════════════════════════════════════════════════

if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]] || [[ "$1" == "help" ]]; then
  usage
  exit 0
fi

ENV="$1"
shift

# Dispatch by environment
case "${ENV}" in
  development|dev)
    ACTION="${1:-start}"; shift || true
    case "${ACTION}" in
      start)   cmd_dev_start ;;
      update)  cmd_dev_update ;;
      stop)    cmd_dev_stop ;;
      status)  cmd_dev_status ;;
      logs)    cmd_dev_logs "$@" ;;
      ready)   cmd_dev_ready ;;
      *)       err "Unknown development action: ${ACTION}"; usage; exit 1 ;;
    esac
    ;;

  staging|production)
    ACTION="${1:-start}"; shift || true
    case "${ACTION}" in
      start)   cmd_start "${ENV}" ;;
      update)  cmd_update "${ENV}" ;;
      stop)    cmd_stop "${ENV}" "$@" ;;
      deploy)  cmd_deploy "${ENV}" "$@" ;;
      quick)   cmd_quick "${ENV}" "$@" ;;
      status)  cmd_status "${ENV}" ;;
      logs)    cmd_logs "${ENV}" "$@" ;;
      restart) cmd_restart "${ENV}" "$@" ;;
      diff)    cmd_diff "${ENV}" ;;
      *)       err "Unknown ${ENV} action: ${ACTION}"; usage; exit 1 ;;
    esac
    ;;

  version) get_version ;;

  *)
    err "Unknown environment: ${ENV}"
    usage
    exit 1
    ;;
esac
