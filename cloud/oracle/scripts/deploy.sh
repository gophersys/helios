#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — Deploy apps to the K3s cluster from your local machine
#
# Prerequisites:
#   - Tailscale connected to the cluster network
#   - kubectl configured (run: scripts/get-kubeconfig.sh)
#   - Docker logged into ghcr.io (gh auth token | docker login ghcr.io -u USERNAME --password-stdin)
#   - helm 3.x installed (for stack deployment)
#
# Usage:
#   ./deploy.sh <app>          Deploy a specific app (dashboard, api)
#   ./deploy.sh all            Deploy all apps (image build + kustomize)
#   ./deploy.sh stack          Deploy the full Helm stack (postgres, clickhouse, api, dashboard)
#   ./deploy.sh stack-oci      Deploy Helm stack with OCI free-tier values

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REGISTRY="ghcr.io/mateosegura"
PLATFORM="linux/arm64"

info()  { echo "  [deploy] $*"; }
ok()    { echo "  [deploy] ✓ $*"; }
die()   { echo "  [deploy] ✗ $*" >&2; exit 1; }

deploy_dashboard() {
  local app_dir="${CODECTL_REPO:-}/apps/dashboard"
  [[ -d "${app_dir}" ]] || die "Dashboard source not found at ${app_dir}. Set CODECTL_REPO env var."

  info "Building dashboard image..."
  docker buildx build --platform "${PLATFORM}" \
    -t "${REGISTRY}/codectl-dashboard:latest" --push \
    "${app_dir}/"
  ok "Image pushed"

  info "Applying k8s manifests..."
  kubectl apply -k "${app_dir}/k8s/"
  kubectl rollout status deployment/dashboard -n codectl --timeout=120s
  ok "Dashboard deployed to app.mateosegura.com"
}

deploy_api() {
  local app_dir="${CODECTL_REPO:-}/api"
  [[ -d "${app_dir}" ]] || die "API source not found at ${app_dir}. Set CODECTL_REPO env var."

  info "Building API image..."
  docker buildx build --platform "${PLATFORM}" \
    -t "${REGISTRY}/codectl-api:latest" --push \
    "${app_dir}/"
  ok "Image pushed"

  info "Applying k8s manifests..."
  kubectl apply -k "${app_dir}/k8s/"
  kubectl rollout status deployment/api -n codectl --timeout=120s
  ok "API deployed to api.mateosegura.com"
}

deploy_helm_stack() {
  local values_flag="${1:-}"
  command -v helm >/dev/null || die "helm not found — install with: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"

  local codectl_repo="${CODECTL_REPO:-}"
  [[ -d "${codectl_repo}" ]] || die "CODECTL_REPO not set or directory not found."

  info "Building images..."
  docker buildx build --platform "${PLATFORM}" \
    -t "${REGISTRY}/codectl-api:latest" --push \
    "${codectl_repo}/api/" &
  docker buildx build --platform "${PLATFORM}" \
    -t "${REGISTRY}/codectl-dashboard:latest" --push \
    "${codectl_repo}/apps/dashboard/" &
  wait
  ok "Images pushed"

  info "Deploying Helm stack..."
  bash "${codectl_repo}/deploy/helm/deploy.sh" "${values_flag}" \
    --set "codectl-api.secrets.DATABASE_URL=$(kubectl get secret codectl-api-secrets -n codectl -o jsonpath='{.data.DATABASE_URL}' 2>/dev/null | base64 -d || echo '')" \
    --set "codectl-api.secrets.JWT_SECRET=$(kubectl get secret codectl-api-secrets -n codectl -o jsonpath='{.data.JWT_SECRET}' 2>/dev/null | base64 -d || echo '')"
  ok "Helm stack deployed"
}

APP="${1:-}"
[ -z "${APP}" ] && die "Usage: deploy.sh <dashboard|api|all|stack|stack-oci>"

# Check prerequisites
command -v kubectl >/dev/null || die "kubectl not found"
command -v docker >/dev/null || die "docker not found"
kubectl cluster-info --request-timeout=5s >/dev/null 2>&1 || die "Cannot reach K3s cluster — is Tailscale connected?"

case "${APP}" in
  dashboard)  deploy_dashboard ;;
  api)        deploy_api ;;
  all)        deploy_dashboard; deploy_api ;;
  stack)      deploy_helm_stack "staging" ;;
  stack-oci)  deploy_helm_stack "oci" ;;
  *)          die "Unknown app: ${APP}. Use: dashboard, api, all, stack, or stack-oci" ;;
esac
