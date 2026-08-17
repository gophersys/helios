#!/usr/bin/env bash
# Assert the bw-serve-sync CronJob is actually wired to the bridge it syncs.
#
# kubeconform proves SHAPE only. Every property this feature depends on is
# invisible to it, and the failure mode is the worst kind: the Job fails every
# 10 minutes in a namespace nobody watches (debt-register D16 — no alert on a
# CronJob that stops working), while the README says the cache is fresh. The
# phase-4 verifier of the change proved it: a selector typo and a wrong port
# passed kubeconform, server dry-run AND ctl.sh validate.
#
# Five ways this silently does not work, all asserted below:
#
#   1. THE NETWORKPOLICY DOES NOT ADMIT THE JOB. Ingress to bw-serve is
#      default-denied. A from.podSelector that does not match the Job pod's
#      labels, or a wrong port, denies every sync forever.
#   2. THE NETWORKPOLICY GUARDS THE WRONG PODS. Its podSelector must select the
#      bridge pods that bw-serve.yaml actually labels.
#   3. THE URL POINTS AT NOTHING. Host and port must be the Service that
#      bw-serve.yaml declares, in the namespace both objects live in.
#   4. THE SHELL SWALLOWS A FAILURE. The job script must keep `curl -f` (fail
#      on HTTP error status), keep the "success":true body check, and contain
#      no `|| true`.
#   5. THE JOB RETRIES ITSELF GREEN OR WEDGES. restartPolicy must stay Never,
#      concurrency Forbid, and activeDeadlineSeconds must stay under the 600 s
#      schedule period so a stuck run can never block the next slot.
#
# Exit 0 = every property holds. Exit 1 = at least one does not. Exit 127 = yq
# is missing.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/platform/core/secrets-operator/manifests"
SYNC="$DIR/bw-serve-sync.yaml"
BRIDGE="$DIR/bw-serve.yaml"

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }
ok()  { printf '  %s %s\n' "$(grn PASS)" "$1"; pass=$((pass + 1)); }
bad() { printf '  %s %s\n' "$(red FAIL)" "$1"; echo "::error::$1"; fail=$((fail + 1)); }

if ! command -v yq >/dev/null 2>&1; then
  # A missing tool is a failure, never a skip.
  printf '  %s yq is required and is not installed\n' "$(red FAIL)"
  exit 127
fi

for f in "$SYNC" "$BRIDGE"; do
  if [ ! -f "$f" ]; then
    bad "missing manifest: ${f#"$ROOT"/}"
  fi
done
if [ "$fail" -gt 0 ]; then
  echo; echo "  pass=$pass fail=$fail"; exit 1
fi

cj()  { yq eval-all "select(.kind == \"CronJob\") | $1" "$SYNC" 2>/dev/null; }
np()  { yq eval-all "select(.kind == \"NetworkPolicy\") | $1" "$SYNC" 2>/dev/null; }
svc() { yq eval-all "select(.kind == \"Service\") | $1" "$BRIDGE" 2>/dev/null; }
dep() { yq eval-all "select(.kind == \"Deployment\") | $1" "$BRIDGE" 2>/dev/null; }

echo "verifying the bw-serve-sync CronJob is wired to the bridge"

# ---- 1. the NetworkPolicy admits the Job pods -------------------------------
# Every key=value the allow's from.podSelector demands must be a label the Job
# pod template carries. An empty selector list is a failure, not a trivial pass.
from_pairs="$(np '.spec.ingress[].from[].podSelector.matchLabels | to_entries[] | .key + "=" + .value')"
if [ -z "$from_pairs" ]; then
  bad "the NetworkPolicy allow has no from.podSelector.matchLabels — it admits nothing it can name"
else
  miss=""
  while IFS= read -r kv; do
    [ -n "$kv" ] || continue
    got="$(cj ".spec.jobTemplate.spec.template.metadata.labels[\"${kv%%=*}\"] // \"\"")"
    [ "$got" = "${kv#*=}" ] || miss="$miss $kv"
  done <<EOF
$from_pairs
EOF
  if [ -z "$miss" ]; then
    ok "the allow's from.podSelector matches the Job pod labels ($(printf '%s' "$from_pairs" | tr '\n' ' '))"
  else
    bad "the Job pod labels do not carry:$miss — default-deny then blocks every sync"
  fi
fi

# ---- 2. the NetworkPolicy guards the bridge pods ----------------------------
target_pairs="$(np '.spec.podSelector.matchLabels | to_entries[] | .key + "=" + .value')"
if [ -z "$target_pairs" ]; then
  bad "the NetworkPolicy has no spec.podSelector.matchLabels — it guards every pod in the namespace"
else
  miss=""
  while IFS= read -r kv; do
    [ -n "$kv" ] || continue
    got="$(dep ".spec.template.metadata.labels[\"${kv%%=*}\"] // \"\"")"
    [ "$got" = "${kv#*=}" ] || miss="$miss $kv"
  done <<EOF
$target_pairs
EOF
  if [ -z "$miss" ]; then
    ok "the NetworkPolicy targets the bridge pods ($(printf '%s' "$target_pairs" | tr '\n' ' '))"
  else
    bad "the bridge pod labels do not carry:$miss — the allow guards nothing"
  fi
fi

# ---- 3. one port, three declarations ----------------------------------------
# The pod port is what an ingress NetworkPolicy filters on, the Service port is
# what the URL dials. All three must be the same number.
np_port="$(np '.spec.ingress[].ports[].port' | head -1)"
pod_port="$(dep '.spec.template.spec.containers[0].ports[0].containerPort')"
svc_port="$(svc '.spec.ports[0].port')"
if [ -n "$np_port" ] && [ "$np_port" = "$pod_port" ] && [ "$svc_port" = "$np_port" ]; then
  ok "NetworkPolicy, container and Service agree on port $np_port"
else
  bad "port mismatch: NetworkPolicy=${np_port:-<none>} container=${pod_port:-<none>} Service=${svc_port:-<none>}"
fi

# ---- 4. the URL dials the Service that exists -------------------------------
script="$(cj '.spec.jobTemplate.spec.template.spec.containers[0].args[0]')"
svc_name="$(svc '.metadata.name')"
svc_ns="$(svc '.metadata.namespace')"
cj_ns="$(cj '.metadata.namespace')"
want_url="http://${svc_name}.${svc_ns}.svc.cluster.local:${svc_port}/sync"
if printf '%s' "$script" | tr -d '\\\n' | tr -s ' ' | grep -qF "$want_url"; then
  ok "the job dials $want_url"
else
  bad "the job script does not dial $want_url — the sync goes nowhere"
fi
if [ "$cj_ns" = "$svc_ns" ]; then
  ok "CronJob and Service share namespace '$svc_ns'"
else
  bad "CronJob namespace '$cj_ns' != Service namespace '$svc_ns' — the podSelector allow cannot cross namespaces"
fi

# ---- 5. the failure chain stays loud ----------------------------------------
if printf '%s' "$script" | grep -q 'curl -fsS'; then
  ok "curl keeps -f: an HTTP error status fails the run"
else
  bad "the job script lost 'curl -fsS' — an HTTP error would read as success"
fi
if printf '%s' "$script" | grep -Eq 'grep .*success'; then
  ok "the 200-with-success:false guard is present"
else
  bad "the job script lost the \"success\":true body check"
fi
if printf '%s' "$script" | grep -q '|| true'; then
  bad "the job script contains '|| true' — a swallowed failure in the one place that must be loud"
else
  ok "no '|| true' in the job script"
fi

# ---- 6. the job cannot retry itself green or wedge the schedule -------------
rp="$(cj '.spec.jobTemplate.spec.template.spec.restartPolicy')"
cp="$(cj '.spec.concurrencyPolicy')"
adl="$(cj '.spec.jobTemplate.spec.activeDeadlineSeconds')"
if [ "$rp" = "Never" ]; then
  ok "restartPolicy is Never"
else
  bad "restartPolicy is '${rp:-<none>}', expected Never — OnFailure hides the failure inside one pod"
fi
if [ "$cp" = "Forbid" ]; then
  ok "concurrencyPolicy is Forbid"
else
  bad "concurrencyPolicy is '${cp:-<none>}', expected Forbid"
fi
if [ -n "$adl" ] && [ "$adl" != "null" ] && [ "$adl" -lt 600 ]; then
  ok "activeDeadlineSeconds $adl is under the 600 s schedule period"
else
  bad "activeDeadlineSeconds is '${adl:-<none>}' — a stuck run must die before the next slot"
fi

echo
echo "  pass=$pass fail=$fail"
[ "$fail" -eq 0 ] || exit 1
