#!/usr/bin/env bash
# k9s-host.sh — run the Clusters "Open in k9s" backend ON THE MAC HOST (not the devcontainer).
#
# WHY THE HOST: the homelab/oracle clusters are reachable only over Tailscale, whose routes live on
# the host — a container (the devcontainer) cannot reach them, so a container-side k9s only ever sees
# a local k3d cluster. Running ttyd+k9s on the host fixes that: k9s sees the REAL namespaces.
#
# WHAT IT DOES: builds a MERGED kubeconfig whose context names ARE the topology cluster ids (home,
# oracle) — renaming each source kubeconfig's cluster/user/context so they don't collide — then serves
# a read-only k9s TUI via ttyd on K9S_PORT. That is exactly what the Clusters button opens
# (http://localhost:<port>/?arg=--context&arg=<cluster>&arg=-n&arg=<ns>&arg=-c&arg=<view>).
#
#   bash apps/frontend/scripts/k9s-host.sh [<clusterId>=<kubeconfig> ...]
#   # default: home=~/.kube/homelab.yaml oracle=~/.kube/cloud.yaml
#
# Requires ttyd + k9s + yq on the host (brew install ttyd k9s yq). The merged kubeconfig is written to
# ~/.kube/eden-clusters.yaml (a gitignored location; it holds REAL credentials — never commit it).
set -Eeuo pipefail

PORT="${K9S_PORT:-7682}"
MERGED="${EDEN_K9S_KUBECONFIG:-$HOME/.kube/eden-clusters.yaml}"
for t in ttyd k9s yq kubectl; do
  command -v "$t" >/dev/null 2>&1 || { echo "missing '$t' on the host (brew install ttyd k9s yq)" >&2; exit 1; }
done

PAIRS=("$@")
[ ${#PAIRS[@]} -eq 0 ] && PAIRS=("home=$HOME/.kube/homelab.yaml" "oracle=$HOME/.kube/cloud.yaml")

parts=()
for pair in "${PAIRS[@]}"; do
  id="${pair%%=*}"; path="${pair#*=}"
  [ -f "$path" ] || { echo "kubeconfig not found for '$id': $path" >&2; exit 1; }
  tmp="$(mktemp)"
  # rename the single cluster/user/context to the cluster id so merged contexts are unique + match
  # the topology clusterId the button passes as --context.
  yq ".clusters[0].name=\"$id\" | .users[0].name=\"$id\" | .contexts[0].name=\"$id\" \
      | .contexts[0].context.cluster=\"$id\" | .contexts[0].context.user=\"$id\" | .current-context=\"$id\"" \
      "$path" > "$tmp"
  parts+=("$tmp")
done
KUBECONFIG="$(IFS=:; echo "${parts[*]}")" kubectl config view --flatten --raw > "$MERGED"
chmod 600 "$MERGED"; rm -f "${parts[@]}"
KUBECONFIG="$MERGED" kubectl config use-context "${PAIRS[0]%%=*}" >/dev/null
echo "[k9s-host] merged kubeconfig: $MERGED — contexts: $(KUBECONFIG="$MERGED" kubectl config get-contexts -o name | tr '\n' ' ')" >&2

pkill -f "ttyd .*${PORT}" 2>/dev/null || true
echo "[k9s-host] serving read-only k9s over the REAL clusters at http://localhost:${PORT}/" >&2
exec ttyd -p "${PORT}" -W -a -t fontSize=13 -t macOptionIsMeta=true \
  k9s --kubeconfig "$MERGED" --readonly
