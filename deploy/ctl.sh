#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────────────
# Concord Deployment CLI
# ───────────────────────────────────────────────────────────────
# Usage:
#   ./deploy/ctl.sh <command>
#
# Environments:
#   dev       — Manual development (start services by hand)
#   local     — Docker Compose with all services containerized
#   staging   — Kubernetes staging namespace
#   production — Kubernetes production namespace
# ───────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Image names
IMAGE_API="concord/http-api"
IMAGE_FRONTEND="concord/frontend"
REGISTRY="containers.ad.corekinect.com"
REGISTRY_API="${REGISTRY}/concord-http-api"
REGISTRY_FRONTEND="${REGISTRY}/concord-frontend"

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
    pkg_version=$(node -p "require('./apps/frontend/concord-app-svelte/package.json').version" 2>/dev/null || echo "0.0.1")
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
    log "Building concord-ui via Nx..."
    npx nx run concord-ui:containerize -c "${env}"
    # Also tag with version
    docker tag "${IMAGE_FRONTEND}:${env}" "${IMAGE_FRONTEND}:${env}-${version}" 2>/dev/null || true
    log "  → ${IMAGE_FRONTEND}:${env}"
  fi

  echo ""
  log "Build complete.  Tags: ${env}, ${env}-${version}"
}

# ─── Local (Docker Compose) ──────────────────────────────────

cmd_local() {
  local action="${1:-up}"
  local compose_dir="${SCRIPT_DIR}/local"

  # Auto-create .env from example if it doesn't exist
  if [[ ! -f "${compose_dir}/.env" ]]; then
    if [[ -f "${compose_dir}/.env.example" ]]; then
      cp "${compose_dir}/.env.example" "${compose_dir}/.env"
      warn "Created ${compose_dir}/.env from .env.example — review and adjust values."
    fi
  fi

  local version
  version=$(get_version)
  export APP_VERSION="${version}"
  export GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  export GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  export GIT_DIRTY="$([ -n "$(git status --porcelain 2>/dev/null)" ] && echo true || echo false)"
  export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  export BUILD_HOST="$(hostname)"

  case "${action}" in
    up)
      log "Starting local environment (all services containerized)..."
      docker compose -f "${compose_dir}/docker-compose.yaml" up --build -d
      echo ""
      log "Local environment is running:"
      info "  Frontend:  http://localhost:3000"
      info "  API:       http://localhost:9001"
      info "  MinIO:     http://localhost:8676"
      info "  InfluxDB:  http://localhost:8086"
      info "  Postgres:  localhost:5432"
      ;;
    down)
      log "Stopping local environment..."
      docker compose -f "${compose_dir}/docker-compose.yaml" down
      ;;
    logs)
      docker compose -f "${compose_dir}/docker-compose.yaml" logs -f "${@:2}"
      ;;
    ps)
      docker compose -f "${compose_dir}/docker-compose.yaml" ps
      ;;
    restart)
      log "Restarting local environment..."
      docker compose -f "${compose_dir}/docker-compose.yaml" down
      docker compose -f "${compose_dir}/docker-compose.yaml" up --build -d
      ;;
    *)
      err "Unknown local action: ${action}"
      err "Usage: ctl.sh local {up|down|logs|ps|restart}"
      exit 1
      ;;
  esac
}

# ─── Dev (manual development) ────────────────────────────────

cmd_dev() {
  local action="${1:-up}"
  local compose_dir="${SCRIPT_DIR}/cloud/development"

  case "${action}" in
    up)
      log "Starting dev infrastructure (DB, MinIO, InfluxDB)..."
      if ! docker network ls | grep -q concord_network; then
        docker network create concord_network
      fi
      docker compose -f "${compose_dir}/docker-compose.yaml" up -d
      echo ""
      log "Dev infrastructure is running. Start your apps manually:"
      info "  Backend:  cd apps/backend/http-api && PYTHONPATH=src:\$(pwd)/../../../libs/python:\$(pwd)/../../../libs:. python3 -m src.main"
      info "  Frontend: cd apps/frontend/concord-app-svelte && npm run dev"
      ;;
    down)
      log "Stopping dev infrastructure..."
      docker compose -f "${compose_dir}/docker-compose.yaml" down
      ;;
    *)
      err "Unknown dev action: ${action}"
      err "Usage: ctl.sh dev {up|down}"
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
      elif command -v k3d &>/dev/null; then
        log "Importing images into K3d..."
        k3d image import "${IMAGE_API}:staging" "${IMAGE_FRONTEND}:staging" 2>/dev/null || true
      else
        # Push to registry for remote clusters
        log "Pushing images to registry..."
        docker push "${REGISTRY_API}:staging" 2>/dev/null || true
        docker push "${REGISTRY_FRONTEND}:staging" 2>/dev/null || true
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
      else
        log "Pushing images to registry..."
        docker push "${REGISTRY_API}:production"
        docker push "${REGISTRY_FRONTEND}:production"
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
  ${CYAN}dev${NC}                          Manual development (infra only, you run apps by hand)
  ${CYAN}local${NC}                        Docker Compose with ALL services containerized
  ${CYAN}staging${NC}                      Kubernetes staging namespace
  ${CYAN}production${NC}                   Kubernetes production namespace (not yet implemented)

${BOLD}Commands:${NC}
  ${GREEN}dev up${NC}                       Start dev infrastructure (DB, MinIO, InfluxDB)
  ${GREEN}dev down${NC}                     Stop dev infrastructure

  ${GREEN}local up${NC}                     Build & start all services in Docker
  ${GREEN}local down${NC}                   Stop all local services
  ${GREEN}local logs [service]${NC}         Tail logs (http-api, frontend, db, etc.)
  ${GREEN}local ps${NC}                     Show running containers
  ${GREEN}local restart${NC}                Rebuild & restart everything

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
  ./deploy/ctl.sh dev up                  # Start DBs, then run backend/frontend manually
  ./deploy/ctl.sh local up                # Full local stack in Docker
  ./deploy/ctl.sh build api staging       # Build only the API image for staging
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
  dev)        cmd_dev "$@" ;;
  local)      cmd_local "$@" ;;
  build)      cmd_build "$@" ;;
  staging)    cmd_staging "$@" ;;
  production) cmd_production "$@" ;;
  diff)       cmd_diff "$@" ;;
  status)     cmd_status "$@" ;;
  version)    cmd_version ;;
  help|-h|--help) usage ;;
  *)
    err "Unknown command: ${COMMAND}"
    usage
    exit 1
    ;;
esac
