#!/usr/bin/env bash
# LOCAL-ONLY. Prove, against the LIVE apiserver, that platform/core/policy's two
# ValidatingAdmissionPolicies actually refuse the deletes they claim to refuse —
# and that they refuse nothing else.
#
# WHY THIS IS NOT IN validate.yml
# There is no offline evaluator for a ValidatingAdmissionPolicy. The supported
# way to exercise one is `--dry-run=server` against a real apiserver that already
# has the policy bound, and a CI runner has no such cluster. A step that fails for
# the environment rather than for the property always ends in a skip, and a
# skipped enforcement check reads as a pass. So this joins verify-access and
# verify-vault-refs as a local-only verb, and its CI-safe half — the manifest
# shape: Deny binding, Fail policy, labels present, retention pinned — lives in
# scripts/verify-vap-policies.sh, which validate.yml does run.
#
# WHY --dry-run=server IS THE RIGHT INSTRUMENT
# It runs the full admission chain, including ValidatingAdmissionPolicy, and then
# discards the write. A denial is a real denial by the real policy. An admission
# persists nothing. That is exactly the "prove it, do not assert it" instrument
# this repository asks for, at zero risk to live data.
#
# WHAT IT PROVES — four directions, not one:
#   1. DENY   a PVC labelled platform.gophersys/retain=true is refused
#   2. DENY   a PVC in a namespace labelled protected-storage=true is refused,
#             even with no label of its own (this is the case that covers
#             data-vault-0 and data-eden-postgres-0, which come from immutable
#             volumeClaimTemplates and cannot be labelled individually)
#   3. DENY   a namespace labelled protected=true is refused
#   4. ADMIT  an unlabelled PVC in an unprotected namespace is NOT refused, and
#             the break-glass annotation really does open the door
# A guard that denies everything is as broken as one that denies nothing, so
# direction 4 carries the same weight as directions 1-3.
#
# WHAT IT TOUCHES
# One scratch namespace and two PVCs, created and removed by this script. The
# PVCs set `storageClassName: ""`, so they stay Pending, bind to nothing and
# provision no volume — no PV is created and no data exists to lose. The teardown
# is itself a proof: the scratch objects are protected by the policy under test,
# so removing them REQUIRES the break-glass annotation to work.
#
# Exit 0 = all four directions hold. Exit 1 = at least one does not.
# Exit 127 = kubectl missing. Exit 2 = the policies are not installed on this
# cluster — a precondition failure, reported as such, never as a pass.
set -uo pipefail

NS="vap-guard-test-$$"
GUARDED_PVC="guarded"
PLAIN_PVC="plain"
NS_LABEL="platform.gophersys/protected"
NS_STORAGE_LABEL="platform.gophersys/protected-storage"
PVC_LABEL="platform.gophersys/retain"
OVERRIDE="platform.gophersys/allow-delete"

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }
ok()  { printf '  %s %s\n' "$(grn PASS)" "$1"; pass=$((pass + 1)); }
bad() { printf '  %s %s\n' "$(red FAIL)" "$1"; fail=$((fail + 1)); }

command -v kubectl >/dev/null 2>&1 || {
  printf '  %s kubectl is required and is not installed\n' "$(red FAIL)"
  exit 127
}

created=0
cleanup() {
  [ "$created" -eq 1 ] || return 0
  echo
  echo "teardown (the scratch objects are protected by the policy under test, so"
  echo "this also proves the break-glass annotation works):"
  kubectl annotate pvc -n "$NS" --all "$OVERRIDE=teardown of $NS" --overwrite >/dev/null
  kubectl delete pvc -n "$NS" --all --wait=false >/dev/null
  kubectl annotate ns "$NS" "$OVERRIDE=teardown of $NS" --overwrite >/dev/null
  kubectl delete ns "$NS" --wait=false >/dev/null
  echo "  removed namespace $NS"
}
trap cleanup EXIT

ctx="$(kubectl config current-context)"
echo "live admission test against context '$ctx'"

# ---- precondition: the policies are installed AND bound with Deny -----------
# A missing policy is a FAILURE with its own exit code, never a skip. Without
# this, every "DENY" case below would fail as if the CEL were wrong, and every
# "ADMIT" case would pass for the wrong reason.
missing=0
for p in storage-delete-guard namespace-delete-guard; do
  if ! kubectl get validatingadmissionpolicy "$p" >/dev/null 2>&1; then
    printf '  %s ValidatingAdmissionPolicy/%s is not installed on %s\n' "$(red FAIL)" "$p" "$ctx"
    missing=1
    continue
  fi
  actions="$(kubectl get validatingadmissionpolicybinding "$p" -o jsonpath='{.spec.validationActions[*]}' 2>/dev/null)"
  if [ "$actions" != "Deny" ]; then
    printf '  %s Binding/%s has validationActions [%s], expected [Deny]\n' "$(red FAIL)" "$p" "${actions:-<none>}"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo
  echo "  PRECONDITION FAILED — platform/core/policy is not enforcing on this cluster."
  echo "  This test cannot measure a guard that is not there, and it will not report"
  echo "  a pass it did not measure. Sync the 'policy' Argo Application first:"
  echo "      kubectl -n argocd get app policy"
  exit 2
fi
ok "both policies are installed and bound with validationActions: [Deny]"

# ---- build the subjects -----------------------------------------------------
# storageClassName: "" keeps both PVCs Pending forever: no StorageClass is
# selected, no provisioner runs, no PV exists. They are admission subjects only.
kubectl apply -f - >/dev/null <<EOF || { bad "could not create the scratch objects"; exit 1; }
apiVersion: v1
kind: Namespace
metadata:
  name: $NS
  labels:
    $NS_LABEL: "true"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $GUARDED_PVC
  namespace: $NS
  labels:
    $PVC_LABEL: "true"
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: ""
  resources:
    requests:
      storage: 1Mi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $PLAIN_PVC
  namespace: $NS
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: ""
  resources:
    requests:
      storage: 1Mi
EOF
created=1
ok "scratch namespace $NS created with 2 Pending PVCs (no PV provisioned)"

# expect_deny <label> <kubectl args...>
expect_deny() {
  local what="$1"; shift
  local out rc
  out="$("$@" --dry-run=server 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    bad "$what — the delete was ADMITTED, the guard did not fire"
    printf '        %s\n' "$out"
    return
  fi
  case "$out" in
    *"is protected"*) ok "$what — DENIED by the policy" ;;
    *) bad "$what — refused, but not by this policy: $out"; return ;;
  esac
  printf '        %s\n' "$(printf '%s' "$out" | head -3)"
}

# expect_admit <label> <kubectl args...>
expect_admit() {
  local what="$1"; shift
  local out rc
  out="$("$@" --dry-run=server 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    ok "$what — ADMITTED"
    printf '        %s\n' "$out"
  else
    bad "$what — the delete was REFUSED, the guard is too wide"
    printf '        %s\n' "$out"
  fi
}

echo
echo "direction 1 — the per-PVC label:"
expect_deny "delete pvc $NS/$GUARDED_PVC ($PVC_LABEL=true)" \
  kubectl delete pvc -n "$NS" "$GUARDED_PVC"

echo
echo "direction 4a — narrowness: an unlabelled PVC in an unprotected namespace:"
expect_admit "delete pvc $NS/$PLAIN_PVC (no labels, namespace not storage-protected)" \
  kubectl delete pvc -n "$NS" "$PLAIN_PVC"

echo
echo "direction 2 — the namespace label reaches a PVC that carries none:"
kubectl label ns "$NS" "$NS_STORAGE_LABEL=true" --overwrite >/dev/null
expect_deny "delete pvc $NS/$PLAIN_PVC (namespace $NS_STORAGE_LABEL=true)" \
  kubectl delete pvc -n "$NS" "$PLAIN_PVC"

echo
echo "direction 3 — the namespace itself:"
expect_deny "delete ns $NS ($NS_LABEL=true)" \
  kubectl delete ns "$NS"

echo
echo "direction 4b — break glass: the override annotation opens the door:"
kubectl annotate pvc -n "$NS" "$PLAIN_PVC" "$OVERRIDE=proving the escape hatch" --overwrite >/dev/null
expect_admit "delete pvc $NS/$PLAIN_PVC (annotated $OVERRIDE)" \
  kubectl delete pvc -n "$NS" "$PLAIN_PVC"

echo
echo "  pass=$pass fail=$fail"
[ "$fail" -eq 0 ] || exit 1
