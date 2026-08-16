#!/usr/bin/env bash
#
# _delta/components/k9s.sh — the k9s TUI, pinned by K9S_VERSION.
#
# Runs inside a Dockerfile RUN, as root. The version arrives as environment
# (the build passes --build-arg from versions.env); a missing pin FAILS and
# names the variable. Idempotent: the download overwrites the installed binary.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${K9S_VERSION:?K9S_VERSION is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

case "${TARGETPLATFORM}" in
  linux/amd64) ARCH=amd64 ;;
  linux/arm64) ARCH=arm64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

curl -fsSL "https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_Linux_${ARCH}.tar.gz" -o /tmp/k9s.tgz
tar -C /tmp -xzf /tmp/k9s.tgz k9s
mv /tmp/k9s /usr/local/bin/k9s
rm /tmp/k9s.tgz

# Proof.
k9s version --short
