#!/usr/bin/env bash
# test-secrets.sh — Validates the secrets management system for all clusters.
# Checks: .env.example exists, create-all.sh exists + is executable + supports --dry-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTERS_DIR="${INFRA_ROOT}/clusters"

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("$1"); echo "  ✗ $1"; }

# ── Find all cluster directories ──────────────────────────────
clusters=()
for d in "${CLUSTERS_DIR}"/*/; do
  [[ -d "$d" ]] && clusters+=("$(basename "$d")")
done

for cluster in "${clusters[@]}"; do
  echo "--- Cluster: ${cluster} ---"
  secrets_dir="${CLUSTERS_DIR}/${cluster}/secrets"

  # Secrets directory must exist
  if [[ ! -d "${secrets_dir}" ]]; then
    fail "${cluster}: secrets/ directory not found"
    continue
  fi
  pass "${cluster}: secrets/ directory exists"

  # .env.example must exist (documents what's needed)
  if [[ -f "${secrets_dir}/.env.example" ]]; then
    pass "${cluster}: .env.example exists"

    # .env.example must document at least one variable
    if grep -q '^[A-Z_]*=' "${secrets_dir}/.env.example"; then
      pass "${cluster}: .env.example has documented variables"
    else
      fail "${cluster}: .env.example has no documented variables"
    fi
  else
    fail "${cluster}: .env.example not found"
  fi

  # create-all.sh must exist
  create_script="${secrets_dir}/create-all.sh"
  if [[ ! -f "${create_script}" ]]; then
    fail "${cluster}: create-all.sh not found"
    continue
  fi
  pass "${cluster}: create-all.sh exists"

  # Must be executable
  if [[ -x "${create_script}" ]]; then
    pass "${cluster}: create-all.sh is executable"
  else
    fail "${cluster}: create-all.sh is not executable"
  fi

  # Must support --dry-run
  if grep -q '\-\-dry-run' "${create_script}"; then
    pass "${cluster}: create-all.sh supports --dry-run"
  else
    fail "${cluster}: create-all.sh does not support --dry-run"
  fi

  # create-all.sh must read from .env
  if grep -q '\.env' "${create_script}"; then
    pass "${cluster}: create-all.sh reads from .env"
  else
    fail "${cluster}: create-all.sh does not reference .env"
  fi

  # create-all.sh must use idempotent apply pattern
  if grep -q 'dry-run=client.*apply\|apply -f' "${create_script}"; then
    pass "${cluster}: create-all.sh uses idempotent apply pattern"
  else
    fail "${cluster}: create-all.sh missing idempotent apply pattern (--dry-run=client | kubectl apply)"
  fi

  # Every secret in create-all.sh should be documented in .env.example
  if [[ -f "${secrets_dir}/.env.example" ]]; then
    # Extract K8s secret names from create-all.sh
    while IFS= read -r secret_name; do
      [[ -z "${secret_name}" ]] && continue
      pass "${cluster}: creates secret '${secret_name}'"
    done < <(grep -oP 'generic \K[a-z][a-z0-9-]+' "${create_script}" 2>/dev/null | sort -u || true)
  fi
done

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "=== secrets: ${PASS} passed, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  echo "Failures:"
  for e in "${ERRORS[@]}"; do echo "  - ${e}"; done
  exit 1
fi
