#!/usr/bin/env bash
#
# The per-image dispatcher of the fixture image `second`. See first/ctl.sh for
# what these files are and why their committed mode is not the stimulus.
#
set -Eeuo pipefail
IFS=$'\n\t'

printf 'fixture dispatcher: second %s\n' "${1:-<no verb>}"
