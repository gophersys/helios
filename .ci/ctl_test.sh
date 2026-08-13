#!/usr/bin/env bash
#
# .ci/ctl_test.sh — prove that a tier verb FAILS when `cictl affected` fails.
#
# .ci/ctl.sh:74:
#
#     mapfile -t projects < <(affected_projects)
#
# `affected_projects` opens with `require_cmd cictl`, whose failure path is `exit 127`.
# A process substitution is a SUBSHELL, so that exit kills the subshell and nothing else.
# `mapfile` reads an empty stream, the caller finds 0 projects, logs "no affected projects
# — clean no-op", and returns 0. Measured on this repository, same worktree, same base:
#
#   without cictl:  [error] missing required tool(s): cictl
#                   no affected projects for base 'origin/main' — clean no-op    rc=0
#   with cictl:     affected = go/objectstorage, go/secrets, go/workspaceprovider rc=1
#
# The pull-request gate reported PASS over 3 real libraries, 1 of them RED.
#
# THE CLASS, NOT THE LINE. The absent binary is only the cheapest stimulus. What is
# discarded is the STATUS of the producer, so ANY failure of `cictl affected` is swallowed
# the same way — a bad base ref, a shallow clone, a git fault, a tool killed half-way. CI
# survives today only because the runner image happens to carry cictl, and nothing asserts
# that. So this suite drives 4 stimuli through the same site, and drives the missing tool
# through all 3 tier verbs, because all 3 read that one stream and a fix at one call site
# would leave the other 2 swallowing.
#
#   absent   no cictl on the PATH at all         → the tier must FAIL and name the tool
#   failing  cictl affected exits 2, prints none → the tier must FAIL
#   partial  cictl prints 1 project, then exits 2→ the tier must FAIL over a part listing
#   empty    cictl exits 0, prints nothing       → the tier must PASS, rc=0
#
# The last one is not optional. A gate that cannot tell "the tool failed" from "the tool
# ran and found nothing" has replaced a false green with a false red, and a fix that simply
# never returns 0 would satisfy the first 3 stimuli. Its counter-stimulus is the failing
# cictl with the SAME empty output, so the ONLY difference between the 2 runs is the exit
# status — which is the byte the defect throws away.
#
# WHERE THE SWALLOW MOVES TO. Reading the status at the call site is not enough on its own,
# because of WHERE the status is read. In
#
#     listing="$(affected_projects)" || status=$?
#
# the producer sits on the LEFT of `||`, and bash disables errexit for the WHOLE of a
# function invoked in a condition. Only the LAST command's status becomes the function's
# status; every earlier command's status is discarded — the same defect, moved one function
# inward. It is harmless only while the producer's body holds nothing that can fail before
# its last line, which is an accident of today's 2-line body, not a property. Adding one
# ordinary line (`git fetch` the base before diffing it) restores the false green in full.
# So 2 more tests, each reading the hazard a different way:
#
#   behaviour  a fault is PLANTED before the producing command, and the tier must fail.
#              This is the only stimulus that can show the fault, because today's body has
#              no command that can fail before its last one — the hazard is latent, and a
#              latent hazard has to be woken to be measured.
#   shape      shellcheck's own `check-set-e-suppressed` (SC2310) reads the whole file, so
#              it also covers call sites this suite never drives. It is OPTIONAL, and
#              `cmd_validate` runs shellcheck bare, so the gate is blind to it: this test is
#              where that check is switched on for this 1 file. The 2 tests are complements
#              — the linter reads shapes but no behaviour, and a lint can be suppressed with
#              a comment while a planted fault cannot.
#
# WHAT 127 MEANS. Rule 20 states the value: "an absent tool is a gate failure (exit 127),
# not a skip". The absent-tool tests therefore pin 127 exactly, not merely "non-zero" — a
# refactor that coerces the status to 1 would keep the gate failing while destroying the
# signal that says WHY. Where no rule states a value (a cictl that ran and failed), the
# tests require failure only, and leave the value to the implementation.
#
# 2 phases, after ctl_test.sh and go/_ctl/lib_test.sh:
#
#   phase 1  behaviour      — each test asserts what the tier verb must do.
#   phase 2  discrimination — each test is re-run under the counter-stimulus declared for
#                             it, and must FAIL. A test that passes both ways read nothing.
#
# Every test builds a THROWAWAY tree under mktemp -d holding a copy of the .ci/ctl.sh under
# test, its own git root, its own 2 fixture libraries, and its own PATH. The PATH holds the
# ordinary utilities and NOTHING else, so "cictl is absent" is a property of the fixture
# rather than a property of the host — and install_cictl PROVES the stimulus before the run,
# because a probe that ran in a shell which already held the tool proves nothing.
#
# Usage: bash .ci/ctl_test.sh [test-name]
#
# shellcheck shell=bash
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CTL="$HERE/ctl.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The 3 tier verbs that read the affected set. All 3 reach the same helper, so all 3 carry
# the same swallow; the list is EXPLICIT so a 4th verb has to be added here to be covered.
TIER_VERBS=(affected-gate-fast affected-gate-substrate gate-all)

# The ordinary utilities the fixture PATH holds. The list is what makes the `absent`
# stimulus real: the sandbox PATH is this directory ALONE, so no cictl on this host — or on
# the CI runner image, which does carry one — can reach the script under test.
SANDBOX_TOOLS=(bash git dirname basename cat mktemp rm sed awk grep tr sort uniq wc head tail env true false)

# The shellcheck check that reads the "invoked where set -e is suppressed" shape. It is
# OPTIONAL, so it is named here once and its presence is asserted before it is trusted.
ERREXIT_CHECK="check-set-e-suppressed"

# CICTL is the stimulus: which cictl the next run finds. MUTATION is the second stimulus:
# an edit to the COPY of the script under test, for the hazards that today's source cannot
# express on its own. The driver repoints both between phase 1 and phase 2.
CICTL="absent"
MUTATION="none"
# OUT, RC and GATED hold the last run_verb result: its merged output, its exit status, and
# the record of which fixture library was gated with which verb.
OUT=""
RC=0
GATED=""

info() { printf '\033[0;36m[test]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[0;31m FAIL \033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[test]\033[0m %s\n' "$*" >&2; exit 1; }
# fail ends the test it is called from. Each test runs in its own subshell.
fail() { printf '       %s\n' "$*" >&2; exit 1; }

# .ci/ctl.sh uses mapfile, which bash 3.2 (the macOS /bin/bash) does not have. Running the
# suite there would exercise nothing, so it is a failure that names the reason.
type -t mapfile >/dev/null ||
  die "this bash (${BASH_VERSION}) has no mapfile, so .ci/ctl.sh cannot run here; run the suite in ghcr.io/gophersys/base"
# FAIL-NOT-SKIP (ADR-0020): a missing tool is a failure that names the tool.
for _tool in "${SANDBOX_TOOLS[@]}" chmod mkdir cp cmp shellcheck; do
  command -v "$_tool" >/dev/null || die "this host has no $_tool; the suite cannot run"
done
# Resolved BEFORE any fixture replaces PATH, so the harness always starts the real bash.
REAL_BASH="$(command -v bash)"
[[ -f "$CTL" ]] || die "the script under test is missing: $CTL"

# ── the fixture ─────────────────────────────────────────────────────────────

# write_project <fixture> <path> — a fixture library. It records the verb it was gated with
# and succeeds, so a gate that RAN is visible in the log, and a gate that never ran is
# visible by the log staying empty.
write_project() {
  local fix="$1" project="$2"
  mkdir -p "$fix/$project"
  cat > "$fix/$project/ctl.sh" <<'PROJECT'
#!/usr/bin/env bash
#
# A fixture library. Every verb succeeds; the point is only whether it was reached.
set -Eeuo pipefail
printf '%s %s\n' "${PWD##*/}" "$*" >> "$EDEN_TEST_GATED_LOG"
printf 'fixture gate: %s %s\n' "${PWD##*/}" "$*"
PROJECT
  chmod +x "$fix/$project/ctl.sh"
}

# install_mutation <fixture> edits the COPY of the script under test. Two hazards in this
# feature cannot be driven from outside the file: one is latent until the producer gains a
# command that can fail, and one is a SHAPE. Each mutation is a change a reviewer would
# plausibly make, and each is proven to have taken — an anchor that is gone, an edit that
# changed nothing, or a result that does not parse is a LOUD failure of this suite, because
# a mutation that did not apply leaves a test asserting a stimulus that never happened.
#
# Each anchor is stated with the test that needs it. They are the price of reaching a hazard
# that lives INSIDE the producer: a test that refuses to name any structure could not reach
# this class at all, and this class is the one that survived the first fix.
install_mutation() {
  local fix="$1" target mutated
  target="$fix/.ci/ctl.sh"
  mutated="$target.mutated"
  case "$MUTATION" in
    none)
      return 0
      ;;
    # ANCHOR: the single `cictl affected -C …` invocation, wherever it lives — inside the
    # producer function or inlined at the call site. A fault is planted on the line BEFORE
    # it, so the producing command is no longer the first command that can fail.
    fault-before-the-producer)
      # shellcheck disable=SC2016  # the awk program must emit a literal $REPO_ROOT, not its value
      awk '
        /cictl affected -C/ {
          match($0, /^[ \t]*/)
          print substr($0, 1, RLENGTH) "git -C \"$REPO_ROOT\" fetch --quiet origin \"$NX_BASE\""
          hits++
        }
        { print }
        END { if (hits != 1) { exit 3 } }
      ' "$target" > "$mutated" ||
        fail "the fault could not be planted: there is no single 'cictl affected -C' invocation to plant it before. The producer has been refactored, so this test must be re-read rather than repaired"
      ;;
    # No anchor at all: the shape is APPENDED after main, where it never runs and only the
    # linter reads it. It is the counter-stimulus for the shape test, and it doubles as the
    # proof that the optional check really looked at this file.
    suppressed-call-appended)
      cp "$target" "$mutated"
      cat >> "$mutated" <<'PROBE'

# Appended by .ci/ctl_test.sh as a counter-stimulus. It is the shape the check exists to
# find: a producer invoked on the left of ||, where set -e is disabled for its whole body.
function _probe_producer() {
  git -C "$REPO_ROOT" rev-parse --show-toplevel
  printf 'probe\n'
}

function _probe_consumer() {
  local out="" status=0
  out="$(_probe_producer)" || status=$?
  printf '%s %s\n' "$out" "$status"
}
PROBE
      ;;
    *) die "unknown mutation: $MUTATION" ;;
  esac
  if cmp -s "$target" "$mutated"; then
    fail "the '$MUTATION' mutation changed nothing, so the run would prove nothing"
  fi
  bash -n "$mutated" ||
    fail "the '$MUTATION' mutation left a file bash cannot parse, so any failure below would be the mutation's, not the script's"
  mv "$mutated" "$target"
}

# new_fixture prints a fresh tree: a git root (.ci/ctl.sh resolves REPO_ROOT with
# `git rev-parse`), a copy of the script under test, a sandbox PATH, and 2 libraries for a
# reporting cictl to name. .ci/ctl.sh reads a project's ctl.sh and nothing else, so a
# project.json here would assert nothing — the affected set arrives from cictl.
new_fixture() {
  local fix tool path
  fix="$(mktemp -d "$WORK/fix.XXXXXX")"
  fix="$(cd "$fix" && pwd -P)"
  mkdir -p "$fix/.ci" "$fix/bin"
  cp "$CTL" "$fix/.ci/ctl.sh"
  install_mutation "$fix"
  git -C "$fix" init --quiet ||
    die "git init failed in $fix; .ci/ctl.sh resolves its repository root with git, so the fixture needs one"
  for tool in "${SANDBOX_TOOLS[@]}"; do
    path="$(command -v "$tool")" ||
      die "this host has no $tool; the sandbox PATH cannot be built (FAIL-NOT-SKIP)"
    ln -s "$path" "$fix/bin/$tool"
  done
  write_project "$fix" go/alpha
  write_project "$fix" go/beta
  printf '%s' "$fix"
}

# write_cictl <fixture> <listing> <exit-code> — the cictl the script under test will find.
# `affected` prints the listing and exits with the code; a non-zero code also prints git's
# own wording for an unresolvable base, because that stream reaching the reader is half of
# what a failing gate owes.
write_cictl() {
  local fix="$1" listing="$2" code="$3"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
#
# The cictl this fixture puts on PATH. It implements `affected` only.
set -Eeuo pipefail
HEAD
    printf 'LISTING=%q\n' "$listing"
    printf 'CODE=%s\n' "$code"
    cat <<'TAIL'
if [[ "${1:-}" != "affected" ]]; then
  printf 'cictl: this fixture implements affected only, not %s\n' "${1:-}" >&2
  exit 64
fi
[[ -z "$LISTING" ]] || printf '%s\n' "$LISTING"
if [[ "$CODE" -ne 0 ]]; then
  printf "cictl: fatal: ambiguous argument 'origin/main': unknown revision\n" >&2
fi
exit "$CODE"
TAIL
  } > "$fix/bin/cictl"
  chmod +x "$fix/bin/cictl"
}

# install_cictl <fixture> puts the stimulus in place AND proves it: an `absent` stimulus
# that is not absent, or an installed one that the script under test cannot reach, would
# make the run below prove nothing at all. The probe runs in a subshell holding EXACTLY the
# PATH the script under test is given, never the harness's own.
install_cictl() {
  local fix="$1" found=0
  case "$CICTL" in
    absent)  rm -f "$fix/bin/cictl" ;;
    failing) write_cictl "$fix" "" 2 ;;
    empty)   write_cictl "$fix" "" 0 ;;
    partial) write_cictl "$fix" "go/alpha" 2 ;;
    reports) write_cictl "$fix" "$(printf 'go/alpha\ngo/beta')" 0 ;;
    *) die "unknown cictl stimulus: $CICTL" ;;
  esac
  if ( PATH="$fix/bin"; command -v cictl >/dev/null ); then
    found=1
  fi
  if [[ "$CICTL" == "absent" ]]; then
    [[ "$found" -eq 0 ]] ||
      fail "the 'absent' stimulus is not absent: a cictl is reachable on the fixture PATH, so the run would prove nothing"
  else
    [[ "$found" -eq 1 ]] ||
      fail "the '$CICTL' stimulus left no reachable cictl on the fixture PATH, so the run would prove nothing"
  fi
}

# ── the harness ─────────────────────────────────────────────────────────────

# run_verb <fixture> <verb> runs one tier verb over the fixture and sets OUT, RC and GATED.
# The fixture PATH REPLACES the harness's, so the only cictl in reach is the stimulus.
run_verb() {
  local fix="$1" verb="$2"
  RC=0
  : > "$fix/gated.log"
  OUT="$(PATH="$fix/bin" EDEN_TEST_GATED_LOG="$fix/gated.log" \
    "$REAL_BASH" "$fix/.ci/ctl.sh" "$verb" 2>&1)" || RC=$?
  GATED="$(cat "$fix/gated.log")"
}

out_has() { grep -Fq -- "$1" <<<"$OUT"; }

# assert_verb_ran refuses a vacuous verdict: a run that died before it announced the tier
# never reached the affected set, so it proves nothing about the affected set.
assert_verb_ran() {
  out_has "$1:" ||
    fail "$1 never announced itself, so the run died before reading the affected set (git root? PATH?) — rc=$RC: $OUT"
}

# ── the tests ───────────────────────────────────────────────────────────────

# 1. The measured case. require_cmd's `exit 127` fires inside the process substitution's
# subshell, which is not the tier's shell, so the tier reads an empty stream and calls it a
# clean no-op. An empty affected set is a CLAIM about the diff; with no cictl to ask, the
# tier is not entitled to make it.
t_a_missing_cictl_fails_the_tier() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  ! out_has 'no affected projects' ||
    fail "no cictl was reachable, and the tier still reported an empty affected set — it never looked (rc=$RC): $OUT"
  # 127 exactly, not merely non-zero. Rule 20 states the value — "an absent tool is a gate
  # failure (exit 127), not a skip" — so a status coerced to 1 keeps the gate failing while
  # destroying the byte that says the TOOL was missing rather than the gate having run.
  [[ "$RC" -eq 127 ]] ||
    fail "no cictl was reachable and the tier exited $RC, not 127; rule 20 states 127 for an absent tool: $OUT"
  out_has 'cictl' ||
    fail "the tier failed without naming the tool it could not find: $OUT"
  [[ -z "$GATED" ]] ||
    fail "the affected set could not be known, yet the tier gated: $GATED"
}

# 2. The same swallow with the tool PRESENT. `cictl affected` exits 2 — a bad base ref, a
# shallow clone, any git fault — and the tier reads the same empty stream. This is the half
# that shows the defect is not about a binary existing: it is the discarded exit status.
t_a_failing_cictl_fails_the_tier() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  ! out_has 'no affected projects' ||
    fail "cictl affected exited 2, and the tier reported an empty affected set instead of a failure (rc=$RC): $OUT"
  [[ "$RC" -ne 0 ]] ||
    fail "cictl affected exited 2 and the tier exited 0; the affected set was never known: $OUT"
  out_has 'cictl' ||
    fail "the tier failed without naming the tool that failed: $OUT"
  out_has 'unknown revision' ||
    fail "cictl's own diagnostic never reached the reader; a stream the tier cannot read must not be discarded: $OUT"
}

# 3. The guard against over-fixing, and it is NOT optional. A genuinely empty diff is a
# clean pass. Its counter-stimulus prints the SAME nothing and exits 2, so the only
# difference between the 2 runs is the status — and a tier that reads the status tells them
# apart while today's tier cannot.
t_an_empty_affected_set_is_a_clean_pass() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  [[ "$RC" -eq 0 ]] ||
    fail "cictl ran and reported that nothing changed, and the tier exited $RC; a gate that cannot pass misleads exactly as much as one that cannot fail: $OUT"
  out_has 'no affected projects' ||
    fail "nothing was affected and the tier never said so: $OUT"
  [[ -z "$GATED" ]] ||
    fail "nothing was affected, and the tier gated anyway: $GATED"
}

# 4. The listing that dies half-way: cictl names go/alpha, then exits 2 with go/beta never
# printed. The tier gates the 1 project it saw and declares the affected projects green.
# This is the stimulus a fix of the shape "an EMPTY listing is a failure" still fails, which
# is why it is here: the status has to be read, not the length of the output.
t_a_partial_listing_that_fails_is_not_a_green_tier() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  [[ "$RC" -ne 0 ]] ||
    fail "cictl printed 1 project and then exited 2, and the tier exited 0 over a listing it cannot know is complete: $OUT"
  ! out_has 'affected project(s) green' ||
    fail "the tier declared the affected projects green from a listing that died half-way: $OUT"
  out_has 'cictl' ||
    fail "the tier failed without naming the tool that failed: $OUT"
}

# 5. The class. All 3 tier verbs reach run_phase_gate_over_affected, so all 3 read the same
# swallowed stream: pr, merge and nightly alike. A fix at 1 call site would leave 2 tiers
# reporting PASS over libraries they never looked at, so the property is asserted per verb.
t_every_tier_verb_refuses_a_missing_cictl() {
  local fix verb
  fix="$(new_fixture)"
  install_cictl "$fix"
  for verb in "${TIER_VERBS[@]}"; do
    run_verb "$fix" "$verb"
    assert_verb_ran "$verb"
    ! out_has 'no affected projects' ||
      fail "$verb reported an empty affected set with no cictl to ask (rc=$RC): $OUT"
    [[ "$RC" -eq 127 ]] ||
      fail "$verb exited $RC, not 127, with no cictl to ask; the swallow is in the shared helper, so the value has to hold at every tier verb, not at one: $OUT"
  done
}

# 6. The swallow one function inward, and the reason the fix has to be structural. The
# producer is invoked on the LEFT of `||`, so bash disables errexit for its whole body and
# only its LAST command's status survives. Today's body cannot show that — `require_cmd`
# EXITS rather than returns, and the only other command is the last one — so the fault is
# PLANTED: a `git fetch` of the base before the diff, which is an ordinary thing to add and
# which fails in this fixture because the fixture has no remote. cictl then SUCCEEDS, so the
# producer's last command is green and the tier is told everything is well.
#
# The stimulus names a structure (the `cictl affected -C` invocation) and this test cannot
# be written without doing so, because the hazard is latent in the source as it stands. The
# anchor is a LOUD failure when it is gone, never a silent pass.
t_a_fault_inside_the_producer_fails_the_tier() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  # The stimulus first: a planted fault that did not fail would make everything below vacuous.
  out_has 'does not appear to be a git repository' ||
    fail "no failing command ran inside the producer in this run, so the assertions below would prove nothing (rc=$RC): $OUT"
  [[ "$RC" -ne 0 ]] ||
    fail "a command inside the producer failed, its diagnostic reached the log, and the tier still exited 0; only the producer's LAST status is being read: $OUT"
  ! out_has 'affected project(s) green' ||
    fail "the tier declared the affected projects green over a listing produced after a failure it never saw: $OUT"
}

# 7. The same hazard read as a SHAPE, over the whole file rather than over the 1 path this
# suite drives. shellcheck states it exactly (SC2310, "invoked in an || condition so set -e
# will be disabled"), but the check is OPTIONAL and cmd_validate runs shellcheck bare, so
# the repository gate cannot see it. Here it is switched on for this 1 file.
#
# The check's own presence is asserted before it is trusted: an unknown -o name makes the
# linter fail loudly rather than pass quietly, but a check merely RENAMED in a later release
# would silently examine nothing, and that is the one outcome a gate must never have. The
# counter-stimulus appends the shape after main, which also proves the option really looked
# at this file.
t_the_producer_is_not_invoked_where_errexit_is_suppressed() {
  local fix out="" rc=0
  fix="$(new_fixture)"
  shellcheck --list-optional | grep -Fq -- "$ERREXIT_CHECK" ||
    fail "this shellcheck does not list the optional check '$ERREXIT_CHECK', so switching it on would examine nothing: $(shellcheck --version | tr '\n' ' ')"
  out="$(shellcheck -o "$ERREXIT_CHECK" -f gcc "$fix/.ci/ctl.sh" 2>&1)" || rc=$?
  # 0 is clean and 1 is findings; anything else is shellcheck failing to read the file at all.
  [[ "$rc" -eq 0 || "$rc" -eq 1 ]] ||
    fail "shellcheck exited $rc, so it never read the file and its silence means nothing: $out"
  ! grep -Fq 'SC2310' <<<"$out" ||
    fail "the affected-set producer is invoked where set -e is suppressed, so only its LAST command's status can ever reach the tier: $out"
}

TESTS=(
  t_a_missing_cictl_fails_the_tier
  t_a_failing_cictl_fails_the_tier
  t_an_empty_affected_set_is_a_clean_pass
  t_a_partial_listing_that_fails_is_not_a_green_tier
  t_every_tier_verb_refuses_a_missing_cictl
  t_a_fault_inside_the_producer_fails_the_tier
  t_the_producer_is_not_invoked_where_errexit_is_suppressed
)

# ── the stimulus tables ─────────────────────────────────────────────────────

# stimulus_for <test> — the cictl phase 1 drives the test with. The table exists so a test
# can never run without a declared stimulus.
stimulus_for() {
  case "$1" in
    t_a_missing_cictl_fails_the_tier)              printf 'absent'  ;;
    t_a_failing_cictl_fails_the_tier)              printf 'failing' ;;
    t_an_empty_affected_set_is_a_clean_pass)       printf 'empty'   ;;
    t_a_partial_listing_that_fails_is_not_a_green_tier) printf 'partial' ;;
    t_every_tier_verb_refuses_a_missing_cictl)     printf 'absent'  ;;
    t_a_fault_inside_the_producer_fails_the_tier)  printf 'reports,fault-before-the-producer' ;;
    # The shape test never runs the script, so which cictl the fixture holds cannot reach it.
    t_the_producer_is_not_invoked_where_errexit_is_suppressed) printf 'absent' ;;
    *) die "no phase-1 stimulus is declared for $1" ;;
  esac
}

# counter_for <test> — the single change that must BREAK the test. Each is a real change of
# stimulus, never a stubbed answer.
counter_for() {
  case "$1" in
    t_a_missing_cictl_fails_the_tier)
      printf 'reports:cictl is on PATH and lists go/alpha + go/beta' ;;
    t_a_failing_cictl_fails_the_tier)
      printf 'empty:cictl prints the same nothing and exits 0, so only the STATUS differs' ;;
    t_an_empty_affected_set_is_a_clean_pass)
      printf 'failing:cictl prints the same nothing and exits 2, so only the STATUS differs' ;;
    t_a_partial_listing_that_fails_is_not_a_green_tier)
      printf 'reports:cictl lists go/alpha + go/beta and exits 0, so the listing is whole' ;;
    t_every_tier_verb_refuses_a_missing_cictl)
      printf 'reports:cictl is on PATH and lists go/alpha + go/beta' ;;
    t_a_fault_inside_the_producer_fails_the_tier)
      printf 'reports:no fault is planted, so every command in the producer succeeds' ;;
    t_the_producer_is_not_invoked_where_errexit_is_suppressed)
      printf 'absent,suppressed-call-appended:the suppressed-invocation shape is appended after main' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. <spec> is
# <cictl>[,<mutation>][:<the prose the driver prints>].
apply() {
  local spec="$1" head
  head="${spec%%:*}"
  CICTL="${head%%,*}"
  MUTATION="none"
  [[ "$head" != *,* ]] || MUTATION="${head#*,}"
  case "$CICTL" in
    absent|failing|empty|partial|reports) ;;
    *) die "unknown cictl in stimulus spec: $spec" ;;
  esac
  case "$MUTATION" in
    none|fault-before-the-producer|suppressed-call-appended) ;;
    *) die "unknown mutation in stimulus spec: $spec" ;;
  esac
}

# ── the driver ──────────────────────────────────────────────────────────────

# An argument selects 1 test by name, so a single red can be read on its own. A name that
# matches nothing is a hard error: a filter that silently selects 0 tests is a suite that
# exits 0 having checked nothing.
if [[ $# -gt 0 ]]; then
  selected=()
  for t in "${TESTS[@]}"; do
    if [[ "$t" == "$1" ]]; then
      selected+=("$t")
    fi
  done
  [[ ${#selected[@]} -gt 0 ]] || die "no test is named '$1'; the suite has: ${TESTS[*]}"
  TESTS=("${selected[@]}")
fi

failures=0
proven=0
t=""
spec=""

info "phase 1 — behaviour: ${#TESTS[@]} test(s) against $CTL"
for t in "${TESTS[@]}"; do
  apply "$(stimulus_for "$t")"
  if ( set -Eeuo pipefail; "$t" ); then
    ok "$t"
  else
    bad "$t"
    failures=$((failures + 1))
  fi
done

info "phase 2 — discrimination: each test under its counter-stimulus must fail"
for t in "${TESTS[@]}"; do
  spec="$(counter_for "$t")"
  apply "$spec"
  if ( set -Eeuo pipefail; "$t" ); then
    bad "$t still passed when ${spec#*:}; it does not read what it claims to read"
    failures=$((failures + 1))
  else
    ok "$t fails when ${spec#*:}"
    proven=$((proven + 1))
  fi
done

if [[ "$failures" -ne 0 ]]; then
  die "$failures failure(s) across both phases"
fi
# The summary is COUNTED, never asserted: a summary that overstates its own rigour is the
# defect this suite exists to catch.
info "${#TESTS[@]} test(s) hold; $proven of ${#TESTS[@]} proven able to fail"
