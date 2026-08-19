#!/usr/bin/env bash
# Spec for scripts/verify-vap-policies.sh — the admission guard must fail LOUDLY
# for every way it can silently stop guarding.
#
# WHY THIS SUITE EXISTS
# The check being tested is the successor to Kyverno, and Kyverno's failure was
# not that it was absent — it was installed, running, reported healthy, and
# enforced nothing, for months, while 5 documents said it enforced. A verifier
# for that class is worthless unless it has been PROVEN to fail. So every case
# below drives the REAL script against a mktemp fixture tree with exactly one
# property broken, and asserts both the exit code and the sentence.
#
# THE CONTRACT THESE CASES PIN
#   DENY-ONLY        a binding with validationActions other than [Deny] FAILS.
#                    Audit and Warn are the exact Kyverno defect, and they are a
#                    one-word edit away.
#   FAIL-CLOSED      failurePolicy other than Fail FAILS. `Ignore` means a broken
#                    expression ADMITS the delete.
#   BOUND            a policy with no binding FAILS. The apiserver stores an
#                    unbound policy and evaluates nothing; `kubectl get` cannot
#                    tell the two apart.
#   NO-DANGLE        a binding naming a policy that does not exist FAILS.
#   ARGO-APPLIES     no Application deploying the manifests FAILS: policies in
#                    git and on no cluster protect nothing.
#   NO-PRUNE         prune:true on that Application FAILS: deleting a manifest
#                    file would delete the live enforcement.
#   NON-VACUOUS      zero labelled namespaces FAILS. A correct, enforcing, bound
#                    policy set that matches no object is the false green this
#                    whole component exists to end.
#   PVC-LABELLED     a PVC in a protected namespace without its own retain label
#                    FAILS.
#   RETENTION-PINNED a StatefulSet with volumeClaimTemplates that does not pin
#                    persistentVolumeClaimRetentionPolicy=Retain/Retain FAILS,
#                    and `Delete` FAILS. `Delete` puts an ownerRef on the PVCs
#                    and garbage-collects them BELOW admission.
#   FLOOR            a missing or empty policy directory FAILS, and a scan over
#                    zero manifests FAILS. Measuring nothing is not a pass.
#   NO-SWALLOW       an unparseable manifest FAILS, in the scan tree AND in the
#                    policy directory. A `2>/dev/null` there would read as "this
#                    file declares no PVC" / "no policy is declared" — the right
#                    exit code for the wrong reason.
#   GREEN            the correct tree passes. A check that cannot pass is as
#                    useless as one that cannot fail.
#
# Exit 0 = the spec holds. Exit 1 = at least one case does not.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/verify-vap-policies.sh"

command -v yq >/dev/null 2>&1 || { echo "test-verify-vap-policies: yq is required and is not installed" >&2; exit 127; }
[ -f "$SCRIPT" ] || { echo "test-verify-vap-policies: $SCRIPT is missing" >&2; exit 1; }

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }
ok()  { printf '  %s %s\n' "$(grn PASS)" "$1"; pass=$((pass + 1)); }
bad() { printf '  %s %s\n' "$(red FAIL)" "$1"; fail=$((fail + 1)); }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# build <dir> — a fixture tree that PASSES. Every case then breaks exactly one
# thing, so a failure names the property and not the fixture.
build() {
  local d="$1"
  mkdir -p "$d/platform/core/policy/manifests" "$d/platform/services/gitops/registry" "$d/apps/demo"

  cat > "$d/platform/core/policy/manifests/00-guard.yaml" <<'YAML'
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: storage-delete-guard
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["DELETE"]
        resources: ["persistentvolumeclaims"]
  validations:
    - expression: "true"
---
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicyBinding
metadata:
  name: storage-delete-guard
spec:
  policyName: storage-delete-guard
  validationActions: [Deny]
YAML

  cat > "$d/platform/services/gitops/registry/app-policy.yaml" <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: policy
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://github.com/gophersys/infrastructure.git
    targetRevision: main
    path: platform/core/policy/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: kube-system
  syncPolicy:
    automated:
      selfHeal: true
      prune: false
YAML

  cat > "$d/apps/demo/00-namespace.yaml" <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: demo
  labels:
    platform.gophersys/protected-storage: "true"
    platform.gophersys/protected: "true"
YAML

  cat > "$d/apps/demo/10-pvc.yaml" <<'YAML'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: demo-data
  namespace: demo
  labels:
    platform.gophersys/retain: "true"
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 1Gi
YAML

  cat > "$d/apps/demo/20-sts.yaml" <<'YAML'
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: demo-db
  namespace: demo
spec:
  serviceName: demo-db
  replicas: 1
  persistentVolumeClaimRetentionPolicy:
    whenDeleted: Retain
    whenScaled: Retain
  selector:
    matchLabels: { app: demo-db }
  template:
    metadata:
      labels: { app: demo-db }
    spec:
      containers:
        - name: db
          image: postgres:17
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
YAML
}

n=0
# case <name> <expected-rc> <expected-substring-or-empty> <mutator-fn>
case_run() {
  local name="$1" want_rc="$2" want_msg="$3" mutate="$4"
  n=$((n + 1))
  local d="$WORK/case-$n"
  mkdir -p "$d"
  build "$d"
  "$mutate" "$d"

  local out rc
  out="$(bash "$SCRIPT" "$d" 2>&1)"; rc=$?

  if [ "$rc" -ne "$want_rc" ]; then
    bad "$name: exit $rc, expected $want_rc"
    printf '%s\n' "$out" | sed 's/^/        /'
    return
  fi
  if [ -n "$want_msg" ] && ! printf '%s' "$out" | grep -qF -- "$want_msg"; then
    bad "$name: exit $rc as expected, but the output never says '$want_msg'"
    printf '%s\n' "$out" | sed 's/^/        /'
    return
  fi
  ok "$name"
}

noop() { :; }

m_audit()      { yq -i '(select(.kind == "ValidatingAdmissionPolicyBinding") | .spec.validationActions) = ["Audit"]' "$1/platform/core/policy/manifests/00-guard.yaml"; }
m_warn()       { yq -i '(select(.kind == "ValidatingAdmissionPolicyBinding") | .spec.validationActions) = ["Deny","Warn"]' "$1/platform/core/policy/manifests/00-guard.yaml"; }
m_ignore()     { yq -i '(select(.kind == "ValidatingAdmissionPolicy") | .spec.failurePolicy) = "Ignore"' "$1/platform/core/policy/manifests/00-guard.yaml"; }
m_unbound()    { yq -i 'select(.kind != "ValidatingAdmissionPolicyBinding")' "$1/platform/core/policy/manifests/00-guard.yaml"; }
m_dangle()     { yq -i '(select(.kind == "ValidatingAdmissionPolicyBinding") | .spec.policyName) = "gone"' "$1/platform/core/policy/manifests/00-guard.yaml"; }
m_no_app()     { rm -f "$1/platform/services/gitops/registry/app-policy.yaml"; }
m_prune()      { yq -i '.spec.syncPolicy.automated.prune = true' "$1/platform/services/gitops/registry/app-policy.yaml"; }
m_unlabelled() { yq -i 'del(.metadata.labels)' "$1/apps/demo/00-namespace.yaml"; }
m_pvc_bare()   { yq -i 'del(.metadata.labels)' "$1/apps/demo/10-pvc.yaml"; }
m_sts_unset()  { yq -i 'del(.spec.persistentVolumeClaimRetentionPolicy)' "$1/apps/demo/20-sts.yaml"; }
m_sts_delete() { yq -i '.spec.persistentVolumeClaimRetentionPolicy.whenDeleted = "Delete"' "$1/apps/demo/20-sts.yaml"; }
m_empty_dir()  { rm -f "$1"/platform/core/policy/manifests/*.yaml; }
m_no_dir()     { rm -rf "$1/platform/core/policy"; }
m_no_scan()    { rm -rf "$1/apps" "$1/platform/services"; }
m_malformed()  { printf 'kind: PersistentVolumeClaim\n  bad: [indent\n' > "$1/apps/demo/99-broken.yaml"; }
m_bad_policy() { printf 'kind: ValidatingAdmissionPolicy\n  bad: [indent\n' > "$1/platform/core/policy/manifests/99-broken.yaml"; }

echo "spec: scripts/verify-vap-policies.sh"

case_run "GREEN            a correct tree passes"                     0 "pass=" noop
case_run "DENY-ONLY        validationActions [Audit] fails"           1 "only [Deny] enforces" m_audit
case_run "DENY-ONLY        validationActions [Deny,Warn] fails"       1 "only [Deny] enforces" m_warn
case_run "FAIL-CLOSED      failurePolicy Ignore fails"                1 "would ADMIT the delete" m_ignore
case_run "BOUND            a policy with no binding fails"            1 "has no ValidatingAdmissionPolicyBinding" m_unbound
case_run "NO-DANGLE        a binding naming a missing policy fails"   1 "it binds nothing" m_dangle
case_run "ARGO-APPLIES     no Argo Application fails"                 1 "on no cluster" m_no_app
case_run "NO-PRUNE         prune:true fails"                          1 "would delete the live enforcement" m_prune
case_run "NON-VACUOUS      zero labelled namespaces fails"            1 "matches nothing" m_unlabelled
case_run "PVC-LABELLED     an unlabelled PVC in a protected ns fails" 1 "loses its guard" m_pvc_bare
case_run "RETENTION-PINNED an unset retention policy fails"           1 "below admission" m_sts_unset
case_run "RETENTION-PINNED whenDeleted: Delete fails"                 1 "below admission" m_sts_delete
case_run "FLOOR            an empty policy directory fails"           1 "nothing is enforced" m_empty_dir
case_run "FLOOR            a missing policy directory fails"          1 "the admission guard is gone" m_no_dir
case_run "FLOOR            a scan over zero manifests fails"          1 "measured nothing" m_no_scan
case_run "NO-SWALLOW       an unparseable POLICY manifest fails"       1 "yq could not read" m_bad_policy
case_run "NO-SWALLOW       an unparseable manifest fails"             1 "yq could not read" m_malformed

echo
echo "  cases=$n pass=$pass fail=$fail"
[ "$fail" -eq 0 ] || exit 1
