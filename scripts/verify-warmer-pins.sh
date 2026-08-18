#!/usr/bin/env bash
# Assert the ci-image-warmer warms the image the pools actually run — and
# stays unprivileged.
#
# The warmer's pinned initContainer ref is a 4th home of the cloud digest the
# 3 scale-set files pin. That duplication is deliberate (a DaemonSet cannot
# read another manifest), and this file is what keeps it honest: a pin bump
# that misses the warmer would quietly warm YESTERDAY'S image while every
# runner pod cold-pulls today's — the exact pull the warmer exists to prevent,
# invisible until someone times a job.
#
# Three properties, all asserted from the FILES (no cluster access — this runs
# in CI):
#
#   1. ONE DIGEST EVERYWHERE. Every `ghcr.io/gophersys/cloud@sha256:` ref
#      across the 3 app-arc-runners-*.yaml files, the warmer DaemonSet and the
#      refresh CronJob is the same digest. Zero refs in any file is a FAILURE,
#      not a pass — a renamed file must not turn this check vacuous.
#
#   2. NO PRIVILEGE RETURNS. The warmer files carry no hostPath and no
#      privileged:true. The previous warmer was node-root by containerd-socket
#      mount; Mateo rejected the mount (2026-08-17). A hostPath that reappears
#      here is a security regression wearing a convenience's name.
#
#   3. NO CONTROL PLANE IS SCHEDULABLE. Every node that declares
#      `kubernetes.role: server` in clusters/instances/homelab/nodes/*/
#      identity.yaml appears in the NotIn list of the warmer DaemonSet, the
#      refresh CronJob and the 2 NotIn-shaped runner pools. The warmer holds
#      ~3.86GB of unreclaimable images on every node it lands on, and the
#      control planes are 38GB VMs running etcd: k3s-cp-0 reached 93% used /
#      2.7GB free on 2026-08-18. Nothing else keeps a pod off them — zero
#      taints exist cluster-wide, see docs/debt-register.md D45. The server set
#      is DERIVED, so a 4th control plane is caught the day its identity file
#      lands; an empty derived set is a FAILURE, because a loop over it asserts
#      nothing and reads green.
#
# Exit 0 = all 3 hold. Exit 1 = at least one does not, naming the file.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$ROOT/platform/services/gitops/registry"
ARC="$ROOT/platform/services/ci/arc-runners"
NODES="$ROOT/clusters/instances/homelab/nodes"

POOL_FILES=(
  "$REGISTRY/app-arc-runners-build.yaml"
  "$REGISTRY/app-arc-runners-org.yaml"
  "$REGISTRY/app-arc-runners-review.yaml"
)
WARMER_FILES=(
  "$ARC/42-image-warmer-daemonset.yaml"
  "$ARC/43-image-warmer-refresh.yaml"
)
# Index-aligned with WARMER_FILES: where each kind keeps its pod spec. The
# CronJob's sits one level deeper, and a read written against the DaemonSet path
# alone finds no affinity there at all.
WARMER_POD_PATHS=(
  ".spec.template.spec"
  ".spec.jobTemplate.spec.template.spec"
)
# The pools held to the NotIn rule. app-arc-runners-build.yaml is absent on
# purpose: it pins an `In` list to k3s-w-0/1/2, so no control plane can be
# selected there, and demanding a NotIn of it would be wrong.
POOL_NOTIN_FILES=(
  "$REGISTRY/app-arc-runners-org.yaml"
  "$REGISTRY/app-arc-runners-review.yaml"
)

# Property 3 reads the cluster's node declarations. A missing tool is a failure,
# never a skip: without yq the server set would come out empty and the check
# would report a green it never measured.
if ! command -v yq >/dev/null 2>&1; then
  echo "verify-warmer-pins: missing required tool: yq" >&2
  exit 127
fi

failures=0
fail() {
  echo "verify-warmer-pins: FAIL: $*" >&2
  failures=$((failures + 1))
}

digests_in() {
  grep -oE 'ghcr\.io/gophersys/cloud@sha256:[0-9a-f]{64}' "$1" 2>/dev/null | sort -u
}

# 1. One digest everywhere, and at least one ref per file.
all_digests=""
for f in "${POOL_FILES[@]}" "${WARMER_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    fail "$f does not exist — a renamed file makes this check vacuous, so it fails instead"
    continue
  fi
  d="$(digests_in "$f")"
  if [[ -z "$d" ]]; then
    fail "$f pins no ghcr.io/gophersys/cloud@sha256 ref — zero refs is not a pass"
    continue
  fi
  if [[ "$(printf '%s\n' "$d" | wc -l | tr -d ' ')" -ne 1 ]]; then
    fail "$f pins more than one distinct cloud digest:"$'\n'"$d"
    continue
  fi
  all_digests="${all_digests}${d}"$'\n'
done

distinct="$(printf '%s' "$all_digests" | sort -u | grep -c . || true)"
if [[ -n "$all_digests" && "$distinct" -ne 1 ]]; then
  fail "the files disagree on the cloud digest — a pin bump missed a home:"$'\n'"$(printf '%s' "$all_digests" | sort | uniq -c)"
fi

# 2. No privilege returns to the warmer.
for f in "${WARMER_FILES[@]}"; do
  [[ -f "$f" ]] || continue
  if grep -nE '^\s*hostPath:|privileged:\s*true' "$f"; then
    fail "$f grants node access — the warmer is unprivileged by decision (2026-08-17)"
  fi
done

# 3. No declared control plane is schedulable for the warmer or for the pools.
#
# No 2>/dev/null on any yq below: an absent path returns empty at exit 0, so a
# non-zero exit means the file did not parse, and a node this check cannot read
# is a node it cannot see. That failure is reported, never skipped.
servers=""
for f in "$NODES"/*/identity.yaml; do
  [[ -f "$f" ]] || continue
  role="$(yq '.kubernetes.role // ""' "$f")" || {
    fail "$f did not parse as YAML — a node declaration this check cannot read is a node it cannot see"
    continue
  }
  [[ "$role" == "server" ]] || continue
  name="$(yq '.name // ""' "$f")"
  if [[ -z "$name" ]]; then
    fail "$f declares kubernetes.role: server without a name — the hostname to exclude cannot be read"
    continue
  fi
  servers="${servers}${name}"$'\n'
done
if [[ -z "$servers" ]]; then
  fail "no node under $NODES declares kubernetes.role: server — the control-plane set is empty, so this check went blind"
fi

# The NotIn hostnames of the kubernetes.io/hostname expression, read structurally
# from the pod spec of a warmer file.
notin_from_yaml() {
  local file="$1" pod="$2"
  yq "${pod}.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[].matchExpressions[] | select(.key == \"kubernetes.io/hostname\" and .operator == \"NotIn\") | .values[]" "$file"
}

# The same list from a pool file, which keeps its affinity inside
# `spec.source.helm.values` — a YAML STRING. A structural read returns one scalar
# and finds no affinity at all, so the flow list is taken as TEXT.
notin_from_text() {
  awk '
    /key:[[:space:]]*kubernetes\.io\/hostname/ { key = 1; next }
    key && /operator:[[:space:]]*NotIn/        { op = 1; key = 0; next }
    op && /values:[[:space:]]*\[/ {
      op = 0
      n = split($0, part, "\"")
      for (i = 2; i <= n; i += 2) print part[i]
    }
  ' "$1"
}

assert_excludes() {
  local label="$1" values="$2" node
  while IFS= read -r node; do
    [[ -n "$node" ]] || continue
    if ! printf '%s\n' "$values" | grep -qxF "$node"; then
      fail "$label leaves $node schedulable — it declares kubernetes.role: server, and a pod there lands on the disk etcd writes to"
    fi
  done <<<"$servers"
}

for i in "${!WARMER_FILES[@]}"; do
  f="${WARMER_FILES[$i]}"
  [[ -f "$f" ]] || continue
  assert_excludes "${f#"$ROOT"/}" "$(notin_from_yaml "$f" "${WARMER_POD_PATHS[$i]}")"
done
for f in "${POOL_NOTIN_FILES[@]}"; do
  [[ -f "$f" ]] || continue
  assert_excludes "${f#"$ROOT"/}" "$(notin_from_text "$f")"
done

if [[ "$failures" -gt 0 ]]; then
  echo "verify-warmer-pins: $failures failure(s)" >&2
  exit 1
fi
echo "verify-warmer-pins: OK — one digest across ${#POOL_FILES[@]} pool files + ${#WARMER_FILES[@]} warmer files, no privilege, $(printf '%s' "$servers" | grep -c .) control-plane node(s) excluded from ${#WARMER_FILES[@]} warmer + ${#POOL_NOTIN_FILES[@]} pool files"
