#!/usr/bin/env bash
# k9s-serve.sh — serve a live, read-only k9s TUI in the browser via ttyd on its OWN port. The
# Clusters "Open in k9s" button opens it directly (a full-page terminal needs no same-origin; vite's
# ws proxy also crashes under bun):
#   http://<host>:<port>/?arg=--context&arg=<cluster>&arg=-n&arg=<namespace>&arg=-c&arg=<resource>
# and ttyd appends those as k9s flags, so the terminal lands on the clicked resource. Inside the
# devcontainer, publish the port to the Mac host with a socat sidecar (mirrors eden-demo-proxy).
#
#   bash apps/frontend/scripts/k9s-serve.sh <kubeconfig> [port]
#
# REACHABILITY: ttyd+k9s must run somewhere that can reach the target cluster's API. The Eden
# devcontainer (where the demo runs) is on the docker bridge and CANNOT reach a Tailscale-only
# cluster (homelab/oracle), so against those run this on the Mac host (which is on the tailnet) and
# point EDEN_K9S_TARGET at it. A local k3d/kind cluster IS reachable from the devcontainer (the
# pipeline proof). Pass a MERGED kubeconfig (all contexts) so the per-cluster --context arg resolves.
#
# SAFETY: k9s runs `--readonly` (no destructive actions); ttyd binds loopback and is reached only
# through the same-origin proxy. `-a` lets the client pass k9s FLAGS (not a shell) — loopback-only.
set -Eeuo pipefail

KUBECONFIG_PATH="${1:?usage: k9s-serve.sh <kubeconfig> [port]}"
PORT="${2:-7682}"
[ -f "${KUBECONFIG_PATH}" ] || { echo "kubeconfig not found: ${KUBECONFIG_PATH}" >&2; exit 1; }

command -v ttyd >/dev/null 2>&1 || { echo "ttyd not found (apt-get install -y ttyd, or bake it into the devcontainer image)" >&2; exit 1; }
command -v k9s  >/dev/null 2>&1 || { echo "k9s not found" >&2; exit 1; }

export KUBECONFIG="${KUBECONFIG_PATH}"
echo "[k9s-serve] ttyd on :${PORT} serving read-only k9s over ${KUBECONFIG_PATH}" >&2
exec ttyd -p "${PORT}" -W -a \
  k9s --kubeconfig "${KUBECONFIG_PATH}" --readonly
