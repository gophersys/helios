#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="base"
IMAGE_BUILD_CONTEXT="$(cd "$project_root/.." && pwd)"
IMAGE_DOCKERFILE="$project_root/Dockerfile"

# shellcheck source=../_ctl/lib.sh
source "$project_root/../_ctl/lib.sh"
versions_env_build_args "$IMAGE_BUILD_CONTEXT/versions.env"
image_main "$@"
