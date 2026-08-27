#!/usr/bin/env bash
#
# .ci/buildx-node.sh — make the buildx builder that every image build of this
# repository uses.
#
#   bash .ci/buildx-node.sh
#
# It replaces docker/setup-buildx-action in the build jobs. The action makes a
# `docker-container` builder and nothing else; this file makes a builder that
# can hold the Mac mini as a second node, which is the one thing the action
# cannot do.
#
# ============================================================================
# ONE DRIVER. THE BUILDER IS `remote`, ALWAYS, AND HERE IS THE FAILURE THAT
# SETTLED IT
# ============================================================================
#
# This file used to make a `docker-container` builder and then append the mini
# with `--driver remote`. buildx refuses that: a builder has ONE driver, and the
# append is rejected with
#
#     ERROR: existing instance for "gophersys" but has mismatched driver
#     "docker-container"
#
# Rehearsal run 32111891941 died there, and a 2-command control on a laptop
# reproduces it exactly (create docker-container rc=0, append remote rc=1). It
# was invisible until the day arm64 was sanctioned, because the append is inside
# the switch that only fires when it is.
#
# So the local node is a `remote` node too: a standalone buildkitd container
# this script starts itself. That is not a workaround, it is the shape buildx
# supports — proven locally with 2 buildkitd containers appended to one remote
# builder: create rc=0, append rc=0, `--bootstrap` rc=0, both nodes running, and
# `docker buildx build --platform <p> --load` rc=0 with the loaded image
# reporting the right architecture. `--load` is the GATE build's shape, so that
# last one is the check that mattered.
#
# What a `remote` local node keeps from the `docker-container` one:
#
#   - a registry cache. The default `docker` driver can neither read nor write
#     one, and that cache is what makes a self-hosted build warm across
#     ephemeral pods. buildkitd does the registry I/O either way.
#   - `load: true`. buildx exports the result back through the client into the
#     pod's docker image store, which is what .ci/smoke.sh then runs.
#   - the pod's network namespace, and the same worker flag. See below.
#   - the ghcr-mirrored BUILDKIT_REF. The container this script runs IS that
#     image, so .ci/mirror-buildkit.sh stays in the boot order ahead of it.
#
# ============================================================================
# THE LOCAL ENDPOINT IS PLAINTEXT TCP ON LOOPBACK, AND THAT IS A DECISION
# ============================================================================
#
# The local node listens on tcp://127.0.0.1 with no TLS, and buildkitd says so
# in its own log ("TLS is not enabled ... mutual TLS authentication is highly
# recommended"). The threat model, stated rather than assumed:
#
#   - `--network host` here means the POD's network namespace. The runner
#     container, the dind daemon and this buildkitd share it, and nothing
#     outside the pod has a route to that loopback address.
#   - so the set of peers that can reach the BUILD API is exactly the set that
#     can already run commands in the pod — which is the build itself. A peer
#     with code execution there holds the docker socket too, and the
#     docker-container driver this replaces was reachable through that socket.
#     The boundary did not move.
#   - the MINI is the opposite case and keeps its mTLS: that endpoint is on the
#     tailnet, off-pod, and a client with no certificate is refused.
#
# ============================================================================
# THE MINI
# ============================================================================
#
# gophersys/infrastructure docs/ci-substrate.md, "The native arm64 builder":
# the Mac mini runs a standalone buildkitd that listens on tcp://10.168.0.92:1234
# and speaks the BUILD API only, over mTLS. arc-build mounts the 3 client PEMs
# at /etc/buildkit-certs/. A native arm64 build there measured 3.44x faster than
# the same build emulated on an amd64 node.
#
# It is wired AND IT RUNS. SANCTIONED_PLATFORMS in _ctl/lib.sh names
# `linux/arm64`, so the switch below appends the node on every build — and it
# took no edit here, because that switch reads the library rather than repeating
# its value. The first dual-arch build is therefore the mini's first real work:
# an unreachable mini, an expired client PEM or a stopped buildkitd all surface
# at `--bootstrap` below, in a step that names them.
#
# THIS FILE NAMES linux/arm64 ON PURPOSE, and it is IN `BUILD_PATH_FILES` in
# _ctl/tests/platform-policy.test.sh. An earlier version of this paragraph said
# the opposite — that the file had to stay OUT of that list because the test
# forbade the token — and both halves are false in this tree. That rule is
# MEMBERSHIP of the sanctioned set, not a deny-list: a build-path file may name
# a platform the library sanctions, and naming one it does not is the failure.
# So this file may name both sanctioned platforms, and it must not name a third
# — not even to say it is forbidden, which is how this very paragraph went red
# once. Naming the platform is this file's job: it is the one place whose work
# is to react to the library's value.
#
# ============================================================================
# THE NETWORK THE BUILDER LIVES ON, AND WHY IT IS THE POD'S OWN
# ============================================================================
#
# The builder container and every RUN step share the runner pod's network
# namespace: `network=host` on the driver, and `--oci-worker-net=host` on the
# daemon. "host" here is the POD — the dind daemon runs inside the pod's
# namespace, so nothing of the node is exposed.
#
# The default is a bridge inside dind at MTU 1500, nested inside a flannel
# VXLAN pod interface at MTU 1450, and that 50-byte lie is a blackhole: the
# inner container advertises an MSS the overlay cannot carry, the peer's
# full-size packets are dropped silently, and whether a fetch survives depends
# on the PEER's path-MTU behaviour. Proven on k3s-w-0 on 2026-08-17 with the
# same URL at both MTUs: get.helm.sh stalled to a reset from a bridge container
# at 1500 in 3 of 3 build attempts and timed out in a probe container, and the
# identical fetch succeeded at a clamped MTU and from the pod's own namespace.
# ghcr.io, docker.io and dl.k8s.io tolerated the mismatch, which is exactly why
# it survived review: a blackhole that most peers cope with reads as one flaky
# host.
#
# The pod namespace needs no clamp — flannel sizes it (1450) and the probe
# proved it clean end to end. Sharing it is therefore the fix with no number to
# maintain: no bridge exists on the build path to disagree with the overlay.
#
# ============================================================================
# WHY THE BUILDKIT IMAGE COMES FROM OUR REGISTRY
# ============================================================================
#
# The builder boots by pulling a BuildKit image, and with no image named it
# pulls docker.io/moby/buildkit:buildx-stable-1 — an unpinned tag from a
# registry nothing else here uses, fetched before one line of ours runs. That
# boot died on a 502 from auth.docker.io on 2026-08-17, attempt 2 of the first
# arc-build wave. BUILDKIT_REF in _ctl/lib.sh names the same image mirrored to
# ghcr.io, pinned by index digest; .ci/mirror-buildkit.sh keeps the mirror
# populated and is the ONLY file that names the docker.io source. This step
# therefore runs after the registry login in the workflow — the mirror package
# is private, like every other package of this repository.
#
# ============================================================================
# WHY THE BUILDER IS MADE IN THE JOB, AND WHY IT IS REMADE FROM SCRATCH
# ============================================================================
#
# `docker buildx create` writes to $HOME/.docker/buildx in the runner container.
# Every job gets a new pod, so a builder made at pod start dies with that pod,
# and an init container cannot write into the runner container's file system.
#
# Re-running this step must not fail on the state the previous run left, and
# `docker buildx create --name <existing>` FAILS even when the driver matches
# (measured: rc=1). Reusing whatever is there is the other trap — a builder left
# by a run that died between the create and the append carries the wrong node
# set, and the next build would silently target one architecture. So the shape
# is REMOVE, then create: `buildx rm` drops local metadata and a `docker rm -f`
# drops our own container. Neither touches the mini, which keeps its own
# buildkitd and its cache across every job.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/smoke.sh sets it: the git fallback in
# _ctl/lib.sh reads the wrong root when this repository is a submodule worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# SANCTIONED_PLATFORMS lives in _ctl/lib.sh, 1 time only; the logging and the
# tool gate live in _ctl/standard.sh, which that file sources. The switch below
# reads that variable, so widening the platform set is still 1 edit in 1 file.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

# The name require_buildx_and_platforms prints in its "no active builder"
# message, so the guard and this file agree on what to look for.
BUILDER_NAME="gophersys"

# The LOCAL node: a buildkitd container this script starts, in the pod's own
# network namespace, reached over loopback.
#
# The port is deliberately nothing like the mini's 1234. A reader skimming 2
# endpoints must not have to decide which loopback 1234 is which, and 18234 is
# below the Linux ephemeral range (32768+) so the kernel will never hand it to
# something else first.
LOCAL_NODE_NAME="pod-local"
LOCAL_CONTAINER_NAME="gophersys-buildkitd"
LOCAL_PORT="18234"
LOCAL_ENDPOINT="tcp://127.0.0.1:${LOCAL_PORT}"

# The platform of the pool. arc-build runs on the three pve-00 workers and every
# node of that cluster is amd64 (gophersys/infrastructure docs/ci-runners.md).
# The node is PINNED to it: buildkitd advertises every platform it can emulate,
# and an unpinned local node would volunteer for the arm64 half and build it
# under QEMU on an amd64 worker — the mislabelled-variant defect, rebuilt.
LOCAL_PLATFORM="linux/amd64"

# The mini, per docs/ci-substrate.md. The endpoint is the BUILD API and not the
# Docker Engine API: a client with no certificate is refused, and the escape to
# a privileged container over this port is dead.
MINI_NODE_NAME="eden-mini"
MINI_ENDPOINT="tcp://10.168.0.92:1234"
MINI_CERT_DIR="/etc/buildkit-certs"
MINI_PLATFORM="linux/arm64"

require_buildx
require_cmd docker

# -------- 1. the local buildkitd --------
# Removed first, for the reason the header gives: a container left by an earlier
# run may hold a different image or a different flag set, and `docker run` would
# fail on the name rather than replace it.
docker rm -f "$LOCAL_CONTAINER_NAME" >/dev/null 2>&1 || true

log_info "starting the local buildkitd '${LOCAL_CONTAINER_NAME}' on ${LOCAL_ENDPOINT} (${BUILDKIT_REF})"
# --network host is the POD namespace, not the node's: the dind daemon runs
# inside the pod, so this shares the netns the runner already has. That is what
# keeps the build path free of a nested bridge, and it is why the endpoint can
# be loopback. --oci-worker-net=host is the same flag the docker-container
# driver received through --buildkitd-flags, passed directly now because this is
# the daemon's own argv.
docker run --detach \
  --name "$LOCAL_CONTAINER_NAME" \
  --privileged \
  --network host \
  --restart no \
  "$BUILDKIT_REF" \
  --addr "$LOCAL_ENDPOINT" \
  --oci-worker-net=host >/dev/null

# It has to ANSWER before a builder is pointed at it. Without this the create
# below succeeds against a socket nobody is listening on yet, and the failure
# lands in `--bootstrap` as a timeout that names nothing.
local_ready=""
for _ in $(seq 1 60); do
  if docker exec "$LOCAL_CONTAINER_NAME" \
      buildctl --addr "$LOCAL_ENDPOINT" debug workers >/dev/null 2>&1; then
    local_ready="yes"
    break
  fi
  sleep 1
done
if [[ -z "$local_ready" ]]; then
  log_error "the local buildkitd did not answer on ${LOCAL_ENDPOINT} within 60s"
  log_error "its own log follows:"
  docker logs "$LOCAL_CONTAINER_NAME" 2>&1 | tail -30 >&2
  exit 1
fi

# -------- 2. the builder, one driver, made from scratch --------
docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1 || true

log_info "creating buildx builder '${BUILDER_NAME}' (remote, node ${LOCAL_NODE_NAME}, ${LOCAL_PLATFORM})"
docker buildx create \
  --name "$BUILDER_NAME" \
  --node "$LOCAL_NODE_NAME" \
  --driver remote \
  --platform "$LOCAL_PLATFORM" \
  --use \
  "$LOCAL_ENDPOINT" >/dev/null

# -------- 3. the mini, when its platform is sanctioned --------
# `,list,` on both sides so `linux/amd64` cannot match inside another entry.
if [[ ",${SANCTIONED_PLATFORMS}," == *",${MINI_PLATFORM},"* ]]; then
  log_info "${MINI_PLATFORM} is sanctioned — appending the native node ${MINI_NODE_NAME}"

  # The credential is a mount, not a download. A missing PEM means the pod spec
  # does not carry the volume, and that is a manifest change in
  # gophersys/infrastructure — never something a job installs for itself.
  missing_pems=""
  for pem in ca.pem cert.pem key.pem; do
    if [[ ! -r "${MINI_CERT_DIR}/${pem}" ]]; then
      missing_pems="${missing_pems:+${missing_pems} }${MINI_CERT_DIR}/${pem}"
    fi
  done
  if [[ -n "$missing_pems" ]]; then
    log_error "the mTLS client credential for ${MINI_NODE_NAME} is not readable: ${missing_pems}"
    log_error "the pool mounts it from app-arc-runners-build.yaml at mode 0400, owned by uid 0,"
    log_error "so the runner container must also declare securityContext.runAsUser: 0"
    exit 1
  fi

  # The SAME driver as the node above. That is the whole fix: buildx allows a
  # second node only when its driver matches the builder's.
  docker buildx create \
    --name "$BUILDER_NAME" \
    --append \
    --node "$MINI_NODE_NAME" \
    --driver remote \
    --driver-opt "cacert=${MINI_CERT_DIR}/ca.pem,cert=${MINI_CERT_DIR}/cert.pem,key=${MINI_CERT_DIR}/key.pem" \
    --platform "$MINI_PLATFORM" \
    "$MINI_ENDPOINT" >/dev/null
fi

# --bootstrap dials every node and reports what each one can build. Without it
# an unreachable mini surfaces halfway through the first arm64 build, in the log
# of a step that is about something else.
if ! docker buildx inspect --bootstrap "$BUILDER_NAME"; then
  log_error "the buildx builder '${BUILDER_NAME}' did not come up"
  log_error "node ${LOCAL_NODE_NAME} is the container ${LOCAL_CONTAINER_NAME} on ${LOCAL_ENDPOINT}"
  if [[ ",${SANCTIONED_PLATFORMS}," == *",${MINI_PLATFORM},"* ]]; then
    log_error "node ${MINI_NODE_NAME} at ${MINI_ENDPOINT} is the node that can be unreachable here"
    log_error "the mini must be awake, on the tailnet, and running the eden-buildkitd container"
  fi
  exit 1
fi
