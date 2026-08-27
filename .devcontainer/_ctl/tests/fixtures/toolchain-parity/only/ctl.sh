#!/usr/bin/env bash
#
# The per-image dispatcher of the fixture image `only`.
#
# It dispatches nothing. `validate` never RUNS a per-image ctl.sh — it asks
# whether the file is executable — so the body here exists only to be a shell
# script that the gate's own shellcheck pass has something to read.
#
# It is the file _ctl/tests/toolchain-parity.test.sh looks for in the progress
# log: a run that linted names it, and a run the version gate refused does not.
#
set -Eeuo pipefail
IFS=$'\n\t'

printf 'fixture dispatcher: only %s\n' "${1:-<no verb>}"
