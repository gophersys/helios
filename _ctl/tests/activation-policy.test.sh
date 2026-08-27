#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
export PROJECT_ROOT="$REPO_ROOT"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="activation-policy.test.sh"
DECLARED_IMAGES=(base cloud embedded hardware mobile ui)
ACTIVE_IMAGES=(base cloud)

joined() { printf '%s\n' "$@" | sort | paste -sd' ' -; }

declared="$(image_names)"
assert_equal "all_six_image_products_remain_declared" \
  "$(joined "${DECLARED_IMAGES[@]}")" "$(joined "$declared")" \
  "disabled products remain inventory; disabling is not deletion"

enabled_status=0
enabled="$(active_image_names 2>&1)" || enabled_status=$?
assert_equal "the_manifest_exposes_an_enabled_image_reader" \
  "0" "$enabled_status" "active_image_names must reject a manifest without explicit boolean activation"
if [[ "$enabled_status" -eq 0 ]]; then
  assert_equal "only_base_and_cloud_are_active" \
    "$(joined "${ACTIVE_IMAGES[@]}")" "$(joined "$enabled")" \
    "publish, scan, build-all and push-all must share this exact active set"
fi

missing_activation="$(manifest_yq '[.images | to_entries[] | select((.value | has("enabled")) | not) | .key] | join(" ")')"
assert_equal "every_image_makes_activation_explicit" "" "$missing_activation" \
  "absence must fail rather than silently enabling a newly added image"

non_boolean="$(manifest_yq '[.images | to_entries[] | select(.value.enabled != true and .value.enabled != false) | .key] | join(" ")')"
assert_equal "every_enabled_value_is_a_boolean" "" "$non_boolean" \
  "quoted booleans are strings and must not decide production fan-out"

disabled_smoke_status=0
disabled_smoke_output="$(bash "$REPO_ROOT/.ci/smoke.sh" hardware hardware:test 2>&1)" || disabled_smoke_status=$?
assert_equal "normal_smoke_rejects_a_disabled_image" "2" "$disabled_smoke_status" \
  "the static contract seam must never weaken an operational invocation"
assert_contains "disabled_smoke_names_the_policy" "$disabled_smoke_output" "disabled" \
  "operators should see an activation failure before Docker is contacted"

seam_name="SMOKE_STATIC_CONTRACT"
seam_references="$(rg -l "${seam_name}=1" "$REPO_ROOT" --glob '!_ctl/tests/smoke-contract.test.sh' || true)"
assert_equal "only_the_contract_test_sets_the_static_seam" "" "$seam_references" \
  "generated workflows and runtime scripts must not bypass activation"

test_summary "$TEST_NAME"
