#!/usr/bin/env bash
#
# _delta/components/aws.sh — READY component, consumed by NOTHING today.
#
# AWS CLI v2 was DROPPED from every image by decision (image-architecture
# §2.3): only arm-builder EC2 operations touch AWS. This file is the documented
# extension point — one delta line away when infra work needs it. The pin
# AWS_CLI_VERSION already lives in versions.env.
#
# Runs inside a Dockerfile RUN, as root. Idempotent: the installer's --update
# replaces an existing install.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${AWS_CLI_VERSION:?AWS_CLI_VERSION is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

case "${TARGETPLATFORM}" in
  linux/amd64) ARCH=x86_64 ;;
  linux/arm64) ARCH=aarch64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}-${AWS_CLI_VERSION}.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update
rm -rf /tmp/awscliv2.zip /tmp/aws

# Proof.
aws --version
