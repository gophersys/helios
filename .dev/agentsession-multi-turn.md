# agentsession-multi-turn

phase:    red
repo:     gophersys/libs
branch:   feat/agentsession-multi-turn
worktree: ~/code/.worktrees/libs-agentsession-multi-turn
pr:       -
attempt:  0/2

## Goal
Contract revision R1: an eden agent session survives its own turn. Today
`pump.go` maps EventResult to a terminal state ("A terminal session never
transitions"), so every claude session is single-turn and a receive-then-reply
peer exchange is impossible. When this is done: a success `result` line becomes
EventTurnEnd (session stays alive, ready for the next Prompt), an error result
stays EventFailed, a graceful Close synthesizes EventResult, and three
consecutive Prompts on ONE real claude session and ONE real omp session are
proven in the harness lane. Also: one home for the `eden:` control-frame
grammar (internal/controlframe), replacing the identifiers.go/control.go
duplication. Zero .apibaseline lines beyond controlframe's own section.

## Plan
plan: SELF-APPROVED (--auto semantics inside the program Mateo approved 2026-08-18
via question gates — the synthesized slice plan; this feature is PR-1a/S2 of it).
Canonical design: ~/.claude/projects/-Users-mateo/f9c810a8-a311-4651-a2e2-c1247d34143e/
design-artifacts/synthesis-1.json. Full plan: planner report 2026-08-18 (task
a5bee710b30ccbfbd). The load-bearing points:
- EXIT RE-SCOPE: this PR proves 3 consecutive Prompts on ONE real PROCESS with the
  turn-driven STUB harness (integration lane). The real-vendor 3-prompt proof runs in
  eden's harness lane at PR-2 — libs CI installs no harness, holds no credential.
- EventTurnEnd appended (token row + types_tokens_test anchored on the LAST const by
  name); nextState: TurnEnd joins MessageEnd on Running→AwaitingInput; success result →
  TurnEnd in both normalizers; graceful Close (s.closed under s.mu, existing) synthesizes
  EventResult{TurnCompleted} with pump-LOCAL cached ledger; unbidden death stays
  EventFailed{ReasonTransport}. Exactly one terminal per session.
- internal/controlframe = ONE home, permission family only, SCALAR-ONLY signatures (an
  agentsession import would cycle). Retires THREE homes: identifiers.go:26,61,
  claudeadapter/control.go:104,109, agentsessiontest/events.go:17.
- Judge fatals answered by construction: no emit off the pump goroutine; no new send
  from pump (events chans are unbuffered — any pump-side write is the deadlock); no new
  send path bypassing guardControl. Blast radius: AwaitingInput becomes reachable, so
  LegalControls(AwaitingInput)={Prompt,Abort} goes live.
- agentruntime runtime.go:132 + advisor.go:313 re-pinned here; eden's agentgateway
  proposer.go sites break at the submodule bump (PR-2's problem, named in its plan).
- Gates: phase-gate implementation/testing/qa in BOTH go/agentsession and
  go/agentruntime, devcontainer only; architecture gate unresolvable in a bare libs
  worktree (contract doc lives in eden) — noted, PR lane never runs it.
- apibaseline: RECORD NOW via apidiff-record (additive: controlframe section only) —
  planner's recommendation adopted; R1 contract text lands in eden at S5.
- Out of scope: all peer/subagent code, rpc rewrite (S3), pins, harness lane (S4).
Phase split: Round A implementer lands the TURN-DRIVEN STUBS ONLY (test dependency,
no feature code); test author then proves tests 1-9 red (7-8 red against new stub +
OLD pump = right reason); Round B implementer full green.

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
