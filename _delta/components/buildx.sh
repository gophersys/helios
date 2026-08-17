#!/usr/bin/env bash
#
# _delta/components/buildx.sh — the docker buildx cli-plugin, pinned by
# DOCKER_BUILDX_VERSION and its per-arch release digests.
#
# Runs inside a Dockerfile RUN, as root, after docker-ce-cli. The plugin
# arrives as a release binary and not as an apt package, so nothing but the
# digest says the bytes are the ones upstream published — the same discipline
# base/Dockerfile applies. This closes the measured base-runner gap: `docker
# buildx version` exited 1 there, and the CI pod is the CLIENT of the remote
# arm64 builder. Idempotent: the download overwrites.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${DOCKER_BUILDX_VERSION:?DOCKER_BUILDX_VERSION is not in versions.env}"
: "${DOCKER_BUILDX_SHA256_AMD64:?DOCKER_BUILDX_SHA256_AMD64 is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

case "${TARGETPLATFORM}" in
  linux/amd64) ARCH=amd64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

mkdir -p /usr/local/lib/docker/cli-plugins
/usr/local/lib/gophersys/fetch-verified.sh \
  "https://github.com/docker/buildx/releases/download/v${DOCKER_BUILDX_VERSION}/buildx-v${DOCKER_BUILDX_VERSION}.linux-${ARCH}" \
  /usr/local/lib/docker/cli-plugins/docker-buildx \
  "${DOCKER_BUILDX_SHA256_AMD64}" DOCKER_BUILDX_SHA256_AMD64
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

# Proof — `docker buildx version` reaches no daemon, so it is a pure
# image-content check.
docker buildx version
