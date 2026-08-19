# harness-conformance-scope

phase:    intake
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
(pending phase 1 — program approval: Mateo's slice-plan adoption 2026-08-18; this is
PR-0b of it, task #7.)

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
