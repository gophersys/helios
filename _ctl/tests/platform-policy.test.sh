#!/usr/bin/env bash
#
# _ctl/tests/platform-policy.test.sh — the static half of the arm64 drop.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and
# on a CI runner.
#
# What it encodes: exactly 1 platform is sanctioned for a published image, the
# library declares it once, and every other place on the build path either
# repeats that same value or does not name a platform at all.
#
# The sanctioned value is written here as a literal ON PURPOSE. A test that
# reads the value out of the implementation and then compares it to itself
# agrees with any value the implementation happens to hold, including a wrong
# one. The literal is the policy; _ctl/lib.sh is the implementation of it.
#
# Usage: bash _ctl/tests/platform-policy.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="platform-policy.test.sh"

# The policy. 1 platform, and its name.
SANCTIONED="linux/amd64"

# The build path, named file by file. This is deliberately NOT a repository-wide
# grep. A document must stay free to say the words "linux/arm64" while it
# explains why arm64 was dropped, and a repository-wide grep would forbid the
# explanation along with the defect. The Dockerfiles are absent for the same
# kind of reason: their TARGETPLATFORM case blocks stay, because they are how a
# binary install resolves its architecture, and they cost nothing on a
# single-platform build. The `_delta/components/*.sh` install scripts are absent
# for that same reason: they run inside a Dockerfile RUN and resolve their
# architecture from TARGETPLATFORM, exactly as the Dockerfile case blocks do.
BUILD_PATH_FILES=(
  "_ctl/lib.sh"
  "ctl.sh"
  "base/ctl.sh"
  "cloud/ctl.sh"
  "flutter/ctl.sh"
  "zephyr/ctl.sh"
  "zephyr-devbox/ctl.sh"
  "zephyr-devbox/devbox-entrypoint.sh"
  ".ci/ctl.sh"
  ".ci/smoke.sh"
  ".github/workflows/build-and-push.yml"
  ".github/workflows/validate.yml"
  ".ci/providers/github/build-and-push.yml"
  "project.json"
  "base/project.json"
  "cloud/project.json"
  "flutter/project.json"
  "zephyr/project.json"
  "zephyr-devbox/project.json"
  ".ci/project.json"
)

# A token that must not appear in any file above. The second one is the old
# variable name: both values become the same string after the drop, so a missed
# rename is invisible at runtime and only a name check finds it.
FORBIDDEN_TOKENS=(
  "linux/arm64"
  "MULTI_ARCH_PLATFORMS"
)

WORKFLOW="$REPO_ROOT/.github/workflows/build-and-push.yml"

# The provider directory is the SOURCE OF TRUTH for the GitHub provider, and
# .github/workflows/ holds a copy of each of its files (.ci/providers/README.md).
# Every file here is compared with its twin, and not build-and-push.yml alone:
# that narrow rule left a second provider file with no check at all the day one
# was added, which is how the first copy became an old copy listing 3 images.
#
# The direction is provider -> workflow. .github/workflows/ may hold a file that
# the provider directory does not — validate.yml and pr-review.yml are both
# provider-native and have no source-of-truth copy — so the reverse direction is
# not a rule here.
PROVIDER_DIRECTORY=".ci/providers/github"
WORKFLOW_DIRECTORY=".github/workflows"

# What that directory holds, as a literal. The comparison below is discovered by
# a glob, so a file added tomorrow is compared with no edit here — and a glob
# that matched nothing would leave a green result that read no file at all. This
# list is what makes the set non-empty, and it is the 1 line to edit when a
# provider file is added or renamed.
EXPECTED_PROVIDER_FILES=(
  "build-and-push.yml"
  "security-nightly.yml"
  "weekly-bumps.yml"
)

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. the library declares the sanctioned set --------
# Read the VALUE, not the text of the line. A declaration is only worth
# anything if the running shell ends up holding it.
lib_probe_status=0
lib_probe_value=""
lib_probe_value="$(PROJECT_ROOT="$REPO_ROOT" bash -c '
  source "$1"
  printf "%s" "${SANCTIONED_PLATFORMS:-<undeclared>}"
' probe "$REPO_ROOT/_ctl/lib.sh")" || lib_probe_status=$?

if [[ "$lib_probe_status" -ne 0 ]]; then
  fail_check "lib_declares_SANCTIONED_PLATFORMS" \
    "sourcing _ctl/lib.sh exited ${lib_probe_status}; its stderr is above" \
    "partial value read: ${lib_probe_value}"
else
  assert_equal "lib_declares_SANCTIONED_PLATFORMS" "$SANCTIONED" "$lib_probe_value" \
    "_ctl/lib.sh must declare SANCTIONED_PLATFORMS as the single source of truth"
fi

# -------- 2. every PLATFORMS* in the workflow repeats it --------
platform_lines=""
platform_lines_status=0
platform_lines="$(grep -E '^[[:space:]]+PLATFORMS[A-Z_]*:' "$WORKFLOW")" || platform_lines_status=$?

if [[ "$platform_lines_status" -ne 0 || -z "$platform_lines" ]]; then
  # No key found means the test is reading the wrong file or the wrong shape.
  # That is a failure, never a silent pass over an empty set.
  fail_check "workflow_declares_at_least_one_PLATFORMS_key" \
    "no line matching '^[[:space:]]+PLATFORMS[A-Z_]*:' in ${WORKFLOW}" \
    "grep exited ${platform_lines_status}"
else
  pass_check "workflow_declares_at_least_one_PLATFORMS_key"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    trimmed="${line#"${line%%[![:space:]]*}"}"
    key="${trimmed%%:*}"
    value="${trimmed#*:}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    assert_equal "workflow_${key}_is_the_sanctioned_set" "$SANCTIONED" "$value" \
      "in ${WORKFLOW}"
  done <<< "$platform_lines"
fi

# -------- 3. EVERY provider copy is byte-identical to its workflow --------
# The 2 build-and-push.yml files drifted in commit d9089b2, which added 5
# `timeout-minutes: 90` blocks to the workflow and to neither copy of the
# provider file, while .claude/rules/00-identity.md called them identical byte
# for byte. Nothing checked it, so nothing said so.
#
# The rule now covers every file of the provider directory rather than that 1
# pair. The narrow version had the same hole one level up: a second provider
# file got no check on the day it was added, and .ci/providers/README.md said so
# in prose — "a second provider file added here gets no such check until you add
# 1 for it". A rule that has to be extended by hand for each new file is a rule
# that will not be.
provider_files=""
for path in "$REPO_ROOT/$PROVIDER_DIRECTORY"/*; do
  [[ -f "$path" ]] || continue
  provider_files="${provider_files:+${provider_files}
}$(basename "$path")"
done

# joined <element...> — 1 element per line, sorted, for a set comparison.
function joined() {
  printf '%s\n' "$@" | sort
}

assert_equal "the_provider_directory_holds_the_expected_files" \
  "$(joined "${EXPECTED_PROVIDER_FILES[@]}")" \
  "$(printf '%s\n' "$provider_files" | sort)" \
  "either a provider file was added, renamed or deleted — and this list is what you edit —" \
  "or the glob in this test stopped matching, which would make the comparison below" \
  "pass over an empty set of files"

if [[ -z "$provider_files" ]]; then
  fail_check "the_provider_directory_holds_at_least_one_file" \
    "no file under ${PROVIDER_DIRECTORY}" \
    "the comparison below reads that set, so an empty one checks nothing"
else
  pass_check "the_provider_directory_holds_at_least_one_file"
fi

while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  provider_path="$REPO_ROOT/$PROVIDER_DIRECTORY/$name"
  workflow_path="$REPO_ROOT/$WORKFLOW_DIRECTORY/$name"
  check_name="provider_copy_of_${name}_is_byte_identical_to_the_workflow"

  if [[ ! -f "$workflow_path" ]]; then
    fail_check "$check_name" \
      "${PROVIDER_DIRECTORY}/${name} has no twin at ${WORKFLOW_DIRECTORY}/${name}" \
      "the provider directory is the source of truth and the provider reads the other path," \
      "so a file that exists only here is a workflow that never runs"
    continue
  fi

  cmp_status=0
  cmp_message=""
  cmp_message="$(cmp "$provider_path" "$workflow_path" 2>&1)" || cmp_status=$?
  if [[ "$cmp_status" -eq 0 ]]; then
    pass_check "$check_name"
  else
    diff_status=0
    diff_text=""
    diff_text="$(diff -u "$provider_path" "$workflow_path")" || diff_status=$?
    fail_check "$check_name" \
      "cmp exited ${cmp_status}: ${cmp_message}" \
      "diff exited ${diff_status}; the drift is:" \
      "$diff_text"
  fi
done <<< "$provider_files"

# -------- 4. no forbidden token on the named build path --------
missing_files=""
for relative in "${BUILD_PATH_FILES[@]}"; do
  if [[ ! -f "$REPO_ROOT/$relative" ]]; then
    missing_files="${missing_files:+${missing_files}
}${relative}"
  fi
done
if [[ -n "$missing_files" ]]; then
  fail_check "every_named_build_path_file_exists" \
    "the file list in this test is stale; these are named but absent:" \
    "$missing_files"
else
  pass_check "every_named_build_path_file_exists"
fi

for token in "${FORBIDDEN_TOKENS[@]}"; do
  hits=""
  for relative in "${BUILD_PATH_FILES[@]}"; do
    [[ -f "$REPO_ROOT/$relative" ]] || continue
    file_hits=""
    hit_status=0
    file_hits="$(grep -nF -- "$token" "$REPO_ROOT/$relative")" || hit_status=$?
    if [[ "$hit_status" -eq 0 ]]; then
      while IFS= read -r hit; do
        [[ -z "$hit" ]] && continue
        hits="${hits:+${hits}
}${relative}:${hit}"
      done <<< "$file_hits"
    fi
  done
  # A token name is part of the check name, so a reader sees which one failed.
  check_name="no_${token}_on_the_named_build_path"
  if [[ -z "$hits" ]]; then
    pass_check "$check_name"
  else
    fail_check "$check_name" \
      "'${token}' still appears on the build path:" \
      "$hits"
  fi
done

# -------- 5. the base image does not pin a build platform in its FROM --------
# `FROM --platform=${BUILDPLATFORM:-linux/amd64} ubuntu:24.04` is the mechanical
# cause of the mislabelled arm64 image: it pins the userland to the BUILD host's
# architecture while buildx labels the result with the TARGET platform. Removing
# arm64 without removing this line reproduces the same defect in the opposite
# direction on an Apple Silicon host.
from_hits=""
from_status=0
from_hits="$(grep -nE '^[[:space:]]*FROM[[:space:]]+--platform=' "$REPO_ROOT/base/Dockerfile")" || from_status=$?
if [[ "$from_status" -ne 0 ]]; then
  pass_check "base_Dockerfile_FROM_pins_no_platform"
else
  fail_check "base_Dockerfile_FROM_pins_no_platform" \
    "base/Dockerfile still pins a platform on a FROM line:" \
    "$from_hits" \
    "want: FROM ubuntu:24.04"
fi

test_summary "$TEST_NAME"
