#!/usr/bin/env bash
#
# _delta/components/ansible.sh — READY component, called by NO Dockerfile today.
#
# ansible + ansible-core are not in the CLOUD image, by decision
# (image-architecture §2.3): 787 MB with oci-cli, the biggest single win after
# the Go cache. **The base family still installs them.** This header said
# "DROPPED from every image", which is false: base/Dockerfile:635-636 is a live
# `uv tool install --with ansible== ... ansible-core==`, so base and its 3
# children ship both, and .ci/smoke.sh:192-193 asserts their versions. The
# trivyignore secret waiver for `.../uv/tools/ansible-core/**/sts_session_token.py`
# exists BECAUSE of that install — a path that could not exist if the drop were
# universal. Scope a drop to the image that made it.
#
# This file is the documented extension point for the cloud family — one delta
# line away when infra work needs it. The pins ANSIBLE_VERSION and
# ANSIBLE_CORE_VERSION already live in versions.env.
#
# ansible-core is the primary because the `ansible` metapackage only ships an
# `ansible-community` info script; the real engine entry points come from
# ansible-core — the same pattern base/Dockerfile uses.
#
# Runs inside a Dockerfile RUN, as the DEV USER: uv tool install writes under
# ${HOME}. Idempotent: uv tool install replaces the tool.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${ANSIBLE_VERSION:?ANSIBLE_VERSION is not in versions.env}"
: "${ANSIBLE_CORE_VERSION:?ANSIBLE_CORE_VERSION is not in versions.env}"
: "${PYTHON_PACKAGE:?PYTHON_PACKAGE is not in versions.env}"

uv tool install --python "${PYTHON_PACKAGE}" \
  --with "ansible==${ANSIBLE_VERSION}" \
  "ansible-core==${ANSIBLE_CORE_VERSION}"

# Proof.
"${HOME}/.local/bin/ansible" --version
