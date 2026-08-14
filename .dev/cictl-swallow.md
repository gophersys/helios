# cictl-swallow

phase:    fix
repo:     gophersys/libs
branch:   fix/cictl-swallow
worktree: ~/code/.worktrees/libs-cictl-swallow
pr:       -
attempt:  2/2

## Goal

`.ci/ctl.sh` reports a clean pass when `cictl` is absent, over libraries it never
looked at. Make the gate fail loudly instead, so a missing tool can never again be
reported as "no affected projects".

## The defect, PROVEN 2026-08-12 — do not re-derive

`.ci/ctl.sh:74`:

```sh
mapfile -t projects < <(affected_projects)
```

`affected_projects` opens with `require_cmd cictl`, whose failure path is
`exit 127`. **Process substitution is a SUBSHELL**, so that exit kills only the
subshell. `mapfile` reads an empty stream, and the caller logs
"no affected projects — clean no-op" and returns 0.

Measured on the same worktree, same base:

```
without cictl:  [error] missing required tool(s): cictl
                no affected projects for base 'origin/main' — clean no-op   rc=0
with cictl:     affected = go/objectstorage, go/secrets, go/workspaceprovider
                                                                            rc=1
```

The PR gate reported PASS over 3 real libraries, one of them RED.

## Why this is bigger than a missing binary

The same swallow hits ANY failure of `cictl affected`, not only an absent tool:
a bad base ref, a shallow clone, a git error. Today CI survives only because the
runner image happens to carry `cictl`. Nothing asserts that.

## Plan

APPROVED (self, under delegated authority, 2026-08-13).

The fix must go where it cannot be repeated. Two candidate shapes:

1. Run the tool check in the CALLER's own shell, before the substitution.
2. Do not read `affected_projects` through a process substitution at all —
   capture to a variable, check the status, then split.

Prefer whichever makes the swallow structurally impossible rather than merely
absent at this one call site. If other process substitutions in this file have
the same shape, they are in scope: the class is the deliverable, not the line.

## Deliberately NOT in this change

- Task #16, rolling `.ci` into the other repos. This must land FIRST, or the
  defect ships to every one of them.
- The runner image's `cictl` presence. That it happens to be there is luck, not a
  guarantee, but asserting it is a different change.

## Proven

Phase 2 — RED. `bash .ci/ctl_test.sh` -> rc=1, `5 failure(s) across both phases`.
The suite has two phases: phase 1 asserts behaviour, phase 2 asserts each test can
FAIL under a counter-stimulus. 4 red in phase 1; test 3 red in phase 2.

Its discrimination was proven from BOTH sides, in throwaway copies:
- correct oracle (capture, check status, split) -> rc=0, 5 of 5 proven able to fail
- LAZY oracle ("an empty listing is a failure") -> rc=1, tests 3 and 4 FAIL

That second one is what makes this suite good. It refuses the over-fix as firmly
as the under-fix, so the change cannot become "always fail".

Phase 3 — GREEN. `run_phase_gate_over_affected` now captures the listing, reads
the status, then splits:

```sh
listing="$(affected_projects)" || status=$?
if [[ "$status" -ne 0 ]]; then
  log_error "cictl affected failed (exit $status) for base '${NX_BASE}'; the affected set is unknown, so nothing was gated"
  return "$status"
fi
[[ -z "$listing" ]] || mapfile -t projects <<<"$listing"
```

The `[[ -z "$listing" ]] ||` guard is LOAD-BEARING: `<<<""` yields one empty
element, which would take a genuinely empty affected set out of the
"no affected projects" arm and break test 3.

`.ci/ctl.sh` now holds ZERO process substitutions.

All 5 tests green in both phases. `shellcheck -S style .ci/ctl.sh` rc=0.
Root `ctl_test.sh` rc=0 (10 hold, 10 of 10 proven able to fail).
`verb_conservation_test.sh` rc=0 (17 records, 3 mutants caught).

The class fix demonstrated on all 3 tier verbs, cictl genuinely absent:

```
affected-gate-fast       rc=127   cictl affected failed (exit 127) ... nothing was gated
affected-gate-substrate  rc=127   identical
gate-all                 rc=127   identical
```

All three fail, all three NAME the tool, none makes an empty-set claim.

## Blocked

Nothing blocking.

### CORRECTION — an arm64 claim I wrote here was FALSE

This section previously said `ghcr.io/gophersys/base:latest` "has no arm64 build,
so it cannot run on this Apple Silicon host at all", and concluded that "a
developer on Apple Silicon cannot run this repository's own gate locally... worth
carrying into the arm64 decision."

**The conclusion is false and I aimed it at a real architecture decision.** The
image is amd64, is already local, and runs here under emulation. Measured by the
verifier:

```
docker image inspect ghcr.io/gophersys/base:latest --format '{{.Architecture}}/{{.Os}}'
  -> amd64/linux
bash ./ctl.sh validate  in that image   -> rc=0, all 6 shell suites green
bash go/_ctl/lib_test.sh                -> rc=0, 17 test(s) hold
```

The premise ("no arm64 manifest") is probably true. The conclusion drawn from it
was not, and it is exactly the kind of plausible-sounding claim that gets carried
into a decision unchecked. I took it from an agent report without running it.

Also corrected: the earlier text said "One neighbour UNVERIFIED". In the ad-hoc
ubuntu image TWO suites failed — `lib_test.sh` and `vulnerability_test.sh`, both
for a missing tool. Both are GREEN in the real base image.

### CORRECTION — the defect narrative overstated the exposure

This file said "Today CI survives only because the runner image happens to carry
`cictl`. Nothing asserts that." **Not true for 2 of the 4 tiers.** In `on-pr.yml`
and `on-push.yml`, `ci-drift` runs FIRST, and `cmd_ci_drift` calls
`require_cmd cictl` in the CALLER's own shell and exits 127. An absent cictl
therefore cannot reach `affected-gate-fast` in those tiers.

The claim holds only for the merge tier (`affected-gate-substrate` runs alone)
and nightly (`gate-all` first). The fix is still needed — the NON-127 stimuli (a
bad base ref, a shallow clone, a git fault) hit every tier — but the stated
reason was wrong.

## Phase 4 — REFUTED. The swallow moved; it did not die.

The verifier broke the central claim, by execution:

**`listing="$(affected_projects)" || status=$?` puts `affected_projects` on the
LEFT of `||`, which disables `set -e` for its whole body.** Only the LAST
command's status becomes the function's status; every earlier command's is
discarded. That is the exact defect this change exists to kill, relocated one
function inward.

`affected_projects` is safe today ONLY BY ACCIDENT: it holds 2 commands and the
first (`require_cmd`) `exit`s rather than returns. Adding one ordinary line
restores the false green. The verifier added a plausible one:

```sh
function affected_projects() {
  require_cmd cictl
  git -C "$REPO_ROOT" fetch --quiet origin "$NX_BASE"   # <- one ordinary line
  cictl affected -C "$REPO_ROOT" --base "$NX_BASE"
}
```

With the fetch failing and cictl succeeding, `affected-gate-fast` printed git's
own `fatal: 'origin' does not appear to be a git repository` and still exited
**rc=0** with `all 1 affected project(s) green`.

`shellcheck` sees it (SC2310 at `.ci/ctl.sh:84:14`) but ONLY under `-o all`, and
`cmd_validate` runs bare `shellcheck`, so CI is blind to it.

The plan asked for a fix that "makes the swallow structurally impossible rather
than merely absent at this one call site". By that standard the deliverable is
NOT met.

**Second finding: the suite proves "non-zero", never 127.** Every status
assertion is `[[ "$RC" -ne 0 ]]`. Changing `return "$status"` to `return 1` keeps
the suite fully green. But rule 20 states the contract — "an absent tool is a
gate failure (exit 127), not a skip" — and this file's own Proven section treats
rc=127 as a property of the deliverable. It is unguarded.

**Out of scope, recorded so it is not lost:** the same class survives at
`ctl.sh:79`, `mapfile -t dirs < <(find ... -printf ...)`. `-printf` is GNU-only,
so on a BSD find the producer fails in the subshell and `./ctl.sh status` reports
0 libraries with rc=0. The three sibling calls at 153-155 have a `_floor_of_one`;
this one does not.

## What the verifier attacked and could NOT break

Recorded because a survived refutation is worth more than a claim: `status` is
truly local (4 calls in one process gave 127, 0, 4, 0); the real status
propagates (cictl exit 3 -> rc=3, SIGKILL -> rc=137, absent -> rc=127 on all 3
tier verbs); the `[[ -z "$listing" ]] ||` guard is load-bearing (removing it
reddens test 3) and no whitespace listing produces a phantom project; all 3 tier
verbs propagate the exact code with no wrapper or pipeline; the test split is
real, not a dodge; and the repository's own `ctl.sh validate` is rc=0 in the real
base image with `ok: .ci/ctl_test.sh` in the log, so the new suite is genuinely
wired into the pr tier.

## Next

Test author: a stimulus where `affected_projects` has a FAILING first command and
a SUCCEEDING last one, plus a test pinning rc=127 rather than merely non-zero.
Then the implementer for the structure.


## Phase 3, attempt 2 — GREEN, and the swallow is gone STRUCTURALLY

The producer function is DELETED. `require_cmd cictl` and the tool itself now run
in `run_phase_gate_over_affected`'s own shell:

```sh
require_cmd cictl
listing="$(cictl affected -C "$REPO_ROOT" --base "$NX_BASE")"
[[ -z "$listing" ]] || mapfile -t projects <<<"$listing"
```

There is no function for a subshell to swallow, so the class cannot return at a
call site. The remaining `$( ... )` holds exactly ONE external command, so its
status IS the assignment's status.

The "harden the producer with `set -e`" option was deliberately NOT taken:
`var="$(producer)"` still emits SC2311, and the moment anyone puts that call in a
condition it is attempt 1 again.

`shopt -s inherit_errexit` was added because the substitution above is safe only
while it stays single-command. Measured on bash 5.2.21, not assumed:

```
x="$(false; echo late)"   without inherit_errexit -> "reached: x=late"  rc=0
                          with    inherit_errexit -> rc=1
```

### Proven

```
.ci/ctl_test.sh              rc=0   7 test(s) hold; 7 of 7 proven able to fail (both phases)
ctl_test.sh (root)           rc=0   10 hold, 10 of 10
verb_conservation_test.sh    rc=0   17 project records, 3 mutants caught
ctl.sh validate              rc=0   22m41s under emulation
shellcheck -S style          rc=0
shellcheck -o all            SC2310/SC2311 = 0   (baseline at HEAD~1: 1x SC2310)

cictl genuinely absent (command -v cictl -> NO):
  affected-gate-fast       rc=127   [error] missing required tool(s): cictl
  affected-gate-substrate  rc=127   identical
  gate-all                 rc=127   identical
```

### RETRACTED — the trade-off was NOT forced. I was wrong and I escalated it.

This section previously claimed the specific diagnostic could not return, because
"any explicit status branch is a CONDITION, a condition is the SC2310 shape, and
test 7 forbids that shape", and escalated the loss to Mateo as a DESIGN DECISION.

**That is false. SC2310 and SC2311 fire ONLY on FUNCTION invocations.** `cictl` is
an external command, so the branch is legal, safe, and passes every gate. The
verifier built it and measured it:

```
                              shipped        withdiag
.ci/ctl_test.sh               rc=0, 7/7      rc=0, 7/7
shellcheck -o all SC2310      0              0
shellcheck -o all SC2311      0              0
shellcheck -S style           rc=0           rc=0
```

An ERR-trap variant also gives 0/0, and `.ci/ctl.sh:52-56` ALREADY carries an
`on_exit` trap reading `rc=$?` — the "trap-based mechanism" this file called a
design decision is half-built in the same file.

**The cost of the error, measured.** With cictl exiting non-zero and printing
nothing (a silent tool fault), the shipped tier's entire CI log is one line:

```
shipped   rc=4   [info] affected-gate-fast: phase-gate implementation ...
withdiag  rc=4   [info] affected-gate-fast: ...
                 [error] cictl affected failed (exit 4) for base 'origin/main';
                         the affected set is unknown, so nothing was gated
```

A red job whose log never names cictl. I took the implementer's reasoning without
testing it, wrote it here as fact, and asked Mateo to rule on a constraint that
does not exist. The escalation is withdrawn.

### An integrity note from the implementer, worth keeping

Another agent running concurrently in this session overwrote its `validate.log`
in the shared scratchpad. It reported the rc from its OWN `docker run` exit
status — trustworthy — and explicitly refused to quote that log's text as its
own. That is the correct call, and it is the reason the shell suites above were
re-run into a uniquely-named file.

## Next

Verifier: try to refute that this is done.


## Phase 5 — verifier round 2, 6 findings

**F1 (HIGH)** — the retraction above. Restore the diagnostic.

**F2 (MEDIUM-HIGH). The `inherit_errexit` comment makes two FALSE claims, and no
test guards the line.**

- **(a) "That default is the swallow this file was fixed for" — FALSE.** The fixed
  swallow was `mapfile < <(...)`, a PROCESS substitution. `inherit_errexit` covers
  COMMAND substitution only. Measured WITH the shopt set:
  `g(){ exit 127; }; mapfile -t a < <(g)` -> rc=0, n=0. The original defect
  survives it untouched.
- **(b) "closed for every substitution here" — FALSE.** `.ci/ctl.sh:195` is not
  closed. With the shopt set and a corrupt `.git/index`, `git status` fails and the
  guard reports REPORTED-CLEAN, rc=0.
- **(c) Nothing guards the line.** Deleting the shopt keeps the suite at rc=0, 7/7,
  and `shellcheck -o all` byte-identical.

Honest verdict from the verifier: it IS a guard for the future, not a comfort
blanket — a mutant with the shopt removed AND a multi-command producer
reintroduced does restore a real swallow, and only test 6 catches it. But the
comment sold it as fixing something it demonstrably does not fix.

**F3 (MEDIUM). The same class survives at `.ci/ctl.sh:195`, in the file this
change owns**, and shellcheck names it — the only SC2312 in the file:

```sh
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
```

A failed `git status` is indistinguishable from a clean tree. On a stimulus where
`status` fails and `fetch` does not, `release-check` prints `ready` over a dirty
tree — the same false green this change exists to kill. The approved plan says
"the class is the deliverable, not the line". Phase 4 recorded `ctl.sh:79` as
out of scope; this one is unrecorded and sits in a changed file.

**F4 (LOW).** `## Proven` quotes `cictl affected failed (exit 127) ... nothing was
gated` for the three tier verbs. rc=127 and "names the tool" both hold, but the
shipped code CANNOT emit that sentence — F1 is why. The quote is stale.

**F5 (LOW).** Two defects in one line. `SC2311 = 0` is VACUOUS: the pinned
ShellCheck 0.9.0 does not emit SC2311 for any of these shapes under any option, so
reporting 0 is a green that checked nothing. And the baseline reference is off by
one — `HEAD~1` is the fix (SC2310=0); attempt 1 is `HEAD~2` (SC2310=1). True when
written, false once the docs commit landed on top.

**F6 (LOW).** `TIER_VERBS` in `.ci/ctl_test.sh:92-94` says "a 4th verb has to be
added here to be covered". Nothing enforces that. `.ci/ctl.sh` already ships a
`__verbs` lister that could be cross-checked against the callers.

## What the verifier could NOT refute

All 7 tests seen RED against real broken code, on scratch copies, never in-tree:
attempt 1's own file (tests 6,7); dropping the empty-listing guard (test 3);
restoring the process substitution (tests 2,4 + 3's discrimination); coercing
127->1 (tests 1,5); shopt removed AND a multi-command producer (test 6).

**M8 is the one it attacked hardest and could not break**: reordering cictl's flags
so test 6's anchor misses makes the suite fail LOUDLY — "the fault could not be
planted ... must be re-read rather than repaired" — instead of silently passing.
That is the correct failure mode for a structure-naming test.

Behaviour, six stimuli: absent -> 127 on all three verbs; exit 3 -> rc=3; exit 0
empty -> clean no-op rc=0; whitespace-only listing -> no phantom project; broken
git repo -> rc=128; SIGKILL -> rc=137.

`ctl.sh validate` rc=0, 18m49s, with `ok: .ci/ctl_test.sh` in the run.

## Next

Implementer: F1 (restore the diagnostic — it was never forbidden), F2(a)(b) (the
comment must state what the shopt actually does), F3 (fix `:195` or record why
not), F4 and F5 (this file's stale quotes — I will take those).
Test author: F2(c) (guard the shopt), F6 (enforce TIER_VERBS).


## Phase 6 — three of SIX findings closed (see the correction below) (`2928dce`)

**F1 — the diagnostic is back.** The implementer owned the error plainly: it
"stated it as a measured constraint when I had not measured it". The comment now
spells out why this is NOT the refuted shape — there a FUNCTION was on the left of
`||` and its body lost every status but the last; here `$?` is one external
command's status with no earlier command to drop — and states the rule for the
future: a second command goes on its own line above, in this shell.

Proven on all three tier verbs with a cictl that exits 3 and prints NOTHING
(0 bytes stdout, 0 bytes stderr, probed before the run):

```
affected-gate-fast       [error] cictl affected failed (exit 3) for base 'origin/main';
                                 the affected set is unknown, so nothing was gated     rc=3
affected-gate-substrate  identical                                                     rc=3
gate-all                 identical                                                     rc=3
cictl absent, all three  [error] missing required tool(s): cictl                       rc=127
```

**F2 — the comment now claims only what the line does**: command substitution
only, and explicitly NOT process substitution — naming that `< <(f)` still
discards `f`'s status, and that THAT, not the errexit default, was the swallow the
affected set was fixed for.

**F3 — fixed, and MY STIMULUS WAS WRONG.** I proposed a corrupt `.git/index`. The
implementer ran it and it does not reproduce the false green: `git fetch` fails
too, so the verb dies at 128 with the dirty-tree check merely bypassed. It
isolated a fault that breaks `git status` ALONE (`status.showUntrackedFiles` set
to a bad value — status exits 128 with empty stdout while `rev-parse` and `fetch`
both return 0):

```
OLD  [ok]    release-check: ready (HEAD 2c8bc70...)                              rc=0
NEW  [error] git status failed (exit 128) in ...; the tree's cleanliness is
             unknown, so nothing is being released                               rc=128
```

with `NOT-COMMITTED.txt` present the whole time. The in-file comment cites the
stimulus actually measured and records that the corrupt index does not show it.

### Proven

```
.ci/ctl_test.sh              rc=0   7 ok phase 1, 7 ok phase 2, 7 of 7 proven able to fail
shellcheck -S style          rc=0
shellcheck -o all            SC2310=0  SC2311=0  SC2312=0   (53 findings, all SC2250 brace style)
ctl_test.sh (root)           rc=0   10 hold, 10/10
verb_conservation_test.sh    rc=0   17 records, 3 mutants caught
ctl.sh validate              rc=0   all 6 suites ok
```

**SC2312 is now 0** — the `release-check` fix removed the last one in the file.

### An environment failure, named rather than swallowed

The first `validate` on the final tree returned rc=1: `test suite failed:
templates/_ctl/template_test.sh`. Cause, from its own log: `mktemp: ... No space
left on device`. The container overlay filled mid-run because another agent's
concurrent base-image containers share the Docker VM disk. That suite reads
nothing from `.ci/ctl.sh`; run in isolation on the same tree it is rc=0, 5/5. The
implementer re-ran validate with `/tmp` bind-mounted to the host disk and it went
green, and deliberately did NOT prune Docker state because other agents are live.

That is the right handling: a red that is the environment's, isolated and proven
so, not explained away.

## Still open, recorded

- `ctl.sh:79` at the repo root — `mapfile -t dirs < <(find ... -printf ...)`, same
  class, GNU-only `-printf`, so on a BSD find `./ctl.sh status` reports 0
  libraries with rc=0. Outside the file this change owns. Task #62.
- 53 x SC2250 (brace style) in `.ci/ctl.sh`. Not this class; the repo gate runs
  bare shellcheck.

## Next

Focused verification of the three fixes, then the pull request. This is the branch
the consolidation audit puts FIRST in its landing order — "the gate that can fail".


## Phase 7 — VERIFIER SAYS DOES NOT PASS. Five findings, one of them mine.

`validate` rc=0 in 21m25s and every `## Proven` line re-ran green. The code is
correct for every stimulus reachable in CI. It still does not pass.

### 1 (HIGH) — the phase-6 deliverable is UNGUARDED

Delete the `log_error "cictl affected failed (exit $status) ..."` line at
`.ci/ctl.sh:102`, keep `return "$status"`, and the suite is **rc=0, 7 of 7
proven able to fail**.

Why it survives: `write_cictl` (`.ci/ctl_test.sh:246-270`) ALWAYS prints
`cictl: fatal: ambiguous argument 'origin/main'` on a non-zero code, so tests 2
and 4's `out_has 'cictl'` pass from **the fixture's own stderr**, never from the
diagnostic. **No test drives the silent-cictl case** — which is precisely the case
the implementer measured to justify F1 ("a red job whose log never names cictl").

Deleting the whole `if` block DOES redden. So the `return` is guarded and the
message is not. The entire content of the finding phase 5 ranked HIGH ships
untested.

### 2 (MEDIUM-HIGH) — the `inherit_errexit` comment is false for the THIRD time

`inherit_errexit` does NOT apply to a command substitution on the LEFT of `||`,
and BOTH substitutions this change introduced (`:97`, `:213`) are exactly that
shape. Measured, shopt set, bash 5.2.21:

```
out="$(/bin/false; printf 'late\n')" || s=$?      ->  s=0   out=late
```

End-to-end on the shipped file, growing `:97` to two commands exactly as the
header comment invites:

```
affected-gate-fast   rc=0
  fatal: 'origin' does not appear to be a git repository
  [ok] gate (implementation): all 1 affected project(s) green      <- the original false green
  .ci/ctl_test.sh rc=0, 7/7        shellcheck -o all: no SC231x
```

The in-function comment at `:91-95` states the CORRECT rule ("keep it one command
— a second one goes on its own line ABOVE"). The header contradicts it. **A
maintainer reading the header will make the change that reopens the defect.**

### 3 (MEDIUM) — `require_cmd` does not establish the "single EXTERNAL command" premise

`command -v` returns 0 for a shell FUNCTION. Nothing makes `cictl` external. On
the SHIPPED, unmodified file:

```
export -f cictl  (first command fails, last succeeds)   ->  rc=0, "all 1 affected project(s) green"
BASH_ENV=<file defining cictl()>                        ->  rc=0, identical
```

A `cictl()` defined INSIDE `.ci/ctl.sh` is caught (SC2310, test 7 reddens —
verified). The injected-function vector is caught by nothing. Realism in GitHub
Actions is low, but the comment states the premise as measured fact.

### 4 (MEDIUM) — the release-check fix has no test of any kind

`grep -rn 'release-check\|release_check' *_test.sh .ci/*_test.sh` -> no match. The
one changed code path with zero mechanical proof, carrying a fix for the same
false-green class this branch exists to kill. Its stimulus lives in a comment
instead of a test.

### 5 (LOW) — MY ERROR: "all three findings closed" was wrong

**Phase 5 raised SIX findings.** I assigned F1, F2(a)(b) and F3 to the
implementer, said F2(c) and F6 would go to the test author — and never dispatched
it. `git diff 626dced..HEAD -- .ci/ctl_test.sh` is **EMPTY**. The test author has
not run since phase 4.

So `## Still open, recorded` listed two items when four were open, and the header
declared an open set closed. Corrected above.

Also uncorrected from phase 5: `## Proven` still quotes `cictl affected failed
(exit 127) ... nothing was gated` for an ABSENT cictl — measured, `require_cmd`
exits BEFORE the substitution and the log reads `missing required tool(s): cictl`.
And `SC2311 = 0` is vacuous: ShellCheck 0.9.0 emits no SC231x for `x="$(f)"` at
all, so reporting 0 is a green that checked nothing.

## What survived, and it is substantial

`validate` rc=0 21m25s with all six suites `ok:`. **SC2312 = 0 is real, not bought
with a suppression** — the only `# shellcheck disable` in `.ci/` is SC2016 for an
awk program, and the trajectory is measured: origin/main 2 -> c4ea722 1 ->
9aedae1 1 -> 2928dce 0. The F3 release-check fix reproduces exactly, including no
regression on clean and dirty trees. The F1 block reproduces byte for byte against
a silent cictl. `status` is genuinely local across four calls in one process. The
suite still reddens against origin/main (6 failures) and against attempt 1 (2).
Zero process substitutions. No masked exit codes anywhere.

## Next

Test author: finding 1 (a silent-cictl stimulus that actually guards the
diagnostic), finding 4 (a release-check test), plus phase 5's F2(c) and F6 which I
failed to dispatch.
Then implementer: findings 2 and 3.


## Phase 8 — the suite went 7 -> 12, and the fixture stopped answering the test (`62e171c`)

**Finding 1 closed, and it was worse than one line.** `write_cictl` now takes a
diagnostic switch, and a `silent` stimulus makes cictl fail having written **0
bytes to either stream** — measured by `assert_cictl_is_silent` BEFORE every run,
which counts the bytes and fails naming them, because one escaping byte puts the
fixture back in the position of answering the test.

Red produced by deleting ONLY the `log_error` line, `return "$status"` untouched:

```
suite at HEAD (7 tests):   rc=0   7 of 7 proven able to fail        <- the hole, reproduced
this suite  (12 tests):    rc=1   FAIL t_a_silent_cictl_failure_is_still_explained
   the tool failed without a word of its own, and the tier's log never names it
   [info] affected-gate-fast: phase-gate implementation ...          <- the ENTIRE log of the red job
```

Exactly one test reddens; the other eleven stay green, so the mutant is isolated.

**The class audit.** It walked every `out_has` and named what supplies the string:

```
test 1  'cictl'                    require_cmd's own log_error, no stub exists   CODE
test 2/4 'cictl','unknown revision' the stub's stderr                            FIXTURE -> relabelled
test 6  'does not appear to be...'  git's stderr — and that IS its job           fixture, by design
test 8  'cictl','[error]'           the tier alone, proven by the silence probe  CODE
test 9  '[error]'                   log_error; git's own `error:` has no brackets CODE
test 10/11 'dirty','ready'          the tier's logger                            CODE
```

Tests 2 and 4 keep their assertions — nothing weakened — but now say what they
actually prove: **pass-through of the tool's own stream**, a real and different
property. The tier's own diagnostic is measurable only under silence.

**release-check gained 3 tests, pinning 128 rather than "non-zero"**, for a reason
worth keeping: the counter-stimulus is the same uncommitted file with git ABLE to
answer, which is a legitimate refusal at 1. A coerced status would make "git could
not tell me" and "the tree is dirty" the same event to every reader.

**F6 closed behaviourally**: verbs come from `bash .ci/ctl.sh __verbs` — ask the
program, never parse it — and a verb that GATES a project is a consumer by
definition. Derived set must equal `TIER_VERBS`, with a floor of 1 so an empty
list cannot compare equal to an empty derivation.

**It found the same defect in its OWN harness.** `run_verb` wrote `gated.log`
INSIDE the fixture, so every tree was untracked-dirty and release-check's clean
case was unreachable — the harness supplying the very thing the test reads.
Artifacts are now siblings of the fixture, never inside it.

```
bash .ci/ctl_test.sh   rc=0   12 hold, 12 of 12 proven able to fail   0.85s
shellcheck -S style    rc=0
```

## F2(c) — the test was REFUSED, and the refusal is correct

Measured, bash 5.2.21:

```
                                          without shopt      with shopt
neutral   x="$(false; echo late)"          x=late, rc=0       rc=1   <- the option works
left of ||  (BOTH substitutions in the file)  s=0 x=late      s=0 x=late   <- BYTE-IDENTICAL
```

`inherit_errexit` is **INERT for the shipped code**. Bash's errexit suppression
propagates into the substitution subshell and overrides it — the same propagation
`go/_ctl/lib.sh` already recorded for `_gate_run`.

The only test available would plant a multi-command substitution in a NEUTRAL
position: a construct the file does not contain and its own comment forbids. It
would pass today for a reason unrelated to the shipped code's safety, and a reader
would take a green "inherit_errexit is guarded" as evidence the substitutions are
protected. They are not. What protects them is that each holds exactly ONE
command.

> "That is a check that would be believed, which is the one thing worse than no
> check."

### MY DECISION: pin the one-command invariant, and keep the shopt with an honest comment

Two options were offered. I take the first.

**Do NOT restructure the capture to make the shopt do real work.** To both catch
the status AND keep errexit active inside the substitution needs a trap or a
neutral form that cannot report the status — the shapes measured in phase 5. That
is a redesign of a call site three verifier rounds have now cleared.

**The real protection is the one-command invariant, so CHECK IT.** It currently
lives in a comment, and this file's comments about this exact line have been wrong
three times.

**Keep `shopt -s inherit_errexit`**, because a future NEUTRAL substitution
elsewhere in the file would genuinely be covered — but its comment must say
plainly that it is inert for the current call sites and why. A guard described as
protecting something it does not protect is how this comment got rewritten twice
already.

## Next

Implementer: verifier findings 2 (the header comment, false a third time) and 3
(`require_cmd` uses `command -v`, which returns 0 for a shell function, so the
"single EXTERNAL command" premise is stated but not established), plus the
one-command invariant above.


## Phase 9 — the comment is honest and the invariant is CHECKED (`4d18683`)

**The header no longer contradicts the call site.** It opens with "INERT for both
`$( … )` this file contains today, and kept anyway", carries the four measured
numbers, and points at the one-command invariant as the real protection.

**`require_cmd` now resolves with `type -t`, not `command -v`.** `file` passes;
empty is `missing`; anything else is `shadowed`. Both arms exit 127. The premise
"a required tool is an external program" is now true for EVERY tool — `git` gets
it too, and so does any tool added later. Proven on the unmodified shipped file:

```
BASH_ENV cictl()                      rc=127  required tool(s) shadowed: cictl is a shell function
export -f cictl                       rc=127  identical
export -f WITH a real cictl on PATH   rc=127  identical
plain absent                          rc=127  missing required tool(s): cictl
```

**`require_single_command_status_reads` is the invariant, and it fires.** Every
non-comment line taking a status with `|| <var>=$?` must be one assignment of one
substitution holding one command. Planted in scratch copies, never in-tree:

```
a second command grown into :97      validate rc=1, names the line
  ... the same file, tier verb       rc=0 "all 1 affected project(s) green"   <- what it BLOCKS
both reads made status-blind         validate rc=1  "finding none means it read nothing"
the read split over 3 lines          validate rc=1  "a shape this check cannot read"
the shipped file                     "status reads in .ci/ctl.sh: 2, each holding one command"
```

**shellcheck cannot express this** — measured, not assumed: on the grown file,
`-o all` emits no SC2310/SC2311/SC2312 at all, and `check-set-e-suppressed` fires
only on FUNCTION invocations, so it is blind to a second command beside an
external one. That is why the two mechanisms compose rather than overlap: test 7
switches SC2310 on for the function case, this check covers the second-command
case.

```
.ci/ctl_test.sh              rc=0   12 hold, 12 of 12 proven able to fail
shellcheck -o all            SC2310=0 SC2311=0 SC2312=0  (77 findings, all SC2250 brace style)
.ci/ctl.sh validate          rc=0   958s
ctl_test.sh / verb_conservation   rc=0 / rc=0
```

### THE LAST GAP, and it is the same shape as phase 7's finding 1

**Neither new control has a test.** Delete the `shadowed` block, or the
`require_single_command_status_reads` call in `cmd_validate`, and
`bash .ci/ctl_test.sh` stays **rc=0, 12/12**.

The primary fix is guarded — 12 tests cover the deleted producer, the restored
diagnostic and release-check. But the `shadowed` arm is what closes the
injected-function false green, so its silent removal is a real regression path,
not merely missing polish.

**This is the last round for this branch.** The bar is "would ship a false
statement or an unguarded deliverable"; this clears it, and nothing else on the
branch does.

### Scope gap, recorded rather than silently widened

The same `|| <var>=$?` shape lives at `ctl.sh:207` and `:218`,
`go/_ctl/lib.sh:338`, `typescript/_ctl/lib.sh:490`,
`templates/_ctl/template.sh:164`. Widening the check repo-wide would have turned
those into gate failures in the same run. **`ctl.sh:218` is the worst of them** —
`usage_cmds="$(_usage_verbs "$ctl")" || help_rc=$?` puts a FUNCTION on the left of
`||`, the exact shape attempt 1 was refuted for, safe today only because that
function's body is a single pipeline.

## Next

Test author: two tests, nothing else. Then the pull request.
