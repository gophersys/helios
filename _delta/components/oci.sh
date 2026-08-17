#!/usr/bin/env bash
#
# _delta/components/oci.sh — READY component, called by NO Dockerfile today.
#
# oci-cli is not in the CLOUD image, by decision (image-architecture §2.3).
# **The base family still installs it.** This header said "DROPPED from every
# image", which is false: base/Dockerfile:637 is a live
# `uv tool install ... oci-cli==${OCI_CLI_VERSION}`, and .ci/smoke.sh:191
# asserts `oci --version` against the pin. The next paragraph of this same file
# says the install matches "the same way base/Dockerfile installs it", so the
# file contradicted itself 2 paragraphs apart. Scope a drop to the image that
# made it.
#
# This file is the documented extension point for the cloud family — one delta
# line away when infra work needs it. The pin OCI_CLI_VERSION already lives in
# versions.env.
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
