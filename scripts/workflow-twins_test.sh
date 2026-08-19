#!/usr/bin/env bash
#
# scripts/workflow-twins_test.sh — repository rule: every CI workflow is written 2 times, and the 2
# copies must be byte-identical.
#
# .ci/providers/README.md states the rule and states why it is fragile: the 2 copies are regular
# files, not symlinks, a person keeps them equal by hand, cictl does not render them here yet, and
# they HAVE drifted apart before. Nothing in the tree checked it. This test is that check, and the
# change that introduced it is exactly the change that could have made the mistake: it edits both
# copies of harness-conformance.yml.
#
# WHAT A GREEN RUN PROVES:
#   - the same set of workflow names is on both sides — a file added or deleted on one side only is
#     a failure that names the file;
#   - each pair is byte-identical under cmp — a 1-character edit on one side is a failure that names
#     the file and the byte;
#   - neither side is empty, and neither side is a symlink. Two empty files compare equal, and cmp
#     follows a symlink, so both shapes would pass a naive twin check while the rule is broken.
#
# SCOPE — read this before you read a green run as more than it is.
#   COVERED: *.yml and *.yaml in .github/workflows/ and in .ci/providers/github/.
#   NOT COVERED: whether a workflow is CORRECT, whether GitHub accepts it, any other provider
#     directory (there is 1 today), and any non-YAML file in either directory.
#
# It reads files only. It runs no workflow and no CI system. Run it directly:
#   bash scripts/workflow-twins_test.sh
# It exits non-zero when any pair mismatches. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
native_directory="${repository_root}/.github/workflows"
provider_directory="${repository_root}/.ci/providers/github"

# The tree holds 5 workflows. A scan that reads fewer has lost a file or lost its glob, and a twin
# test over 0 pairs is the green that proves nothing.
minimum_pairs=5

for directory in "$native_directory" "$provider_directory"; do
  if [[ ! -d "$directory" ]]; then
    printf 'workflow-twins_test: FAILED — the directory does not exist: %s\n' "$directory" >&2
    exit 1
  fi
done

fails=0

report_fail() {
  local name="$1"
  shift
  printf '  FAIL  %s\n' "$name" >&2
  local problem
  for problem in "$@"; do
    printf '          %s\n' "$problem" >&2
  done
  fails=$((fails + 1))
}

# workflow_names <directory> — the base name of each *.yml / *.yaml in it, sorted, one per line. An
# unmatched glob stays literal under bash, so each candidate is tested before it is used.
workflow_names() {
  local directory="$1" candidate
  for candidate in "$directory"/*.yml "$directory"/*.yaml; do
    [[ -f "$candidate" ]] || continue
    printf '%s\n' "${candidate##*/}"
  done | sort
}

native_names=()
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  native_names+=("$name")
done < <(workflow_names "$native_directory")

provider_names=()
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  provider_names+=("$name")
done < <(workflow_names "$provider_directory")

printf -v native_list '%s\n' "${native_names[@]+"${native_names[@]}"}"
printf -v provider_list '%s\n' "${provider_names[@]+"${provider_names[@]}"}"

# --- the set is the same on both sides ------------------------------------------------------------
printf -- '-- the workflow set --\n'
set_problems=()
for name in "${native_names[@]+"${native_names[@]}"}"; do
  if [[ $'\n'"$provider_list" != *$'\n'"$name"$'\n'* ]]; then
    set_problems+=("${name} is in .github/workflows/ and NOT in .ci/providers/github/")
  fi
done
for name in "${provider_names[@]+"${provider_names[@]}"}"; do
  if [[ $'\n'"$native_list" != *$'\n'"$name"$'\n'* ]]; then
    set_problems+=("${name} is in .ci/providers/github/ and NOT in .github/workflows/")
  fi
done
if [[ ${#set_problems[@]} -ne 0 ]]; then
  set_problems+=('every workflow is written 2 times; edit both copies together (.ci/providers/README.md)')
  report_fail 'set equality: the 2 sides hold the same workflow names' "${set_problems[@]}"
else
  printf '  ok    set equality: %d name(s) on both sides\n' "${#native_names[@]}"
fi

# --- the scan really read the tree ----------------------------------------------------------------
if [[ ${#native_names[@]} -lt $minimum_pairs ]]; then
  report_fail 'scan guard: the workflow set is smaller than the tree' \
    "read ${#native_names[@]} workflow(s) in .github/workflows/, want >= ${minimum_pairs}" \
    'a twin test over too few pairs is a green that proves nothing'
fi

# --- each pair is byte-identical, non-empty and a regular file -------------------------------------
printf -- '-- the pairs --\n'
compared=0
for name in "${native_names[@]+"${native_names[@]}"}"; do
  native_file="${native_directory}/${name}"
  provider_file="${provider_directory}/${name}"
  [[ -f "$provider_file" ]] || continue

  pair_problems=()
  for side in "$native_file" "$provider_file"; do
    if [[ -L "$side" ]]; then
      pair_problems+=("${side#"${repository_root}/"} is a symlink; the 2 copies are regular files (git mode 100644), and cmp follows a symlink")
    fi
    if [[ ! -s "$side" ]]; then
      pair_problems+=("${side#"${repository_root}/"} is empty; 2 empty twins compare equal and prove nothing")
    fi
  done

  compared=$((compared + 1))
  cmp_output="$(cmp -- "$native_file" "$provider_file" 2>&1)" && cmp_status=0 || cmp_status=$?
  if [[ $cmp_status -gt 1 ]]; then
    report_fail "pair: ${name}" "cmp exited ${cmp_status}: ${cmp_output}"
    continue
  fi
  if [[ $cmp_status -eq 1 ]]; then
    pair_problems+=("the 2 copies differ: ${cmp_output}" \
      ".github/workflows/${name} and .ci/providers/github/${name} must be byte-identical")
  fi

  if [[ ${#pair_problems[@]} -ne 0 ]]; then
    report_fail "pair: ${name}" "${pair_problems[@]}"
  else
    printf '  ok    pair: %-30s identical (%s bytes)\n' "$name" "$(wc -c <"$native_file" | tr -d ' ')"
  fi
done

if [[ $compared -eq 0 ]]; then
  report_fail 'scan guard: no pair was compared' \
    "native=${#native_names[@]} provider=${#provider_names[@]}" \
    'cmp ran on nothing, so nothing was proven'
fi

if [[ $fails -ne 0 ]]; then
  printf '\nworkflow-twins_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nworkflow-twins_test: all assertions passed (%d twin pair(s))\n' "$compared"
