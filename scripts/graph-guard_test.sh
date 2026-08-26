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
#   NOT COVERED: the CONTENT of eden's real graph, and whether nx itself is correct. This file
#     plants synthetic projects and reads the verb's exit status; it does not audit the 49 real
#     projects. It DOES run nx, because the earlier "reads files only" scope was exactly the hole an
#     adversarial refutation walked through — see "WHY THESE RUN THE VERB" below.
#
# It plants synthetic projects under `libs/`, runs the verb, and sweeps them under an EXIT trap.
# Run it directly:
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
# The directory the escape assertion plants into. It must NOT be covered by .nxignore — that is what
# makes it an escape — and check 5 below asserts exactly that, so this literal and the planted path
# cannot drift apart.
escape_dir="_fixtures"

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

# 5. The escape directory is genuinely UNCOVERED by .nxignore. If somebody adds a pattern for it, the
#    planted escape below would be excluded, assertion 7 would go red, and the reason would be
#    obscure. Asserting it here names the cause.
covered_escape=()
for p in "${patterns[@]}"; do
  [[ "$p" == *"/${escape_dir}/"* ]] && covered_escape+=("$p")
done
if [[ ${#covered_escape[@]} -gt 0 ]]; then
  report_fail "the escape directory '${escape_dir}' is uncovered by .nxignore" \
    "it now has ${#covered_escape[@]} pattern(s), so it is no longer an escape: ${covered_escape[0]}"
else
  report_ok "the escape directory '${escape_dir}' is genuinely uncovered by .nxignore"
fi

printf -- '-- the verb, EXECUTED --\n'

# WHY THESE RUN THE VERB INSTEAD OF GREPPING IT. The previous version of this section asked whether
# `.ci/ctl.sh` CONTAINED the string `nx_cmd show projects`, and whether it contained `$root/.git`.
# A refutation defeated both by moving the string into a comment: the verb was regressed to exactly
# the two defects the checks existed to stop, and this file still printed
# "ok  the verb asserts resolution with 'nx show projects'" — a certification that was false at the
# moment it was printed. A check that a comment can satisfy is not a check.
#
# So each assertion below PLANTS a real input, RUNS `bash .ci/ctl.sh graph-guard`, and reads its exit
# status. Everything planted is swept by the EXIT trap, whatever happens.

guard() { ( cd "$repository_root" && bash .ci/ctl.sh graph-guard ) >/dev/null 2>&1; }

# nx is required. A missing tool is a FAILURE, never a skip: this suite runs inside
# ghcr.io/gophersys/base in the `fast` lane, where the workspace is installed.
if [[ ! -x "${repository_root}/node_modules/.bin/nx" ]] && ! command -v nx >/dev/null 2>&1; then
  printf '  FAIL  nx is available to execute the verb\n' >&2
  printf '          no nx on PATH and no node_modules/.bin/nx — this gate cannot be tested, which is a failure, not a skip\n' >&2
  printf 'graph-guard_test: 1 failure(s)\n' >&2
  exit 1
fi

planted=()
hidden_git=""
sweep() {
  local p
  for p in "${planted[@]}"; do rm -rf "$p"; done
  if [[ -n "$hidden_git" && -e "${hidden_git}.graph-guard-selftest" ]]; then
    mv "${hidden_git}.graph-guard-selftest" "$hidden_git"
  fi
  # The restore is VERIFIED, not assumed. Leaving a submodule without its .git would break the
  # developer's checkout, so a failed restore must be loud.
  if [[ -n "$hidden_git" && ! -e "$hidden_git" ]]; then
    printf 'graph-guard_test: FATAL — could not restore %s. Run: mv %s.graph-guard-selftest %s\n' \
      "$hidden_git" "$hidden_git" "$hidden_git" >&2
  fi
}
trap sweep EXIT

# ANTI-VACUITY FIRST. If the verb does not pass on the untouched tree, every red below could be red
# for an unrelated reason and this whole section would prove nothing.
if guard; then
  report_ok "the verb PASSES on the untouched tree (so the reds below mean something)"
else
  report_fail "the verb passes on the untouched tree" \
    "graph-guard exited non-zero before anything was planted — the reds below prove nothing"
fi

# 6. A duplicate project NAME must be REFUSED. This is the eden#14 collision, and the defect this
#    replaces: `nx graph --file` exits 0 and silently deduplicates it, so a verb asserting with that
#    reader tolerates the very thing it exists to catch.
dup_a="${repository_root}/libs/.graph-guard-selftest-dup-a"
dup_b="${repository_root}/libs/.graph-guard-selftest-dup-b"
planted+=("$dup_a" "$dup_b")
mkdir -p "$dup_a" "$dup_b"
printf '{"name":"graph-guard-selftest-dup"}\n' > "${dup_a}/project.json"
printf '{"name":"graph-guard-selftest-dup"}\n' > "${dup_b}/project.json"
if guard; then
  report_fail "a duplicate project name is REFUSED" \
    "two projects both named graph-guard-selftest-dup, and graph-guard exited 0"
else
  report_ok "a duplicate project name is REFUSED"
fi
rm -rf "$dup_a" "$dup_b"

# 7. A fixture in a directory .nxignore does NOT cover must be caught by the verb. This is the
#    strict-superset property: an escape is a red gate, never a quiet hole.
esc="${repository_root}/libs/.graph-guard-selftest-esc/${escape_dir}/one"
planted+=("${repository_root}/libs/.graph-guard-selftest-esc")
mkdir -p "$esc"
printf '{"name":"graph-guard-selftest-escape"}\n' > "${esc}/project.json"
if guard; then
  report_fail "a fixture in an UNCOVERED directory is caught by the verb" \
    "libs/.graph-guard-selftest-esc/${escape_dir}/one entered the graph and graph-guard exited 0"
else
  report_ok "a fixture in an UNCOVERED directory is caught by the verb"
fi
rm -rf "${repository_root}/libs/.graph-guard-selftest-esc"

# 8. A fixture in a COVERED directory must be excluded, and the verb must still pass. Without this
#    the suite could be satisfied by a verb that simply always fails.
cov="${repository_root}/libs/.graph-guard-selftest-cov/testdata/one"
planted+=("${repository_root}/libs/.graph-guard-selftest-cov")
mkdir -p "$cov"
printf '{"name":"graph-guard-selftest-covered"}\n' > "${cov}/project.json"
printf '{"name":"graph-guard-selftest-covered-pkg","version":"0.0.0"}\n' > "${cov}/package.json"
if guard; then
  report_ok "a fixture in a COVERED directory is excluded and the verb passes"
else
  report_fail "a fixture in a COVERED directory is excluded" \
    "libs/.graph-guard-selftest-cov/testdata/one should have been ignored, and graph-guard exited non-zero"
fi
rm -rf "${repository_root}/libs/.graph-guard-selftest-cov"

# 9. A submodule that is PRESENT but not CHECKED OUT must be refused. `git clone` without
#    --recursive leaves the mount point as an empty directory, which a `[[ -d ]]` test passes while
#    39 of the 49 projects are absent.
hidden_git="${repository_root}/.devcontainer/.git"
if [[ -e "$hidden_git" ]]; then
  mv "$hidden_git" "${hidden_git}.graph-guard-selftest"
  if guard; then
    report_fail "an uninitialised submodule is REFUSED" \
      ".devcontainer has no .git entry and graph-guard exited 0"
  else
    report_ok "an uninitialised submodule is REFUSED"
  fi
  mv "${hidden_git}.graph-guard-selftest" "$hidden_git"
  hidden_git=""
else
  report_fail "an uninitialised submodule is REFUSED" \
    ".devcontainer/.git does not exist, so this assertion could not be made"
fi

printf '\n'
if [[ $fails -gt 0 ]]; then
  printf 'graph-guard_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'graph-guard_test: all assertions passed (%d pattern(s), %d file type(s))\n' \
  "${#patterns[@]}" "${#project_files[@]}"
