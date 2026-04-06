#!/usr/bin/env bash
# test-rbac.sh — Validates RBAC manifests match the role-mapping.yaml spec.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("$1"); echo "  ✗ $1"; }

yq_read() { yq -r "$1" "$2" 2>/dev/null | grep -v '^null$' || true; }

command -v yq >/dev/null 2>&1 || { echo "SKIP: yq not installed"; exit 1; }

# ── role-mapping.yaml must exist ──────────────────────────────
ROLE_MAP="${INFRA_ROOT}/rbac/role-mapping.yaml"
if [[ ! -f "${ROLE_MAP}" ]]; then
  fail "rbac/role-mapping.yaml not found"
  echo "=== rbac: ${PASS} passed, ${FAIL} failed ==="
  exit 1
fi
pass "rbac/role-mapping.yaml exists"

# ── Validate role-mapping has all 4 platform roles ────────────
for role in admin maintainer developer operator; do
  platform_role=$(yq_read ".roles.${role}.platformRole" "${ROLE_MAP}")
  cluster_role=$(yq_read ".roles.${role}.clusterRole" "${ROLE_MAP}")
  if [[ -z "${platform_role}" ]]; then
    fail "role-mapping: missing platformRole for '${role}'"
  else
    pass "role-mapping: ${role} → platformRole=${platform_role}"
  fi
  if [[ -z "${cluster_role}" ]]; then
    fail "role-mapping: missing clusterRole for '${role}'"
  else
    pass "role-mapping: ${role} → clusterRole=${cluster_role}"
  fi
done

# ── Service account mapping must exist ────────────────────────
sa_role=$(yq_read '.serviceAccounts.concord-api.clusterRole' "${ROLE_MAP}")
if [[ -z "${sa_role}" ]]; then
  fail "role-mapping: missing serviceAccounts.concord-api"
else
  pass "role-mapping: concord-api SA → ${sa_role}"
fi

# ── Validate each cluster's RBAC manifests ────────────────────
for cluster_dir in "${INFRA_ROOT}"/clusters/*/; do
  cluster=$(basename "${cluster_dir}")
  rbac_dir="${cluster_dir}rbac"
  echo "--- Cluster: ${cluster} ---"

  # clusterroles.yaml must exist
  cr_file="${rbac_dir}/clusterroles.yaml"
  if [[ ! -f "${cr_file}" ]]; then
    fail "${cluster}: rbac/clusterroles.yaml not found"
    continue
  fi
  pass "${cluster}: clusterroles.yaml exists"

  # Must define all 4 ClusterRoles referenced in role-mapping
  for role in admin maintainer developer operator; do
    expected_cr=$(yq_read ".roles.${role}.clusterRole" "${ROLE_MAP}")
    if [[ -n "${expected_cr}" ]]; then
      # Search across all documents in the multi-doc YAML
      found=$(yq -r 'select(.kind == "ClusterRole") | .metadata.name' "${cr_file}" 2>/dev/null | grep -Fx "${expected_cr}" || true)
      if [[ -z "${found}" ]]; then
        fail "${cluster}: ClusterRole '${expected_cr}' not found in clusterroles.yaml"
      else
        pass "${cluster}: ClusterRole '${expected_cr}' defined"
      fi
    fi
  done

  # Must define the service account ClusterRole
  sa_cr=$(yq_read '.serviceAccounts.concord-api.clusterRole' "${ROLE_MAP}")
  if [[ -n "${sa_cr}" ]]; then
    found=$(yq -r 'select(.kind == "ClusterRole") | .metadata.name' "${cr_file}" 2>/dev/null | grep -Fx "${sa_cr}" || true)
    if [[ -z "${found}" ]]; then
      fail "${cluster}: ClusterRole '${sa_cr}' (service account) not found"
    else
      pass "${cluster}: ClusterRole '${sa_cr}' (service account) defined"
    fi
  fi

  # service-accounts.yaml must exist
  sa_file="${rbac_dir}/service-accounts.yaml"
  if [[ ! -f "${sa_file}" ]]; then
    fail "${cluster}: rbac/service-accounts.yaml not found"
  else
    pass "${cluster}: service-accounts.yaml exists"
  fi

  # Check namespace-scoped bindings exist
  cluster_yaml="${cluster_dir}cluster.yaml"
  if [[ -f "${cluster_yaml}" ]]; then
    while IFS= read -r ns; do
      binding_file="${rbac_dir}/bindings-${ns}.yaml"
      if [[ ! -f "${binding_file}" ]]; then
        fail "${cluster}: rbac/bindings-${ns}.yaml not found"
      else
        pass "${cluster}: bindings-${ns}.yaml exists"
      fi
    done < <(yq -r '.namespaces[]' "${cluster_yaml}" 2>/dev/null)
  fi
done

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "=== rbac: ${PASS} passed, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  echo "Failures:"
  for e in "${ERRORS[@]}"; do echo "  - ${e}"; done
  exit 1
fi
