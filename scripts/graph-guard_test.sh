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
#   3. The verb's directory vocabulary is a strict SUPERSET of the names spelled in `.nxignore`, and
#      EVERY entry of it is exercised by planting a real fixture in that directory and requiring the
#      verb to go red. A vocabulary narrowed to one entry is caught, because each entry has its own
#      assertion rather than one representative standing in for all of them.
#   4. The verb's `.nxignore` COVERAGE clause is exercised by removing one pattern from the file and
#      requiring the verb to go red. That clause is the only one with anything to say on a tree that
#      carries no fixture, which is the state of eden `main`.
#   5. The verb REFUSES a duplicate project name, and REFUSES a submodule that is not checked out.
#      Both are executed against planted inputs, never inferred from the source text.
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
# The directory names the VERB must recognise that `.nxignore` does NOT spell. Each one is an ESCAPE:
# a fixture placed there reaches the graph, and the verb is the only thing that can catch it. Every
# entry gets its own executed assertion below — a single representative was not enough, because the
# verb's vocabulary could be narrowed to that one entry with nothing going red.
uncovered_dirs=("_fixtures" "test-fixtures")

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

printf -- '-- the verb, EXECUTED --\n'

# WHY THESE RUN THE VERB INSTEAD OF READING IT. An earlier version of this section grepped
# `.ci/ctl.sh` for marker strings, and a refutation defeated it by moving each string into a comment:
# the verb was regressed to the very defects the checks existed to stop, and this file stayed green
# while printing a certification that was false as it printed. A check a comment can satisfy is not
# a check.
#
# A LATER refutation defeated the first fix too, and that is why the loops below are loops. The
# executed assertions covered 2 of the verb's 4 clauses, so narrowing the verb's directory vocabulary
# to a single entry — or neutering its `.nxignore` coverage clause outright — left every assertion
# green. One representative input cannot hold a rule that quantifies over a set. So EVERY entry of
# the vocabulary gets its own planted fixture, and the coverage clause gets a mangled `.nxignore`.
#
# Everything planted is swept by the trap, on every signal that can be trapped.

guard() { ( cd "$repository_root" && bash .ci/ctl.sh graph-guard ) >/dev/null 2>&1; }

# nx is required. A missing tool is a FAILURE, never a skip: this suite runs inside
# ghcr.io/gophersys/base in the `fast` lane, where the workspace is installed.
if [[ ! -x "${repository_root}/node_modules/.bin/nx" ]] && ! command -v nx >/dev/null 2>&1; then
  printf '  FAIL  nx is available to execute the verb\n' >&2
  printf '          no nx on PATH and no node_modules/.bin/nx — this gate cannot be tested, which is a failure, not a skip\n' >&2
  printf 'graph-guard_test: 1 failure(s)\n' >&2
  exit 1
fi

selftest_root="${repository_root}/libs/.graph-guard-selftest"
hidden_git=""
nxignore_backup=""

interrupted=0
sweep() {
  local rc=$?
  rm -rf "$selftest_root"
  if [[ -n "$nxignore_backup" && -f "$nxignore_backup" ]]; then
    cp "$nxignore_backup" "$nxignore"
    rm -f "$nxignore_backup"
  fi
  if [[ -n "$hidden_git" && -e "${hidden_git}.graph-guard-selftest" ]]; then
    mv "${hidden_git}.graph-guard-selftest" "$hidden_git"
  fi
  # The restore is VERIFIED, not assumed. Leaving a submodule without its .git breaks the checkout.
  if [[ -n "$hidden_git" && ! -e "$hidden_git" ]]; then
    printf 'graph-guard_test: FATAL — could not restore %s. Run: mv %s.graph-guard-selftest %s\n' \
      "$hidden_git" "$hidden_git" "$hidden_git" >&2
  fi
  # A run cut short is a run that judged nothing, and it must never report success. bash runs this
  # EXIT trap on a trapped signal too, and the trap's own status would otherwise become the script's:
  # measured, an interrupted run exited 0 after 2 of its 13 assertions. The signal traps below record
  # the conventional 128+n status and this line forces it.
  if [[ $interrupted -ne 0 ]]; then
    printf 'graph-guard_test: INTERRUPTED before it finished — reporting %d, never success\n' "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
# EXIT alone made an INTERRUPTED run exit 0: bash runs the EXIT trap on SIGINT and the trap's own
# status becomes the script's, so a test killed after 2 of its assertions reported SUCCESS — a skip
# reading as a pass, which is the failure this repository refuses everywhere else. Each signal is
# trapped explicitly and re-raises the conventional 128+n status.
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP

# plant <relative-path-under-selftest_root> <project-name> [extra-file-basename]
plant() {
  local rel="$1" name="$2" extra="${3:-}"
  mkdir -p "${selftest_root}/${rel}"
  printf '{"name":"%s"}\n' "$name" > "${selftest_root}/${rel}/project.json"
  if [[ -n "$extra" ]]; then
    printf '{"name":"%s-pkg","version":"0.0.0"}\n' "$name" > "${selftest_root}/${rel}/${extra}"
  fi
}

# ANTI-VACUITY FIRST, AND IT ABORTS. If the verb does not pass on the untouched tree, every red below
# could be red for that unrelated reason, and each would print `ok` while proving nothing. A previous
# round measured exactly that: 3 assertions certified themselves against a failure they had not
# caused. So this one exits the section rather than continuing.
if guard; then
  report_ok "the verb PASSES on the untouched tree (so the reds below mean something)"
else
  report_fail "the verb passes on the untouched tree" \
    "graph-guard exited non-zero before anything was planted — the rest of this section is ABORTED, because a red it cannot explain would certify itself"
  printf '\n'
  printf 'graph-guard_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi

# A. EVERY UNCOVERED directory of the verb's vocabulary is exercised, one assertion each.
#    These have no `.nxignore` pattern, so the VERB is their only defence — narrowing its regex to
#    one entry must not leave the others silent.
for d in "${uncovered_dirs[@]}"; do
  covering=()
  for p in "${patterns[@]}"; do
    [[ "$p" == *"/${d}/"* ]] && covering+=("$p")
  done
  if [[ ${#covering[@]} -gt 0 ]]; then
    report_fail "'${d}' is uncovered by .nxignore (so the verb is its only defence)" \
      "it now has a pattern, so this assertion no longer tests the verb: ${covering[0]}"
    continue
  fi
  rm -rf "$selftest_root"
  plant "esc-${d}/${d}/one" "graph-guard-selftest-esc-${d}"
  if guard; then
    report_fail "a fixture in the UNCOVERED directory '${d}' is caught by the verb" \
      "it entered eden's graph and graph-guard exited 0 — the verb's fixture vocabulary has lost '${d}'"
  else
    report_ok "a fixture in the UNCOVERED directory '${d}' is caught by the verb"
  fi
  rm -rf "$selftest_root"
done

# B. EVERY COVERED directory is excluded by `.nxignore`, and the verb still passes. Planted together
#    in one run: they are held by the pattern file, not by the verb's regex, so one run is enough to
#    prove the globs match and no run of them can be traded against another.
rm -rf "$selftest_root"
for d in "${ignored_dirs[@]}"; do
  plant "cov/${d}/one" "graph-guard-selftest-cov-${d}" "package.json"
done
if guard; then
  report_ok "a fixture in each of the ${#ignored_dirs[@]} COVERED directories is excluded, and the verb passes"
else
  report_fail "a fixture in each COVERED directory is excluded" \
    "one of ${ignored_dirs[*]} was not excluded by .nxignore and graph-guard exited non-zero"
fi
rm -rf "$selftest_root"

# C. The verb's `.nxignore` COVERAGE clause really runs. On a tree with no fixture this is the ONLY
#    clause with anything to say, and it was possible to neuter it in the verb while every assertion
#    here stayed green — because assertions 1-5 read the FILE and none of them read the VERB.
nxignore_backup="${nxignore}.graph-guard-selftest-backup"
cp "$nxignore" "$nxignore_backup"
grep -v '^libs/\*\*/testdata/\*\*/package\.json$' "$nxignore_backup" > "$nxignore"
if guard; then
  report_fail "the verb REFUSES a .nxignore that is missing a required pattern" \
    "one of the 36 patterns was removed and graph-guard exited 0 — its coverage clause is not running"
else
  report_ok "the verb REFUSES a .nxignore that is missing a required pattern"
fi
cp "$nxignore_backup" "$nxignore"
rm -f "$nxignore_backup"
nxignore_backup=""

# D. A duplicate project NAME is REFUSED. This is the eden#14 collision. `nx graph --file` exits 0
#    and silently deduplicates it, so a verb asserting with that reader tolerates the very defect it
#    exists to catch; only `nx show projects` refuses.
rm -rf "$selftest_root"
plant "dup-a" "graph-guard-selftest-dup"
plant "dup-b" "graph-guard-selftest-dup"
if guard; then
  report_fail "a duplicate project name is REFUSED" \
    "two projects both named graph-guard-selftest-dup, and graph-guard exited 0"
else
  report_ok "a duplicate project name is REFUSED"
fi
rm -rf "$selftest_root"

# E. A submodule PRESENT but not CHECKED OUT is refused. `git clone` without --recursive leaves the
#    mount point as an empty directory, which a bare `[[ -d ]]` passes while 39 projects are absent.
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
