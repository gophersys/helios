#!/usr/bin/env bash
# Hold the generated publish workflow to one upload path: the image itself.
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="cache-topology.test.sh"
WORKFLOW="$REPO_ROOT/.ci/providers/github/build-and-push.yml"

if ! command -v yq >/dev/null 2>&1; then
  fail_check "the_yaml_reader_is_available" "yq is not on PATH"
  test_summary "$TEST_NAME"
  exit 1
fi
pass_check "the_yaml_reader_is_available"

mapfile -t jobs < <(yq -r '.jobs | keys | .[]' "$WORKFLOW")
assert_status_nonzero "the_workflow_contains_a_publish_job" "${#jobs[@]}"

for job in "${jobs[@]}"; do
  export CACHE_JOB="$job"
  expected="type=registry,ref=\${{ env.REGISTRY }}/\${{ env.OWNER }}/${job}:latest"

  for step in \
    "build the image, load it locally, publish nothing yet" \
    "publish the image the smoke test passed" \
    "rehearsal — build what the publish step would build, ship nothing"; do
    export CACHE_STEP="$step"
    value="$(yq -r '.jobs[strenv(CACHE_JOB)].steps[] | select(.name == strenv(CACHE_STEP)) | .with["cache-from"] // "<absent>"' "$WORKFLOW")"
    assert_equal "${job}_${step}_reads_latest" "$expected" "$value"
  done

  publish_inline="$(yq -r '[.jobs[strenv(CACHE_JOB)].steps[] | select(.with.push == true and .with["cache-to"] == "type=inline")] | length' "$WORKFLOW")"
  other_exports="$(yq -r '[.jobs[strenv(CACHE_JOB)].steps[] | select(.with.push != true and .with["cache-to"] != null)] | length' "$WORKFLOW")"
  legacy_refs="$(yq -r '.jobs[strenv(CACHE_JOB)].steps[].with | (.["cache-from"] // ""), (.["cache-to"] // "")' "$WORKFLOW" | grep -cF -- "${job}-cache" || true)"

  assert_equal "${job}_publish_embeds_one_inline_cache" "1" "$publish_inline"
  assert_equal "${job}_no_other_step_exports_cache" "0" "$other_exports"
  assert_equal "${job}_has_no_legacy_cache_package_ref" "0" "$legacy_refs"
done

test_summary "$TEST_NAME"
