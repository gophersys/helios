#!/usr/bin/env bash
# Assert a runner image works in the POD SHAPE that ARC actually uses.
#
# Usage: bash scripts/verify-runner-image.sh <tag>        e.g. 3d05c74
#
# WHY THIS EXISTS
# The image build asserts what it can, and `.ci/smoke.sh` runs the image under
# `docker run`. Neither can see the failure that matters most: a runner that
# cannot reach the Docker socket. There is no dind sidecar in a `docker run`, so
# there is nothing to fail against. Two separate defects reached a published image
# that way — a root-owned /home/runner, and a runner user outside the docker group
# — and both were only found when a real job failed hours later.
#
# This runs the image as a Kubernetes Job with the same shape the scale set uses:
# the dind sidecar, the same DOCKER_GROUP_GID, the same volumes, the same user.
# If this passes, the image can serve jobs.
#
# It is READ-ONLY with respect to the pool. It creates one Job in a scratch
# namespace and removes it. It never touches the AutoscalingRunnerSet.
#
# Run it BEFORE pinning a new tag in
# platform/services/gitops/registry/app-arc-runners-org.yaml.
set -uo pipefail

TAG="${1:-}"
NS="${VERIFY_NS:-arc-runners}"
IMAGE_REPO="ghcr.io/gophersys/base-runner"
JOB="verify-runner-image"
# Must match DOCKER_GROUP_GID in the scale set values and in
# .devcontainer/runner/Dockerfile. All three are the same number on purpose.
DOCKER_GID=123

red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

if [ -z "$TAG" ]; then
  echo "usage: bash scripts/verify-runner-image.sh <tag>" >&2
  exit 2
fi
command -v kubectl >/dev/null 2>&1 || { echo "missing required tool: kubectl" >&2; exit 127; }

IMAGE="${IMAGE_REPO}:${TAG}"
echo "verifying ${IMAGE} in the ARC pod shape (namespace ${NS})"

# Remove a previous run before starting, but do NOT remove this one on exit when
# it fails. An earlier version deleted the Job in an EXIT trap and destroyed the
# only copy of the failure logs. A failing test must leave its evidence in place.
cleanup() { kubectl delete job "$JOB" -n "$NS" --ignore-not-found --wait=false >/dev/null 2>&1 || true; }
cleanup

# The assertions. Each prints its own PASS/FAIL line and the script exits non-zero
# on the first failure, so the log names the defect rather than requiring a
# teardown of the image afterwards.
read -r -d '' CHECKS <<'EOF' || true
set -u
fail=0
ok()   { printf '  PASS  %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }

# The runner image runs as ROOT on purpose: it sits beside a privileged dind
# sidecar, so an unprivileged runner was never a boundary, and running as dev
# produced 3 classes of permission defect in 1 day. The dev images keep the dev
# user, because a developer bind-mounts a repository into those.
[ "$(id -u)" = "0" ] && ok "runs as root" || bad "runs as $(id -un) uid=$(id -u), expected root"

# What matters is whether THIS PROCESS holds gid 123, because that is what the
# kernel checks against the socket. The pod grants it with supplementalGroups, so
# it holds even when the image's /etc/group does not list the user.
if id -G | tr " " "\n" | grep -qx 123; then
  ok "process holds gid 123"
else
  bad "process does NOT hold gid 123 (groups: $(id -G)); /etc/group says: $(getent group 123)"
fi

[ -w /home/runner ] && ok "/home/runner is writable" || bad "/home/runner is not writable"
[ -x /home/runner/run.sh ] && ok "run.sh is executable" || bad "run.sh missing or not executable"
[ -d /home/runner/externals ] && ok "externals present" || bad "externals missing"
[ -w /home/runner/_work ] && ok "_work is writable" || bad "_work is not writable"

# THE CHECK THAT ONLY WORKS HERE. A `docker run` smoke test has no dind sidecar,
# so it cannot tell whether the runner can reach the socket.
if docker info >/dev/null 2>&1; then
  ok "docker socket reachable ($(docker version --format '{{.Server.Version}}' 2>/dev/null))"
else
  bad "docker socket UNREACHABLE: $(docker info 2>&1 | head -1)"
fi

# A real container run, not just an API ping.
if docker run --rm hello-world >/dev/null 2>&1; then
  ok "docker can run a container"
else
  bad "docker cannot run a container"
fi

# hnslint joins the list because gophersys/libs cannot gate without it. It was in
# no image at all until gophersys/hnslint v0.1.0, and nothing here would have said
# so: the harness asserted the tools it happened to know about.
for t in cictl hnslint kubeconform kubectl helm jq yq git go node python3; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t on PATH"; else bad "$t MISSING from PATH"; fi
done

sudo -n true 2>/dev/null && ok "passwordless sudo" || bad "no passwordless sudo"

# THE CHECK THAT MATTERS MOST, and the one this harness did not have.
#
# Every other assertion passed on an image whose runner died in under a second
# with "Must not run interactively with sudo". run.sh refuses to start as root
# unless RUNNER_ALLOW_RUNASROOT is set, and nothing here noticed.
#
# This asserts the CONDITION rather than the symptom. An earlier version invoked
# run.sh and matched its output, and that version reported PASS on an image that
# was independently proven to refuse — under `docker run` the same image printed
# the refusal, but inside this Job it did not. The reason is unexplained, so the
# check does not rely on it. The condition below is what run.sh itself tests:
#   if [ $(id -u) = 0 -a -z "$RUNNER_ALLOW_RUNASROOT" ]; then refuse
if [ "$(id -u)" = "0" ] && [ -z "${RUNNER_ALLOW_RUNASROOT:-}" ]; then
  bad "running as root with RUNNER_ALLOW_RUNASROOT unset — run.sh will refuse to start"
else
  ok "run.sh will start (root with RUNNER_ALLOW_RUNASROOT=${RUNNER_ALLOW_RUNASROOT:-n/a})"
fi

[ "$fail" -eq 0 ] && echo "ALL CHECKS PASSED" || echo "CHECKS FAILED"
exit "$fail"
EOF

CHECKS_B64="$(printf '%s' "$CHECKS" | openssl base64 -A)"

kubectl apply -n "$NS" -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: Never
      # The socket's gid belongs to the POD, because the dind sidecar decides it.
      # Granting it here works whatever the image's /etc/group holds, and it is
      # the layer where the decision actually lives.
      securityContext:
        supplementalGroups: [${DOCKER_GID}]
      imagePullSecrets:
        - name: ghcr-pull
      initContainers:
        # The dind sidecar, mirroring the scale set. A native sidecar so it stays
        # up for the whole job.
        - name: dind
          image: docker:dind
          args: ["dockerd", "--host=unix:///var/run/docker.sock", "--group=${DOCKER_GID}"]
          env:
            - name: DOCKER_GROUP_GID
              value: "${DOCKER_GID}"
          securityContext:
            privileged: true
          restartPolicy: Always
          startupProbe:
            exec: { command: ["docker", "info"] }
            failureThreshold: 24
            periodSeconds: 5
          volumeMounts:
            - { name: work, mountPath: /home/runner/_work }
            - { name: dind-sock, mountPath: /var/run }
      containers:
        - name: runner
          image: ${IMAGE}
          # The check script crosses into YAML as base64, so no quoting or
          # indentation rule can corrupt it. Escaping a shell script into a YAML
          # scalar is a well-known way to ship a broken test that still exits 0.
          command: ["bash", "-c"]
          args: ["echo ${CHECKS_B64} | base64 -d | bash"]
          env:
            - { name: DOCKER_HOST, value: "unix:///var/run/docker.sock" }
          volumeMounts:
            - { name: work, mountPath: /home/runner/_work }
            - { name: dind-sock, mountPath: /var/run }
      volumes:
        - { name: work, emptyDir: {} }
        - { name: dind-sock, emptyDir: {} }
YAML

echo "  waiting for the job (image pull can take several minutes on a cold node)"
kubectl wait --for=condition=complete "job/$JOB" -n "$NS" --timeout=900s >/dev/null 2>&1
rc=$?
POD="$(kubectl get pods -n "$NS" -l "job-name=$JOB" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)"
[ -n "$POD" ] && kubectl logs "$POD" -n "$NS" -c runner 2>/dev/null

if [ "$rc" -eq 0 ]; then
  cleanup
  printf '\n  %s %s is fit to serve jobs\n' "$(grn PASS)" "$IMAGE"
  exit 0
fi
printf '\n  %s %s FAILED the pod-shape check — do not pin it\n' "$(red FAIL)" "$IMAGE"
printf '  the Job is left in place on purpose: kubectl logs -n %s job/%s -c runner\n' "$NS" "$JOB"
[ -n "$POD" ] && kubectl describe pod "$POD" -n "$NS" 2>/dev/null | sed -n '/Events/,$p' | head -20
exit 1
