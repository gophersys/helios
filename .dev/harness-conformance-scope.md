# harness-conformance-scope

phase:    fix
repo:     gophersys/eden
branch:   ci/harness-conformance-scope
worktree: ~/code/.worktrees/eden-harness-conformance-scope
pr:       -
attempt:  1/2

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
- RED (author, d0e59db/f254103/3ec75c3): suite A red-by-absence (bite proven vs naive
  scratch impl — 15 FAILs — and green vs correct reference); suite B red on the
  missing UNEXERCISED tier (2 verbatim failures) with 6 guard-green hard-fail cases;
  suite C green-by-design as a regression guard (twins identical via independent cmp)
  with 5 scratch-tree failure modes proven.
- GREEN (implementer, 839e388/17a5150/49be9a9): all 3 suites rc=0 in base; ctl.sh
  lint 10 scripts rc=0; test 5 suites rc=0; mktemp scan 78 files rc=0; affected-check
  rc=0 (repository-scripts lint+test ran); both twins shasum-equal.
- VERIFY round 1: DEAD-filter claim independently CONFIRMED (gitlink; libs/go/** never
  matched in 76 pointer commits); live low band proven REAL in-container (2.1.212 →
  UNEXERCISED, no session, exit 0); socket shape proven live on this machine; 6 break
  tests red correctly; band edge shapes all sane. BLOCKERS: F1 success path exits 1
  (EXIT trap reads a `local` var post-return — fires ONLY on success; temp dir leaks);
  F2 probe body zero coverage (only credential-absent reaches it); F3 codex-absent
  case keeps nvm on PATH — red in devcontainer, green in CI (the worst polarity);
  F5 inert HARNESS_VERSIONS_FILE + self-contradicting comment (cleanup-remove, both
  twins); F6 timeout without -k + no timeout-minutes on the job (360min default on a
  paid runner). F4 = this file lagged two phases (orchestrator's defect, third
  occurrence tonight — corrected here with the full record).

## Blocked
-

## Blocked
-

## Next
Fix round 1: author F2 (probe-body stub cases: success/no-receipt/timeout-124) + F3
(clean PATH per the sibling suite's pattern); implementer F1 (trap owns its path —
not a local), F5 (remove inert env + comment, both twins), F6 (timeout -k 30 120 +
timeout-minutes on the job). Then re-verify (round 2, bounded), PR.
