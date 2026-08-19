# harness-conformance-scope

phase:    red
repo:     gophersys/eden
branch:   ci/harness-conformance-scope
worktree: ~/code/.worktrees/eden-harness-conformance-scope
pr:       -
attempt:  0/2

## Goal
Three gate items the fleet/messaging programs need before eden PR-2 (from the
synthesized slice plan's PR-0, deliberately excluded from the merged mktemp PR #11):
1. harness-conformance fires on a libs submodule pointer bump (paths: += the pointer
   path) — today the job never runs on the bump that carries agentsession changes.
2. scripts/assert-peer-messaging-available.sh — an in-container preflight asserting the
   cross-session messaging socket exists for a claude -p session; a missing socket
   FAILS the job with a named cause (never "no message received" later).
3. assert-harness-conformance-preconditions.sh labels the codex row UNEXERCISED
   (Mateo's D3: bump + declare the tier loudly; no codex adapter exists).

## Plan
plan: SELF-APPROVED (--auto). Risk weighed+accepted: the libs-gitlink trigger adds ~5
live-credit conformance runs/month (a superproject cannot filter submodule content) —
the price of the never-mock directive; range-diff narrowing shelved as a named deferral.
KEY FINDING: the current paths filter libs/go/agentsession/** is DEAD (gitlink; 0
matches ever) — item 1 is a REPAIR, the job has never fired on an adapter change.
- Both workflow twins in one commit (paths: versions.env, libs, the 2 assert scripts;
  new preflight step between preconditions and Go tests, carrying the token).
- scripts/assert-peer-messaging-available.sh: band from INSTALLED claude --version;
  always: version parses, 4 kill-switches unset, OS check. <2.1.224: prints
  UNEXERCISED, asserts MESSAGING_SOCKET not set, exits 0, starts NO session.
  >=2.1.224: credential absent = named failure; one -p turn with a SessionStart hook
  writing a receipt; judge receipt text (/tmp/cc-socks/<pid>.sock + is_socket=yes).
  Main-guard so tests source pure functions.
- preconditions script: codex row gains UNEXERCISED tier, label loud in row+summary,
  drift assert UNCHANGED (test 5 proves the label does not soften it).
- NEW scripts/workflow-twins_test.sh: cmp all twin pairs + set-equality guard — the
  exact mistake this PR could make, uncaught today.
- Tests 1-6 per the plan; new-script suites follow the controlframe precedent
  (red-by-absence in its own commit + bite proven against a naive scratch impl).
- Gates: scripts lint+test via affected-gate-fast; this PR TRIGGERS harness-conformance
  itself (scripts enter paths:), so the low band runs FOR REAL pre-merge.
- Out of scope: pin bump + ADR text (PR-2), codex adapter, submodule range-diff,
  2-session msg_id round trip (PR-1c/2), other workflows' paths.
- UNVERIFIED (named): SessionStart hooks in -p at >=2.1.224 fire pre/post auth —
  settled at the band flip; the low band is NOT evidence for it.

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
