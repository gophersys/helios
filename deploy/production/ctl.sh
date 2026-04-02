#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────────────
# Concord Deployment CLI
# ───────────────────────────────────────────────────────────────
# Usage:
#   ./deploy/ctl.sh <environment> <action> [targets...]
#
# Environments:
#   development — Docker Compose infra only, run apps via Nx
#   staging     — Kubernetes staging namespace
#   production  — Kubernetes production namespace
#
# Targets (for build/deploy):
#   api, frontend, git-poller, validation, build-service, docs
#   Default: api frontend git-poller
# ───────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

REGISTRY="containers.ad.corekinect.com"
REGISTRY_API="${REGISTRY}/concord-http-api"
REGISTRY_FRONTEND="${REGISTRY}/concord-frontend"
REGISTRY_GIT_POLLER="${REGISTRY}/concord-git-poller"
REGISTRY_VALIDATION="${REGISTRY}/concord-validation-alpha"
REGISTRY_BUILD_SERVICE="${REGISTRY}/concord-build-service"
REGISTRY_DOCS="${REGISTRY}/concord-docs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[concord]${NC} $*"; }
warn() { echo -e "${YELLOW}[concord]${NC} $*"; }
err()  { echo -e "${RED}[concord]${NC} $*" >&2; }
info() { echo -e "${CYAN}[concord]${NC} $*"; }

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

# ─── Version ──────────────────────────────────────────────────

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

# ─── Prisma Schema Change Detection ──────────────────────────

_prisma_needs_regen() {
  # Compare local schema hash to the last deployed hash (stored in .nx/cache)
  local local_hash
  local_hash=$(sha256sum prisma/schema.prisma 2>/dev/null | awk '{print $1}')

  local cache_file="${REPO_ROOT}/.nx/prisma-schema-hash"
  local cached_hash=""
  [[ -f "${cache_file}" ]] && cached_hash=$(cat "${cache_file}" 2>/dev/null)

  if [[ "${local_hash}" != "${cached_hash}" ]]; then
    # Update the cache after build
    mkdir -p "$(dirname "${cache_file}")"
    echo "${local_hash}" > "${cache_file}"
    return 0  # Needs regen
  fi
  return 1  # Schema matches
}

# ─── Build ────────────────────────────────────────────────────

cmd_build() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend" "git-poller")

  local version
  version=$(get_version)

  log "Building  version=${BOLD}${version}${NC}  env=${BOLD}${env}${NC}  targets=${BOLD}${targets[*]}${NC}"

  # Export build metadata
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
        # Check if Prisma schema changed — force no-cache on builder stage if so
        local docker_args=()
        if _prisma_needs_regen "${env}"; then
          warn "Prisma schema changed — rebuilding with fresh client generation"
          docker_args+=("--no-cache")
        fi

        timer_start
        docker buildx build "${docker_args[@]}" \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/http-api/deploy/Dockerfile \
          --tag "${REGISTRY_API}:${env}" \
          --load . > /dev/null 2>&1
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
          --load . > /dev/null 2>&1
        timer_end "Frontend build"
        ;;

      git-poller|poller)
        timer_start
        docker buildx build \
          --file apps/backend/git-poller/deploy/Dockerfile \
          --tag "${REGISTRY_GIT_POLLER}:${env}" \
          --load . > /dev/null 2>&1
        timer_end "Git-poller build"
        ;;

      validation|val)
        timer_start
        local val_git_hash
        val_git_hash=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg BUILD_TIME \
          --file apps/validation/alpha/deploy/Dockerfile \
          --tag "${REGISTRY_VALIDATION}:${env}" \
          --tag "${REGISTRY_VALIDATION}:${env}-${val_git_hash}" \
          --load . > /dev/null 2>&1
        timer_end "Validation build"
        ;;

      build-service)
        timer_start
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg BUILD_TIME \
          --file apps/backend/build-service/deploy/Dockerfile \
          --tag "${REGISTRY_BUILD_SERVICE}:${env}" \
          --load . > /dev/null 2>&1
        timer_end "Build-service build"
        ;;

      docs)
        timer_start
        docker buildx build \
          --file apps/frontend/docs/deploy/Dockerfile \
          --tag "${REGISTRY_DOCS}:${env}" \
          --load . > /dev/null 2>&1
        timer_end "Docs build"
        ;;

      *)
        err "Unknown build target: ${target}"
        err "Valid: api, frontend, git-poller, validation, build-service, docs"
        exit 1
        ;;
    esac
  done

  log "Build complete."
}

# ─── Push ─────────────────────────────────────────────────────

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
        validation|val)           docker save "${REGISTRY_VALIDATION}:${env}" | sudo k3s ctr images import - 2>/dev/null || true ;;
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
        validation|val)           docker push "${REGISTRY_VALIDATION}:${env}" > /dev/null 2>&1 || true ;;
        build-service)            docker push "${REGISTRY_BUILD_SERVICE}:${env}" > /dev/null 2>&1 || true ;;
        docs)                     docker push "${REGISTRY_DOCS}:${env}" > /dev/null 2>&1 || true ;;
      esac
    done
    timer_end "Push"
  fi
}

# ─── Helm Deploy ──────────────────────────────────────────────

_helm_deploy() {
  local env="$1"
  local helm_args=(
    upgrade --install concord
    "${SCRIPT_DIR}/helm/concord"
    -n "${env}" --create-namespace
    -f "${SCRIPT_DIR}/helm/values-${env}.yaml"
    --set "httpApi.image.tag=${env}"
    --set "frontend.image.tag=${env}"
    --set "gitPoller.image.tag=${env}"
  )

  if [[ -f "${SCRIPT_DIR}/helm/values-${env}-secrets.yaml" ]]; then
    helm_args+=(-f "${SCRIPT_DIR}/helm/values-${env}-secrets.yaml")
  fi

  timer_start
  helm "${helm_args[@]}" --wait --timeout 180s
  timer_end "Helm upgrade"
}

# ─── Selective Restart ────────────────────────────────────────

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
      esac
    done
    timer_end "Rollout"
  fi
}

# ─── Development ──────────────────────────────────────────────

# Development is handled by: npx nx start platform -c development
# See deploy/development/docker-compose.yaml

# ─── Deploy (staging/production) ──────────────────────────────

cmd_deploy() {
  local env="$1"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend" "git-poller")

  local version
  version=$(get_version)
  local total_start
  total_start=$(date +%s)

  log "Deploying to ${BOLD}${env}${NC}  version=${BOLD}${version}${NC}  targets=${BOLD}${targets[*]}${NC}"
  echo ""

  # Build
  cmd_build "${env}" "${targets[@]}"
  echo ""

  # Push
  _push_images "${env}" "${targets[@]}"
  echo ""

  # Helm (always runs — updates ConfigMaps, rollme annotations force restarts)
  log "Helm upgrade..."
  _helm_deploy "${env}"

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Deployed in ${total_elapsed}s${NC}"
}

# ─── Status/Logs/Restart ─────────────────────────────────────

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

# ─── Quick (selective build + restart, no helm) ───────────────

cmd_quick() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend")

  local version
  version=$(get_version)
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

# ─── Diff ─────────────────────────────────────────────────────

cmd_diff() {
  local env="${1:-staging}"
  local values_file="${SCRIPT_DIR}/helm/values-${env}.yaml"
  [[ ! -f "${values_file}" ]] && { err "No values file for: ${env}"; exit 1; }

  local helm_args=(diff upgrade concord "${SCRIPT_DIR}/helm/concord" -n "${env}" -f "${values_file}")
  [[ -f "${SCRIPT_DIR}/helm/values-${env}-secrets.yaml" ]] && helm_args+=(-f "${SCRIPT_DIR}/helm/values-${env}-secrets.yaml")

  helm "${helm_args[@]}" 2>/dev/null || warn "Install helm-diff: helm plugin install https://github.com/databus23/helm-diff"
}

# ─── Help ─────────────────────────────────────────────────────

usage() {
  cat <<EOF

${BOLD}Concord Deployment CLI${NC}

${BOLD}Usage:${NC}
  ./deploy/ctl.sh <command> [args...]

${BOLD}Commands:${NC}
  ${GREEN}development up|down|status|logs${NC}          Local Docker Compose infra

  ${GREEN}staging deploy [targets...]${NC}              Build + push + helm deploy to staging
  ${GREEN}staging quick [targets...]${NC}               Build + push + restart (skip helm)
  ${GREEN}staging status${NC}                           Show pods and services
  ${GREEN}staging logs [component]${NC}                 Tail logs (http-api, frontend, git-poller)
  ${GREEN}staging restart [targets...]${NC}             Rolling restart

  ${GREEN}production deploy [targets...]${NC}           Build + push + helm deploy to production
  ${GREEN}production quick [targets...]${NC}            Build + push + restart (skip helm)
  ${GREEN}production status|logs|restart${NC}           Same as staging

  ${GREEN}build <env> [targets...]${NC}                 Build Docker images only
  ${GREEN}diff [env]${NC}                               Preview Helm changes
  ${GREEN}version${NC}                                  Show version string

${BOLD}Targets:${NC}
  api, frontend, git-poller, validation, build-service, docs
  Default: api frontend git-poller

${BOLD}Examples:${NC}
  ./deploy/ctl.sh staging deploy                    # Full deploy everything
  ./deploy/ctl.sh staging deploy api                # Only rebuild + deploy API
  ./deploy/ctl.sh staging quick frontend            # Fast: rebuild frontend + restart pod
  ./deploy/ctl.sh staging quick api frontend        # Fast: rebuild both + restart
  ./deploy/ctl.sh staging logs http-api             # Watch API logs
  ./deploy/ctl.sh production deploy                 # Full production deploy

${BOLD}Notes:${NC}
  - Prisma schema changes are auto-detected → forces fresh client generation
  - 'quick' skips Helm (faster) — use 'deploy' when ConfigMaps/secrets change
  - rollme annotations ensure pods restart on every 'deploy'

EOF
}

# ─── Main ─────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

COMMAND="$1"
shift

case "${COMMAND}" in
  development|dev) err "Use: npx nx start platform -c development" ; exit 1 ;;
  build)           cmd_build "$@" ;;
  staging)
    action="${1:-deploy}"
    shift || true
    case "${action}" in
      deploy)  cmd_deploy staging "$@" ;;
      quick)   cmd_quick staging "$@" ;;
      status)  cmd_status staging ;;
      logs)    cmd_logs staging "$@" ;;
      restart) cmd_restart staging "$@" ;;
      destroy) warn "Removing staging..."; helm uninstall concord -n staging ;;
      *)       err "Unknown: staging ${action}"; exit 1 ;;
    esac
    ;;
  production)
    action="${1:-deploy}"
    shift || true
    case "${action}" in
      deploy)  cmd_deploy production "$@" ;;
      quick)   cmd_quick production "$@" ;;
      status)  cmd_status production ;;
      logs)    cmd_logs production "$@" ;;
      restart) cmd_restart production "$@" ;;
      *)       err "Unknown: production ${action}"; exit 1 ;;
    esac
    ;;
  diff)    cmd_diff "$@" ;;
  status)  cmd_status "$@" ;;
  version) get_version ;;
  help|-h|--help) usage ;;
  *)
    err "Unknown command: ${COMMAND}"
    usage
    exit 1
    ;;
esac
