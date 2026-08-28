#!/usr/bin/env bash
#
# scripts/verbs-check_test.sh — the holder of `bash .ci/ctl.sh verbs --check` (blueprint P0-6c).
#
# WHAT THE VERB IS FOR. Every project in eden's graph belongs to exactly one CLASS, resolved from
# the tree rather than from a hand-kept list: `go.mod` -> Go, `package.json` + `tsconfig*.json` ->
# TypeScript, neither -> bash/config, BOTH -> ambiguous, which is a defect. A class owes a set of
# verbs; a project may also declare a verb outside its class when it genuinely runs one (the six
# `.devcontainer` image units really do `docker build`). `verbs --check` holds three properties
# over that, and `.ci/verb-exceptions.txt` is the SHRINK-ONLY register of every difference that is
# known and accepted — the `SUBSTRATE_ENV_REGISTER` pattern of `libs/.ci/ctl.sh:91-127`, where a
# row whose cause has gone away is STALE and fails the lane until it is deleted. A register that
# cannot go stale rots into a permanent skip, which is the same nothing as a gate that cannot fail.
#
# THE THREE CLAUSES, AND EACH IS ASSERTED SEPARATELY AND IDENTIFIED BY ITS MESSAGE. That rule is
# scripts/graph-guard_test.sh's, and refutation #5 is why: an assertion that reads only the exit
# status passes while a DIFFERENT clause is the one firing, so a neutered clause looks proven.
# Every case below stages a full COPY of the tree, mutates exactly ONE thing, and demands a red
# that NAMES that thing.
#
#   clause 1  one class per project    — plant go.mod beside package.json+tsconfig.json -> RED
#   clause 2  R-BODY                   — a closed-set target's command must be exactly
#                                        `bash ./ctl.sh <verb>`; change one -> RED
#   clause 3a unregistered difference  — the blueprint's certified NEGATIVE exit proof, verbatim:
#                                        add a no-op `typecheck` to a Go module -> RED
#   clause 3b a STALE register row     — repair a registered difference (declare the `validate` a
#                                        Go module owes) and the row that excused it -> RED
#   clause 3c the clean tree           — exit 0, and it reports the REAL project count read from
#                                        `.ci/graph-roster.txt`, never a second census
#
# THE MESSAGE CONTRACT THIS FILE IMPOSES, stated here so the implementer can meet it rather than
# guess it. Each red must put, ON ONE SINGLE LINE: the mutated project (its roster name or its
# root), the verb where a verb is involved, and one word identifying WHICH clause fired. That is
# the blueprint's own wording — "RED naming project and verb" — plus the clause identity that
# graph-guard_test.sh's rule (b) requires. A line of the shape
#
#     [error] verbs --check: libs/go/envelope declares 'typecheck', which its class does not own
#             and .ci/verb-exceptions.txt does not register
#
# satisfies it. The clause words are broad alternations, listed at each case below: naming is
# strict, wording is not. ONE LINE rather than "anywhere in the output" is deliberate and measured
# — see the comment on `expect_red`.
#
# WHAT THIS FILE DOES NOT DO. It does not write `.ci/verb-exceptions.txt` — that register is the
# implementer's file, and a test that authored its own expectation would be a gate repairing its
# own expectation (the defect `cmd_graph_roster_update` refuses to be). It asserts the register's
# PROPERTIES: unregistered differences red, repaired rows red, and the clean tree green.
#
# SCOPE — read this before reading a green run as more than it is.
#   COVERED: the exit status and the message of `verbs --check` over a staged copy of the real 49
#     projects, under 4 single-thing mutations and once clean.
#   NOT COVERED: clause 4 of the blueprint (a `__verbs` dispatch probe, DEFERRED — 19 dispatcher
#     bodies, 6 of them in `infrastructure`, whose sourcing seam does not exist); whether any verb
#     a project declares actually PASSES; the CONTENT of the register's rows and their counts, which
#     the plan states as 47 OWES-GAP + 7 EXTRA and which this file deliberately does not pin,
#     because a register the test also authored proves nothing.
#
# HERMETIC. Every run is a COPY under `mktemp -d` (`cp -RL`, never a symlink) with `git init`, so
# the verb's own `git rev-parse --show-toplevel` resolves inside the staged tree and no mutation
# can reach the real one.
#
# Run it directly:  bash scripts/verbs-check_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
ctl_source="${repository_root}/.ci/ctl.sh"
roster="${repository_root}/.ci/graph-roster.txt"
bash_binary="$(command -v bash)"

# The roster holds 49 rows today. The count `verbs --check` must report is READ from the roster at
# run time (one concept, one home), and this literal is the guard that the roster itself has not
# silently shrunk under both of them.
expected_roster_rows=49

# The subjects, as LITERALS, each with a freshness preflight below.
ambiguous_root="libs/go/gitrepository"        # Go today; the mutation makes it Go AND TypeScript
r_body_root="libs/go/observability"           # its `build` command is the R-BODY the mutation breaks
r_body_verb="build"
extra_root="libs/go/envelope"                 # the certified negative proof: a Go module gains `typecheck`
extra_verb="typecheck"
stale_root="libs/go/codeinsight"              # a Go module that owes `validate` and does not declare it
stale_verb="validate"
r_body_expected_command="bash ./ctl.sh ${r_body_verb}"
r_body_mutation="echo eden-r-body-probe"

fails=0
report_fail() {
  local name="$1"; shift
  printf '  FAIL  %s\n' "$name" >&2
  local problem
  for problem in "$@"; do printf '          %s\n' "$problem" >&2; done
  fails=$((fails + 1))
}
report_ok() { printf '  ok    %s\n' "$1"; }

for required_file in "$ctl_source" "$roster"; do
  if [[ ! -f "$required_file" ]]; then
    printf 'verbs-check_test: FAILED — the file does not exist: %s\n' "$required_file" >&2
    exit 1
  fi
done
if ! command -v jq >/dev/null 2>&1; then
  printf 'verbs-check_test: FAILED — required tool(s) missing: jq\n' >&2
  printf '          jq is in ghcr.io/gophersys/base and .ci/ctl.sh require_cmds it itself.\n' >&2
  printf '          Its absence is a broken environment, not a reason to skip.\n' >&2
  exit 1
fi

work_dir=""
interrupted=0
sweep() {
  local rc=$?
  [[ -n "$work_dir" ]] && rm -rf "$work_dir"
  if [[ $interrupted -ne 0 ]]; then
    printf 'verbs-check_test: INTERRUPTED before it finished — reporting %d, never success\n' \
      "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP

# --- the roster, read once ----------------------------------------------------------------------
roster_names=()
roster_roots=()
while IFS=$'\t' read -r roster_name roster_root; do
  [[ -n "${roster_name:-}" ]] || continue
  [[ "${roster_name:0:1}" != '#' ]] || continue
  roster_names+=("$roster_name")
  roster_roots+=("$roster_root")
done < <(grep -vE '^[[:space:]]*(#|$)' "$roster")

printf -- '-- the tree this file mutates --\n'
if [[ ${#roster_roots[@]} -ne $expected_roster_rows ]]; then
  report_fail "the roster holds ${expected_roster_rows} project row(s)" \
    "it holds ${#roster_roots[@]}" \
    'the count verbs --check must report is read from this file; a silent shrink would move both together' \
    'if the change is deliberate, update expected_roster_rows in scripts/verbs-check_test.sh with it'
else
  report_ok "the roster holds ${#roster_roots[@]} project row(s)"
fi

# root_name <root> — the roster name for a root, or the empty string.
root_name() {
  local wanted="$1" index
  for index in "${!roster_roots[@]}"; do
    if [[ "${roster_roots[index]}" == "$wanted" ]]; then printf '%s' "${roster_names[index]}"; return 0; fi
  done
  printf ''
}

has_tsconfig() {
  local candidate
  for candidate in "$1"/tsconfig*.json; do
    [[ -f "$candidate" ]] && return 0
  done
  return 1
}

# --- staleness preflight — every literal above still describes the tree --------------------------
# Without this a pointer bump turns a probe into a no-op and the clause it drives reds with a
# message that blames the verb. `scripts/graph-guard_test.sh` lost five roster rows to exactly that
# and the failure named neither the dead pair nor the file holding it.
ambiguous_name="$(root_name "$ambiguous_root")"
r_body_name="$(root_name "$r_body_root")"
extra_name="$(root_name "$extra_root")"
stale_name="$(root_name "$stale_root")"

preflight_problems=()
for pair in "${ambiguous_root}|${ambiguous_name}" "${r_body_root}|${r_body_name}" \
            "${extra_root}|${extra_name}" "${stale_root}|${stale_name}"; do
  probe_root="${pair%%|*}"
  probe_name="${pair#*|}"
  [[ -n "$probe_name" ]] || preflight_problems+=("no roster row is rooted at '${probe_root}'")
  [[ -f "${repository_root}/${probe_root}/project.json" ]] \
    || preflight_problems+=("no project.json at '${probe_root}'")
  [[ -f "${repository_root}/${probe_root}/go.mod" ]] \
    || preflight_problems+=("'${probe_root}' has no go.mod, so it is not the Go-class project this file assumes")
done
if [[ -f "${repository_root}/${ambiguous_root}/package.json" ]] || has_tsconfig "${repository_root}/${ambiguous_root}"; then
  preflight_problems+=("'${ambiguous_root}' is ALREADY TypeScript-shaped, so planting one there mutates nothing")
fi
r_body_command="$(jq -r --arg t "$r_body_verb" '.targets[$t].options.command // ""' \
  "${repository_root}/${r_body_root}/project.json")"
if [[ "$r_body_command" != "$r_body_expected_command" ]]; then
  preflight_problems+=("'${r_body_root}' target '${r_body_verb}' runs '${r_body_command}', not '${r_body_expected_command}' — the R-BODY probe would mutate the wrong thing")
fi
if jq -e --arg t "$extra_verb" '.targets | has($t)' "${repository_root}/${extra_root}/project.json" >/dev/null; then
  preflight_problems+=("'${extra_root}' ALREADY declares '${extra_verb}', so adding it mutates nothing")
fi
if jq -e --arg t "$stale_verb" '.targets | has($t)' "${repository_root}/${stale_root}/project.json" >/dev/null; then
  preflight_problems+=("'${stale_root}' ALREADY declares '${stale_verb}', so it is not a registered OWES-GAP and repairing it mutates nothing")
fi
if [[ ${#preflight_problems[@]} -ne 0 ]]; then
  report_fail 'every project this file mutates is the shape the mutation assumes' \
    "${preflight_problems[@]}" \
    'the fix is the literal block at the top of scripts/verbs-check_test.sh, updated in the same change that moved the tree'
  printf '\nverbs-check_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
report_ok "the 4 mutated projects are the shape each mutation assumes (${ambiguous_name}, ${r_body_name}, ${extra_name}, ${stale_name})"

# --- the pristine staged tree --------------------------------------------------------------------
work_dir="$(mktemp -d -t eden-verbs-check.XXXXXX)"
pristine="${work_dir}/pristine"

mkdir -p "${pristine}/.ci"
cp "$ctl_source" "${pristine}/.ci/ctl.sh"
cp "$roster" "${pristine}/.ci/graph-roster.txt"
# The register is the IMPLEMENTER's file. It is copied when it exists and never written here.
[[ -f "${repository_root}/.ci/verb-exceptions.txt" ]] \
  && cp "${repository_root}/.ci/verb-exceptions.txt" "${pristine}/.ci/verb-exceptions.txt"
if [[ -d "${repository_root}/.devcontainer/_ctl" ]]; then
  mkdir -p "${pristine}/.devcontainer"
  cp -RL "${repository_root}/.devcontainer/_ctl" "${pristine}/.devcontainer/_ctl"
fi

staged_files=0
for project_root in "${roster_roots[@]}"; do
  mkdir -p "${pristine}/${project_root}"
  for base in project.json go.mod package.json ctl.sh; do
    if [[ -f "${repository_root}/${project_root}/${base}" ]]; then
      cp "${repository_root}/${project_root}/${base}" "${pristine}/${project_root}/${base}"
      staged_files=$((staged_files + 1))
    fi
  done
  for candidate in "${repository_root}/${project_root}"/tsconfig*.json; do
    [[ -f "$candidate" ]] || continue
    cp "$candidate" "${pristine}/${project_root}/${candidate##*/}"
    staged_files=$((staged_files + 1))
  done
done
report_ok "staged a copy of ${#roster_roots[@]} project root(s), ${staged_files} class/target file(s)"

# stage_case <name> — a fresh COPY of the pristine tree, git-initialised. Each case gets its own so
# a mutation can never leak into the next one.
stage_case() {
  local case_root="${work_dir}/$1" git_output
  cp -RL "$pristine" "$case_root"
  if ! git_output="$(git -C "$case_root" init --quiet 2>&1)"; then
    printf 'verbs-check_test: FAILED — git init in the staged tree failed: %s\n' "$git_output" >&2
    exit 1
  fi
  printf '%s' "$case_root"
}

check_rc=0
check_out=''
run_check() {
  check_rc=0
  check_out="$( ( cd "$1" && "$bash_binary" .ci/ctl.sh verbs --check ) 2>&1 )" || check_rc=$?
}

first_error_line() {
  local line
  line="$(printf '%s' "$check_out" | grep -aE '\[error\]' | head -1)"
  [[ -n "$line" ]] || line="$(printf '%s' "$check_out" | head -1)"
  printf '%s' "$(printf '%s' "$line" | cut -c1-160)"
}

# expect_red <label> <regex>... — the verb must fail AND ONE SINGLE LINE of its output must satisfy
# EVERY pattern: the clause, the project, and the verb, together.
#
# WHY ONE LINE AND NOT "ANYWHERE". Measured while writing this file: with `verbs` still an unknown
# command, `.ci/ctl.sh` prints its USAGE, and that usage text alone satisfied `build`, `typecheck`,
# `validate` and `command` as free-floating patterns. Only the project-name pattern was
# load-bearing, so three of every four patterns were decoration — refutation #5's shape exactly.
# Narrowing the candidate set one pattern at a time is what makes each of them carry weight.
expect_red() {
  local label="$1"; shift
  local pattern remaining="$check_out" narrowed grep_rc
  local -a unmatched=()
  if [[ $check_rc -eq 0 ]]; then
    report_fail "$label" "verbs --check exited 0 with the mutation in place"
    return
  fi
  for pattern in "$@"; do
    set +e
    narrowed="$(printf '%s\n' "$remaining" | grep -iE "$pattern")"
    grep_rc=$?
    set -e
    if [[ $grep_rc -gt 1 ]]; then
      report_fail "$label" "grep exited ${grep_rc} on the pattern: ${pattern}"
      return
    fi
    if [[ $grep_rc -ne 0 || -z "$narrowed" ]]; then
      unmatched+=("$pattern")
      break
    fi
    remaining="$narrowed"
  done
  if [[ ${#unmatched[@]} -ne 0 ]]; then
    report_fail "$label" \
      "it went red (${check_rc}), but NO SINGLE LINE satisfies the message contract" \
      "the first pattern no candidate line matched: ${unmatched[0]}" \
      "first error was: $(first_error_line)"
    return
  fi
  report_ok "$label"
}

# --- CASE 3c / ANTI-VACUITY — the clean tree ------------------------------------------------------
# It runs FIRST. If the verb does not pass on the untouched staged tree, every red below could be
# that unrelated failure, and each would report a clause proven when nothing was.
printf -- '-- the verb, EXECUTED --\n'
clean_root="$(stage_case clean)"
run_check "$clean_root"
clean_is_green=0
if [[ $check_rc -ne 0 ]]; then
  report_fail "clause 3c: the CLEAN tree passes (the premise of every red below)" \
    "verbs --check exited ${check_rc} on the untouched staged tree" \
    "first line: $(first_error_line)" \
    'EVERY case below is therefore RED FOR THE WRONG REASON — they are still run, so the implementer sees the whole list, but not one of them is evidence about its clause yet'
else
  clean_is_green=1
  if ! printf '%s' "$check_out" | grep -qiE "(^|[^0-9])${#roster_roots[@]}([^0-9].*project|[^0-9]*$)|project[^0-9]{0,24}(^|[^0-9])${#roster_roots[@]}([^0-9]|$)"; then
    report_fail "clause 3c: the clean tree reports ${#roster_roots[@]} project(s) checked" \
      "it exited 0 and no line reports the count ${#roster_roots[@]}" \
      'the count is read from .ci/graph-roster.txt, never from a second census — a run that reports no count could have checked none' \
      "output: $(printf '%s' "$check_out" | tail -1 | cut -c1-160)"
  else
    report_ok "clause 3c: the clean tree exits 0 and reports ${#roster_roots[@]} project(s)"
  fi
fi

# --- CASE 1 — clause 1, an AMBIGUOUS class --------------------------------------------------------
# Zero projects are ambiguous today, so this clause can be triggered by no ordinary state of the
# tree. It is planted, exactly as graph-guard_test.sh shims its two unreachable clauses, because a
# clause that nothing can reach is decoration.
case_root="$(stage_case ambiguous)"
printf '{"name":"eden-verbs-check-probe","version":"0.0.0"}\n' > "${case_root}/${ambiguous_root}/package.json"
printf '{"compilerOptions":{"strict":true}}\n' > "${case_root}/${ambiguous_root}/tsconfig.json"
run_check "$case_root"
expect_red "clause 1: a project that is BOTH Go and TypeScript is RED, naming '${ambiguous_name}'" \
  "(^|[^a-z0-9_-])(${ambiguous_name}|${ambiguous_root})([^a-z0-9_-]|$)" \
  "ambiguous|more than one class|two classes|both go and typescript"

# --- CASE 2 — clause 2, R-BODY --------------------------------------------------------------------
case_root="$(stage_case rbody)"
project_file="${case_root}/${r_body_root}/project.json"
jq --arg t "$r_body_verb" --arg c "$r_body_mutation" '.targets[$t].options.command = $c' \
  "$project_file" > "${project_file}.mutated"
mv "${project_file}.mutated" "$project_file"
run_check "$case_root"
expect_red "clause 2: a closed-set target whose command is not 'bash ./ctl.sh ${r_body_verb}' is RED, naming '${r_body_name}' and '${r_body_verb}'" \
  "(^|[^a-z0-9_-])(${r_body_name}|${r_body_root})([^a-z0-9_-]|$)" \
  "(^|[^a-z0-9_-])${r_body_verb}([^a-z0-9_-]|$)" \
  "r-body|bash \\./ctl\\.sh|command"

# --- CASE 3a — clause 3, an UNREGISTERED difference ----------------------------------------------
# The blueprint's certified NEGATIVE exit proof, verbatim: "a no-op `typecheck` added to a Go module
# is an unregistered EXTRA -> non-zero, naming the project and the verb". The command is R-BODY
# clean on purpose, so the ONLY difference from the clean tree is the extra target.
case_root="$(stage_case extra)"
project_file="${case_root}/${extra_root}/project.json"
jq --arg t "$extra_verb" \
  '.targets[$t] = {"executor":"nx:run-commands","options":{"command":("bash ./ctl.sh " + $t),"cwd":"{projectRoot}"},"cache":false}' \
  "$project_file" > "${project_file}.mutated"
mv "${project_file}.mutated" "$project_file"
run_check "$case_root"
expect_red "clause 3a: an UNREGISTERED '${extra_verb}' on the Go module '${extra_name}' is RED, naming project and verb" \
  "(^|[^a-z0-9_-])(${extra_name}|${extra_root})([^a-z0-9_-]|$)" \
  "(^|[^a-z0-9_-])${extra_verb}([^a-z0-9_-]|$)" \
  "unregistered|not registered|verb-exceptions|extra|register"

# --- CASE 3b — clause 3, a STALE register row ----------------------------------------------------
# The register may only SHRINK. `${stale_name}` owes `${stale_verb}` and does not declare it, so a
# row excuses it. Declaring it REPAIRS the difference, and the row that excused it now describes
# nothing — it is stale, and the register fails until it is deleted. This is the property that
# stops the register rotting into a permanent skip (`libs/.ci/ctl.sh:114-121`).
case_root="$(stage_case stale)"
project_file="${case_root}/${stale_root}/project.json"
jq --arg t "$stale_verb" \
  '.targets[$t] = {"executor":"nx:run-commands","options":{"command":("bash ./ctl.sh " + $t),"cwd":"{projectRoot}"},"cache":false}' \
  "$project_file" > "${project_file}.mutated"
mv "${project_file}.mutated" "$project_file"
run_check "$case_root"
expect_red "clause 3b: a REPAIRED difference makes its register row STALE and RED, naming '${stale_name}' and '${stale_verb}'" \
  "(^|[^a-z0-9_-])(${stale_name}|${stale_root})([^a-z0-9_-]|$)" \
  "(^|[^a-z0-9_-])${stale_verb}([^a-z0-9_-]|$)" \
  "stale|repaired|no longer|delete the row|may only shrink"

printf '\n'
if [[ $fails -ne 0 ]]; then
  if [[ $clean_is_green -ne 1 ]]; then
    printf 'verbs-check_test: the CLEAN tree did not pass, so every clause above went red for the WRONG reason.\n' >&2
    printf '                  verbs --check has to exist and pass on an untouched tree before any red here is evidence.\n' >&2
  fi
  printf 'verbs-check_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'verbs-check_test: all assertions passed (%d project(s) staged, 3 clause(s) + the register, each proven able to fire)\n' \
  "${#roster_roots[@]}"
