#!/usr/bin/env bash
#
# runner/ctl.sh — control script for the `+ runner` variant of a dev image:
#   ghcr.io/gophersys/<parent>-runner
#
# Thin dispatcher. The body of every verb is in _ctl/lib.sh, 1 time only.
# 1 Dockerfile serves every parent. Select the parent with RUNNER_PARENT:
#   RUNNER_PARENT=zephyr ./ctl.sh build
#
# Why the runner layer exists at all: gophersys/infrastructure
# docs/ci-substrate.md
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RUNNER_PARENT="${RUNNER_PARENT:-base}"
PARENT_TAG="${PARENT_TAG:-latest}"
BASE_IMAGE="ghcr.io/gophersys/${RUNNER_PARENT}:${PARENT_TAG}"
IMAGE_NAME="${RUNNER_PARENT}-runner"

# The parent is a build argument, not a second Dockerfile.
IMAGE_BUILD_ARGS=(--build-arg "BASE_IMAGE=${BASE_IMAGE}")

# A runner image only ever runs as an ARC pod, and every node in that cluster
# is amd64. Its arm64 half would be Go compiled under QEMU for an architecture
# that nothing runs. That measured ~13 minutes for an otherwise thin layer. The
# devcontainer images stay multi-arch. This image builds the arch it deploys to.
MULTI_ARCH_PLATFORMS="linux/amd64"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

IMAGE_USAGE_HEADER="
Parent: ${BASE_IMAGE}   (override with RUNNER_PARENT / PARENT_TAG)"

image_main "$@"
