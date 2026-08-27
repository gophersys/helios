#!/usr/bin/env bash
#
# scripts/gate-lanes_test.sh — repository rule (blueprint P0-4b): a declared check that is in no
# gate lane has never run, and eden's sqlc drift check is exactly that.
#
# WHY THIS FILE EXISTS. `apps/platformgateway/persistence/project.json` declares a `verify` target
# (`bash ./ctl.sh verify` -> `require_cmd sqlc` -> `sqlc vet`), which is the check that fails when
# `generated/` has drifted from `schema/` + the queries. It appears in NO `-t` list of
# `.ci/ctl.sh`, so no lane has ever selected it: the drift check exists, is correct, and has never
# executed in CI. A target nobody runs is the same class of nothing as a gate that cannot fail.
#
# IT ASSERTS BY OBSERVED INVOCATION, NEVER BY GREPPING THE SOURCE. `scripts/graph-guard_test.sh`
# refutation #3 is the reason: a holder that grepped `.ci/ctl.sh` for marker strings certified a
# verb that had regressed, because moving a string into a comment satisfied the grep. So the `-t`
# list judged here is the one an `nx` planted at `node_modules/.bin/nx` RECORDS being handed to it.
#
# THE SHIM'S MODEL, STATED SO A GREEN RUN IS NOT READ AS MORE THAN IT IS. It answers as though the
# affected set were exactly `{platformgateway-persistence}`: for each target in the `-t` list that
# the project's own `project.json` declares, it prints `platformgateway-persistence:<target>`. That
# is a model of `nx affected`, not nx — it proves the target is SELECTED by the lane, never that
# sqlc passes. The sqlc pin itself is blueprint P0-4 in `.devcontainer` (PR-A), and until that
# lands and the pointer moves, the real lane is red for want of the tool. That is the intended
# state and it is stated here rather than hidden.
#
# WHAT A GREEN RUN PROVES:
#   1. `affected-gate-fast` hands nx a `-t` list that NAMES `verify`;
#   2. the blueprint's own proof line is satisfiable — the verb's output holds `persistence:verify`
#      exactly once;
#   3. the 9 targets the fast lane carries today are all still in it, so `verify` is ADDED and the
#      lane is not rewritten;
#   4. `affected-gate` remains exactly the union of the fast and substrate lists, which is what its
#      own comment claims it is ("this verb is the union a single job can invoke").
#
# SCOPE.
#   COVERED: which targets each gate verb selects, read off the invocation.
#   NOT COVERED: whether any of those targets PASSES; whether `nx affected` would really select
#     this project for a given diff; the sqlc toolchain, which lives in `.devcontainer`.
#
# Run it directly:  bash scripts/gate-lanes_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
ctl_source="${repository_root}/.ci/ctl.sh"
bash_binary="$(command -v bash)"

# The subject, as LITERALS. A staleness preflight below proves each still describes the tree, so a
# pointer bump or a rename produces a red that names THIS file rather than a red that blames the
# verb — the failure mode scripts/graph-guard_test.sh's `probe_is_fresh` exists to prevent.
drift_project_name="platformgateway-persistence"
drift_project_root="apps/platformgateway/persistence"
drift_target="verify"
# The proof line the blueprint states, as the substring it greps for.
drift_proof_needle="persistence:verify"

# The fast lane as it stands today. `verify` is what P0-4b ADDS; these 9 must survive the edit.
fast_lane_baseline=(lint typecheck test leak property maintainability vuln sast secretscan)

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
  printf 'gate-lanes_test: FAILED — the file under test does not exist: %s\n' "$ctl_source" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  printf 'gate-lanes_test: FAILED — required tool(s) missing: jq\n' >&2
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
    printf 'gate-lanes_test: INTERRUPTED before it finished — reporting %d, never success\n' \
      "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP

# --- staleness preflight — the literals above still describe the tree --------------------------
printf -- '-- the subject still exists --\n'
preflight_problems=()
roster="${repository_root}/.ci/graph-roster.txt"
if ! grep -qxF -- "${drift_project_name}"$'\t'"${drift_project_root}" "$roster"; then
  preflight_problems+=("the roster has no row '${drift_project_name}' -> '${drift_project_root}'; the project moved or was renamed")
fi
drift_project_file="${repository_root}/${drift_project_root}/project.json"
if [[ ! -f "$drift_project_file" ]]; then
  preflight_problems+=("no project.json at ${drift_project_root}")
elif ! jq -e --arg t "$drift_target" '.targets | has($t)' "$drift_project_file" >/dev/null; then
  preflight_problems+=("${drift_project_root}/project.json declares no '${drift_target}' target — the check this file exists for is gone")
fi
if [[ ${#preflight_problems[@]} -ne 0 ]]; then
  report_fail 'the drift check this file wires into a lane still exists' \
    "${preflight_problems[@]}" \
    'the fix is the literals at the top of scripts/gate-lanes_test.sh'
  printf '\ngate-lanes_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
report_ok "${drift_project_root} declares '${drift_target}' and is rostered as '${drift_project_name}'"

# --- the staged tree ---------------------------------------------------------------------------
work_dir="$(mktemp -d -t eden-gate-lanes.XXXXXX)"
staged_root="${work_dir}/staged"
record_file="${work_dir}/nx-invocations.txt"

mkdir -p "${staged_root}/.ci" "${staged_root}/${drift_project_root}"
cp "$ctl_source" "${staged_root}/.ci/ctl.sh"
cp "${repository_root}/.ci/graph-roster.txt" "${staged_root}/.ci/graph-roster.txt"
cp "$drift_project_file" "${staged_root}/${drift_project_root}/project.json"
if [[ -d "${repository_root}/.devcontainer/_ctl" ]]; then
  mkdir -p "${staged_root}/.devcontainer"
  cp -RL "${repository_root}/.devcontainer/_ctl" "${staged_root}/.devcontainer/_ctl"
fi
if ! git_output="$(git -C "$staged_root" init --quiet 2>&1)"; then
  printf 'gate-lanes_test: FAILED — git init in the staged tree failed: %s\n' "$git_output" >&2
  exit 1
fi

declared_targets="$(jq -r '.targets | keys | join(" ")' "$drift_project_file")"
: > "$record_file"
mkdir -p "${staged_root}/node_modules/.bin"
cat > "${staged_root}/node_modules/.bin/nx" <<SHIM
#!/usr/bin/env bash
# A model of \`nx affected\` whose affected set is exactly {${drift_project_name}}. It records the
# argv it was handed and prints the task ids that set would produce for the requested -t list.
printf '%s\n' "\$*" >> "${record_file}"
declared="${declared_targets}"
requested=""
want_list=0
for argument in "\$@"; do
  if [[ \$want_list -eq 1 ]]; then requested="\$argument"; want_list=0; continue; fi
  [[ "\$argument" == "-t" ]] && want_list=1
done
[[ -n "\$requested" ]] || exit 0
IFS=',' read -r -a requested_targets <<< "\$requested"
for target in "\${requested_targets[@]}"; do
  for candidate in \$declared; do
    [[ "\$target" == "\$candidate" ]] && printf '%s:%s\n' "${drift_project_name}" "\$target"
  done
done
exit 0
SHIM
chmod +x "${staged_root}/node_modules/.bin/nx"

# PREFLIGHT — the shim must be the nx that answers. nx_cmd prefers PATH over node_modules/.bin.
if command -v nx >/dev/null 2>&1; then
  report_fail 'the recording shim is the nx that answers' \
    "an nx is on PATH at $(command -v nx); nx_cmd prefers it over node_modules/.bin/nx" \
    'this test cannot observe the -t list while a real nx shadows the shim'
  printf '\ngate-lanes_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi

verb_rc=0
verb_out=''
# run_verb <verb> — combined output, exactly the text the blueprint's `2>&1 | grep` would carry.
# The status is the verb's own; `|| true` would discard it and a dead verb would read as a pass.
run_verb() {
  verb_rc=0
  verb_out="$( ( cd "$staged_root" && "$bash_binary" .ci/ctl.sh "$1" ) 2>&1 )" || verb_rc=$?
}

# recorded_target_list — the value of the `-t` argument of the last nx invocation, as a sorted,
# space-separated set.
recorded_target_list() {
  local recorded want_list=0 argument requested=''
  recorded="$(tail -1 "$record_file")"
  local -a recorded_arguments=()
  IFS=$' \t\n' read -r -a recorded_arguments <<< "$recorded"
  for argument in "${recorded_arguments[@]+"${recorded_arguments[@]}"}"; do
    if [[ $want_list -eq 1 ]]; then requested="$argument"; want_list=0; continue; fi
    [[ "$argument" == "-t" ]] && want_list=1
  done
  printf '%s' "$requested" | tr ',' '\n' | grep -vE '^[[:space:]]*$' | LC_ALL=C sort -u | tr '\n' ' '
}

# split_targets <space-separated list> — fill `split_result` with its members. The file-wide
# IFS is $'\n\t', so an unquoted expansion would NOT split on the spaces this list uses.
split_result=()
split_targets() {
  split_result=()
  IFS=$' \t\n' read -r -a split_result <<< "$1"
}

lane_targets() {
  local verb="$1"
  : > "$record_file"
  run_verb "$verb"
  if [[ $verb_rc -ne 0 ]]; then
    printf 'RC=%d' "$verb_rc"
    return 0
  fi
  if [[ ! -s "$record_file" ]]; then
    printf 'NO-INVOCATION'
    return 0
  fi
  recorded_target_list
}

printf -- '-- the lanes, read off the nx invocation --\n'

fast_targets="$(lane_targets affected-gate-fast)"
substrate_targets="$(lane_targets affected-gate-substrate)"
union_targets="$(lane_targets affected-gate)"

for pair in "affected-gate-fast|${fast_targets}" "affected-gate-substrate|${substrate_targets}" "affected-gate|${union_targets}"; do
  lane_name="${pair%%|*}"
  lane_value="${pair#*|}"
  case "$lane_value" in
    RC=* | NO-INVOCATION)
      report_fail "'${lane_name}' invokes nx with a -t list" \
        "it produced: ${lane_value}" \
        'nothing below can be judged for this lane'
      ;;
    *) report_ok "'${lane_name}' -t = ${lane_value}" ;;
  esac
done

# CLAUSE 1 — the fast lane NAMES the drift check.
if [[ " ${fast_targets} " == *" ${drift_target} "* ]]; then
  report_ok "clause 1: 'affected-gate-fast' selects '${drift_target}' — ${drift_project_root} finally has a lane"
else
  report_fail "clause 1: 'affected-gate-fast' selects '${drift_target}'" \
    "its -t list is: ${fast_targets}" \
    "'${drift_target}' is in no gate verb's list, so ${drift_project_root}'s sqlc drift check has never run in CI"
fi

# CLAUSE 2 — the blueprint's own proof line, executed.
run_verb affected-gate-fast
set +e
proof_count="$(printf '%s\n' "$verb_out" | grep -c -F -- "$drift_proof_needle")"
proof_rc=$?
set -e
if [[ $proof_rc -gt 1 ]]; then
  report_fail "clause 2: the blueprint proof line runs" "grep exited ${proof_rc}"
elif [[ "$proof_count" -ne 1 ]]; then
  report_fail "clause 2: 'affected-gate-fast' output holds '${drift_proof_needle}' exactly once" \
    "it holds it ${proof_count} time(s); the blueprint's exit proof is: bash .ci/ctl.sh affected-gate-fast 2>&1 | grep -c '${drift_proof_needle}' -> 1" \
    "verb exit status: ${verb_rc}"
else
  report_ok "clause 2: the blueprint proof line yields 1 — '${drift_proof_needle}' is selected"
fi

# CLAUSE 3 — the 9 targets the fast lane carries today all survive. `verify` is added, never
# swapped in: a lane rewritten to hold one target would satisfy clause 1 and gate nothing else.
missing_baseline=()
for target in "${fast_lane_baseline[@]}"; do
  [[ " ${fast_targets} " == *" ${target} "* ]] || missing_baseline+=("$target")
done
if [[ ${#missing_baseline[@]} -ne 0 ]]; then
  report_fail "clause 3: the fast lane keeps all ${#fast_lane_baseline[@]} target(s) it carries today" \
    "${#missing_baseline[@]} lost: ${missing_baseline[*]}" \
    "its -t list is: ${fast_targets}"
else
  report_ok "clause 3: all ${#fast_lane_baseline[@]} of today's fast-lane targets survive"
fi

# CLAUSE 4 — `affected-gate` is the UNION of the two split lanes, which is what its own comment
# claims. Measured today: 9 fast + 6 substrate = 15, and the union verb carries exactly 15. Adding
# a target to a split lane and not to the union silently un-unions it.
split_targets "$fast_targets"
union_members=("${split_result[@]+"${split_result[@]}"}")
split_targets "$substrate_targets"
union_members+=("${split_result[@]+"${split_result[@]}"}")
expected_union="$(printf '%s\n' "${union_members[@]+"${union_members[@]}"}" \
  | grep -vE '^[[:space:]]*$' | LC_ALL=C sort -u | tr '\n' ' ')"
split_targets "$union_targets"
if [[ "$union_targets" == "$expected_union" ]]; then
  report_ok "clause 4: 'affected-gate' is exactly fast U substrate (${#split_result[@]} target(s))"
else
  report_fail "clause 4: 'affected-gate' is exactly the union of fast and substrate" \
    "union verb: ${union_targets}" \
    "fast U substrate: ${expected_union}" \
    "the verb's own comment says it is 'the union a single job can invoke'"
fi

printf '\n'
if [[ $fails -ne 0 ]]; then
  printf 'gate-lanes_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'gate-lanes_test: all assertions passed (3 lane(s) observed, 4 clause(s))\n'
