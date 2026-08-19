# ompadapter-rpc-mode

phase:    intake
repo:     gophersys/libs
branch:   feat/ompadapter-rpc-mode
worktree: ~/code/.worktrees/libs-ompadapter-rpc-mode
pr:       -
attempt:  0/2

## Goal
PR-1b/S3 of the approved program: rewrite ompadapter from one-process-per-turn
(--mode json, positional argv) to ONE long-lived `omp --mode rpc` process per session.
Forced three times over: multi-turn needs a surviving process; set_host_tools needs a
live one; turn injection needs an open channel. Zero .apibaseline delta (the ompadapter
section stays byte-identical) — which is exactly why it must be its OWN reviewable PR.
Also carries a security fix: omp stops inheriting the operator's approval mode (the
probe watched it let `bash` run ungated). Exit: the credential-free real-omp frame
contract proven in libs CI; manifest promotions CapHostTools Partial→FULL and
CapPermissionPrompt Partial→FULL asserted by conformance (an over-claim FAILS).

## Plan
(pending phase 1 — canonical design: design-artifacts/synthesis-1.json sliceBoundaries
[S3/PR-1b] + designDoc rpc sections; probe evidence: design-artifacts/probe-2 (omp rpc
frames at 17.3.7) + omp.json discovery. Program approval: Mateo 2026-08-18.)

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
