#!/usr/bin/env bash
# deploy/ci/ctl.sh — Lifecycle CLI for the concord-ci Helm chart.
#
# Usage:
#   bash deploy/ci/ctl.sh start          Install/upgrade the CI platform
#   bash deploy/ci/ctl.sh stop           Uninstall (preserves PVCs)
#   bash deploy/ci/ctl.sh update         Rebuild admin image + helm upgrade
#   bash deploy/ci/ctl.sh status         Show running resources
#   bash deploy/ci/ctl.sh diff           Preview Helm changes
#   bash deploy/ci/ctl.sh logs [name]    Tail logs (default: admin dashboard)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$SCRIPT_DIR/helm/concord-ci"
NAMESPACE="devops"
RELEASE="concord-ci"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ci]${NC} $*"; }
info() { echo -e "${CYAN}[ci]${NC} $*"; }
err()  { echo -e "${RED}[ci]${NC} $*" >&2; }

ACTION="${1:-help}"
shift || true

case "$ACTION" in

  start)
    log "Installing/upgrading ${BOLD}${RELEASE}${NC} in namespace ${BOLD}${NAMESPACE}${NC}"
    helm upgrade --install "$RELEASE" "$CHART_DIR" \
      -n "$NAMESPACE" --create-namespace \
      --wait --timeout 300s
    log "Done. Run 'bash deploy/ci/ctl.sh status' to verify."
    ;;

  stop)
    log "Uninstalling ${BOLD}${RELEASE}${NC} from ${BOLD}${NAMESPACE}${NC}"
    info "PVCs are preserved (helm.sh/resource-policy: keep)"
    helm uninstall "$RELEASE" -n "$NAMESPACE" 2>/dev/null || info "Already uninstalled"
    log "Done."
    ;;

  update)
    log "Rebuilding admin image + deploying..."
    # Build admin dashboard image if the app exists
    if [[ -d "$REPO_ROOT/apps/frontend/ci-admin" ]]; then
      info "Building admin dashboard image..."
      docker buildx build \
        --file "$REPO_ROOT/apps/frontend/ci-admin/deploy/Dockerfile" \
        --tag "containers.ad.corekinect.com/concord-ci-admin:latest" \
        --load "$REPO_ROOT" 2>&1 | tail -3
    fi
    # Helm upgrade
    helm upgrade --install "$RELEASE" "$CHART_DIR" \
      -n "$NAMESPACE" --create-namespace \
      --wait --timeout 300s
    log "Done."
    ;;

  status)
    echo ""
    echo -e "${BOLD}concord-ci status (namespace: ${NAMESPACE})${NC}"
    echo ""
    kubectl get all -n "$NAMESPACE" -l app.kubernetes.io/part-of=concord-ci 2>/dev/null || true
    echo ""
    echo -e "${BOLD}PVCs:${NC}"
    kubectl get pvc -n "$NAMESPACE" -l app.kubernetes.io/part-of=concord-ci 2>/dev/null || true
    echo ""
    echo -e "${BOLD}CronJobs:${NC}"
    kubectl get cronjob -n "$NAMESPACE" -l app.kubernetes.io/part-of=concord-ci 2>/dev/null || true
    ;;

  diff)
    helm diff upgrade "$RELEASE" "$CHART_DIR" -n "$NAMESPACE" 2>/dev/null || \
      helm template "$RELEASE" "$CHART_DIR" -n "$NAMESPACE" | head -100
    ;;

  logs)
    COMPONENT="${1:-admin}"
    case "$COMPONENT" in
      admin)   kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=concord-ci-admin -f --tail=100 ;;
      minio)   kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=concord-ci-minio -f --tail=100 ;;
      nightly) kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=concord-ci-nightly -c ci-runner -f --tail=100 ;;
      weekly)  kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=concord-ci-weekly -c ci-runner -f --tail=100 ;;
      *)       err "Unknown component: $COMPONENT. Use: admin, minio, nightly, weekly" ;;
    esac
    ;;

  help|--help|-h)
    echo "Usage: bash deploy/ci/ctl.sh <command>"
    echo ""
    echo "Commands:"
    echo "  start           Install/upgrade the CI Helm chart"
    echo "  stop            Uninstall (preserves data PVCs)"
    echo "  update          Rebuild admin image + helm upgrade"
    echo "  status          Show CI resources in K8s"
    echo "  diff            Preview Helm changes"
    echo "  logs [name]     Tail logs (admin, minio, nightly, weekly)"
    ;;

  *)
    err "Unknown command: $ACTION"
    echo "Run 'bash deploy/ci/ctl.sh help' for usage."
    exit 1
    ;;
esac
