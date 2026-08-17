#!/usr/bin/env bash
# Spec for scripts/verify-buildx-key.sh — an owner-only key must be readable by
# the user the runner actually runs as.
#
# THE GAP THESE CASES PIN (live in scripts/verify-buildx-key.sh today)
# Check 10 proves the mount is owner-only: no group bit, no other bit, owner read
# present. That is half of a readability argument. A projected secret file is
# owned by uid 0, so `0400` is readable by uid 0 and by nobody else — and NOTHING
# in the pool manifest says which uid the runner is. Today the whole claim rests
# on a COMMENT in app-arc-runners-org.yaml:
#
#     # The runner container runs as root (see .devcontainer/runner), and a
#     # secret volume is owned by root, so owner-only is readable here.
#
# A comment is not a check. The premise is a property of the IMAGE, and the image
# is a tag that changes. `ghcr.io/gophersys/cloud` ends `USER dev` (uid 1000), so
# repointing this pool at the cloud image — which is what arc-build does — makes
# every one of the 15 current checks pass while key.pem becomes unreadable to the
# process that must read it. mTLS then fails at the first arm64 build, with a
# permission error and no line in any manifest to point at.
#
# THE HONEST RULE, AND WHY 0440 IS NOT THE ESCAPE HATCH
# A secret volume projects files owned by uid 0, group 0, unless `fsGroup` is set
# — then the group becomes fsGroup. So a non-root runner can read the key by
# exactly two routes: run as uid 0, or hold a group bit through fsGroup. Check 10
# already forbids EVERY group and other bit, because tls refuses a group-readable
# private key, and this suite does not weaken that: `0440` stays a failure, with
# or without fsGroup. That leaves ONE admissible combination, and it is the one
# arc-build's plan chose: owner-only mode AND uid 0, DECLARED in the manifest.
#
# `runAsUser: 0` written down is the point. The invariant is already true at
# runtime for base-runner; what is missing is the declaration that makes it
# survive an image change, and a check that reads it.
#
# THE CONTRACT THESE CASES PIN
#   C1  an owner-only cert mount in a pool that declares NO runAsUser for the
#       container that mounts it is a FAIL, and the failure names the user.
#   C2  `runAsUser: 0` on that container is accepted, quietly and positively: the
#       run exits 0 and prints a PASS line for the property, like every other
#       check in this script.
#   C3  `runAsUser: 0` on the POD securityContext is accepted too. It applies to
#       every container in the pod, and refusing it would be wrong.
#   C4  a DECLARED non-root uid is a FAIL, and the failure names that uid. This
#       is the cloud-image defect written out: uid 1000 cannot read a root-owned
#       0400 file.
#   C5  `runAsUser: 0` on a DIFFERENT container does not count. The container
#       that mounts the certs is the one that must read them.
#   C6  a 0440 mount stays a FAIL for its mode, AND the user complaint fires
#       beside it: without fsGroup the group is root, so a non-root runner cannot
#       read a group-readable file either. Two independent defects, two lines.
#
# HOW THESE CASES REACH THE REAL SCRIPT
# verify-buildx-key.sh derives ROOT from its own location
# (ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)) and reads only manifests
# under it. There is no -f/env override, so we point it at a fixture tree WITHOUT
# editing it: a SYMLINK at <tmp>/scripts/verify-buildx-key.sh -> the real script
# makes BASH_SOURCE the symlink path, so ROOT resolves to <tmp>. The fixture tree
# holds a registry Application, an ExternalSecret and a ci-substrate.md, all
# minimal copies of the real shapes. The symlink runs the REAL script live, so the
# implementer's change is exercised, not a stale copy. Everything lives under
# mktemp; nothing is written into the repo tree and no cluster is contacted.
#
# THE FIXTURE IS SOUND ONLY IF THE ACCEPTED CASES ARE SILENT. C2 and C3 refute
# EVERY FAIL line, not just the user one, so a typo in the fixture surfaces as
# its own named failure instead of as a mysterious red somewhere else.
#
# Run: bash scripts/test-verify-buildx-key.sh            # every case
#      bash scripts/test-verify-buildx-key.sh <name>...  # one case, by name
#      bash scripts/test-verify-buildx-key.sh --list     # the case names
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/verify-buildx-key.sh"
ESC="$(printf '\033')"

CASES="
an_undeclared_runner_user_fails_the_owner_only_key
an_explicit_root_runner_is_accepted
pod_level_root_is_accepted_too
a_declared_non_root_uid_is_rejected
root_on_another_container_does_not_count
a_group_readable_mode_stays_a_failure
"

# A missing tool is a failure, never a skip. The subject exits 127 without yq, and
# every case below would then read 127 and say nothing about the rule.
if ! command -v yq >/dev/null 2>&1; then
  echo "test-verify-buildx-key: missing required tool: yq" >&2
  exit 127
fi
if [ ! -f "$SUT" ]; then
  echo "test-verify-buildx-key: subject not found: $SUT" >&2
  exit 2
fi

# mktemp dirs to shred on exit. The guard form ${arr[@]+"${arr[@]}"} is for bash
# 3.2 (the macOS system bash) under set -u, where "${empty[@]}" aborts.
TMPDIRS=()
cleanup() {
  local d
  for d in ${TMPDIRS[@]+"${TMPDIRS[@]}"}; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

failures=0
case_failures=0
out=""
rc=0
ENV_DIR=""

note() { echo "    $*"; }

bad() {
  note "FAIL: $*"
  failures=$((failures + 1))
  case_failures=$((case_failures + 1))
}

# One line of a securityContext, emitted at a chosen indent, or nothing. Keeping
# the knobs as bare uids rather than YAML fragments is what makes each case below
# a single readable line.
uid_line() { # <indent> <uid-or-empty>
  [ -n "$2" ] || return 0
  printf '%s%s\n' "$1" "runAsUser: $2"
}

sc_block() { # <indent> <uid-or-empty>
  [ -n "$2" ] || return 0
  printf '%ssecurityContext:\n' "$1"
  printf '%s  runAsUser: %s\n' "$1" "$2"
}

# A fresh fixture tree: the symlink that relocates ROOT, plus the three manifests
# the subject reads. The knobs are the mount mode and where (if anywhere) a uid is
# declared. Everything else is a trimmed copy of the real arc-org shapes, so the
# other 15 checks pass and a case measures one thing.
new_env() { # <defaultMode> <runner-uid> <pod-uid> <dind-uid>
  local mode="$1" runner_uid="$2" pod_uid="$3" dind_uid="$4"
  ENV_DIR="$(mktemp -d)"; TMPDIRS+=("$ENV_DIR")
  mkdir -p "$ENV_DIR/scripts" "$ENV_DIR/docs" \
    "$ENV_DIR/platform/services/gitops/registry" \
    "$ENV_DIR/platform/services/ci/arc-runners"
  ln -s "$SUT" "$ENV_DIR/scripts/verify-buildx-key.sh"

  cat >"$ENV_DIR/docs/ci-substrate.md" <<'EOMD'
# ci-substrate (fixture)

    docker buildx create --name mini --driver remote \
      --driver-opt cacert=/etc/buildkit-certs/ca.pem,cert=/etc/buildkit-certs/cert.pem,key=/etc/buildkit-certs/key.pem \
      tcp://10.168.0.92:1234
EOMD

  cat >"$ENV_DIR/platform/services/ci/arc-runners/40-buildkit-client-certs-externalsecret.yaml" <<'EOYAML'
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: buildkit-client-certs
  namespace: arc-runners
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: vaultwarden
  target:
    name: buildkit-client-certs
    creationPolicy: Owner
  data:
    - secretKey: ca.pem
      remoteRef:
        key: shared/eden/buildkit-client-ca
    - secretKey: cert.pem
      remoteRef:
        key: shared/eden/buildkit-client-cert
    - secretKey: key.pem
      remoteRef:
        key: shared/eden/buildkit-client-key
EOYAML

  cat >"$ENV_DIR/platform/services/gitops/registry/app-arc-runners-org.yaml" <<EOYAML
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: arc-runners-org
  namespace: argocd
spec:
  project: ci
  source:
    repoURL: ghcr.io/actions/actions-runner-controller-charts
    chart: gha-runner-scale-set
    targetRevision: 0.14.2
    helm:
      releaseName: arc-org
      values: |
        githubConfigUrl: https://github.com/gophersys
        githubConfigSecret: arc-github-app
        runnerScaleSetName: arc-org
        minRunners: 1
        maxRunners: 4
        template:
          spec:
            securityContext:
              supplementalGroups: [123]
$(uid_line "              " "$pod_uid")
            initContainers:
              - name: dind
                image: docker:dind
                restartPolicy: Always
$(sc_block "                " "$dind_uid")
                volumeMounts:
                  - name: work
                    mountPath: /home/runner/_work
            containers:
              - name: runner
                image: ghcr.io/gophersys/base-runner:e0c6bc5
                command: ["/home/runner/run.sh"]
$(sc_block "                " "$runner_uid")
                volumeMounts:
                  - name: work
                    mountPath: /home/runner/_work
                  - name: buildkit-client-certs
                    mountPath: /etc/buildkit-certs
                    readOnly: true
            volumes:
              - name: work
                emptyDir:
                  sizeLimit: 10Gi
              - name: buildkit-client-certs
                secret:
                  secretName: buildkit-client-certs
                  defaultMode: $mode
                  optional: true
  destination:
    server: https://kubernetes.default.svc
    namespace: arc-runners
EOYAML
}

# Drive the REAL script through the symlink. set +e wraps the call so a non-zero
# exit does not abort the run, and rc=\$? sits on the line right after the
# substitution so nothing runs between them. A pipeline would report its last
# stage instead — a misreading that has produced false findings here.
run_verify() {
  set +e
  out="$(bash "$ENV_DIR/scripts/verify-buildx-key.sh" 2>&1)"
  rc=$?
  out="$(printf '%s\n' "$out" | sed "s/${ESC}\[[0-9;]*m//g")"
  set -e
}

expect_rc() { # <want> <why>
  if [ "$rc" -eq "$1" ]; then
    return 0
  fi
  bad "exit $rc, want $1 — $2"
  printf '%s\n' "$out" | grep -E 'FAIL|pass=' | sed 's/^/      | /'
}

expect_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    return 0
  fi
  bad "no line matched /$1/ — $2"
  printf '%s\n' "$out" | grep -E 'FAIL|pass=' | sed 's/^/      | /'
}

refute_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    bad "a line matched /$1/ but must not — $2"
    printf '%s\n' "$out" | grep -E "$1" | sed 's/^/      | /'
  fi
}

# -------- the cases --------

# 1. C1 — THE DEFECT AS IT STANDS TODAY. This fixture IS app-arc-runners-org.yaml:
# 0400, and not one word about which uid the runner is. It passes every check the
# script has, and it is one image repoint away from an unreadable key. RED now:
# exit 0, 15 PASS lines, no mention of a user anywhere.
test_an_undeclared_runner_user_fails_the_owner_only_key() {
  new_env 0400 "" "" ""
  run_verify
  expect_rc 1 "an owner-only key with no declared runner user is unproven, not proven (C1)"
  expect_line 'FAIL.*(runAsUser|uid)' "the failure must name the user, so a reader knows what to declare (C1)"
}

# 2. C2 — THE FIX, AND THE PROOF THAT THE CHECK IS NOT A BLANKET FAIL. The
# combination arc-build ships: 0400 plus an explicit `runAsUser: 0` on the
# container that mounts the certs. Every FAIL is refuted, so a fixture defect
# reports itself here rather than corrupting another case. RED now: the run is
# already silent, but it is silent about nothing — no PASS line covers the
# property, which is the whole gap.
test_an_explicit_root_runner_is_accepted() {
  new_env 0400 0 "" ""
  run_verify
  expect_rc 0 "0400 read by uid 0 is exactly the admissible combination (C2)"
  refute_line 'FAIL' "the accepted fixture must be clean — any FAIL here is a fixture defect (C2)"
  expect_line 'PASS.*(runAsUser|uid)' \
    "the property must be asserted out loud, like every other check in this script (C2)"
}

# 3. C3 — POD-LEVEL ROOT IS STILL ROOT. `runAsUser` on the pod securityContext
# applies to every container that does not override it, so refusing it would
# reject a correct pool. RED now: no PASS line for the property. It also kills the
# narrowest possible implementation — one that reads the container securityContext
# and nothing else.
test_pod_level_root_is_accepted_too() {
  new_env 0400 "" 0 ""
  run_verify
  expect_rc 0 "a pod-level runAsUser: 0 makes the runner root (C3)"
  refute_line 'FAIL' "the accepted fixture must be clean — any FAIL here is a fixture defect (C3)"
  expect_line 'PASS.*(runAsUser|uid)' "pod-level root must satisfy the property, not merely escape it (C3)"
}

# 4. C4 — THE CLOUD IMAGE, WRITTEN OUT. uid 1000 against a root-owned 0400 file:
# unreadable, and the mode check still says owner-only because it is. The uid must
# appear in the message — an operator fixes what the line names. RED now: exit 0.
test_a_declared_non_root_uid_is_rejected() {
  new_env 0400 1000 "" ""
  run_verify
  expect_rc 1 "uid 1000 cannot read a root-owned 0400 key (C4)"
  expect_line 'FAIL.*(runAsUser|uid)' "the failure must name the user (C4)"
  expect_line 'FAIL.*1000' "the failure must name the offending uid, as the mode check names the mode (C4)"
}

# 5. C5 — ROOT ON THE WRONG CONTAINER. dind runs as root; the runner does not.
# dind never opens key.pem — the buildx client in the runner does. An
# implementation that scans the pod for any `runAsUser: 0` passes a pool that
# cannot read its own key. RED now: exit 0.
test_root_on_another_container_does_not_count() {
  new_env 0400 "" "" 0
  run_verify
  expect_rc 1 "root on dind does not let the runner read the key (C5)"
  expect_line 'FAIL.*(runAsUser|uid)' "the failure must name the user of the container that mounts the certs (C5)"
}

# 6. C6 — 0440 IS NOT THE ESCAPE HATCH, AND IT IS TWO DEFECTS. The mode rule is
# unchanged: tls refuses a group-readable private key, so `owner-only` still
# fails. And without fsGroup the group is root, so a non-root runner cannot read
# it through the group bit either — the user complaint is independent and must
# fire beside the mode complaint. Half RED now: the mode line is already printed,
# the user line is not.
test_a_group_readable_mode_stays_a_failure() {
  new_env 0440 "" "" ""
  run_verify
  expect_rc 1 "a group-readable private key is refused whatever the user (C6)"
  expect_line 'FAIL.*owner-only' "the existing mode rule must not be weakened to admit 0440 (C6)"
  expect_line 'FAIL.*(runAsUser|uid)' \
    "a group bit without fsGroup grants a non-root runner nothing — the user is still wrong (C6)"
}

# -------- runner --------

run_case() {
  local name="$1"
  case_failures=0
  echo "== $name"
  "test_$name"
  if [ "$case_failures" -eq 0 ]; then
    note "ok"
  fi
}

main() {
  local selected="" name known found
  if [ "$#" -eq 0 ]; then
    selected="$CASES"
  elif [ "$1" = "--list" ]; then
    printf '%s' "$CASES" | sed '/^$/d'
    return 0
  else
    for name in "$@"; do
      found=0
      for known in $CASES; do
        [ "$name" = "$known" ] && found=1
      done
      if [ "$found" -eq 0 ]; then
        echo "test-verify-buildx-key: no such case: $name" >&2
        echo "  known: $(printf '%s' "$CASES" | tr '\n' ' ')" >&2
        exit 2
      fi
      selected="$selected$name
"
    done
  fi

  local total=0
  for name in $selected; do
    run_case "$name"
    total=$((total + 1))
  done

  echo
  echo "cases=$total assertion-failures=$failures"
  [ "$failures" -eq 0 ] || exit 1
}

main "$@"
