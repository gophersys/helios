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

job_count="$(awk '
  /^jobs:$/ { in_jobs=1; next }
  in_jobs && /^  [a-z0-9-]+:$/ { count++ }
  END { print count + 0 }
' "$WORKFLOW")"
inline_count="$(grep -cF 'cache-to: type=inline' "$WORKFLOW" || true)"
latest_count="$(grep -cE 'cache-from: type=registry,ref=.*:[Ll]atest$' "$WORKFLOW" || true)"
legacy_count="$(grep -cE 'cache-(from|to): .*-[Cc]ache' "$WORKFLOW" || true)"

assert_equal "one_inline_export_per_publish_job" "$job_count" "$inline_count"
assert_equal "gate_publish_and_rehearsal_read_the_image_cache" "$((job_count * 3))" "$latest_count"
assert_equal "no_separate_registry_cache_package" "0" "$legacy_count"

test_summary "$TEST_NAME"
