# agentsession-multi-turn

phase:    intake
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
(pending phase 1 — canonical design: ~/.claude/projects/-Users-mateo/
f9c810a8-a311-4651-a2e2-c1247d34143e/design-artifacts/synthesis-1.json,
sections designDoc [R1], testMap, apibaselineImpact, sliceBoundaries [S2/PR-1a].
Program approval: Mateo 2026-08-18 via question gates in the pair session —
slice plan adopted; this feature is PR-1a of it.)

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
