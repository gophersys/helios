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
# It is wired and it does not run. SANCTIONED_PLATFORMS in _ctl/lib.sh is
# `linux/amd64` alone (debt D42 — no arm64 consumer can be verified for any
# image), so this file appends nothing today. The day that list widens, the
# builder gains the node with no edit here: the switch below reads the library
# rather than repeating its value.
#
# THIS FILE NAMES linux/arm64 ON PURPOSE, and it must therefore stay out of
# BUILD_PATH_FILES in _ctl/tests/platform-policy.test.sh. That test forbids the
# token on the build path so a re-added architecture cannot arrive quietly. This
# file is the one place whose JOB is to react to the library's value, so naming
# the platform is what it is for — the same reason the test reads the sanctioned
# value as a literal instead of from the implementation.
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
  log_info "creating buildx builder '${BUILDER_NAME}' (docker-container, ${LOCAL_PLATFORM})"
  docker buildx create \
    --name "$BUILDER_NAME" \
    --driver docker-container \
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
