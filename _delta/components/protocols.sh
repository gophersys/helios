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
: "${GRPCURL_VERSION:?GRPCURL_VERSION is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

# buf names its assets uname-style; grpcurl mixes x86_64 with arm64.
case "${TARGETPLATFORM}" in
  linux/amd64) BUF_ARCH=x86_64;  GRPCURL_ARCH=x86_64 ;;
  linux/arm64) BUF_ARCH=aarch64; GRPCURL_ARCH=arm64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

curl -fsSL "https://github.com/bufbuild/buf/releases/download/v${BUF_VERSION}/buf-Linux-${BUF_ARCH}" \
  -o /usr/local/bin/buf
chmod 0755 /usr/local/bin/buf

curl -fsSL "https://github.com/fullstorydev/grpcurl/releases/download/v${GRPCURL_VERSION}/grpcurl_${GRPCURL_VERSION}_linux_${GRPCURL_ARCH}.tar.gz" \
  -o /tmp/grpcurl.tgz
tar -C /tmp -xzf /tmp/grpcurl.tgz grpcurl
mv /tmp/grpcurl /usr/local/bin/grpcurl
rm /tmp/grpcurl.tgz

# Proof. grpcurl takes a single-dash -version.
buf --version
grpcurl -version
