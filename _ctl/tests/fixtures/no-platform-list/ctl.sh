#!/usr/bin/env bash
#
# _ctl/tests/fixtures/no-platform-list/ctl.sh — a test-only image dispatcher.
#
# It exists for 1 condition of the push guard: "the platform list is empty".
# That condition cannot be reached from the environment, because the library
# declares its default with `: "${VAR:=...}"`, and `:=` replaces an empty value
# as well as an unset one. So an empty list from the environment silently
# becomes the default list, and a test that tried it would prove nothing.
#
# This fixture reaches the condition the only way a real dispatcher could: by
# removing the variable after the library has loaded.
#
#   UNSET_PLATFORM_LIST=1   remove the list  -> the guard must refuse to push
#   UNSET_PLATFORM_LIST=0   keep the default -> the counter-stimulus run, which
#                           must reach the push, so the check above is known to
#                           distinguish a refusal from an acceptance
#
# Both names are removed. The old one is what the library reads today; the new
# one is what it reads after the drop. `unset` and not `=""` on purpose: a
# tripwire that fails when the OLD name is still SET must not be what makes
# this fixture fail, or the check would pass for a reason it did not test.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_NAME="fixture"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../../../lib.sh
source "$PROJECT_ROOT/../../../lib.sh"

if [[ "${UNSET_PLATFORM_LIST:-0}" == "1" ]]; then
  unset MULTI_ARCH_PLATFORMS IMAGE_PLATFORMS
fi

image_main "$@"
