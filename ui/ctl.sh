#!/usr/bin/env bash
#
# ui/ctl.sh — control script for the ui image:
#   ghcr.io/gophersys/ui
#
# Thin dispatcher. The body of every verb is in _ctl/lib.sh, 1 time only.
#
# It is the second CHILD that reads versions.env rather than spelling its own
# pins, the way hardware does: value-less ARGs in the Dockerfile, and
# `pins: versions.env` on its images.yaml entry is what makes the CI job
# generate the same list this line generates locally.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_NAME="ui"

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
