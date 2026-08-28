#!/usr/bin/env bash
#
# cloud/ctl.sh — control script for the cloud image:
#   ghcr.io/gophersys/cloud
#
# Thin dispatcher. The body of every verb is in _ctl/lib.sh, 1 time only.
#
# Two things make this image different from the siblings, and both are data
# set here rather than verbs written here:
#   - the build context is the REPOSITORY ROOT, because versions.env and
#     _delta/ sit one level above this directory;
#   - every version arrives as --build-arg generated from versions.env — the
#     ONE home for every pin of the new mechanism. The Dockerfile's ARGs are
#     value-less, and its pin gate fails the build naming any missing one.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_NAME="cloud"
IMAGE_BUILD_CONTEXT="$(cd "$PROJECT_ROOT/.." && pwd)"
IMAGE_DOCKERFILE="$PROJECT_ROOT/Dockerfile"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

# Appends one --build-arg per line of versions.env to IMAGE_BUILD_ARGS.
versions_env_build_args "$IMAGE_BUILD_CONTEXT/versions.env"

IMAGE_USAGE_HEADER="
Versions: every pin comes from versions.env at the repository root"

image_main "$@"
