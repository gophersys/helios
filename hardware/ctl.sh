#!/usr/bin/env bash
#
# hardware/ctl.sh — control script for the hardware image:
#   ghcr.io/gophersys/hardware
#
# Thin dispatcher. The body of every verb is in _ctl/lib.sh, 1 time only.
#
# One thing makes this image different from the other 3 children, and it is
# data set here rather than a verb written here: it is a CHILD that reads
# versions.env. flutter, zephyr and zephyr-devbox spell their own pins inline;
# this one declares value-less ARGs and takes the values from the one pin home,
# the way cloud does. `pins: versions.env` on its images.yaml entry is what
# makes the CI job generate the same list.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_NAME="hardware"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

# Appends one --build-arg per line of versions.env to IMAGE_BUILD_ARGS. The
# build context stays this directory — nothing here is COPYed in, so the file is
# READ by the control script and never shipped.
versions_env_build_args "$PROJECT_ROOT/../versions.env"

IMAGE_USAGE_HEADER="
Versions: every pin comes from versions.env at the repository root"

image_main "$@"
