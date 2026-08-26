#!/usr/bin/env bash
#
# scripts/graph-guard_test.sh — the holder of `.ci/ctl.sh graph-guard` and of `.nxignore`.
#
# WHY THIS FILE EXISTS. `graph-guard` is a gate, and a gate with no test is a claim. This one landed
# once with none, and an adversarial refutation then found three defects in it that a test of this
# shape would have caught on the commit that introduced them:
#
#   - its "the graph builds" clause was written on `nx graph --file`, which exits 0 and SILENTLY
#     DEDUPLICATES a duplicate-name graph — the exact collision the gate exists to catch;
#   - its liveness clause tested `[[ -d ]]` on each submodule, which passes on the EMPTY DIRECTORY
#     that `git clone` without `--recursive` leaves behind, so 39 missing projects read as OK;
#   - it covered `project.json` alone while `nx.json` enables `@nx/js/typescript`, which infers a
#     project from `package.json` + `tsconfig*.json`.
#
# WHAT A GREEN RUN PROVES — and every one of these is an ANTI-VACUITY assertion, because the failure
# mode of this gate is passing while reading nothing:
#
#   1. `.nxignore` exists and holds every one of the 36 patterns the verb requires. Deleting the
#      file, or dropping one line of it, is RED — including on a tree that carries no fixture at all,
#      which is the state of eden `main` and was the state of the run used to justify merging it.
#   2. The pattern set is COMPLETE over the 3 file types that define an nx project here. A set that
#      lists only `project.json` is RED.
#   3. The verb's own directory vocabulary is a strict SUPERSET of the directory names spelled in
#      `.nxignore`. That is the direction that fails safe: a fixture directory nobody wrote a pattern
#      for is caught by the verb as a red gate instead of entering the graph quietly.
#   4. The verb asserts graph resolution with a command that REFUSES a duplicate-name graph. It
#      greps `.ci/ctl.sh` for the strict reader, because this is the defect that shipped.
#
# SCOPE — read this before you read a green run as more than it is.
#   COVERED: the contract between `.ci/ctl.sh graph-guard` and `.nxignore`, by reading both files.
#   NOT COVERED: running nx. This test builds no project graph — nx is not installed in every
#     context that runs the `repository-scripts` suite, and a test that needs a 49-project graph is
#     not a unit test. The live behaviour is exercised by the verb itself in the `fast` lane of
#     on-pr.yml and in on-push.yml, which is where a real graph exists.
#
# It reads files only. Run it directly:
#   bash scripts/graph-guard_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
nxignore="${repository_root}/.nxignore"
ctl="${repository_root}/.ci/ctl.sh"

# The contract, written here as LITERALS and never read out of the files under test. A test that
# derives its expectation from its subject agrees with a wrong subject too — the same rule
# `_ctl/tests/platform-policy.test.sh` states in the .devcontainer submodule.
submodules=(".devcontainer" "libs" "infrastructure")
ignored_dirs=("fixture" "fixtures" "__fixtures__" "testdata")
project_files=("project.json" "package.json" "tsconfig*.json")
# Directory names the VERB must recognise beyond the ones .nxignore spells. These are the escapes:
# a fixture in one of them has no pattern, reaches the graph, and must be caught by the verb.
verb_only_dirs=("_fixtures" "test-fixtures")

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

report_ok() { printf '  ok    %s\n' "$1"; }

for f in "$nxignore" "$ctl"; do
  if [[ ! -f "$f" ]]; then
    printf 'graph-guard_test: FAILED — the file does not exist: %s\n' "$f" >&2
    exit 1
  fi
done

# The lines of .nxignore that are patterns: comments and blanks are not.
mapfile -t patterns < <(grep -vE '^\s*(#|$)' "$nxignore" || true)

printf -- '-- .nxignore coverage --\n'

# 1. Every required pattern is present. 3 x 4 x 3 = 36.
expected_total=$(( ${#submodules[@]} * ${#ignored_dirs[@]} * ${#project_files[@]} ))
missing=()
for sm in "${submodules[@]}"; do
  for d in "${ignored_dirs[@]}"; do
    for pf in "${project_files[@]}"; do
      want="${sm}/**/${d}/**/${pf}"
      printf '%s\n' "${patterns[@]}" | grep -qxF -- "$want" || missing+=("$want")
    done
  done
done
if [[ ${#missing[@]} -gt 0 ]]; then
  report_fail "every required pattern is present" \
    "${#missing[@]} of ${expected_total} missing, first: ${missing[0]}"
else
  report_ok "every required pattern is present (${expected_total})"
fi

# 2. ANTI-VACUITY on the count. A file that somehow satisfied the loop above with far fewer lines
#    than the contract needs would mean the loop stopped judging.
if [[ ${#patterns[@]} -lt $expected_total ]]; then
  report_fail "the pattern file is not smaller than the contract" \
    "${#patterns[@]} pattern line(s) for ${expected_total} required patterns"
else
  report_ok "the pattern file holds at least the contracted ${expected_total} pattern(s)"
fi

# 3. All 3 project-defining file types are covered. This is BLOCKS-1 from the refutation, written as
#    a standing check: a set that lists project.json alone leaves package.json + tsconfig*.json to
#    infer a project through @nx/js/typescript.
for pf in "${project_files[@]}"; do
  count=0
  for p in "${patterns[@]}"; do
    [[ "$p" == *"/${pf}" ]] && count=$((count + 1))
  done
  if [[ $count -lt $(( ${#submodules[@]} * ${#ignored_dirs[@]} )) ]]; then
    report_fail "the file type '${pf}' is covered for every submodule and directory" \
      "found ${count} pattern(s), need $(( ${#submodules[@]} * ${#ignored_dirs[@]} ))"
  else
    report_ok "the file type '${pf}' is covered ${count} time(s)"
  fi
done

# 4. No negation line. `.nxignore` takes gitignore syntax, so a later `!pattern` RE-INCLUDES what an
#    earlier line excluded. The verb's coverage check greps for the positive line and would still
#    pass, so the hole would be invisible to it. Nothing in this repository needs a negation here.
negations=()
for p in "${patterns[@]}"; do
  [[ "$p" == '!'* ]] && negations+=("$p")
done
if [[ ${#negations[@]} -gt 0 ]]; then
  report_fail "no negation re-includes an excluded fixture file" \
    "${#negations[@]} negation line(s), first: ${negations[0]}"
else
  report_ok "no negation line re-includes an excluded fixture file"
fi

printf -- '-- the verb --\n'

# 5. The verb's directory vocabulary is a strict SUPERSET of .nxignore's. Both halves are asserted:
#    every ignored dir is recognised, AND at least one escape dir is recognised that has no pattern.
#    The refutation found these two sets IDENTICAL while a comment claimed the verb was wider, so a
#    `__fixtures__` fixture escaped both and the hole opened silently.
vocab_line="$(grep -E "^\s*local fixture_dir_re=" "$ctl" || true)"
if [[ -z "$vocab_line" ]]; then
  report_fail "the verb declares a fixture directory vocabulary" "no fixture_dir_re= line in .ci/ctl.sh"
else
  vocab_missing=()
  for d in "${ignored_dirs[@]}" "${verb_only_dirs[@]}"; do
    # `fixtures?` covers both `fixture` and `fixtures`; match on the stem for those two.
    stem="$d"
    [[ "$d" == "fixture" || "$d" == "fixtures" ]] && stem="fixtures?"
    [[ "$vocab_line" == *"$stem"* ]] || vocab_missing+=("$d")
  done
  if [[ ${#vocab_missing[@]} -gt 0 ]]; then
    report_fail "the verb recognises every ignored directory AND the escapes" \
      "not recognised: ${vocab_missing[*]}"
  else
    report_ok "the verb recognises all ${#ignored_dirs[@]} ignored directories and ${#verb_only_dirs[@]} escape(s)"
  fi
  # The strict-superset half: an escape dir must NOT have a pattern, or it is not an escape and this
  # test has stopped proving the fail-safe direction.
  not_escapes=()
  for d in "${verb_only_dirs[@]}"; do
    for p in "${patterns[@]}"; do
      [[ "$p" == *"/${d}/"* ]] && { not_escapes+=("$d"); break; }
    done
  done
  if [[ ${#not_escapes[@]} -gt 0 ]]; then
    report_fail "the escape directories are genuinely uncovered by .nxignore" \
      "these now have patterns, so the superset is no longer strict: ${not_escapes[*]}"
  else
    report_ok "the escape directories are genuinely uncovered — the verb is strictly wider"
  fi
fi

# 6. The verb asserts graph resolution with a reader that REFUSES a duplicate-name graph.
#    Measured on this workspace: `nx show projects` exits 1 on the collision that blocked eden#14,
#    while `nx graph --file` exits 0 and deduplicates it. A gate written on the second tolerates the
#    defect it exists to catch, which is what shipped and what this check holds shut.
if grep -qE 'nx_cmd show projects' "$ctl"; then
  report_ok "the verb asserts resolution with 'nx show projects' (refuses a duplicate-name graph)"
else
  report_fail "the verb asserts resolution with a reader that refuses duplicates" \
    "no 'nx_cmd show projects' in .ci/ctl.sh — 'nx graph --file' exits 0 on a duplicate-name graph"
fi

# 7. The liveness clause tests CHECKED OUT, not merely present. `[[ -d ]]` alone passes on the empty
#    directory an uninitialised submodule leaves behind.
# shellcheck disable=SC2016
# The single quotes are the point: this greps .ci/ctl.sh for the LITERAL text `$root/.git`. Expanding
# it here would search for this test's own empty $root instead of the verb's source line.
if grep -qE '\$root/\.git' "$ctl"; then
  report_ok "the liveness clause tests for a checked-out submodule (.git entry), not just a directory"
else
  report_fail "the liveness clause tests for a checked-out submodule" \
    "no '\$root/.git' test in .ci/ctl.sh — an uninitialised submodule is an empty directory that passes -d"
fi

printf '\n'
if [[ $fails -gt 0 ]]; then
  printf 'graph-guard_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'graph-guard_test: all assertions passed (%d pattern(s), %d file type(s))\n' \
  "${#patterns[@]}" "${#project_files[@]}"
