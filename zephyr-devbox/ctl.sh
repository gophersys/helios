#!/usr/bin/env bash
#
# zephyr-devbox/ctl.sh — control script for the zephyr-devbox image:
#   ghcr.io/gophersys/zephyr-devbox
#
# Thin dispatcher. The body of every verb is in _ctl/lib.sh, 1 time only.
# Run `bash ./ctl.sh help` for the interface, and read _ctl/lib.sh for the
# platform policy that `push` enforces.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_NAME="zephyr-devbox"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

image_main "$@"
