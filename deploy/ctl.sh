#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────────────
# Concord Deployment CLI
# ───────────────────────────────────────────────────────────────
# Usage:
#   ./deploy/ctl.sh <command>
#
# Environments:
#   development — Docker Compose infra only (DB, MinIO, InfluxDB), run apps via Nx
#   staging     — Kubernetes staging namespace
#   production  — Kubernetes production namespace
# ───────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Image names
IMAGE_API="concord/http-api"
IMAGE_FRONTEND="concord/frontend"
REGISTRY="containers.ad.corekinect.com"
REGISTRY_API="${REGISTRY}/concord-http-api"
REGISTRY_FRONTEND="${REGISTRY}/concord-frontend"
REGISTRY_GIT_POLLER="${REGISTRY}/concord-git-poller"

# Colors
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

# ─── Version ──────────────────────────────────────────────────

get_version() {
  cd "${REPO_ROOT}"
  # Try git tag first, then fallback to package.json version + short sha
  local tag
  tag=$(git describe --tags --exact-match 2>/dev/null || true)
  if [[ -n "${tag}" ]]; then
    echo "${tag}"
  else
    local pkg_version
    pkg_version=$(node -p "require('./apps/frontend/app/package.json').version" 2>/dev/null || echo "0.0.1")
    local sha
    sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    echo "${pkg_version}-${sha}"
  fi
}

# ─── Build ────────────────────────────────────────────────────

cmd_build() {
  local target="${1:-all}"
  local env="${2:-staging}"
  local version
  version=$(get_version)

  log "Building images  version=${BOLD}${version}${NC}  env=${BOLD}${env}${NC}"
  echo ""

  cd "${REPO_ROOT}"

  # Export build metadata so Docker picks them up via --build-arg (no =value)
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

  if [[ "${target}" == "all" || "${target}" == "api" ]]; then
    log "Building http-api via Nx..."
    npx nx run http-api:containerize -c "${env}"
    # Also tag with version
    docker tag "${IMAGE_API}:${env}" "${IMAGE_API}:${env}-${version}" 2>/dev/null || true
    log "  → ${IMAGE_API}:${env}"
  fi

  if [[ "${target}" == "all" || "${target}" == "frontend" || "${target}" == "ui" ]]; then
    log "Building app via Nx..."
    npx nx run app:containerize -c "${env}"
    # Also tag with version
    docker tag "${IMAGE_FRONTEND}:${env}" "${IMAGE_FRONTEND}:${env}-${version}" 2>/dev/null || true
    log "  → ${IMAGE_FRONTEND}:${env}"
  fi

  if [[ "${target}" == "all" || "${target}" == "git-poller" ]]; then
    log "Building git-poller via Nx..."
    npx nx run git-poller:containerize -c "${env}"
    docker tag "concord/git-poller:${env}" "concord/git-poller:${env}-${version}" 2>/dev/null || true
    log "  → concord/git-poller:${env}"
  fi

  echo ""
  log "Build complete.  Tags: ${env}, ${env}-${version}"
}

# ─── Development (infrastructure only) ────────────────────────

cmd_development() {
  local action="${1:-up}"
  local compose_dir="${SCRIPT_DIR}/cloud/development"

  case "${action}" in
    up)
      log "Starting development infrastructure (DB, MinIO, InfluxDB)..."
      if ! docker network ls | grep -q concord_network; then
        docker network create concord_network
      fi
      docker compose -f "${compose_dir}/docker-compose.yaml" up -d
      echo ""
      log "Development infrastructure is running."
      echo ""
      info "Start apps via Nx (recommended):"
      info "  npx nx serve http-api         # Backend on :9001"
      info "  npx nx dev app         # Frontend on :4200"
      echo ""
      info "Or run both in parallel:"
      info "  npx nx run-many -t serve dev -p http-api app"
      ;;
    down)
      log "Stopping development infrastructure..."
      docker compose -f "${compose_dir}/docker-compose.yaml" down
      ;;
    status)
      docker compose -f "${compose_dir}/docker-compose.yaml" ps
      ;;
    logs)
      docker compose -f "${compose_dir}/docker-compose.yaml" logs -f "${@:2}"
      ;;
    *)
      err "Unknown development action: ${action}"
      err "Usage: ctl.sh development {up|down|status|logs}"
      exit 1
      ;;
  esac
}

# ─── Staging (Kubernetes) ────────────────────────────────────

cmd_staging() {
  local action="${1:-deploy}"

  case "${action}" in
    deploy)
      local version
      version=$(get_version)

      log "Deploying to staging namespace...  version=${BOLD}${version}${NC}"
      echo ""

      # Build images via Nx
      cmd_build all staging

      # Import images into K3s if running locally
      if command -v k3s &>/dev/null; then
        log "Importing images into K3s..."
        docker save "${IMAGE_API}:staging" | sudo k3s ctr images import - 2>/dev/null || true
        docker save "${IMAGE_FRONTEND}:staging" | sudo k3s ctr images import - 2>/dev/null || true
        docker save "concord/git-poller:staging" | sudo k3s ctr images import - 2>/dev/null || true
      elif command -v k3d &>/dev/null; then
        log "Importing images into K3d..."
        k3d image import "${IMAGE_API}:staging" "${IMAGE_FRONTEND}:staging" "concord/git-poller:staging" 2>/dev/null || true
      else
        # Push to registry for remote clusters
        log "Pushing images to registry..."
        docker push "${REGISTRY_API}:staging" 2>/dev/null || true
        docker push "${REGISTRY_FRONTEND}:staging" 2>/dev/null || true
        docker push "${REGISTRY_GIT_POLLER}:staging" 2>/dev/null || true
      fi

      echo ""

      # Deploy via Helm
      local helm_args=(
        upgrade --install concord
        "${SCRIPT_DIR}/helm/concord"
        -n staging --create-namespace
        -f "${SCRIPT_DIR}/helm/values-staging.yaml"
        --set "httpApi.image.tag=staging"
        --set "frontend.image.tag=staging"
        --set "gitPoller.image.tag=staging"
      )

      # Include secrets file if it exists (gitignored)
      if [[ -f "${SCRIPT_DIR}/helm/values-staging-secrets.yaml" ]]; then
        helm_args+=(-f "${SCRIPT_DIR}/helm/values-staging-secrets.yaml")
      fi

      log "Running Helm upgrade..."
      helm "${helm_args[@]}" --wait --timeout 180s

      echo ""
      log "Staging deployment complete."
      cmd_staging status
      ;;

    status)
      echo ""
      echo -e "${BOLD}=== Staging Pods ===${NC}"
      kubectl get pods -n staging -l app.kubernetes.io/part-of=concord -o wide 2>/dev/null || echo "  No pods found"
      echo ""
      echo -e "${BOLD}=== Staging Services ===${NC}"
      kubectl get svc -n staging -l app.kubernetes.io/part-of=concord 2>/dev/null || echo "  No services found"
      echo ""
      echo -e "${BOLD}=== Staging Ingress ===${NC}"
      kubectl get ingress -n staging 2>/dev/null || echo "  No ingress found"
      ;;

    logs)
      local component="${2:-http-api}"
      kubectl logs -n staging -l "app.kubernetes.io/name=concord-${component}" -f --tail=100
      ;;

    restart)
      log "Restarting staging deployments..."
      kubectl rollout restart deployment/concord-http-api -n staging
      kubectl rollout restart deployment/concord-frontend -n staging
      ;;

    destroy)
      warn "Removing all Concord resources from staging namespace..."
      helm uninstall concord -n staging
      log "Staging resources removed."
      ;;

    *)
      err "Unknown staging action: ${action}"
      err "Usage: ctl.sh staging {deploy|status|logs [component]|restart|destroy}"
      exit 1
      ;;
  esac
}

# ─── Production (Kubernetes) ──────────────────────────────────

cmd_production() {
  local action="${1:-deploy}"

  case "${action}" in
    deploy)
      local version
      version=$(get_version)

      log "Deploying to production namespace...  version=${BOLD}${version}${NC}"
      echo ""

      # Build images via Nx
      cmd_build all production

      # Import images into K3s if running locally, otherwise push to registry
      if command -v k3s &>/dev/null; then
        log "Importing images into K3s..."
        docker save "${IMAGE_API}:production" | sudo k3s ctr images import - 2>/dev/null || true
        docker save "${IMAGE_FRONTEND}:production" | sudo k3s ctr images import - 2>/dev/null || true
        docker save "concord/git-poller:production" | sudo k3s ctr images import - 2>/dev/null || true
      else
        log "Pushing images to registry..."
        docker push "${REGISTRY_API}:production"
        docker push "${REGISTRY_FRONTEND}:production"
        docker push "${REGISTRY_GIT_POLLER}:production" 2>/dev/null || true
      fi

      echo ""

      # Deploy via Helm
      local helm_args=(
        upgrade --install concord
        "${SCRIPT_DIR}/helm/concord"
        -n production --create-namespace
        -f "${SCRIPT_DIR}/helm/values-production.yaml"
        --set "httpApi.image.tag=production"
        --set "frontend.image.tag=production"
        --set "gitPoller.image.tag=production"
      )

      # Include secrets file if it exists (gitignored)
      if [[ -f "${SCRIPT_DIR}/helm/values-production-secrets.yaml" ]]; then
        helm_args+=(-f "${SCRIPT_DIR}/helm/values-production-secrets.yaml")
      fi

      log "Running Helm upgrade..."
      helm "${helm_args[@]}" --wait --timeout 180s

      echo ""
      log "Production deployment complete."
      cmd_production status
      ;;

    status)
      echo ""
      echo -e "${BOLD}=== Production Pods ===${NC}"
      kubectl get pods -n production -l app.kubernetes.io/part-of=concord -o wide 2>/dev/null || echo "  No pods found"
      echo ""
      echo -e "${BOLD}=== Production Services ===${NC}"
      kubectl get svc -n production -l app.kubernetes.io/part-of=concord 2>/dev/null || echo "  No services found"
      echo ""
      echo -e "${BOLD}=== Production Ingress ===${NC}"
      kubectl get ingress -n production 2>/dev/null || echo "  No ingress found"
      ;;

    logs)
      local component="${2:-http-api}"
      kubectl logs -n production -l "app.kubernetes.io/name=concord-${component}" -f --tail=100
      ;;

    restart)
      log "Restarting production deployments..."
      kubectl rollout restart deployment/concord-http-api -n production
      kubectl rollout restart deployment/concord-frontend -n production
      ;;

    *)
      err "Unknown production action: ${action}"
      err "Usage: ctl.sh production {deploy|status|logs [component]|restart}"
      exit 1
      ;;
  esac
}

# ─── Diff (Helm) ─────────────────────────────────────────────

cmd_diff() {
  local env="${1:-staging}"
  local values_file="${SCRIPT_DIR}/helm/values-${env}.yaml"

  if [[ ! -f "${values_file}" ]]; then
    err "No values file found for env: ${env}"
    exit 1
  fi

  log "Diffing Helm template for ${env}..."

  local helm_args=(
    diff upgrade concord
    "${SCRIPT_DIR}/helm/concord"
    -n "${env}"
    -f "${values_file}"
  )

  if [[ -f "${SCRIPT_DIR}/helm/values-${env}-secrets.yaml" ]]; then
    helm_args+=(-f "${SCRIPT_DIR}/helm/values-${env}-secrets.yaml")
  fi

  helm "${helm_args[@]}" 2>/dev/null || warn "helm-diff plugin not installed — run: helm plugin install https://github.com/databus23/helm-diff"
}

# ─── Status (shortcut) ──────────────────────────────────────

cmd_status() {
  local env="${1:-staging}"
  case "${env}" in
    staging)    cmd_staging status ;;
    production) cmd_production status ;;
    *)          err "Unknown env: ${env}" ;;
  esac
}

# ─── Version ──────────────────────────────────────────────────

cmd_version() {
  echo "$(get_version)"
}

# ─── Help ─────────────────────────────────────────────────────

usage() {
  cat <<EOF

${BOLD}Concord Deployment CLI${NC}

${BOLD}Usage:${NC}
  ./deploy/ctl.sh <command> [options]

${BOLD}Environments:${NC}
  ${CYAN}development${NC}                  Docker Compose infra only — run apps via Nx
  ${CYAN}staging${NC}                      Kubernetes staging namespace
  ${CYAN}production${NC}                   Kubernetes production namespace

${BOLD}Commands:${NC}
  ${GREEN}development up${NC}               Start infrastructure (DB, MinIO, InfluxDB)
  ${GREEN}development down${NC}             Stop infrastructure
  ${GREEN}development status${NC}           Show infrastructure containers
  ${GREEN}development logs${NC}             Tail infrastructure logs

  ${GREEN}build [target] [env]${NC}         Build Docker images (target: all|api|frontend, env: staging|production)

  ${GREEN}staging deploy${NC}               Build images + deploy to K8s staging (via Helm)
  ${GREEN}staging status${NC}               Show pods, services, ingress in staging
  ${GREEN}staging logs [component]${NC}     Tail logs (http-api or frontend)
  ${GREEN}staging restart${NC}              Rolling restart of staging deployments
  ${GREEN}staging destroy${NC}              Remove all Concord resources from staging

  ${GREEN}production deploy${NC}            Build images + deploy to K8s production (via Helm)
  ${GREEN}production status${NC}            Show pods, services, ingress in production
  ${GREEN}production logs [component]${NC}  Tail logs (http-api or frontend)
  ${GREEN}production restart${NC}           Rolling restart of production deployments

  ${GREEN}diff [env]${NC}                   Preview Helm changes before deploying (needs helm-diff)
  ${GREEN}status [env]${NC}                 Show pods/svc/ingress for an environment

  ${GREEN}version${NC}                      Show current version string

${BOLD}Examples:${NC}
  ./deploy/ctl.sh development up          # Start DBs, then run apps via Nx
  ./deploy/ctl.sh build api staging       # Build only the API image for staging
  ./deploy/ctl.sh diff staging            # Preview Helm changes before deploying
  ./deploy/ctl.sh staging deploy          # Build + deploy everything to K8s staging
  ./deploy/ctl.sh staging logs http-api   # Watch backend logs in staging
  ./deploy/ctl.sh production deploy       # Build + deploy to K8s production

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
  development|dev) cmd_development "$@" ;;
  build)           cmd_build "$@" ;;
  staging)         cmd_staging "$@" ;;
  production)      cmd_production "$@" ;;
  diff)            cmd_diff "$@" ;;
  status)          cmd_status "$@" ;;
  version)         cmd_version ;;
  help|-h|--help)  usage ;;
  *)
    err "Unknown command: ${COMMAND}"
    usage
    exit 1
    ;;
esac
