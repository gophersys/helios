#!/usr/bin/env bash
#
# scripts/nx-absent_test.sh — repository rule (blueprint P0-2): an eden CI verb that cannot reach
# `nx` FAILS. It never warns and returns 0.
#
# WHY THIS FILE EXISTS. `.ci/ctl.sh` was written for a fresh scaffold that had not run `yarn
# install` yet, and its header still says so: "the verbs fall through to a no-op with an
# informational message so the workflow doesn't explode on day one". Eden is not day one. Measured
# on this tree, ELEVEN verbs report success with no nx reachable — `cmd_validate` warns and then
# prints `log_success` having run only shellcheck, and ten more `log_warn` and `return 0`. A lane
# whose toolchain vanished is therefore indistinguishable from a lane that passed, which is the
# defect class this repository already names in `cmd_graph_guard`:
#
#     "This is a GATE, and a gate that cannot run is a failure, never a pass."
#
# `graph-guard` and `graph-roster-update` already obey that. The other eleven do not, and the
# comment at `.ci/ctl.sh:192-194` that excuses them ("they are RUNNERS and a fresh scaffold has no
# nx") is exactly what P0-2 overrules.
#
# THE RULES IT OBEYS, taken from scripts/graph-guard_test.sh, which five refutations shaped:
#   (a) never read the verb's SOURCE for the verdict — run the verb, read its exit status and its
#       stderr. The source IS read once, to ENUMERATE the dispatcher's verbs, so a twelfth verb
#       added later cannot be silently outside this file's table;
#   (b) assert WHICH failure fired, by requiring the tool's name in stderr — a red that says
#       nothing about nx would let a broken staged tree masquerade as a working gate;
#   (c) quantify over the SET — all eleven verbs, never one representative;
#   (d) prove the OTHER direction too. A verb that always exits 127 would satisfy every assertion
#       in the first half. The second half puts a recording `nx` at node_modules/.bin/nx — eden's
#       real CI shape, where nx is NOT on PATH — and requires each of the eleven to reach it and
#       exit 0. That is what stops the fix being `require_cmd nx`, which reads PATH only and would
#       fail every real eden lane.
#
# WHAT A GREEN RUN PROVES:
#   - with no nx on PATH, no node_modules/.bin/nx and no .pnp.cjs, each of the 11 verbs exits 127
#     and names nx on stderr;
#   - graph-guard and graph-roster-update still fail on absent nx, naming nx (they already do);
#   - with nx reachable ONLY at node_modules/.bin/nx, each of the 11 verbs reaches it and exits 0;
#   - the dispatcher declares no verb this file has not classified.
#
# SCOPE — read this before reading a green run as more than it is.
#   COVERED: the exit status and stderr of eden's `.ci/ctl.sh` verbs under two nx environments.
#   NOT COVERED: what the verbs do when nx is present and REAL — the shim answers 0 to everything,
#     so this file proves reachability, never that any nx target passes. It says nothing about
#     libs/.ci/ctl.sh (blueprint P0-3, a different repository) or infrastructure/ctl.sh.
#
# HERMETIC BY CONSTRUCTION. It never runs `.ci/ctl.sh` in place: this repository grows a real
# `node_modules/.bin/nx` the moment anybody runs `yarn install`, and CI always has one, so an
# in-place run would silently test the opposite premise. Every run is a COPY under `mktemp -d`,
# with `git init` so the verb's own `git rev-parse --show-toplevel` resolves, and PATH rebuilt
# with every directory holding an `nx` removed — then that removal is VERIFIED before it is used.
#
# Run it directly:  bash scripts/nx-absent_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
ctl_source="${repository_root}/.ci/ctl.sh"
bash_binary="$(command -v bash)"

# THE ELEVEN, as LITERALS. Each row is <verb>|<function it dispatches to>|<the line that returns 0
# today>. The function and the line are documentation for the reader and for the implementer; the
# ASSERTION is made against the verb alone, by running it. A verb added to the dispatcher and not
# added here is caught by the inventory check at the end of this file.
nx_required_verbs=(
  "validate|cmd_validate|82-88 warns, then log_success having run only shellcheck"
  "build-all|cmd_build_all|92"
  "test-all|cmd_test_all|100"
  "lint-all|cmd_lint_all|108"
  "typecheck-all|cmd_typecheck_all|116"
  "affected-build|cmd_affected_build|124"
  "affected-test|cmd_affected_test|129"
  "affected-check|cmd_affected_check|134"
  "affected-gate|cmd_affected_gate|145"
  "affected-gate-fast|cmd_affected_gate_fast|159"
  "affected-gate-substrate|cmd_affected_gate_substrate|508"
)
# The 2 that ALREADY fail on absent nx, and say why in their own comments (`.ci/ctl.sh:192-198` and
# `:466-469`). They are asserted so P0-2 cannot regress the prior art it is modelled on. They exit
# non-zero rather than 127: they `return 1` after logging, which is the shape they already have.
nx_gate_verbs=("graph-guard" "graph-roster-update")
# Verbs that do not touch nx at all. `help` prints usage; `lib-gate` dispatches into a library's own
# ctl.sh; `release-check` talks to git and a remote. Listing them is what makes the inventory check
# at the end complete rather than a subset.
nx_exempt_verbs=("help" "lib-gate" "release-check")

fails=0
report_fail() {
  local name="$1"; shift
  printf '  FAIL  %s\n' "$name" >&2
  local problem
  for problem in "$@"; do printf '          %s\n' "$problem" >&2; done
  fails=$((fails + 1))
}
report_ok() { printf '  ok    %s\n' "$1"; }

if [[ ! -f "$ctl_source" ]]; then
  printf 'nx-absent_test: FAILED — the file under test does not exist: %s\n' "$ctl_source" >&2
  exit 1
fi

work_dir=""
interrupted=0
sweep() {
  local rc=$?
  [[ -n "$work_dir" ]] && rm -rf "$work_dir"
  if [[ $interrupted -ne 0 ]]; then
    printf 'nx-absent_test: INTERRUPTED before it finished — reporting %d, never success\n' \
      "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP

work_dir="$(mktemp -d -t eden-nx-absent.XXXXXX)"

# stage_tree <destination> — a COPY of everything `.ci/ctl.sh` reads, and nothing else. Never a
# symlink (`cp -RL` dereferences), so a staged file cannot reach back into the real tree.
stage_tree() {
  local destination="$1" git_output
  mkdir -p "${destination}/.ci"
  cp "$ctl_source" "${destination}/.ci/ctl.sh"
  cp "${repository_root}/.ci/graph-roster.txt" "${destination}/.ci/graph-roster.txt"
  [[ -f "${repository_root}/.nxignore" ]] && cp "${repository_root}/.nxignore" "${destination}/.nxignore"
  # PR-A of this blueprint gives `.ci/ctl.sh` a `source .devcontainer/_ctl/standard.sh`. Staging the
  # directory now means this file does not have to change when that lands, and a `set -e` death on a
  # missing source would otherwise read as an nx failure.
  if [[ -d "${repository_root}/.devcontainer/_ctl" ]]; then
    mkdir -p "${destination}/.devcontainer"
    cp -RL "${repository_root}/.devcontainer/_ctl" "${destination}/.devcontainer/_ctl"
  fi
  if ! git_output="$(git -C "$destination" init --quiet 2>&1)"; then
    printf 'nx-absent_test: FAILED — git init in the staged tree failed: %s\n' "$git_output" >&2
    exit 1
  fi
}

# path_without_nx — PATH with every directory that holds an executable `nx` removed. Reading PATH
# through `read -r -a` rather than unquoted word splitting keeps a directory name with a glob
# character from expanding.
path_without_nx() {
  local -a entries=()
  local entry sanitized=''
  IFS=':' read -r -a entries <<< "$PATH"
  for entry in "${entries[@]}"; do
    [[ -n "$entry" ]] || continue
    [[ -x "${entry}/nx" ]] && continue
    sanitized="${sanitized:+${sanitized}:}${entry}"
  done
  printf '%s' "$sanitized"
}

verb_rc=0
verb_out=''
verb_err=''
# run_verb <staged root> <PATH value> <verb...> — the status is the command's own. `|| true` would
# discard it and every run below would read as a success.
run_verb() {
  local root="$1" path_value="$2"
  shift 2
  local error_file="${work_dir}/verb.err"
  verb_rc=0
  verb_out="$( ( cd "$root" && PATH="$path_value" "$bash_binary" .ci/ctl.sh "$@" ) 2>"$error_file" )" \
    || verb_rc=$?
  verb_err="$(cat "$error_file")"
  rm -f "$error_file"
}

names_nx() { printf '%s' "$1" | grep -qE '(^|[^[:alnum:]_-])nx([^[:alnum:]_-]|$)'; }
first_line() { printf '%s' "$1" | head -1 | cut -c1-160; }

# ── PART A — no nx anywhere ────────────────────────────────────────────────────────────────────
printf -- '-- part A: nx is unreachable --\n'

absent_root="${work_dir}/absent"
stage_tree "$absent_root"
clean_path="$(path_without_nx)"

# The premise is PROVEN before a single verb is judged against it. A sanitized PATH that still
# resolves nx, or a staged tree that grew a node_modules, would make all eleven reds below mean
# nothing at all — and they would still print as failures of the verbs.
premise_problems=()
if [[ -z "$clean_path" ]]; then
  premise_problems+=("the sanitized PATH is empty; every verb would fail for want of a shell, not for want of nx")
fi
set +e
( PATH="$clean_path"; command -v nx >/dev/null 2>&1 )
resolves_nx=$?
set -e
if [[ $resolves_nx -eq 0 ]]; then
  premise_problems+=("nx still resolves on the sanitized PATH — path_without_nx did not remove it")
fi
[[ -e "${absent_root}/node_modules" ]] && premise_problems+=("the staged tree holds node_modules; has_nx would find it")
[[ -e "${absent_root}/.pnp.cjs" ]] && premise_problems+=("the staged tree holds .pnp.cjs; has_nx would find it")
if [[ ${#premise_problems[@]} -ne 0 ]]; then
  report_fail 'the staged tree really has no nx (the premise of every assertion in part A)' \
    "${premise_problems[@]}"
  printf '\nnx-absent_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
report_ok "the staged tree really has no nx: none on PATH, no node_modules/.bin/nx, no .pnp.cjs"

for row in "${nx_required_verbs[@]}"; do
  verb="${row%%|*}"
  rest="${row#*|}"
  function_name="${rest%%|*}"
  today="${rest#*|}"
  run_verb "$absent_root" "$clean_path" "$verb"
  if [[ $verb_rc -ne 127 ]]; then
    report_fail "'${verb}' exits 127 when nx is unreachable" \
      "it exited ${verb_rc} (${function_name}, .ci/ctl.sh:${today})" \
      "stdout: $(first_line "$verb_out")" \
      "stderr: $(first_line "$verb_err")"
  elif ! names_nx "$verb_err"; then
    report_fail "'${verb}' names nx on stderr when it fails" \
      "it exited 127 but no stderr line names nx — the operator cannot tell which tool is missing" \
      "stderr: $(first_line "$verb_err")"
  else
    report_ok "'${verb}' exits 127 and names nx on stderr"
  fi
done

for verb in "${nx_gate_verbs[@]}"; do
  run_verb "$absent_root" "$clean_path" "$verb"
  if [[ $verb_rc -eq 0 ]]; then
    report_fail "'${verb}' still FAILS when nx is unreachable (prior art, .ci/ctl.sh:192-198 and :466-469)" \
      "it exited 0" \
      "stdout: $(first_line "$verb_out")"
  elif ! names_nx "$verb_err"; then
    report_fail "'${verb}' names nx on stderr when it fails" \
      "it exited ${verb_rc} but no stderr line names nx" \
      "stderr: $(first_line "$verb_err")"
  else
    report_ok "'${verb}' fails (${verb_rc}) and names nx on stderr — green by design, and asserted so P0-2 cannot regress it"
  fi
done

# ── PART B — nx reachable ONLY at node_modules/.bin/nx ─────────────────────────────────────────
# Eden's real shape: `yarn install` puts nx there and nothing puts it on PATH. A fix written as
# `require_cmd nx` would pass every assertion in part A and break every real eden lane, so this half
# is not decoration — it is the clause that pins WHICH check the implementer may write.
printf -- '-- part B: nx reachable only at node_modules/.bin/nx --\n'

present_root="${work_dir}/present"
stage_tree "$present_root"
record_file="${work_dir}/nx-invocations.txt"
: > "$record_file"
mkdir -p "${present_root}/node_modules/.bin"
cat > "${present_root}/node_modules/.bin/nx" <<SHIM
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "${record_file}"
exit 0
SHIM
chmod +x "${present_root}/node_modules/.bin/nx"

for row in "${nx_required_verbs[@]}"; do
  verb="${row%%|*}"
  before="$(wc -l < "$record_file" | tr -d ' ')"
  run_verb "$present_root" "$clean_path" "$verb"
  after="$(wc -l < "$record_file" | tr -d ' ')"
  if [[ $verb_rc -ne 0 ]]; then
    report_fail "'${verb}' RUNS when nx is only at node_modules/.bin/nx" \
      "it exited ${verb_rc}; eden's own CI has nx exactly there and nowhere on PATH" \
      "a guard written as 'require_cmd nx' reads PATH only and would fail every real lane" \
      "stderr: $(first_line "$verb_err")"
  elif [[ "$after" -le "$before" ]]; then
    report_fail "'${verb}' actually invokes nx when nx is reachable" \
      "it exited 0 but the nx shim recorded no invocation — the verb returned success without running anything"
  else
    report_ok "'${verb}' reaches node_modules/.bin/nx and exits 0 ($(( after - before )) invocation(s))"
  fi
done

# ── PART C — the dispatcher declares no verb this file has not classified ──────────────────────
# The one place the SOURCE is read, and it is read for COMPLETENESS, never for a verdict: a twelfth
# verb that warns and returns 0 would otherwise be outside the table above and invisible here.
printf -- '-- part C: the verb inventory --\n'

dispatcher_verbs=()
in_case=0
while IFS= read -r line; do
  if [[ $in_case -eq 0 ]]; then
    # shellcheck disable=SC2016
    # `$cmd` is the LITERAL text of the dispatcher's own line, not a variable of this file. Single
    # quotes are what keeps it so.
    [[ "$line" == *'case "$cmd" in'* ]] && in_case=1
    continue
  fi
  [[ "$line" =~ ^[[:space:]]*esac ]] && break
  [[ "$line" == *')'* ]] || continue
  token="${line%%)*}"
  token="${token#"${token%%[![:space:]]*}"}"
  IFS='|' read -r -a arm_patterns <<< "$token"
  for pattern in "${arm_patterns[@]+"${arm_patterns[@]}"}"; do
    pattern="${pattern//\"/}"
    [[ -n "$pattern" ]] || continue
    [[ "$pattern" == '*' ]] && continue
    dispatcher_verbs+=("$pattern")
  done
done < "$ctl_source"

known_verbs=()
for row in "${nx_required_verbs[@]}"; do known_verbs+=("${row%%|*}"); done
known_verbs+=("${nx_gate_verbs[@]}" "${nx_exempt_verbs[@]}")
printf -v known_list '%s\n' "${known_verbs[@]}"

if [[ ${#dispatcher_verbs[@]} -lt 16 ]]; then
  report_fail 'the dispatcher inventory really read the case arms' \
    "it extracted ${#dispatcher_verbs[@]} verb(s); .ci/ctl.sh declares 16 or more" \
    'the parse in part C of this file has stopped matching the dispatcher'
else
  unclassified=()
  for verb in "${dispatcher_verbs[@]}"; do
    if [[ $'\n'"$known_list" != *$'\n'"$verb"$'\n'* ]]; then unclassified+=("$verb"); fi
  done
  if [[ ${#unclassified[@]} -ne 0 ]]; then
    report_fail "every verb .ci/ctl.sh dispatches is classified by this file (${#dispatcher_verbs[@]} verb(s))" \
      "${#unclassified[@]} unclassified: ${unclassified[*]}" \
      'add it to nx_required_verbs, nx_gate_verbs or nx_exempt_verbs — a new verb that warns and returns 0 on absent nx is exactly what this table exists to make visible'
  else
    report_ok "every one of the ${#dispatcher_verbs[@]} dispatched verb(s) is classified (${#nx_required_verbs[@]} must-fail, ${#nx_gate_verbs[@]} gate, ${#nx_exempt_verbs[@]} nx-free)"
  fi
fi

printf '\n'
if [[ $fails -ne 0 ]]; then
  printf 'nx-absent_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'nx-absent_test: all assertions passed (%d verb(s) must fail on absent nx, %d already did, both directions executed)\n' \
  "${#nx_required_verbs[@]}" "${#nx_gate_verbs[@]}"
