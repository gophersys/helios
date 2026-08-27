#!/usr/bin/env bash
#
# scripts/nx-base_test.sh — repository rule (blueprint P0-2b): the base commit `nx affected` runs
# against is RESOLVED, and it resolves to a base that exists.
#
# WHY THIS FILE EXISTS, AND WHY IT IS NOT A FAILING TEST. `.ci/ctl.sh` reads:
#
#     44  NX_BASE="${NX_BASE:-origin/main}"
#     45  if [[ -z "$NX_BASE" || "$NX_BASE" == "0000000000000000000000000000000000000000" ]]; then
#     46    NX_BASE="HEAD~1"
#
# Line 44 substitutes for BOTH an unset and an empty NX_BASE, so by line 45 the variable can never
# be empty and the `-z` arm can never be true. P0-2 deletes it. **Deleting unreachable code changes
# no behaviour, so no test can fail today because of it, and this file does not pretend otherwise.**
# Writing one would be a check that cannot fail, which is the defect this repository already has 5
# refutations' worth of scar tissue about (scripts/graph-guard_test.sh).
#
# What this file does instead is HOLD THE SURVIVING BEHAVIOUR, so the implementer cannot delete the
# wrong half. Every assertion here is GREEN TODAY and must stay green after the deletion.
#
# ASSERTION 2 IS ALSO THE EVIDENCE THAT THE ARM IS DEAD, and it is an observation rather than a
# reading of the source: with NX_BASE set to the empty string the verb invokes nx with
# `--base=origin/main`. Were the `-z` arm reachable, that same input would produce `--base=HEAD~1`.
# The two are distinguishable at the seam, so the claim "the arm is dead" is measured here, not
# asserted from line numbers that a later edit could move.
#
# HOW THE RESOLVED VALUE IS OBSERVED. No verb prints it — that is a real gap and it is stated in
# the report rather than papered over. So the observation is made at the only seam that carries it:
# an `nx` that records the argv it was invoked with, planted at `node_modules/.bin/nx` inside a
# staged COPY of the repository. This is scripts/graph-guard_test.sh's shim idiom, and
# node_modules/.bin is deliberately the location rather than PATH because that is eden's real CI
# shape (nx is installed by `yarn install` and is never on PATH).
#
# WHAT A GREEN RUN PROVES, over all 6 verbs that pass `--base`:
#   1. NX_BASE unset          -> --base=origin/main
#   2. NX_BASE=""             -> --base=origin/main   (line 44 substitutes; the `-z` arm is dead)
#   3. NX_BASE=0000...0       -> --base=HEAD~1        (the first-push / force-push sentinel)
#   4. NX_BASE=<any ref>      -> --base=<that ref>    (nothing is hard-coded over the caller)
#   plus, in every case, that `--base=` is never passed EMPTY — the failure the sentinel fold and
#   the dead arm were both written to prevent.
#
# SCOPE — read this before reading a green run as more than it is.
#   COVERED: the value of the `--base=` argument each affected-* verb hands to nx.
#   NOT COVERED: whether that base RESOLVES in git (the shim answers 0 to everything), what nx does
#     with it, and any verb that does not take a base (run-many, graph-guard).
#
# Run it directly:  bash scripts/nx-base_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
ctl_source="${repository_root}/.ci/ctl.sh"
bash_binary="$(command -v bash)"

# The verbs that pass a base, as LITERALS. A verb that stops passing one is caught by the
# per-invocation assertion below, which requires a `--base=` argument to be present at all.
base_verbs=(
  "affected-build"
  "affected-test"
  "affected-check"
  "affected-gate"
  "affected-gate-fast"
  "affected-gate-substrate"
)

# The all-zeros SHA GitHub delivers as `github.event.before` on a first push or a force push.
zero_sha="0000000000000000000000000000000000000000"

# <label>|<mode>|<NX_BASE value>|<expected --base= value>
# mode `unset` runs with NX_BASE removed from the environment; mode `set` exports the value, empty
# string included.
base_cases=(
  "NX_BASE unset|unset||origin/main"
  "NX_BASE is the empty string|set||origin/main"
  "NX_BASE is the all-zeros SHA|set|${zero_sha}|HEAD~1"
  "NX_BASE names a ref|set|eden-nx-base-probe-ref|eden-nx-base-probe-ref"
)

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
  printf 'nx-base_test: FAILED — the file under test does not exist: %s\n' "$ctl_source" >&2
  exit 1
fi

work_dir=""
interrupted=0
sweep() {
  local rc=$?
  [[ -n "$work_dir" ]] && rm -rf "$work_dir"
  if [[ $interrupted -ne 0 ]]; then
    printf 'nx-base_test: INTERRUPTED before it finished — reporting %d, never success\n' \
      "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP

work_dir="$(mktemp -d -t eden-nx-base.XXXXXX)"
staged_root="${work_dir}/staged"
record_file="${work_dir}/nx-invocations.txt"

# A COPY of everything `.ci/ctl.sh` reads, never a symlink, with `git init` so the verb's own
# `git rev-parse --show-toplevel` resolves inside the staged tree and never reaches the real one.
mkdir -p "${staged_root}/.ci"
cp "$ctl_source" "${staged_root}/.ci/ctl.sh"
cp "${repository_root}/.ci/graph-roster.txt" "${staged_root}/.ci/graph-roster.txt"
if [[ -d "${repository_root}/.devcontainer/_ctl" ]]; then
  mkdir -p "${staged_root}/.devcontainer"
  cp -RL "${repository_root}/.devcontainer/_ctl" "${staged_root}/.devcontainer/_ctl"
fi
if ! git_output="$(git -C "$staged_root" init --quiet 2>&1)"; then
  printf 'nx-base_test: FAILED — git init in the staged tree failed: %s\n' "$git_output" >&2
  exit 1
fi

: > "$record_file"
mkdir -p "${staged_root}/node_modules/.bin"
cat > "${staged_root}/node_modules/.bin/nx" <<SHIM
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "${record_file}"
exit 0
SHIM
chmod +x "${staged_root}/node_modules/.bin/nx"

# PREFLIGHT — the shim must be the nx that answers. A real nx on PATH would take precedence
# (has_nx and nx_cmd both check PATH first), and then every recorded line below would be missing
# and every assertion would red for a reason that has nothing to do with the base.
if command -v nx >/dev/null 2>&1; then
  report_fail 'the recording shim is the nx that answers' \
    "an nx is on PATH at $(command -v nx); nx_cmd prefers it over node_modules/.bin/nx" \
    'this test cannot observe the base while a real nx shadows the shim'
  printf '\nnx-base_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi

verb_rc=0
verb_err=''
# run_verb <mode> <NX_BASE value> <verb> — the status is the command's own; `|| true` would discard
# it and a dead verb would read as a success.
run_verb() {
  local mode="$1" value="$2" verb="$3"
  local error_file="${work_dir}/verb.err"
  verb_rc=0
  if [[ "$mode" == "unset" ]]; then
    ( cd "$staged_root" && env -u NX_BASE "$bash_binary" .ci/ctl.sh "$verb" ) \
      >/dev/null 2>"$error_file" || verb_rc=$?
  else
    ( cd "$staged_root" && NX_BASE="$value" "$bash_binary" .ci/ctl.sh "$verb" ) \
      >/dev/null 2>"$error_file" || verb_rc=$?
  fi
  verb_err="$(cat "$error_file")"
  rm -f "$error_file"
}

printf -- '-- the resolved --base=, read off the nx invocation --\n'

for base_case in "${base_cases[@]}"; do
  IFS='|' read -r case_label case_mode case_value case_expected <<< "$base_case"
  for verb in "${base_verbs[@]}"; do
    : > "$record_file"
    run_verb "$case_mode" "$case_value" "$verb"
    recorded="$(cat "$record_file")"
    if [[ $verb_rc -ne 0 ]]; then
      report_fail "${case_label}: '${verb}' invokes nx" \
        "the verb exited ${verb_rc} before nx could be observed" \
        "stderr: $(printf '%s' "$verb_err" | head -1 | cut -c1-160)"
      continue
    fi
    if [[ -z "$recorded" ]]; then
      report_fail "${case_label}: '${verb}' invokes nx" \
        'the verb exited 0 and the nx shim recorded nothing — it reported success having run nothing'
      continue
    fi
    IFS=$' \t\n' read -r -a recorded_arguments <<< "$recorded"
    seen_base=''
    has_base=0
    for argument in "${recorded_arguments[@]+"${recorded_arguments[@]}"}"; do
      if [[ "$argument" == --base=* ]]; then
        has_base=1
        seen_base="${argument#--base=}"
      fi
    done
    if [[ $has_base -eq 0 ]]; then
      report_fail "${case_label}: '${verb}' passes a --base= to nx" \
        "the recorded invocation carries no --base= argument: ${recorded}"
    elif [[ -z "$seen_base" ]]; then
      report_fail "${case_label}: '${verb}' never passes an EMPTY base" \
        'nx was invoked with a bare --base= — every affected git call would fail' \
        "recorded: ${recorded}"
    elif [[ "$seen_base" != "$case_expected" ]]; then
      report_fail "${case_label}: '${verb}' resolves the base to '${case_expected}'" \
        "it passed --base=${seen_base}" \
        "recorded: ${recorded}"
    else
      report_ok "${case_label}: '${verb}' -> --base=${seen_base}"
    fi
  done
done

printf '\n'
if [[ $fails -ne 0 ]]; then
  printf 'nx-base_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'nx-base_test: all assertions passed (%d base case(s) x %d verb(s) = %d observed invocation(s))\n' \
  "${#base_cases[@]}" "${#base_verbs[@]}" "$(( ${#base_cases[@]} * ${#base_verbs[@]} ))"
