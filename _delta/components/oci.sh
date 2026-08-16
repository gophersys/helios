#!/usr/bin/env bash
#
# _delta/components/oci.sh — READY component, consumed by NOTHING today.
#
# oci-cli was DROPPED from every image by decision (image-architecture §2.3).
# This file is the documented extension point — one delta line away when infra
# work needs it. The pin OCI_CLI_VERSION already lives in versions.env.
#
# Runs inside a Dockerfile RUN, as the DEV USER: uv tool install writes its
# venv and its shims under ${HOME} (.local/share/uv, .local/bin), the same way
# base/Dockerfile installs it. Idempotent: uv tool install replaces the tool.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${OCI_CLI_VERSION:?OCI_CLI_VERSION is not in versions.env}"
: "${PYTHON_PACKAGE:?PYTHON_PACKAGE is not in versions.env}"

uv tool install --python "${PYTHON_PACKAGE}" "oci-cli==${OCI_CLI_VERSION}"

# Proof.
"${HOME}/.local/bin/oci" --version
