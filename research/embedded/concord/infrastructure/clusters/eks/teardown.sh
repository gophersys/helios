#!/usr/bin/env bash
# teardown.sh — EKS cluster teardown (placeholder).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_YAML="${SCRIPT_DIR}/cluster.yaml"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

command -v yq >/dev/null 2>&1 || { echo "yq not found"; exit 1; }

cluster_name=$(yq -r '.name' "${CLUSTER_YAML}")
echo "[teardown] EKS teardown: ${cluster_name} (placeholder)"
$DRY_RUN && echo "  Mode: DRY RUN"

# Placeholder — would mirror office/teardown.sh logic
echo "  TODO: Implement EKS teardown"
