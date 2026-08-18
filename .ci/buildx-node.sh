#!/usr/bin/env bash
#
# .ci/buildx-node.sh — make the buildx builder that every image build of this
# repository uses.
#
#   bash .ci/buildx-node.sh
#
# It replaces docker/setup-buildx-action in the build jobs. The action makes a
# `docker-container` builder and nothing else; this file makes the same builder
# AND owns the one decision the action cannot make — whether the arm64 half of a
# build leaves the pod for the Mac mini.
#
# ============================================================================
# WHY A LOCAL docker-container NODE AT ALL
# ============================================================================
#
# The default `docker` driver cannot export a registry cache and cannot read
# one, and the registry cache is what makes a self-hosted build warm across
# ephemeral pods. The `docker-container` driver can do both, and `load: true`
# still works: buildx copies the result into the pod's docker image store, which
# is what .ci/smoke.sh then runs.
#
# ============================================================================
# THE MINI, AND WHY IT IS INERT TODAY
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
# THIS FILE NAMES linux/arm64 ON PURPOSE, and it must therefore stay out of
# BUILD_PATH_FILES in _ctl/tests/platform-policy.test.sh. That test forbids the
# token on the build path so a re-added architecture cannot arrive quietly. This
# file is the one place whose JOB is to react to the library's value, so naming
# the platform is what it is for — the same reason the test reads the sanctioned
# value as a literal instead of from the implementation.
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
# WHY THE BUILDER IS MADE IN THE JOB
# ============================================================================
#
# `docker buildx create` writes to $HOME/.docker/buildx in the runner container.
# Every job gets a new pod, so a builder made at pod start dies with that pod,
# and an init container cannot write into the runner container's file system.
# The remote driver spawns no BuildKit container of its own — buildkitd already
# runs on the mini and keeps its cache across jobs — so the cost of remaking the
# builder is local metadata.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/smoke.sh sets it: the git fallback in
# _ctl/lib.sh reads the wrong root when this repository is a submodule worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# SANCTIONED_PLATFORMS, the logging and the tool gate live in _ctl/lib.sh, 1
# time only. The switch below reads that variable, so widening the platform set
# is still 1 edit in 1 file.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

# The name require_buildx_and_platforms prints in its "no active builder"
# message, so the guard and this file agree on what to look for.
BUILDER_NAME="gophersys"

# The platform of the pool. arc-build runs on the three pve-00 workers and every
# node of that cluster is amd64 (gophersys/infrastructure docs/ci-runners.md).
LOCAL_PLATFORM="linux/amd64"

# The mini, per docs/ci-substrate.md. The endpoint is the BUILD API and not the
# Docker Engine API: a client with no certificate is refused, and the escape to
# a privileged container over this port is dead.
MINI_NODE_NAME="eden-mini"
MINI_ENDPOINT="tcp://10.168.0.92:1234"
MINI_CERT_DIR="/etc/buildkit-certs"
MINI_PLATFORM="linux/arm64"

require_buildx

# A pod is fresh, so this is normally a create. It is written to be re-runnable
# anyway: a second run of a step must not fail on the state the first one left.
if docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
  log_info "buildx builder '${BUILDER_NAME}' already exists — reusing it"
  docker buildx use "$BUILDER_NAME"
else
  log_info "creating buildx builder '${BUILDER_NAME}' (docker-container, ${LOCAL_PLATFORM}, ${BUILDKIT_REF})"
  docker buildx create \
    --name "$BUILDER_NAME" \
    --driver docker-container \
    --driver-opt "image=${BUILDKIT_REF}" \
    --driver-opt network=host \
    --buildkitd-flags '--oci-worker-net=host' \
    --platform "$LOCAL_PLATFORM" \
    --use >/dev/null
fi

# The switch. `,list,` on both sides so `linux/amd64` cannot match inside
# another entry.
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
  if [[ ",${SANCTIONED_PLATFORMS}," == *",${MINI_PLATFORM},"* ]]; then
    log_error "node ${MINI_NODE_NAME} at ${MINI_ENDPOINT} is the node that can be unreachable here"
    log_error "the mini must be awake, on the tailnet, and running the eden-buildkitd container"
  fi
  exit 1
fi
