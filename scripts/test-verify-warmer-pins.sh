#!/usr/bin/env bash
# Spec for scripts/verify-warmer-pins.sh — the warmer must never pin images onto
# a control-plane node.
#
# THE GAP THESE CASES PIN (live in the manifests today)
# 42-image-warmer-daemonset.yaml is a DaemonSet whose initContainers run `true`
# on every node it lands on. That is how it warms: the kubelet pulls the image
# and a container holds it, so image GC can never reclaim it. ~3.86GB per node,
# unreclaimable by design. Its affinity excludes exactly one node:
#
#     - key: kubernetes.io/hostname
#       operator: NotIn
#       values: ["k3s-w-4"]
#
# and its comment claims the rest is covered by taints:
#
#     # No tolerations — if control-plane nodes are tainted away from runners
#     # they are tainted away from the warmer too.
#
# The premise is false. ZERO taints exist cluster-wide (verified live,
# 2026-08-18). So the warmer schedules on k3s-cp-0/1/2 — three 38GB VMs that run
# etcd — and holds 3.86GB there forever. k3s-cp-0 reached 93% used / 2.7GB free
# at 22:31Z while serving etcd, and the kubelet's image GC could not free enough,
# because the warmer's own containers were the holders.
#
# Nothing in this repository fails when that is true. verify-warmer-pins.sh
# asserts two properties — one digest everywhere, no privilege — and both are
# green on the manifests as they stand.
#
# THE CONTRACT THESE CASES PIN
#   CP-EXCLUDED             every node that declares `kubernetes.role: server`
#                           in clusters/instances/homelab/nodes/*/identity.yaml
#                           appears in the NotIn list of all 4 warmer/pool files,
#                           and a miss FAILS naming the file AND the node.
#   DERIVED-NOT-HARDCODED   the server set is DERIVED from the identity files. A
#                           4th server node added tomorrow fails the same way. A
#                           hardcoded ["k3s-cp-0","k3s-cp-1","k3s-cp-2"] inside
#                           the verifier passes CP-EXCLUDED and dies here.
#   ZERO-SERVERS            zero derived servers is a FAILURE, not a vacuous
#                           pass. This is the same floor property 1 already
#                           holds ("zero refs is not a pass"): a renamed
#                           directory, a schema drift or a typo in the key must
#                           not turn the check into a no-op that reads green.
#   REFRESH-COVERED         43-image-warmer-refresh.yaml is covered too. Its
#                           CronJob pod is short-lived, but it carries its own
#                           affinity and a pod that lands on a control plane
#                           pulls the cloud image there — which is the pin the
#                           DaemonSet exclusion just removed.
#   POOLS-COVERED           the runner pools are covered. Their NotIn lives
#                           inside a Helm `values: |` STRING block, so a
#                           structural yq read of the Application finds nothing
#                           there; the verifier must read that block as text.
#                           app-arc-runners-build.yaml is NOT in this set: it
#                           uses an `In` list already pinned to k3s-w-0/1/2, and
#                           demanding a NotIn of it would be wrong.
#
# HOW THESE CASES REACH THE REAL SCRIPT
# verify-warmer-pins.sh derives ROOT from its own location
# (ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)) and reads only files
# under it. There is no -f/env override, so we point it at a fixture tree WITHOUT
# editing it: a SYMLINK at <tmp>/scripts/verify-warmer-pins.sh -> the real script
# makes BASH_SOURCE the symlink path, so ROOT resolves to <tmp>. The fixture holds
# the 5 manifests the subject reads plus the node identity files the new property
# derives from, all trimmed copies of the real shapes. The symlink runs the REAL
# script live, so the implementer's change is exercised, not a stale copy.
# Everything lives under mktemp; nothing is written into the repo tree, and no
# cluster is contacted.
#
# THE FIXTURE IS SOUND ONLY IF THE CONTROL IS SILENT. The control case runs
# FIRST, on a fully-correct tree, and refutes EVERY FAIL line. It also proves the
# new property is not a blanket fail. Beyond that, each red case refutes the
# failure texts of properties 1 and 2 by name: a case that goes red because a
# fixture digest drifted, or because a file is missing, says so instead of
# masquerading as evidence for the property under test.
#
# Run: bash scripts/test-verify-warmer-pins.sh            # every case
#      bash scripts/test-verify-warmer-pins.sh <name>...  # one case, by name
#      bash scripts/test-verify-warmer-pins.sh --list     # the case names
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/verify-warmer-pins.sh"

# The one digest the fixture pins everywhere, so property 1 is satisfied and a
# case measures the scheduling property alone.
DIGEST="ghcr.io/gophersys/cloud@sha256:9a150cbff74b67f67f69cca1b25a463103cbe8885ba0b7a0f777de42e7f7f7f1"

# The node sets. SERVERS is what the new property must derive; the exclusion
# lists below are what a manifest declares.
CP_NODES="k3s-cp-0 k3s-cp-1 k3s-cp-2"
WORKER_NODES="k3s-w-0 k3s-w-1 k3s-w-2 k3s-w-3 k3s-w-4"
LAB_ONLY="k3s-w-4"                                       # every NotIn today
LAB_AND_CPS="k3s-w-4 k3s-cp-0 k3s-cp-1 k3s-cp-2"         # what the fix writes

CASES="
a_fully_excluded_tree_is_accepted
the_control_planes_must_be_excluded_from_the_warmer
a_fourth_server_node_is_caught_without_a_manifest_change
zero_declared_servers_is_not_a_pass
the_refresh_cronjob_is_covered
the_runner_pools_are_covered
"

# A missing tool is a failure, never a skip (docs/testing-standard.md rule 3).
# The subject reads the node identity files with yq and exits 127 without it;
# every case would then read 127 and say nothing about the rule.
if ! command -v yq >/dev/null 2>&1; then
  echo "test-verify-warmer-pins: missing required tool: yq" >&2
  exit 127
fi
if [ ! -f "$SUT" ]; then
  echo "test-verify-warmer-pins: subject not found: $SUT" >&2
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

# The whole subject output, indented. No pipeline: under `set -o pipefail` a
# `grep` that matches nothing would abort the suite and print nothing at all,
# which is how a diagnostic turns into a silent stop.
dump() {
  local line
  while IFS= read -r line; do
    printf '      | %s\n' "$line"
  done <<EOF
$out
EOF
}

# "a b c" -> ["a", "b", "c"] — the flow style all 4 manifests use today.
flow_list() {
  local out_list="" host
  for host in $1; do
    if [ -n "$out_list" ]; then out_list="$out_list, "; fi
    out_list="$out_list\"$host\""
  done
  printf '[%s]' "$out_list"
}

# One cluster member declaration, in the shape of the real ones: the k3s role
# under `kubernetes.role`, and a `cluster_role` + `labels.role` beside it whose
# values are the node-role taxonomy (apps|devops|...), never "server".
emit_identity() {
  local dir="$1" name="$2" k3s_role="$3" cluster_role
  case "$name" in
    k3s-cp-*|k3s-w-0) cluster_role=devops ;;
    *) cluster_role=apps ;;
  esac
  mkdir -p "$dir/$name"
  cat >"$dir/$name/identity.yaml" <<EOYAML
# identity.yaml — $name (fixture cluster member)
name: $name
os: linux-ubuntu
purpose: "fixture homelab node"
status: active
owner: mateo.segura413@gmail.com

roles:
  - common
  - networking-tailscale
  - cluster-node-labels

kubernetes:
  role: $k3s_role                      # k3s role
  cluster_role: $cluster_role
  labels:
    role: $cluster_role
  taints: []
  extra_flags: []
EOYAML
}

# The warmer DaemonSet: the file that holds 3.86GB on whatever it lands on.
emit_daemonset() {
  local path="$1" values="$2"
  cat >"$path" <<EOYAML
# ci-image-warmer (fixture) — initContainers run \`true\` so the kubelet pulls
# the image and a container holds it. Scheduling is the whole payload.
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ci-image-warmer
  namespace: arc-runners
spec:
  selector:
    matchLabels:
      app: ci-image-warmer
  template:
    metadata:
      labels:
        app: ci-image-warmer
    spec:
      serviceAccountName: ci-image-warmer
      automountServiceAccountToken: false
      imagePullSecrets:
        - name: ghcr-pull
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: NotIn
                    values: $values
      initContainers:
        - name: warm-cloud-pinned
          image: $DIGEST
          imagePullPolicy: IfNotPresent
          command: ["true"]
          securityContext: &warmctx
            runAsNonRoot: true
            runAsUser: 1000
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
            seccompProfile:
              type: RuntimeDefault
        - name: warm-cloud-latest
          image: ghcr.io/gophersys/cloud:latest
          imagePullPolicy: Always
          command: ["true"]
          securityContext: *warmctx
        - name: warm-dind
          image: docker.io/library/docker:dind
          imagePullPolicy: IfNotPresent
          command: ["true"]
          securityContext: *warmctx
      containers:
        - name: hold
          image: registry.k8s.io/pause:3.10
          resources:
            requests:
              cpu: 5m
              memory: 8Mi
            limits:
              memory: 32Mi
          securityContext:
            runAsNonRoot: true
            runAsUser: 65535
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
            seccompProfile:
              type: RuntimeDefault
EOYAML
}

# The daily refresh CronJob. Its affinity is nested one level deeper, under
# jobTemplate.spec.template.spec — a reader that hardcodes the DaemonSet path
# finds nothing here.
emit_refresh() {
  local path="$1" values="$2"
  cat >"$path" <<EOYAML
# ci-image-warmer-refresh (fixture) — the daily rollout restart.
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ci-image-warmer-refresh
  namespace: arc-runners
spec:
  schedule: "30 3 * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      activeDeadlineSeconds: 300
      backoffLimit: 2
      template:
        spec:
          serviceAccountName: ci-image-warmer-refresher
          restartPolicy: Never
          imagePullSecrets:
            - name: ghcr-pull
          affinity:
            nodeAffinity:
              requiredDuringSchedulingIgnoredDuringExecution:
                nodeSelectorTerms:
                  - matchExpressions:
                      - key: kubernetes.io/hostname
                        operator: NotIn
                        values: $values
          containers:
            - name: restart
              image: $DIGEST
              imagePullPolicy: IfNotPresent
              command:
                - kubectl
                - -n
                - arc-runners
                - rollout
                - restart
                - daemonset/ci-image-warmer
              securityContext:
                runAsNonRoot: true
                runAsUser: 1000
                allowPrivilegeEscalation: false
                readOnlyRootFilesystem: true
                capabilities:
                  drop: ["ALL"]
                seccompProfile:
                  type: RuntimeDefault
EOYAML
}

# A runner pool Application. The affinity sits inside `helm.values`, which is a
# STRING — yq reads it as one scalar, so the exclusion is text until someone
# parses the block.
emit_pool_notin() {
  local path="$1" app="$2" release="$3" values="$4"
  cat >"$path" <<EOYAML
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: $app
  namespace: argocd
spec:
  project: ci
  source:
    repoURL: ghcr.io/actions/actions-runner-controller-charts
    chart: gha-runner-scale-set
    targetRevision: 0.14.2
    helm:
      releaseName: $release
      values: |
        githubConfigUrl: https://github.com/gophersys
        githubConfigSecret: arc-github-app
        runnerScaleSetName: $release
        minRunners: 1
        maxRunners: 4
        template:
          spec:
            securityContext:
              supplementalGroups: [123]

            # k3s-w-4 owns the USB-passthrough embedded lab.
            affinity:
              nodeAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                  nodeSelectorTerms:
                    - matchExpressions:
                        - key: kubernetes.io/hostname
                          operator: NotIn
                          values: $values
              podAntiAffinity:
                preferredDuringSchedulingIgnoredDuringExecution:
                  - weight: 100
                    podAffinityTerm:
                      topologyKey: kubernetes.io/hostname
                      labelSelector:
                        matchLabels:
                          actions.github.com/scale-set-name: $release

            imagePullSecrets:
              - name: ghcr-pull

            initContainers:
              - name: init-dind-externals
                image: $DIGEST
                command: ["cp", "-r", "/home/runner/externals/.", "/home/runner/tmpDir/"]
            containers:
              - name: runner
                image: $DIGEST
                command: ["/home/runner/run.sh"]
  destination:
    server: https://kubernetes.default.svc
    namespace: arc-runners
EOYAML
}

# arc-build. An `In` list already pinned to the three big workers, so no control
# plane can be selected. It is a pool file property 1 reads, and it must NOT be
# held to the NotIn rule — the control case is what proves that.
emit_pool_in() {
  local path="$1"
  cat >"$path" <<EOYAML
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: arc-runners-build
  namespace: argocd
spec:
  project: ci
  source:
    repoURL: ghcr.io/actions/actions-runner-controller-charts
    chart: gha-runner-scale-set
    targetRevision: 0.14.2
    helm:
      releaseName: arc-build
      values: |
        githubConfigUrl: https://github.com/gophersys
        githubConfigSecret: arc-github-app
        runnerScaleSetName: arc-build
        minRunners: 0
        maxRunners: 2
        template:
          spec:
            # PINNED to the three pve-00 workers — an \`In\` list, not a NotIn.
            affinity:
              nodeAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                  nodeSelectorTerms:
                    - matchExpressions:
                        - key: kubernetes.io/hostname
                          operator: In
                          values: ["k3s-w-0", "k3s-w-1", "k3s-w-2"]
            imagePullSecrets:
              - name: ghcr-pull
            containers:
              - name: runner
                image: $DIGEST
                command: ["/home/runner/run.sh"]
  destination:
    server: https://kubernetes.default.svc
    namespace: arc-runners
EOYAML
}

# A fresh fixture tree: the symlink that relocates ROOT, the node identity files
# the property derives from, and the 5 manifests the subject reads. Every knob is
# a space-separated hostname list.
new_env() {
  local servers="$1" agents="$2" ds_values="$3" refresh_values="$4"
  local org_values="$5" review_values="$6"
  local node registry arc nodes_dir
  ENV_DIR="$(mktemp -d)"; TMPDIRS+=("$ENV_DIR")
  registry="$ENV_DIR/platform/services/gitops/registry"
  arc="$ENV_DIR/platform/services/ci/arc-runners"
  nodes_dir="$ENV_DIR/clusters/instances/homelab/nodes"
  mkdir -p "$ENV_DIR/scripts" "$registry" "$arc" "$nodes_dir"
  ln -s "$SUT" "$ENV_DIR/scripts/verify-warmer-pins.sh"

  for node in $servers; do
    emit_identity "$nodes_dir" "$node" server
  done
  for node in $agents; do
    emit_identity "$nodes_dir" "$node" agent
  done

  emit_daemonset "$arc/42-image-warmer-daemonset.yaml" "$(flow_list "$ds_values")"
  emit_refresh "$arc/43-image-warmer-refresh.yaml" "$(flow_list "$refresh_values")"
  emit_pool_notin "$registry/app-arc-runners-org.yaml" arc-runners-org arc-org \
    "$(flow_list "$org_values")"
  emit_pool_notin "$registry/app-arc-runners-review.yaml" arc-runners-review arc-review \
    "$(flow_list "$review_values")"
  emit_pool_in "$registry/app-arc-runners-build.yaml"
}

# Drive the REAL script through the symlink. `set +e` wraps the call so a
# non-zero exit does not abort the run, and rc=$? sits on the line right after
# the substitution so nothing runs between them. A pipeline would report its last
# stage instead — a misreading that has produced false findings here.
run_verify() {
  set +e
  out="$(bash "$ENV_DIR/scripts/verify-warmer-pins.sh" 2>&1)"
  rc=$?
  set -e
}

expect_rc() {
  if [ "$rc" -eq "$1" ]; then
    return 0
  fi
  bad "exit $rc, want $1 — $2"
  dump
}

expect_line() {
  if printf '%s\n' "$out" | grep -qE "$1"; then
    return 0
  fi
  bad "no line matched /$1/ — $2"
  dump
}

refute_line() {
  if printf '%s\n' "$out" | grep -qE "$1"; then
    bad "a line matched /$1/ but must not — $2"
    dump
  fi
}

# The evidence guard. A red that comes from a broken fixture proves nothing, so
# every red case refutes the failure texts of the two EXISTING properties by
# name. If the digest drifts, a file goes missing, or a hostPath slips into a
# fixture, the case says THAT instead of pretending to be evidence for the
# scheduling rule.
refute_fixture_defects() {
  refute_line 'FAIL.*does not exist' "a missing fixture file, not the property under test"
  refute_line 'FAIL.*pins no' "a fixture manifest lost its digest, not the property under test"
  refute_line 'FAIL.*more than one distinct' "a fixture manifest holds two digests, not the property under test"
  refute_line 'FAIL.*disagree on the cloud digest' "the fixture digests drifted, not the property under test"
  refute_line 'FAIL.*grants node access' "a hostPath slipped into a fixture, not the property under test"
}

# -------- the cases --------

# 0. THE CONTROL, and it runs FIRST. A tree where every declared server is in
# every NotIn list. It must exit 0 both before and after the property exists, so
# it is not evidence of the feature — it is what makes the 5 reds below readable.
# It also refutes two wrong implementations: a blanket fail, and one that holds
# app-arc-runners-build.yaml (an `In` list, already worker-pinned) to a NotIn it
# does not have.
test_a_fully_excluded_tree_is_accepted() {
  new_env "$CP_NODES" "$WORKER_NODES" \
    "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_AND_CPS"
  run_verify
  expect_rc 0 "a tree that excludes every server node from every file is correct"
  refute_line 'FAIL' "the accepted fixture must be clean — any FAIL here is a fixture defect"
}

# 1. CP-EXCLUDED — THE DEFECT AS IT STANDS TODAY, byte for byte: three nodes
# declare `kubernetes.role: server`, and all 4 files exclude only k3s-w-4. This
# is the tree that put 3.86GB of unreclaimable images on an etcd node and took
# k3s-cp-0 to 93%. The failure must name the file AND the node: an operator fixes
# what the line names, and there are 4 files to fix.
test_the_control_planes_must_be_excluded_from_the_warmer() {
  new_env "$CP_NODES" "$WORKER_NODES" \
    "$LAB_ONLY" "$LAB_ONLY" "$LAB_ONLY" "$LAB_ONLY"
  run_verify
  expect_rc 1 "the warmer pins 3.86GB on every node it lands on; a server node is not eligible"
  refute_fixture_defects
  expect_line 'FAIL.*k3s-cp-0' "the failure must name the node an operator has to exclude"
  expect_line 'FAIL.*k3s-cp-1' "every declared server counts, not just the first"
  expect_line 'FAIL.*k3s-cp-2' "every declared server counts, not just the first"
  expect_line 'FAIL.*42-image-warmer-daemonset\.yaml' "the DaemonSet is the file that holds the images"
  expect_line 'FAIL.*43-image-warmer-refresh\.yaml' "the refresh pod pulls the same image on the node it lands on"
  expect_line 'FAIL.*app-arc-runners-org\.yaml' "a runner pod on an etcd node is the same disk"
  expect_line 'FAIL.*app-arc-runners-review\.yaml' "the review pool has the same affinity and the same gap"
}

# 2. DERIVED-NOT-HARDCODED — the kill shot for a verifier that hardcodes
# ["k3s-cp-0","k3s-cp-1","k3s-cp-2"]. A 4th server node is declared and NO
# manifest changes. A hardcoded list is green here while the new control plane
# takes the pin; a derived one names k3s-cp-3. The failure must name the node
# that was added, not the three that were already handled.
test_a_fourth_server_node_is_caught_without_a_manifest_change() {
  new_env "$CP_NODES k3s-cp-3" "$WORKER_NODES" \
    "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_AND_CPS"
  run_verify
  expect_rc 1 "the server set is derived from the identity files, so a new one is caught the day it lands"
  refute_fixture_defects
  expect_line 'FAIL.*k3s-cp-3' "the failure must name the newly declared server, which no manifest excludes"
}

# 3. ZERO-SERVERS-IS-NOT-A-PASS — the floor. Every node declares `role: agent`,
# so the derived set is empty and a loop over it asserts nothing. That is the
# exact shape of a check that reads green while measuring nothing, and property 1
# already refuses it ("zero refs is not a pass"). A renamed nodes/ directory, a
# schema change or a typo in the key must fail loudly here.
test_zero_declared_servers_is_not_a_pass() {
  new_env "" "$CP_NODES $WORKER_NODES" \
    "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_AND_CPS"
  run_verify
  expect_rc 1 "a derived set of zero servers means the check measured nothing"
  refute_fixture_defects
  expect_line 'FAIL.*[Ss]erver' "the failure must say the server set is empty, so a reader knows the check went blind"
}

# 4. REFRESH-COVERED — only 43-image-warmer-refresh.yaml is short. Its affinity
# sits one level deeper (jobTemplate.spec.template.spec), so a verifier written
# against the DaemonSet path alone passes this tree while the daily CronJob pod
# lands on an etcd node and pulls 2.06GB there.
test_the_refresh_cronjob_is_covered() {
  new_env "$CP_NODES" "$WORKER_NODES" \
    "$LAB_AND_CPS" "$LAB_ONLY" "$LAB_AND_CPS" "$LAB_AND_CPS"
  run_verify
  expect_rc 1 "the refresh pod pulls the cloud image onto whatever node it lands on"
  refute_fixture_defects
  expect_line 'FAIL.*43-image-warmer-refresh\.yaml' "the failure must name the file that is short"
  expect_line 'FAIL.*k3s-cp-0' "and the node it fails to exclude"
}

# 5. POOLS-COVERED — only app-arc-runners-org.yaml is short, and its NotIn lives
# inside the Helm `values: |` STRING block. A structural read of the Application
# sees one scalar and finds no affinity at all, so an implementation that trusts
# yq here passes a tree that puts a 4-runner pool on the etcd nodes.
test_the_runner_pools_are_covered() {
  new_env "$CP_NODES" "$WORKER_NODES" \
    "$LAB_AND_CPS" "$LAB_AND_CPS" "$LAB_ONLY" "$LAB_AND_CPS"
  run_verify
  expect_rc 1 "a runner pool that can schedule on an etcd node is the same disk, filled faster"
  refute_fixture_defects
  expect_line 'FAIL.*app-arc-runners-org\.yaml' "the exclusion inside a helm values string must be read, not skipped"
  expect_line 'FAIL.*k3s-cp-0' "and the node it fails to exclude"
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
        echo "test-verify-warmer-pins: no such case: $name" >&2
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
