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

cleanup() { kubectl delete job "$JOB" -n "$NS" --ignore-not-found --wait=false >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

# The assertions. Each prints its own PASS/FAIL line and the script exits non-zero
# on the first failure, so the log names the defect rather than requiring a
# teardown of the image afterwards.
read -r -d '' CHECKS <<'EOF' || true
set -u
fail=0
ok()   { printf '  PASS  %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }

[ "$(id -un)" = "dev" ] && ok "runs as dev" || bad "runs as $(id -un), expected dev"

# /etc/group is the image's own record. `id -G` reports the process's groups,
# which is a different thing and has produced a false pass and a false fail here.
if getent group 123 | cut -d: -f4 | tr ',' '\n' | grep -qx dev; then
  ok "dev is in gid 123 (/etc/group)"
else
  bad "dev is NOT in gid 123: $(getent group 123)"
fi

[ -O /home/runner ] && ok "/home/runner owned by dev" || bad "/home/runner not owned by dev"
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

for t in cictl kubeconform kubectl helm jq yq git go node python3; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t on PATH"; else bad "$t MISSING from PATH"; fi
done

sudo -n true 2>/dev/null && ok "passwordless sudo" || bad "no passwordless sudo"

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
  printf '\n  %s %s is fit to serve jobs\n' "$(grn PASS)" "$IMAGE"
  exit 0
fi
printf '\n  %s %s FAILED the pod-shape check — do not pin it\n' "$(red FAIL)" "$IMAGE"
[ -n "$POD" ] && kubectl describe pod "$POD" -n "$NS" 2>/dev/null | sed -n '/Events/,$p' | head -20
exit 1
