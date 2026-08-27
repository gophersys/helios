#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="startup-policy.test.sh"
BASE_LIFECYCLE="$REPO_ROOT/base/ctl.sh"
BASE_DOCKERFILE="$REPO_ROOT/base/Dockerfile"

network_installs="$(rg -n 'curl .*\|[[:space:]]*(ba)?sh|npm[[:space:]]+install|pnpm[[:space:]]+add|yarn[[:space:]]+add|bun[[:space:]]+add|pip(x|3)?[[:space:]]+install|go[[:space:]]+install|cargo[[:space:]]+install|apt(-get)?[[:space:]]+(install|update)|apk[[:space:]]+add|dnf[[:space:]]+install|brew[[:space:]]+install' "$BASE_LIFECYCLE" || true)"
assert_equal "base_startup_is_offline_and_install_free" "" "$network_installs" \
  "slow and stable tools belong in the image; this feature declares zero startup-install exceptions"

for pin in CLAUDE_CODE_VERSION OMP_VERSION CODEX_VERSION; do
  if rg -q "^ARG ${pin}$" "$BASE_DOCKERFILE"; then
    pass_check "base_bakes_${pin}"
  else
    fail_check "base_bakes_${pin}" \
      "base/Dockerfile does not declare ARG ${pin}" \
      "the base devcontainer must contain every pinned harness before startup"
  fi
done

if rg -q 'components/agents\.sh' "$BASE_DOCKERFILE"; then
  pass_check "base_runs_the_shared_agent_bake"
else
  fail_check "base_runs_the_shared_agent_bake" \
    "base/Dockerfile never runs the shared agents component" \
    "Claude, OMP and Codex must use the same baked installation implementation as cloud"
fi

test_summary "$TEST_NAME"
