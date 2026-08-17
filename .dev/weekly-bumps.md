# weekly-bumps

phase:    red
repo:     gophersys/.devcontainer
branch:   ci/weekly-bumps
worktree: ~/code/.worktrees/.devcontainer-weekly-bumps
pr:       -
attempt:  0/2

## Goal
A weekly workflow resolves every pin's upstream (one table _build/upstreams.txt,
one resolver _build/resolve-upstream.sh with one function per datasource, 11+
no-autobump=12) and opens ONE gated bump PR where anything moved — version and
sha256 from the SAME fetch, re-proven by fetch-verified.sh before writing, so a
stale digest is impossible by construction. Failures file a ci-weekly-red issue
via the parameterized notifier. The last piece of ledger #100.

## Plan
Approved under standing-orders §4 delegation, 2026-08-17, WITH the fallback as
day-1 state for the one open credential: the 3 harness pins (claude/omp/codex)
take no-autobump ("eden harness-upgrade-check is the one decision point; the
cross-repo read needs EDEN_MANIFEST_READ, a fine-grained PAT only Mateo can
mint — NEEDS-MATEO item 16"); the eden-manifest datasource ships ready and
FAILS NAMING THE SECRET if selected while it is absent. Full plan:
tasks/a692df0b23121fdae.output. Planner's premise corrections accepted: PR#48
shipped no generator (the resolver is the FIRST digest-computing home);
dual-home version equality needs a NEW static rule (only UBUNTU_BASE_REF held
today). 12 datasources incl. no-autobump (9 pins); readers fetch_urls/
evidence_of/homes_of MOVE from download-coverage.test.sh into _ctl/lib.sh
(move, not copy); notifier ISSUE_LABEL parameterized (weekly=ci-weekly-red,
a green weekly must not close nightly issues).

## Proven
(nothing yet)

## Blocked
Nothing. The PR#48 wiring-proof build was 5/6 green at intake (devbox
finishing); landing order unaffected.

## Next
dev-test-author: the 7 red suites from the plan (+2 free ratchets) proven red
for the right reasons.
