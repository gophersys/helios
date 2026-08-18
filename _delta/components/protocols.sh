#!/usr/bin/env bash
#
# _delta/components/protocols.sh — the protobuf/gRPC pair: buf + grpcurl,
# pinned by BUF_VERSION and GRPCURL_VERSION.
#
# Runs inside a Dockerfile RUN, as root. Versions arrive as environment; a
# missing pin FAILS and names the variable. Idempotent: downloads overwrite.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${BUF_VERSION:?BUF_VERSION is not in versions.env}"
: "${BUF_SHA256_AMD64:?BUF_SHA256_AMD64 is not in versions.env}"
: "${BUF_SHA256_ARM64:?BUF_SHA256_ARM64 is not in versions.env}"
: "${GRPCURL_VERSION:?GRPCURL_VERSION is not in versions.env}"
: "${GRPCURL_SHA256_AMD64:?GRPCURL_SHA256_AMD64 is not in versions.env}"
: "${GRPCURL_SHA256_ARM64:?GRPCURL_SHA256_ARM64 is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

# buf names its assets uname-style; grpcurl uses the same spelling on amd64 and
# the buildx spelling on arm64. This file is why the locals carry the tool's
# name: 1 arm feeds 2 fetches, and a bare SHA256 would hand buf's digest to
# grpcurl.
#
# The local holding the pin NAME is BUF_PIN and not BUF_SHA256_PIN, and that is
# not a taste. `<PREFIX>_SHA256_<SUFFIX>` is the shape every reader of the
# digest vocabulary matches, so BUF_SHA256_PIN reads as a digest row that no
# home declares — measured: it made download-coverage report a digest living in
# "nowhere" while the real rows were correct.
#
# Each arm stays on 1 LINE. fetch_urls in _ctl/lib.sh reads a case arm as the
# text between `linux/amd64)` and the `;;` on the same logical line, so an arm
# broken across lines reads as an arm that assigns nothing, and every download
# below it becomes a download nobody can answer for.
case "${TARGETPLATFORM}" in
  linux/amd64) BUF_ARCH=x86_64; BUF_SHA256="${BUF_SHA256_AMD64}"; BUF_PIN=BUF_SHA256_AMD64; GRPCURL_ARCH=x86_64; GRPCURL_SHA256="${GRPCURL_SHA256_AMD64}"; GRPCURL_PIN=GRPCURL_SHA256_AMD64 ;;
  linux/arm64) BUF_ARCH=aarch64; BUF_SHA256="${BUF_SHA256_ARM64}"; BUF_PIN=BUF_SHA256_ARM64; GRPCURL_ARCH=arm64; GRPCURL_SHA256="${GRPCURL_SHA256_ARM64}"; GRPCURL_PIN=GRPCURL_SHA256_ARM64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

/usr/local/lib/gophersys/fetch-verified.sh \
  "https://github.com/bufbuild/buf/releases/download/v${BUF_VERSION}/buf-Linux-${BUF_ARCH}" \
  /usr/local/bin/buf "${BUF_SHA256}" "${BUF_PIN}"
chmod 0755 /usr/local/bin/buf

/usr/local/lib/gophersys/fetch-verified.sh \
  "https://github.com/fullstorydev/grpcurl/releases/download/v${GRPCURL_VERSION}/grpcurl_${GRPCURL_VERSION}_linux_${GRPCURL_ARCH}.tar.gz" \
  /tmp/grpcurl.tgz "${GRPCURL_SHA256}" "${GRPCURL_PIN}"
tar -C /tmp -xzf /tmp/grpcurl.tgz grpcurl
mv /tmp/grpcurl /usr/local/bin/grpcurl
rm /tmp/grpcurl.tgz

# Proof. grpcurl takes a single-dash -version.
buf --version
grpcurl -version
