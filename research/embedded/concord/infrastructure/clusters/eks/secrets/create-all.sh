#!/usr/bin/env bash
# create-all.sh — EKS secret creation (placeholder).
# Mirrors office/secrets/create-all.sh — adapt for EKS when cluster is ready.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

echo "[secrets] EKS secrets: placeholder"
$DRY_RUN && echo "  Mode: DRY RUN"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "  No .env file — skipping"
  exit 0
fi

# Placeholder — would read .env and apply secrets via kubectl apply -f
echo "  TODO: Implement EKS secret creation (see office/secrets/create-all.sh)"
echo "=== secrets: 0 applied, 0 failed ==="
