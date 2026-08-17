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
# Two properties, both asserted from the FILES (no cluster access — this runs
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
# Exit 0 = both hold. Exit 1 = at least one does not, naming the file.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$ROOT/platform/services/gitops/registry"
ARC="$ROOT/platform/services/ci/arc-runners"

POOL_FILES=(
  "$REGISTRY/app-arc-runners-build.yaml"
  "$REGISTRY/app-arc-runners-org.yaml"
  "$REGISTRY/app-arc-runners-review.yaml"
)
WARMER_FILES=(
  "$ARC/42-image-warmer-daemonset.yaml"
  "$ARC/43-image-warmer-refresh.yaml"
)

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

if [[ "$failures" -gt 0 ]]; then
  echo "verify-warmer-pins: $failures failure(s)" >&2
  exit 1
fi
echo "verify-warmer-pins: OK — one digest across ${#POOL_FILES[@]} pool files + ${#WARMER_FILES[@]} warmer files, no privilege"
