#!/usr/bin/env bash
#
# The per-image dispatcher of the fixture image `first`.
#
# It dispatches nothing. `validate` never RUNS a per-image ctl.sh — it asks
# whether the file is executable, because image_ctl in the root ctl.sh refuses
# one that is not — so the body here exists only to be a shell script the gate's
# own `shellcheck -x -S style` pass can read and accept.
#
# Its MODE is what this file is for, and the mode it is committed with is not
# what the test reads: _ctl/tests/dispatcher-mode.test.sh chmods every staged
# copy itself, so the stimulus of each run is written in the test rather than
# carried in a git index a reader would have to inspect.
#
set -Eeuo pipefail
IFS=$'\n\t'

printf 'fixture dispatcher: first %s\n' "${1:-<no verb>}"
