#!/usr/bin/env bash
#
# The per-image dispatcher of the fixture image `first`.
#
# It dispatches nothing. `validate` never RUNS a per-image ctl.sh — it asks
# whether the file is executable, because image_ctl in the root ctl.sh refuses
# one that is not — so the body here exists only to be a shell script the gate's
# own `shellcheck -x -S style` pass can read and accept.
#
# _ctl/tests/devcontainer-contract.test.sh chmods every staged copy 755 itself,
# so the dispatcher-mode rule is satisfied in every run of that file and the
# refusals it reads are about devcontainer.json alone.
#
set -Eeuo pipefail
IFS=$'\n\t'

printf 'fixture dispatcher: first %s\n' "${1:-<no verb>}"
