#!/usr/bin/env bash
# test-cluster-yaml.sh — Validates cluster.yaml schema for all defined clusters.
# Each cluster.yaml must have: name, apiServer, distribution, registry, nodes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTERS_DIR="${INFRA_ROOT}/clusters"

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("$1"); echo "  ✗ $1"; }

yq_read() {
  # Safely read a field from YAML, returns empty string if missing
  yq -r "$1" "$2" 2>/dev/null | grep -v '^null$' || true
}

# ── Require yq ────────────────────────────────────────────────
command -v yq >/dev/null 2>&1 || { echo "SKIP: yq not installed"; exit 1; }

# ── Find all cluster directories ──────────────────────────────
clusters=()
for d in "${CLUSTERS_DIR}"/*/; do
  [[ -d "$d" ]] && clusters+=("$(basename "$d")")
done

if [[ ${#clusters[@]} -eq 0 ]]; then
  fail "No cluster directories found under ${CLUSTERS_DIR}"
fi

for cluster in "${clusters[@]}"; do
  echo "--- Cluster: ${cluster} ---"
  yaml="${CLUSTERS_DIR}/${cluster}/cluster.yaml"

  if [[ ! -f "${yaml}" ]]; then
    fail "${cluster}: cluster.yaml not found"
    continue
  fi

  # Required top-level fields
  for field in name apiServer distribution; do
    val=$(yq_read ".${field}" "${yaml}")
    if [[ -z "${val}" ]]; then
      fail "${cluster}: missing required field '${field}'"
    else
      pass "${cluster}: has '${field}' = ${val}"
    fi
  done

  # Registry section
  reg_mode=$(yq_read '.registry.mode' "${yaml}")
  if [[ -z "${reg_mode}" ]]; then
    fail "${cluster}: missing registry.mode"
  elif [[ "${reg_mode}" != "local-import" && "${reg_mode}" != "push" ]]; then
    fail "${cluster}: registry.mode must be 'local-import' or 'push', got '${reg_mode}'"
  else
    pass "${cluster}: registry.mode = ${reg_mode}"
  fi

  reg_host=$(yq_read '.registry.host' "${yaml}")
  if [[ -z "${reg_host}" ]]; then
    fail "${cluster}: missing registry.host"
  else
    pass "${cluster}: registry.host = ${reg_host}"
  fi

  # Nodes section — must have at least one node defined
  node_count=$(yq -r '[.nodes.servers // [], .nodes.agents // [], .nodes.edge // []] | flatten | length' "${yaml}" 2>/dev/null || echo 0)
  if [[ "${node_count}" -eq 0 ]]; then
    fail "${cluster}: no nodes defined"
  else
    pass "${cluster}: ${node_count} nodes defined"
  fi

  # Each node must have name and ip
  for group in servers agents edge; do
    count=$(yq -r ".nodes.${group} // [] | length" "${yaml}" 2>/dev/null || echo 0)
    for ((i=0; i<count; i++)); do
      node_name=$(yq_read ".nodes.${group}[${i}].name" "${yaml}")
      node_ip=$(yq_read ".nodes.${group}[${i}].ip" "${yaml}")
      if [[ -z "${node_name}" ]]; then
        fail "${cluster}: nodes.${group}[${i}] missing 'name'"
      fi
      if [[ -z "${node_ip}" ]]; then
        fail "${cluster}: nodes.${group}[${i}] missing 'ip'"
      elif ! [[ "${node_ip}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        fail "${cluster}: nodes.${group}[${i}].ip '${node_ip}' is not a valid IPv4 address"
      fi
    done
  done

  # ── Workload types — all 6 must be defined ───────────────────
  REQUIRED_WORKLOADS="platform data build devops worker edge"
  for wtype in ${REQUIRED_WORKLOADS}; do
    desc=$(yq_read ".workloadTypes.${wtype}.description" "${yaml}")
    if [[ -z "${desc}" ]]; then
      fail "${cluster}: missing workloadType '${wtype}'"
    else
      pass "${cluster}: workloadType '${wtype}' defined"
    fi
  done

  # Every node must have a workloads list with valid types
  for group in servers agents edge; do
    count=$(yq -r ".nodes.${group} // [] | length" "${yaml}" 2>/dev/null || echo 0)
    for ((i=0; i<count; i++)); do
      node_name=$(yq_read ".nodes.${group}[${i}].name" "${yaml}")
      wl_count=$(yq -r ".nodes.${group}[${i}].workloads // [] | length" "${yaml}" 2>/dev/null || echo 0)
      if [[ "${wl_count}" -eq 0 ]]; then
        fail "${cluster}: node '${node_name}' has no workloads assigned"
      else
        # Validate each workload is one of the 6 types
        for ((j=0; j<wl_count; j++)); do
          wl=$(yq_read ".nodes.${group}[${i}].workloads[${j}]" "${yaml}")
          if ! echo "${REQUIRED_WORKLOADS}" | grep -qw "${wl}"; then
            fail "${cluster}: node '${node_name}' has invalid workload '${wl}'"
          fi
        done
        pass "${cluster}: node '${node_name}' workloads=[$(yq -r ".nodes.${group}[${i}].workloads | join(\",\")" "${yaml}" 2>/dev/null)]"
      fi
    done
  done

  # ── Dependencies — each must have name, chart, version, namespace ─
  dep_count=$(yq -r '.dependencies // [] | length' "${yaml}" 2>/dev/null || echo 0)
  if [[ "${dep_count}" -gt 0 ]]; then
    pass "${cluster}: ${dep_count} dependencies defined"
    for ((i=0; i<dep_count; i++)); do
      dep_name=$(yq_read ".dependencies[${i}].name" "${yaml}")
      dep_chart=$(yq_read ".dependencies[${i}].chart" "${yaml}")
      dep_ns=$(yq_read ".dependencies[${i}].namespace" "${yaml}")
      dep_ver=$(yq_read ".dependencies[${i}].version" "${yaml}")
      if [[ -z "${dep_name}" || -z "${dep_chart}" || -z "${dep_ns}" || -z "${dep_ver}" ]]; then
        fail "${cluster}: dependency[${i}] missing name/chart/namespace/version"
      else
        pass "${cluster}: dependency '${dep_name}' (${dep_chart} ${dep_ver} → ${dep_ns})"
      fi
    done
  fi

  # Namespaces list
  ns_count=$(yq -r '.namespaces // [] | length' "${yaml}" 2>/dev/null || echo 0)
  if [[ "${ns_count}" -eq 0 ]]; then
    fail "${cluster}: no namespaces defined"
  else
    pass "${cluster}: ${ns_count} namespaces defined"
  fi
done

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "=== cluster-yaml: ${PASS} passed, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  echo "Failures:"
  for e in "${ERRORS[@]}"; do echo "  - ${e}"; done
  exit 1
fi
