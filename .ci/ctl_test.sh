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
# TREE is the third stimulus: what state of the working tree `release-check` meets.
TREE="clean"
# SHADOW is the fourth: what the tier's own shell resolves the tool NAME to. A tool can be
# present on PATH and still not be the thing that runs.
SHADOW="none"
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
    # ANCHOR: the single `cictl updatability …` invocation. It turns a verb that does NOT
    # read the affected set into one that does, which is the drift the tier-verb list has to
    # notice: a new consumer added without being covered.
    updatability-gates)
      awk '
        /^  cictl updatability -C/ {
          print "  run_phase_gate_over_affected implementation"
          hits++
          next
        }
        { print }
        END { if (hits != 1) { exit 3 } }
      ' "$target" > "$mutated" ||
        fail "the mutation found no single 'cictl updatability -C' invocation to turn into a consumer of the affected set; the dispatcher has been refactored and this test must be re-read"
      ;;
    # ANCHOR: the status read that produces the affected set. A second command is grown INSIDE
    # its substitution — the regression the one-command invariant exists to catch, and the
    # exact edit a reader would make to fetch the base before diffing it.
    second-command-in-a-status-read)
      awk '
        /^  listing="\$\(cictl affected/ {
          print "  listing=\"$(git -C \"$REPO_ROOT\" fetch --quiet origin \"$NX_BASE\"; cictl affected -C \"$REPO_ROOT\" --base \"$NX_BASE\")\" || status=$?"
          hits++
          next
        }
        { print }
        END { if (hits != 1) { exit 3 } }
      ' "$target" > "$mutated" ||
        fail "the mutation found no single affected-set status read to grow a second command into; the line has been refactored and this test must be re-read"
      ;;
    # ANCHOR: every `|| status=$?`, of which this file has exactly 2. They become `|| true` —
    # the shape this repository bans — so the reads still exist but no longer take a status,
    # and the check that scans for them finds NONE. That is the stimulus the floor exists for.
    status-reads-made-blind)
      awk '
        /\|\| status=\$\?$/ {
          sub(/\|\| status=\$\?$/, "|| true")
          hits++
        }
        { print }
        END { if (hits != 2) { exit 3 } }
      ' "$target" > "$mutated" ||
        fail "the mutation did not find exactly 2 '|| status=\$?' reads to blind; the file's status reads have changed and this test must be re-read"
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
  # The repository-level ctl.sh `.ci/ctl.sh validate` delegates to. It stands in for the
  # twenty-minute half, so a `validate` run here measures what .ci/ctl.sh does BEFORE the
  # delegation and nothing else; without it every validate would end at a missing file and a
  # check that failed could not be told from one that never ran.
  cat > "$fix/ctl.sh" <<'ROOT'
#!/usr/bin/env bash
#
# The delegation target. It is not the subject of any test here.
set -Eeuo pipefail
printf 'fixture root ctl.sh: %s\n' "$*"
ROOT
  chmod +x "$fix/ctl.sh"
  install_shadow "$fix"
  printf '%s' "$fix"
}

# install_shadow <fixture> writes the file BASH_ENV points at, and PROVES what it did. A
# shell FUNCTION named after the tool is the shape `command -v` answered 0 for: the tier then
# reads a status through `$( … ) || status=$?`, where a function's body drops every status but
# its last. The body here is the attack in full — a command that FAILS, then a listing that
# succeeds — so a tier that accepts it gates a project over a diff nothing ever computed.
install_shadow() {
  local fix="$1" kind
  case "$SHADOW" in
    none) rm -f "$fix/inject.sh" ;;
    function)
      cat > "$fix/inject.sh" <<'INJECT'
# Sourced by every non-interactive bash through BASH_ENV — a CI runner can set it, and
# `export -f` reaches the same place by another door. It prints nothing of its own.
cictl() {
  git -C /nonexistent-repository rev-parse --show-toplevel
  printf 'go/alpha\n'
}
INJECT
      ;;
    *) die "unknown shadow stimulus: $SHADOW" ;;
  esac
  # What will the tier's own shell say the name resolves to? Asked in a shell built exactly
  # like the one run_verb starts, because a shadow that is not in force would leave the test
  # measuring the ordinary path and calling it proof.
  # shellcheck disable=SC2016  # `type -t` must run in the INNER shell — that is the whole question
  kind="$(PATH="$fix/bin" BASH_ENV="$fix/inject.sh" "$REAL_BASH" -c 'printf "%s" "$(type -t cictl)"')"
  if [[ "$SHADOW" == "function" ]]; then
    [[ "$kind" == "function" ]] ||
      fail "the shadow is not in force: the tier's shell resolves cictl as '${kind:-nothing}', so the run would prove nothing"
  else
    [[ "$kind" != "function" ]] ||
      fail "a shadow is in force although none was asked for: cictl resolves as a function"
  fi
}

# new_release_fixture prints a tree `release-check` can reach a verdict in: a committed tree
# on main, with an origin it can fetch and whose main is HEAD. TREE then decides what the
# verb meets, and each variant is MEASURED before the run, never assumed:
#
#   clean          nothing uncommitted                     → the verb must report ready
#   dirty          1 uncommitted file                      → the verb must refuse
#   status-broken  the same uncommitted file, plus a bad `status.showUntrackedFiles`, so
#                  `git status` EXITS NON-ZERO PRINTING NOTHING while rev-parse and fetch
#                  stay healthy → the tier is told nothing, and must not call that clean
new_release_fixture() {
  local fix origin
  fix="$(new_fixture)"
  origin="$(mktemp -d "$WORK/origin.XXXXXX")/origin.git"
  git -C "$fix" config user.email "ctl-test@example.invalid"
  git -C "$fix" config user.name "ctl test"
  git -C "$fix" checkout --quiet -b main
  git -C "$fix" add -A
  git -C "$fix" commit --quiet -m "fixture tree"
  git init --quiet --bare "$origin"
  git -C "$fix" remote add origin "$origin"
  git -C "$fix" push --quiet origin main
  case "$TREE" in
    clean) : ;;
    dirty|status-broken)
      printf 'uncommitted\n' > "$fix/uncommitted.txt"
      [[ "$TREE" == "dirty" ]] ||
        git -C "$fix" config status.showUntrackedFiles bogusvalue
      ;;
    *) die "unknown tree stimulus: $TREE" ;;
  esac
  assert_tree_stimulus "$fix"
  printf '%s' "$fix"
}

# assert_tree_stimulus <fixture> measures what the verb is about to meet. The status-broken
# variant is the one that matters: if `git status` ever answered, or if fetch/rev-parse also
# broke, the verb would fail somewhere else and the run would prove nothing about the branch
# under test.
assert_tree_stimulus() {
  local fix="$1" out rc=0 fetch_rc=0
  out="$(git -C "$fix" status --porcelain 2>/dev/null)" || rc=$?
  git -C "$fix" fetch --quiet origin || fetch_rc=$?
  [[ "$fetch_rc" -eq 0 ]] ||
    fail "git fetch failed ($fetch_rc) in the fixture, so release-check would die there instead of at the branch under test"
  case "$TREE" in
    clean)
      [[ "$rc" -eq 0 && -z "$out" ]] ||
        fail "the 'clean' tree is not clean (status rc=$rc): $out" ;;
    dirty)
      [[ "$rc" -eq 0 && -n "$out" ]] ||
        fail "the 'dirty' tree does not report as dirty (status rc=$rc): $out" ;;
    status-broken)
      [[ "$rc" -ne 0 ]] ||
        fail "the 'status-broken' tree answered its status (rc=0), so nothing is broken and the run would prove nothing: $out"
      [[ -z "$out" ]] ||
        fail "the 'status-broken' tree printed on stdout, so the caller could still read a verdict: $out" ;;
  esac
}

# write_cictl <fixture> <listing> <exit-code> <diagnostic:yes|no> — the cictl the script
# under test will find.
#
# The DIAGNOSTIC switch is the point of this parameter. A stub that always prints something
# on failure supplies the word "cictl" itself, which then satisfies any assertion that the
# TIER named the tool — the assertion reads the fixture's own noise and never the code under
# test. A tool that fails while printing nothing is both a real case (`cictl affected` can
# die with an empty diagnostic) and the ONLY stimulus under which "the tier said which tool
# failed" can be measured at all.
write_cictl() {
  local fix="$1" listing="$2" code="$3" diagnostic="$4"
  {
    cat <<'HEAD'
#!/usr/bin/env bash
#
# The cictl this fixture puts on PATH. It implements `affected` only.
set -Eeuo pipefail
HEAD
    printf 'LISTING=%q\n' "$listing"
    printf 'CODE=%s\n' "$code"
    printf 'DIAGNOSTIC=%q\n' "$diagnostic"
    cat <<'TAIL'
if [[ "${1:-}" != "affected" ]]; then
  printf 'cictl: this fixture implements affected only, not %s\n' "${1:-}" >&2
  exit 64
fi
[[ -z "$LISTING" ]] || printf '%s\n' "$LISTING"
if [[ "$CODE" -ne 0 && "$DIAGNOSTIC" == "yes" ]]; then
  printf "cictl: fatal: ambiguous argument 'origin/main': unknown revision\n" >&2
fi
exit "$CODE"
TAIL
  } > "$fix/bin/cictl"
  chmod +x "$fix/bin/cictl"
}

# assert_cictl_is_silent <fixture> measures the stub rather than trusting how it was
# written: `affected` must exit non-zero having written 0 bytes to stdout AND 0 bytes to
# stderr. If one byte carrying "cictl" escaped, the test that reads the tier's own
# diagnostic would be reading the fixture instead, which is the defect this whole stimulus
# exists to close.
assert_cictl_is_silent() {
  local fix="$1" out err rc=0 out_bytes err_bytes
  # Siblings of the fixture, for the same reason run_verb's log is: nothing this harness
  # writes may land inside the tree under test.
  out="${fix}.silence.out"
  err="${fix}.silence.err"
  ( PATH="$fix/bin"; cictl affected --base origin/main ) >"$out" 2>"$err" || rc=$?
  out_bytes="$(wc -c <"$out")"
  err_bytes="$(wc -c <"$err")"
  [[ "$rc" -ne 0 ]] ||
    fail "the 'silent' stimulus exited 0, so there is no failure for the tier to report"
  [[ "$out_bytes" -eq 0 && "$err_bytes" -eq 0 ]] ||
    fail "the 'silent' stimulus is not silent (stdout ${out_bytes}B, stderr ${err_bytes}B); a test reading the tier's diagnostic would be reading this instead: $(cat "$out" "$err")"
}

# install_cictl <fixture> puts the stimulus in place AND proves it: an `absent` stimulus
# that is not absent, or an installed one that the script under test cannot reach, would
# make the run below prove nothing at all. The probe runs in a subshell holding EXACTLY the
# PATH the script under test is given, never the harness's own.
install_cictl() {
  local fix="$1" found=0
  case "$CICTL" in
    absent)  rm -f "$fix/bin/cictl" ;;
    failing) write_cictl "$fix" "" 2 yes ;;
    silent)  write_cictl "$fix" "" 2 no ;;
    empty)   write_cictl "$fix" "" 0 no ;;
    partial) write_cictl "$fix" "go/alpha" 2 yes ;;
    reports) write_cictl "$fix" "$(printf 'go/alpha\ngo/beta')" 0 no ;;
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
  [[ "$CICTL" != "silent" ]] || assert_cictl_is_silent "$fix"
}

# ── the harness ─────────────────────────────────────────────────────────────

# run_verb <fixture> <verb> runs one tier verb over the fixture and sets OUT, RC and GATED.
# The fixture PATH REPLACES the harness's, so the only cictl in reach is the stimulus.
run_verb() {
  local fix="$1" verb="$2" log
  # The log is a SIBLING of the fixture, never a file inside it. A harness artifact written
  # into the tree is untracked, which makes every tree dirty and takes `release-check`'s
  # clean case out of reach — the harness would then be supplying the very thing the test
  # reads. (Measured: with the log inside, the clean-tree test failed on `?? gated.log`.)
  log="${fix}.gated.log"
  RC=0
  : > "$log"
  # BASH_ENV is how the shadow reaches the tier's shell: bash reads it when it starts a
  # script. With SHADOW=none the file does not exist and bash reads nothing.
  OUT="$(PATH="$fix/bin" EDEN_TEST_GATED_LOG="$log" BASH_ENV="$fix/inject.sh" \
    "$REAL_BASH" "$fix/.ci/ctl.sh" "$verb" 2>&1)" || RC=$?
  GATED="$(cat "$log")"
}

out_has()  { grep -Fq -- "$1" <<<"$OUT"; }
out_hasE() { grep -Eq -- "$1" <<<"$OUT"; }

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
  # This stub SPEAKS on failure, so both lines below are about PASS-THROUGH — the tool's own
  # stream reaching the reader — and NEITHER can show that the tier named the tool itself.
  # That property is measurable only against a stub that says nothing (test 8).
  out_has 'unknown revision' ||
    fail "cictl's own diagnostic never reached the reader; a stream the tier cannot read must not be discarded: $OUT"
  out_has 'cictl' ||
    fail "neither the tool's own stream nor the tier's log named cictl anywhere: $OUT"
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
  # As in test 2, this stub speaks for itself, so these 2 lines pin PASS-THROUGH only.
  out_has 'unknown revision' ||
    fail "cictl's own diagnostic never reached the reader; a stream the tier cannot read must not be discarded: $OUT"
  out_has 'cictl' ||
    fail "neither the tool's own stream nor the tier's log named cictl anywhere: $OUT"
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

# 8. The tier's OWN diagnostic, which no other test in this file can see. Every other failing
# stimulus uses a cictl that prints its own error, and that stderr flows to the same log, so
# an assertion that "the tier named the tool" is satisfied by the FIXTURE's noise and would
# stay green if the tier said nothing at all. Here cictl exits non-zero having written 0
# bytes to either stream (measured, not assumed — see assert_cictl_is_silent), so the words
# below can only come from the tier. Without them the whole CI log of a red job is the tier's
# own announcement: nothing naming the tool, nothing saying the affected set was never known.
t_a_silent_cictl_failure_is_still_explained() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  ! out_has 'no affected projects' ||
    fail "cictl failed silently, and the tier reported an empty affected set instead (rc=$RC): $OUT"
  [[ "$RC" -ne 0 ]] ||
    fail "cictl exited non-zero and the tier exited 0: $OUT"
  out_has 'cictl' ||
    fail "the tool failed without a word of its own, and the tier's log never names it, so the reader of this red job cannot tell what failed: $OUT"
  out_has '[error]' ||
    fail "the tool failed without a word of its own, and the tier logged no error line at all: $OUT"
}

# 9. The same class in the OTHER verb this change touched. `git status --porcelain` prints
# nothing on stdout when it FAILS, so reading its output without its status called a broken
# answer a clean tree, and release-check reported ready over an uncommitted file. The
# stimulus is a bad `status.showUntrackedFiles`: status exits 128 printing nothing, while
# rev-parse and fetch stay healthy, so nothing downstream catches it.
#
# 128 exactly, not merely non-zero: the counter-stimulus is the SAME uncommitted file with
# git able to answer, which is a legitimate refusal at 1. A status coerced to 1 would make
# "git could not tell me" and "the tree is dirty" the same event to every reader — the same
# loss of signal as an absent tool coerced away from 127.
t_a_git_status_that_fails_is_not_a_clean_tree() {
  local fix
  fix="$(new_release_fixture)"
  run_verb "$fix" release-check
  [[ "$RC" -eq 128 ]] ||
    fail "git status could not answer and release-check exited $RC, not git's own 128; the tree's cleanliness was never known: $OUT"
  out_has '[error]' ||
    fail "git status failed and release-check logged no error of its own: $OUT"
  ! out_has 'ready' ||
    fail "release-check reported ready over a tree whose cleanliness it could not read: $OUT"
}

# 10. The non-regression on the other side of the same branch: a tree that IS dirty must
# still be refused, and refused as a dirty tree (1), not as an unreadable one.
t_a_dirty_tree_is_refused() {
  local fix
  fix="$(new_release_fixture)"
  run_verb "$fix" release-check
  [[ "$RC" -eq 1 ]] ||
    fail "the tree holds an uncommitted file and release-check exited $RC, not 1: $OUT"
  out_has 'dirty' ||
    fail "release-check refused the tree without saying it was dirty: $OUT"
  ! out_has 'ready' ||
    fail "release-check reported ready over an uncommitted file: $OUT"
}

# 11. And the pass. A verb that cannot report ready is as useless as one that always does —
# the same rule that keeps the empty affected set a clean pass in test 3.
t_a_clean_tree_on_main_reports_ready() {
  local fix
  fix="$(new_release_fixture)"
  run_verb "$fix" release-check
  [[ "$RC" -eq 0 ]] ||
    fail "the tree is committed, on main, and level with origin/main, and release-check exited $RC: $OUT"
  out_has 'ready' ||
    fail "release-check passed without reporting ready: $OUT"
}

# 12. TIER_VERBS says a 4th verb "has to be added here to be covered", and until now nothing
# made that true: a new verb that read the affected set would simply not be covered by test
# 5, silently. So the list is CONSERVED against the dispatcher's own behaviour — the verbs
# are taken from `__verbs` (ask the program, never parse it: the rule .ci/ctl.sh:200 already
# sets), each is run against a cictl that reports 2 projects, and a verb that GATES one is by
# definition a consumer of the affected set. That derived set must be exactly TIER_VERBS.
t_the_tier_verb_list_is_conserved() {
  local fix verb listed=() gating=() derived expected
  fix="$(new_fixture)"
  install_cictl "$fix"
  mapfile -t listed < <(PATH="$fix/bin" "$REAL_BASH" "$fix/.ci/ctl.sh" __verbs)
  # A floor of 1: an empty verb list would make the comparison below vacuously equal to an
  # empty derived set, and report a clean sheet over a dispatcher it never read.
  [[ "${#listed[@]}" -gt 0 ]] ||
    fail "the dispatcher listed no verbs at all, so nothing was compared against TIER_VERBS"
  for verb in "${listed[@]}"; do
    [[ -n "$verb" ]] || continue
    run_verb "$fix" "$verb"
    [[ -z "$GATED" ]] || gating+=("$verb")
  done
  derived="$(printf '%s\n' "${gating[@]:-}" | sort)"
  expected="$(printf '%s\n' "${TIER_VERBS[@]}" | sort)"
  [[ "$derived" == "$expected" ]] ||
    fail "the verbs that gate the affected set are not the ones TIER_VERBS covers — derived [$(tr '\n' ' ' <<<"$derived")] vs TIER_VERBS [$(tr '\n' ' ' <<<"$expected")]; a consumer outside that list is a tier this suite never checks"
}

# 13. A tool can be on PATH and still not be what runs. `command -v cictl` answers 0 for a
# shell FUNCTION, so it could never establish the premise the affected-set read depends on:
# that the thing on the left of `|| status=$?` is a single external command with a single
# status. A function has a BODY, and only its last command's status survives — so an injected
# `cictl()` that fails first and prints a listing last hands the tier a green diff nothing
# computed. This stimulus is the worst case of the three that were measured: a REAL cictl is
# on PATH, and a function shadows it, which is precisely the pair `command -v` cannot tell
# apart. The counter removes the function and nothing else.
#
# Both failure arms exit 127, so the status alone cannot say WHICH one fired; the assertion
# reads the word only the shadow arm produces.
t_a_shadowed_cictl_is_refused() {
  local fix
  fix="$(new_fixture)"
  install_cictl "$fix"
  run_verb "$fix" affected-gate-fast
  assert_verb_ran affected-gate-fast
  [[ -z "$GATED" ]] ||
    fail "a shell function answered for cictl and the tier gated over what it printed: $GATED"
  ! out_has 'affected project(s) green' ||
    fail "the tier declared the affected projects green from a listing a shell function invented: $OUT"
  [[ "$RC" -eq 127 ]] ||
    fail "cictl resolves to a shell function in the tier's shell and the tier exited $RC, not 127: $OUT"
  out_has 'shadowed' ||
    fail "the tier refused, but never said the tool was SHADOWED; a missing tool and a shadowed one exit alike, so the message is the only thing that tells a reader which happened: $OUT"
}

# 14. The one-command invariant, checked where the pr tier already runs it. The affected set
# is safe only while exactly one external command sits on the left of `|| status=$?`, and
# nothing but this check makes that true tomorrow. The stimulus is the edit a reader would
# plausibly make — fold the base fetch into the substitution — and the check must name the
# line and fail `validate`.
#
# This also pins that the check is CALLED: deleting the call from cmd_validate leaves the
# violation unreported, and this test reddens.
t_a_second_command_in_a_status_read_fails_validate() {
  local fix
  fix="$(new_fixture)"
  run_verb "$fix" validate
  [[ "$RC" -eq 1 ]] ||
    fail "a status read grew a second command and validate exited $RC, not 1: $OUT"
  out_hasE '\.ci/ctl\.sh:[0-9]+ holds more than one command' ||
    fail "validate failed without naming the line that takes a status from more than one command: $OUT"
}

# 15. The floor, and the half that matters most. 0 status reads found and 0 status reads
# checked are the same green: a rename, a refactor, or a read written in another shape puts
# this file's status reads out of the check's reach, and the check would then report a clean
# sheet over nothing. The stimulus turns both reads into `|| true` — the shape this repository
# bans — so the reads still exist and the scan finds NONE of them.
t_a_status_check_that_finds_nothing_fails_validate() {
  local fix
  fix="$(new_fixture)"
  run_verb "$fix" validate
  [[ "$RC" -eq 1 ]] ||
    fail "the check found no status read at all and validate exited $RC, not 1; finding none is finding nothing, never a clean sheet: $OUT"
  ! out_has 'each holding one command' ||
    fail "the check reported its success line over a file whose status reads it never found: $OUT"
  out_has '[error]' ||
    fail "the check found nothing and logged no error of its own: $OUT"
}

TESTS=(
  t_a_missing_cictl_fails_the_tier
  t_a_failing_cictl_fails_the_tier
  t_an_empty_affected_set_is_a_clean_pass
  t_a_partial_listing_that_fails_is_not_a_green_tier
  t_every_tier_verb_refuses_a_missing_cictl
  t_a_fault_inside_the_producer_fails_the_tier
  t_the_producer_is_not_invoked_where_errexit_is_suppressed
  t_a_silent_cictl_failure_is_still_explained
  t_a_git_status_that_fails_is_not_a_clean_tree
  t_a_dirty_tree_is_refused
  t_a_clean_tree_on_main_reports_ready
  t_the_tier_verb_list_is_conserved
  t_a_shadowed_cictl_is_refused
  t_a_second_command_in_a_status_read_fails_validate
  t_a_status_check_that_finds_nothing_fails_validate
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
    t_a_silent_cictl_failure_is_still_explained)   printf 'silent' ;;
    # release-check reads git, never cictl, so the tree is the whole stimulus.
    t_a_git_status_that_fails_is_not_a_clean_tree) printf 'status-broken' ;;
    t_a_dirty_tree_is_refused)                     printf 'dirty' ;;
    t_a_clean_tree_on_main_reports_ready)          printf 'clean' ;;
    t_the_tier_verb_list_is_conserved)             printf 'reports' ;;
    # The worst case of the 3 measured: a real cictl IS on PATH, and a function shadows it.
    t_a_shadowed_cictl_is_refused)                 printf 'reports,shadowed-cictl' ;;
    t_a_second_command_in_a_status_read_fails_validate) printf 'absent,second-command-in-a-status-read' ;;
    t_a_status_check_that_finds_nothing_fails_validate) printf 'absent,status-reads-made-blind' ;;
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
    t_a_silent_cictl_failure_is_still_explained)
      printf 'empty:cictl prints the same nothing and exits 0, so only the STATUS differs' ;;
    t_a_git_status_that_fails_is_not_a_clean_tree)
      printf 'dirty:the bad status config is dropped, so git answers and the tree is merely dirty' ;;
    t_a_dirty_tree_is_refused)
      printf 'clean:the uncommitted file is not written, so there is nothing to refuse' ;;
    t_a_clean_tree_on_main_reports_ready)
      printf 'dirty:one uncommitted file appears, so the tree is no longer releasable' ;;
    t_the_tier_verb_list_is_conserved)
      printf 'reports,updatability-gates:a verb outside the list starts gating the affected set' ;;
    t_a_shadowed_cictl_is_refused)
      printf 'reports:the injected function is gone, so the name resolves to the real cictl on PATH' ;;
    t_a_second_command_in_a_status_read_fails_validate)
      printf 'absent:the status read holds one command again, as the file ships it' ;;
    t_a_status_check_that_finds_nothing_fails_validate)
      printf 'absent:both status reads take a status again, so the check finds the 2 it ships with' ;;
    *) die "no counter-stimulus is declared for $1; every test must state what makes it fail" ;;
  esac
}

# apply <spec> points the next run at the named stimulus. <spec> is a comma-separated list of
# stimulus tokens, optionally followed by ':' and the prose the driver prints. Each token
# names one axis — the cictl, the source mutation, the working tree — and every axis not
# named returns to its neutral value, so a spec states exactly what it changes. An unknown
# token is a hard error: a silently ignored one would run a test under a stimulus nobody
# declared.
apply() {
  local spec="$1" head token
  head="${spec%%:*}"
  CICTL="absent"
  MUTATION="none"
  TREE="clean"
  SHADOW="none"
  local IFS=','
  for token in $head; do
    case "$token" in
      absent|failing|silent|empty|partial|reports)              CICTL="$token" ;;
      fault-before-the-producer|suppressed-call-appended)       MUTATION="$token" ;;
      updatability-gates)                                       MUTATION="$token" ;;
      second-command-in-a-status-read|status-reads-made-blind)  MUTATION="$token" ;;
      clean|dirty|status-broken)                                TREE="$token" ;;
      shadowed-cictl)                                           SHADOW="function" ;;
      *) die "unknown stimulus token '$token' in spec: $spec" ;;
    esac
  done
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
