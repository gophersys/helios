#!/usr/bin/env bash
#
# .ci/mirror-buildkit.sh — keep ghcr.io holding the BuildKit image the builder
# boots from.
#
#   bash .ci/mirror-buildkit.sh
#
# .ci/buildx-node.sh boots the builder from BUILDKIT_REF, which names OUR
# registry — the boot must not depend on docker.io (see the header there).
# Somebody has to put the image at that name, and this file is that somebody:
# it asks ghcr.io whether the pinned digest is already there, and only when it
# is not does it copy the index across from BUILDKIT_UPSTREAM_REF.
#
# The warm path — every run after the first, until the pin moves — is 1
# authenticated read of our own registry and touches docker.io not at all. The
# cold path runs once per pin value, can fail on upstream weather like any
# fetch, and FAILS LOUDLY when it does: the next run retries it, and nothing
# is left half-published because a manifest copy lands atomically or not at
# all.
#
# `imagetools create` copies the manifest LIST by digest, so what lands at
# ghcr.io is byte-identical to what the pin names — the digest in BUILDKIT_REF
# verifies the mirror on every boot, which is why this file needs no digest
# check of its own after the copy.
#
# It runs in the build jobs AFTER the registry login: the push needs
# packages:write, and the boot pull that follows needs packages:read on a
# private package. Concurrent jobs racing this are safe — both copy the same
# bytes to the same digest-addressed name.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

require_buildx

# The digest is the identity; the tag parts differ between the 2 refs' homes.
PINNED_DIGEST="${BUILDKIT_REF##*@}"
if [[ "$PINNED_DIGEST" != sha256:* ]]; then
  log_error "BUILDKIT_REF carries no sha256 digest: ${BUILDKIT_REF}"
  exit 1
fi

if docker buildx imagetools inspect "$BUILDKIT_REF" >/dev/null 2>&1; then
  log_info "ghcr.io already holds ${PINNED_DIGEST} — nothing to mirror"
  exit 0
fi

log_info "ghcr.io does not hold ${PINNED_DIGEST} — copying ${BUILDKIT_UPSTREAM_REF}"
if ! docker buildx imagetools create \
  --tag "${BUILDKIT_REF%@*}" \
  "$BUILDKIT_UPSTREAM_REF"; then
  log_error "the copy from ${BUILDKIT_UPSTREAM_REF} failed — the builder cannot boot until the mirror holds ${PINNED_DIGEST}"
  exit 1
fi

# The copy is not the proof; the read-back is. A tag push that landed a
# DIFFERENT index — an upstream tag that moved between the pin and the copy —
# must fail here, not at the next boot.
if ! docker buildx imagetools inspect "$BUILDKIT_REF" >/dev/null 2>&1; then
  log_error "the mirror was written but ghcr.io still does not resolve ${BUILDKIT_REF}"
  exit 1
fi
log_info "mirrored ${BUILDKIT_UPSTREAM_REF} -> ${BUILDKIT_REF%@*}"
