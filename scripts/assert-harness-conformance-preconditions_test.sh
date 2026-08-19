#!/usr/bin/env bash
#
# scripts/assert-harness-conformance-preconditions_test.sh — behaviour test for
# scripts/assert-harness-conformance-preconditions.sh.
#
# The gate on the gate must say 2 things at once, and the second one must never weaken the first:
#
#   THE TIER IS LOUD. There is no codex adapter, so nothing in the conformance suite exercises the
#   codex pin. Today the row for codex reads exactly like the rows for claude and omp, so a green
#   run reports "3 harness pin(s) verified" and a reader takes codex for a proven pin. It is a
#   PINNED-BUT-UNEXERCISED tier, and the run must say so in the codex row AND in the summary
#   (Mateo's D3: bump it and declare the tier loudly). The label belongs to codex alone: a claude or
#   omp row that carries it would hide a tier that IS exercised.
#
#   THE LABEL SOFTENS NOTHING. A label that turns the codex row advisory is the failure this file
#   exists to prevent — a drifted codex binary, an absent codex binary and an absent credential must
#   each still stop the run. Those cases pass TODAY, and they are here to stay red-proof after the
#   label lands.
#
# It drives the subject against stub `claude`, `omp` and `codex` binaries on PATH, in the style of
# assert-no-skipped-tests_test.sh, and against the REAL harnesses/versions.env: the stubs answer
# with the pins the manifest holds today, so a pin bump keeps this test honest instead of stale. No
# harness, no credential and no network take part. Run it directly:
#   bash scripts/assert-harness-conformance-preconditions_test.sh
# It exits non-zero when any assertion mismatches. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
subject="${here}/assert-harness-conformance-preconditions.sh"
versions_file="${here}/../harnesses/versions.env"

for required_file in "$subject" "$versions_file"; do
  if [[ ! -f "$required_file" ]]; then
    printf 'assert-harness-conformance-preconditions_test: FAILED — absent: %s\n' "$required_file" >&2
    exit 1
  fi
done

fails=0
work="$(mktemp -d "${TMPDIR:-/tmp}/assert-harness-conformance-preconditions_test.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# --- the pins under test come from the manifest itself -------------------------------------------
# pin_value <variable> — read one pin out of the tracked manifest in a subshell, so the test shell
# never inherits the manifest's variables.
pin_value() {
  bash -c '
    set -Eeuo pipefail
    # shellcheck disable=SC1090
    source "$1"
    printf "%s\n" "${!2:-}"
  ' _ "$versions_file" "$1"
}

pinned_claude="$(pin_value CLAUDE_CODE_VERSION)"
pinned_omp="$(pin_value OMP_VERSION)"
pinned_codex="$(pin_value CODEX_VERSION)"
for pin_pair in "CLAUDE_CODE_VERSION=${pinned_claude}" "OMP_VERSION=${pinned_omp}" \
  "CODEX_VERSION=${pinned_codex}"; do
  if [[ "${pin_pair#*=}" == '' ]]; then
    printf 'assert-harness-conformance-preconditions_test: FAILED — %s is empty in %s; the stubs would answer with nothing and every case below would pass vacuously.\n' \
      "${pin_pair%%=*}" "$versions_file" >&2
    exit 1
  fi
done

# --- the stubs ----------------------------------------------------------------------------------
stub_directory="${work}/bin"
mkdir -p "$stub_directory"
cat >"${stub_directory}/claude" <<'STUB_CLAUDE'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s (Claude Code)\n' "${STUB_CLAUDE_VERSION}"
STUB_CLAUDE
cat >"${stub_directory}/omp" <<'STUB_OMP'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "${STUB_OMP_VERSION}"
STUB_OMP
cat >"${stub_directory}/codex" <<'STUB_CODEX'
#!/usr/bin/env bash
set -Eeuo pipefail
printf 'codex-cli %s\n' "${STUB_CODEX_VERSION}"
STUB_CODEX
chmod +x "${stub_directory}/claude" "${stub_directory}/omp" "${stub_directory}/codex"

# The same stub set without codex, for the not-installed case.
stub_directory_without_codex="${work}/bin-without-codex"
mkdir -p "$stub_directory_without_codex"
cp "${stub_directory}/claude" "${stub_directory}/omp" "$stub_directory_without_codex/"

original_path="$PATH"
PATH="${stub_directory}:${original_path}"
export PATH
export HARNESS_VERSIONS_FILE="$versions_file"
export STUB_CLAUDE_VERSION="$pinned_claude"
export STUB_OMP_VERSION="$pinned_omp"
export STUB_CODEX_VERSION="$pinned_codex"
# Obvious non-credentials: the subject only asks whether they are non-empty, and no session, no
# request and no harness runs anywhere in this file.
export CLAUDEADAPTER_LIVE_TOKEN='test-only-not-a-credential'
export OPENROUTER_API_KEY='test-only-not-a-credential'

for stub_name in claude omp codex; do
  resolved="$(command -v "$stub_name")"
  if [[ "$resolved" != "${stub_directory}/${stub_name}" ]]; then
    printf 'assert-harness-conformance-preconditions_test: FAILED — the stub %s is not first on PATH (got %s).\n' \
      "$stub_name" "$resolved" >&2
    exit 1
  fi
done

# --- the harness --------------------------------------------------------------------------------
run_status=0
run_output=''

run_subject() {
  run_output="$( ( bash "$subject" ) 2>&1 )" && run_status=0 || run_status=$?
}

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

# expect_case <name> <want status> <text that must appear> <text that must not appear|empty>
expect_case() {
  local name="$1" want_status="$2" want_present="$3" want_absent="$4"
  local problems=()
  if [[ $run_status -ne $want_status ]]; then
    problems+=("exit status got=${run_status} want=${want_status}")
  fi
  if [[ -n "$want_present" && "$run_output" != *"$want_present"* ]]; then
    problems+=("output does not contain: ${want_present}")
  fi
  if [[ -n "$want_absent" && "$run_output" == *"$want_absent"* ]]; then
    problems+=("output must not contain: ${want_absent}")
  fi
  if [[ ${#problems[@]} -ne 0 ]]; then
    problems+=('--- subject output ---' "$run_output" '----------------------')
    report_fail "$name" "${problems[@]}"
    return 0
  fi
  printf '  ok    %s\n' "$name"
}

# output_line_starting_with <prefix> — the first line of the last run that starts with the prefix.
output_line_starting_with() {
  local prefix="$1" line
  while IFS= read -r line; do
    if [[ "$line" == "${prefix}"* ]]; then
      printf '%s\n' "$line"
      return 0
    fi
  done <<<"$run_output"
  return 1
}

# expect_line_label <case name> <line prefix> <present|absent> — the UNEXERCISED label is on the row
# it belongs to and on no other row.
expect_line_label() {
  local name="$1" prefix="$2" want="$3" line=''
  if ! line="$(output_line_starting_with "$prefix")"; then
    report_fail "$name" "no line of the output starts with '${prefix}'" \
      '--- subject output ---' "$run_output" '----------------------'
    return 0
  fi
  if [[ "$want" == 'present' && "$line" != *UNEXERCISED* ]]; then
    report_fail "$name" "this line carries no UNEXERCISED label: ${line}" \
      'the codex pin is bumped and exercised by nothing; the row and the summary must say so'
    return 0
  fi
  if [[ "$want" == 'absent' && "$line" == *UNEXERCISED* ]]; then
    report_fail "$name" "the row carries an UNEXERCISED label it must not: ${line}" \
      'claude and omp ARE exercised by the conformance suite'
    return 0
  fi
  printf '  ok    %s\n' "$name"
}

# --- test 4 — the codex row is labelled UNEXERCISED, in the row and in the summary ----------------
printf '\n-- test 4: the UNEXERCISED tier --\n'
run_subject
expect_case 'preconditions: stubs on the pins + both credentials -> exit 0' \
  0 'assert-harness-conformance-preconditions: OK' 'FAILED'
expect_line_label 'tier: the codex row carries UNEXERCISED' 'codex --version' present
expect_line_label 'tier: the claude row does not carry UNEXERCISED' 'claude --version' absent
expect_line_label 'tier: the omp row does not carry UNEXERCISED' 'omp --version' absent
expect_line_label 'tier: the summary carries UNEXERCISED' \
  'assert-harness-conformance-preconditions: OK' present

# --- test 5 — the label softens nothing -----------------------------------------------------------
printf '\n-- test 5: the label softens nothing --\n'

# A codex binary that does not carry its pin is drift, and drift stops the run.
export STUB_CODEX_VERSION='0.99.0'
run_subject
expect_case 'drift: codex reports 0.99.0 against its pin -> exit 1' 1 'drift' 'OK —'
expect_case 'drift: the failure names codex and both versions' 1 "0.99.0" ''
expect_case 'drift: the failure names the pin it wanted' 1 "$pinned_codex" ''
export STUB_CODEX_VERSION="$pinned_codex"

# A drifted claude proves the label is scoped to codex: the other rows keep their teeth.
export STUB_CLAUDE_VERSION='0.0.1'
run_subject
expect_case 'drift: claude reports 0.0.1 against its pin -> exit 1' 1 'drift' 'OK —'
export STUB_CLAUDE_VERSION="$pinned_claude"

# An absent codex binary is not "unexercised, so never mind": the pin cannot be proven at all.
#
# The case CONSTRUCTS the absence rather than hoping for it. Keeping the inherited PATH here was a
# defect of the worst polarity: post-create installs codex through npm, so in the devcontainer
# ~/.nvm/versions/node/*/bin still resolves one and the case reported FAIL, while the CI container
# resolved none and the same case reported ok. The set is the stub directory plus the system
# directories the stubs' own `#!/usr/bin/env bash` needs — this is the sibling suite's pattern
# (assert-peer-messaging-available_test.sh, the claude-absent case).
saved_path="$PATH"
PATH="${stub_directory_without_codex}:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
if command -v codex >/dev/null 2>&1; then
  report_fail 'absent: codex is not installed -> exit 1' \
    "this PATH still resolves a codex: $(command -v codex)" \
    'a codex in a system directory would have to be removed for this case to construct absence'
else
  run_subject
  expect_case 'absent: codex is not installed -> exit 1, named' 1 'not installed' 'OK —'
  expect_case 'absent: the failure names codex' 1 'codex' ''
fi
PATH="$saved_path"
export PATH

# An absent live credential is still the FAIL-NOT-SKIP rule, label or no label.
unset OPENROUTER_API_KEY
run_subject
expect_case 'credential: OPENROUTER_API_KEY unset -> exit 1, named' 1 'OPENROUTER_API_KEY' 'OK —'
export OPENROUTER_API_KEY='test-only-not-a-credential'

unset CLAUDEADAPTER_LIVE_TOKEN
run_subject
expect_case 'credential: CLAUDEADAPTER_LIVE_TOKEN unset -> exit 1, named' \
  1 'CLAUDEADAPTER_LIVE_TOKEN' 'OK —'
export CLAUDEADAPTER_LIVE_TOKEN='test-only-not-a-credential'

if [[ $fails -ne 0 ]]; then
  printf '\nassert-harness-conformance-preconditions_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nassert-harness-conformance-preconditions_test: all assertions passed (pins %s / %s / %s)\n' \
  "$pinned_claude" "$pinned_omp" "$pinned_codex"
