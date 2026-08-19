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
#      nothing and reads green. The judgement is PER TERM and structural: a
#      `preferred...Execution` block scores nodes and removes none, and
#      nodeSelectorTerms are OR-ed, so a term that does not rule the node out
#      makes it eligible however correct the term beside it reads.
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

# Both shapes are judged from a PARSED DOCUMENT, never from the bytes. A warmer
# file is the pod's manifest, so the document is the file. A pool file keeps the
# pod template inside `spec.source.helm.values`, which is a YAML STRING: one yq
# read returns that whole block as a single scalar and finds no affinity in it —
# a property of the READ, not of the file. Take the scalar and parse it AS a
# document and the same structure is there. A line-oriented scan reaches it too,
# and then has to guess: it cannot tell a `#`-commented block from a live one, a
# scoring preference from a constraint, or a block sequence from a flow list.
pool_pod_document() {
  yq '.spec.source.helm.values' "$1"
}

term_count() {
  local doc="$1" pod="$2"
  printf '%s\n' "$doc" | yq "${pod}.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms | length" -
}

# The hostnames ONE nodeSelectorTerm rules out, from that term's own
# kubernetes.io/hostname NotIn expressions. `preferred...Execution` is not read
# at all: it scores nodes, it does not remove them. An `In` list is not read as
# an exclusion either — the one file that pins that way,
# app-arc-runners-build.yaml, is deliberately outside POOL_NOTIN_FILES, and a
# file that moves to `In` belongs there rather than under a rule written for
# NotIn.
term_notin_hostnames() {
  local doc="$1" pod="$2" idx="$3"
  printf '%s\n' "$doc" | yq "${pod}.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[$idx].matchExpressions[] | select(.key == \"kubernetes.io/hostname\" and .operator == \"NotIn\") | .values[]" -
}

# nodeSelectorTerms are OR-ed: a node that satisfies ANY term is eligible. So a
# node is excluded only when EVERY term rules it out, and zero terms rule out
# nothing at all.
assert_excludes() {
  local label="$1" doc="$2" pod="$3"
  local terms vals node open i
  local -a ruled_out
  if ! terms="$(term_count "$doc" "$pod")"; then
    fail "$label did not parse as YAML — an affinity this check cannot read is an affinity it cannot judge"
    return
  fi
  if [[ ! "$terms" =~ ^[0-9]+$ ]]; then
    fail "$label has an unreadable nodeSelectorTerms list ($terms) — the exclusion cannot be judged"
    return
  fi
  for ((i = 0; i < terms; i++)); do
    if ! vals="$(term_notin_hostnames "$doc" "$pod" "$i")"; then
      fail "$label did not parse as YAML at nodeSelectorTerm #$i — the exclusion cannot be judged"
      return
    fi
    ruled_out[i]="$vals"
  done

  while IFS= read -r node; do
    [[ -n "$node" ]] || continue
    if [[ "$terms" -eq 0 ]]; then
      fail "$label leaves $node schedulable — it carries no requiredDuringScheduling nodeSelectorTerms, and a preference only scores a node, it never removes it"
      continue
    fi
    open=""
    for ((i = 0; i < terms; i++)); do
      if ! printf '%s\n' "${ruled_out[$i]}" | grep -qxF "$node"; then
        open="$i"
        break
      fi
    done
    if [[ -n "$open" ]]; then
      fail "$label leaves $node schedulable — nodeSelectorTerm #$open does not rule it out, and terms are OR-ed, so one open term is enough"
    fi
  done <<<"$servers"
}

for i in "${!WARMER_FILES[@]}"; do
  f="${WARMER_FILES[$i]}"
  [[ -f "$f" ]] || continue
  assert_excludes "${f#"$ROOT"/}" "$(cat "$f")" "${WARMER_POD_PATHS[$i]}"
done
for f in "${POOL_NOTIN_FILES[@]}"; do
  [[ -f "$f" ]] || continue
  if ! pool_doc="$(pool_pod_document "$f")"; then
    fail "${f#"$ROOT"/} did not parse as YAML — its helm values block cannot be read, so its affinity cannot be judged"
    continue
  fi
  assert_excludes "${f#"$ROOT"/}" "$pool_doc" ".template.spec"
done

if [[ "$failures" -gt 0 ]]; then
  echo "verify-warmer-pins: $failures failure(s)" >&2
  exit 1
fi
echo "verify-warmer-pins: OK — one digest across ${#POOL_FILES[@]} pool files + ${#WARMER_FILES[@]} warmer files, no privilege, $(printf '%s' "$servers" | grep -c .) control-plane node(s) excluded from ${#WARMER_FILES[@]} warmer + ${#POOL_NOTIN_FILES[@]} pool files"
