#!/usr/bin/env bash
# test-manifests.sh — Validates all Kubernetes YAML manifests are syntactically
# correct via kubectl dry-run. Also checks for duplicate resource names within
# a cluster.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("$1"); echo "  ✗ $1"; }

command -v kubectl >/dev/null 2>&1 || { echo "SKIP: kubectl not installed"; exit 1; }
command -v yq >/dev/null 2>&1 || { echo "SKIP: yq not installed"; exit 1; }

# ── Validate every .yaml file under clusters/ ─────────────────
for cluster_dir in "${INFRA_ROOT}"/clusters/*/; do
  cluster=$(basename "${cluster_dir}")
  echo "--- Cluster: ${cluster} ---"

  # Collect all K8s manifest yamls (skip cluster.yaml — it's metadata, not a manifest)
  manifest_files=()
  while IFS= read -r -d '' f; do
    # Skip non-K8s files: cluster.yaml (metadata), scripts, nodes/ (custom format)
    base=$(basename "$f")
    [[ "${base}" == "cluster.yaml" ]] && continue
    [[ "${f}" == *.sh ]] && continue
    [[ "${f}" == */nodes/* ]] && continue
    manifest_files+=("$f")
  done < <(find "${cluster_dir}" -name '*.yaml' -type f -print0 2>/dev/null)

  if [[ ${#manifest_files[@]} -eq 0 ]]; then
    fail "${cluster}: no manifest YAML files found"
    continue
  fi

  pass "${cluster}: found ${#manifest_files[@]} manifest files"

  # Validate each file with kubectl dry-run
  for f in "${manifest_files[@]}"; do
    rel_path="${f#${INFRA_ROOT}/}"
    # Check it's valid YAML first
    if ! yq '.' "${f}" >/dev/null 2>&1; then
      fail "${rel_path}: invalid YAML syntax"
      continue
    fi

    # Check if it contains a K8s kind field
    kind=$(yq -r '.kind // ""' "${f}" 2>/dev/null)
    if [[ -z "${kind}" ]]; then
      # Might be a multi-document file
      kind=$(yq -r 'select(.kind) | .kind' "${f}" 2>/dev/null | head -1)
    fi

    if [[ -z "${kind}" ]]; then
      fail "${rel_path}: no 'kind' field — not a valid K8s manifest"
      continue
    fi

    # kubectl dry-run validation
    output=$(kubectl apply --dry-run=client -f "${f}" 2>&1)
    if [[ $? -eq 0 ]]; then
      pass "${rel_path}: valid (${kind})"
    else
      fail "${rel_path}: kubectl dry-run failed — ${output}"
    fi
  done

  # ── Check for duplicate resource names ────────────────────
  declare -A seen_resources
  for f in "${manifest_files[@]}"; do
    while IFS= read -r line; do
      [[ -n "${line}" ]] && {
        if [[ -n "${seen_resources[${line}]+_}" ]]; then
          fail "${cluster}: duplicate resource '${line}' in $(basename "$f") and ${seen_resources[${line}]}"
        else
          seen_resources["${line}"]="$(basename "$f")"
        fi
      }
    done < <(yq -r 'select(.kind and .metadata.name) | "\(.kind)/\(.metadata.namespace // "cluster")/\(.metadata.name)"' "${f}" 2>/dev/null)
  done
  unset seen_resources
done

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "=== manifests: ${PASS} passed, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  echo "Failures:"
  for e in "${ERRORS[@]}"; do echo "  - ${e}"; done
  exit 1
fi
