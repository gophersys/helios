#!/usr/bin/env bash
#
# The per-image dispatcher of the fixture image `second`.
#
# It dispatches nothing, for the reason first/ctl.sh states. It exists because
# `validate` asks every image of the manifest for a ctl.sh, a Dockerfile and a
# project.json, and a staged root missing one of them would go red for a reason
# _ctl/tests/devcontainer-contract.test.sh says nothing about.
#
set -Eeuo pipefail
IFS=$'\n\t'

printf 'fixture dispatcher: second %s\n' "${1:-<no verb>}"
