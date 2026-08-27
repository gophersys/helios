#!/usr/bin/env bash
#
# _delta/components/terraform.sh — READY component, consumed by NOTHING today.
#
# terraform was DROPPED from every image by decision (image-architecture §2.3):
# infra work has its own home. This file is the documented extension point —
# the day an image needs terraform, its delta gains the ONE line
# `bash /opt/delta/components/terraform.sh` and nothing else changes. The pin
# TERRAFORM_VERSION already lives in versions.env.
#
# Runs inside a Dockerfile RUN, as root. Idempotent: unzip -o overwrites.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${TERRAFORM_VERSION:?TERRAFORM_VERSION is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

case "${TARGETPLATFORM}" in
  linux/amd64) ARCH=amd64 ;;
  linux/arm64) ARCH=arm64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" -o /tmp/tf.zip
unzip -o -q /tmp/tf.zip -d /usr/local/bin
rm /tmp/tf.zip

# Proof.
terraform version
