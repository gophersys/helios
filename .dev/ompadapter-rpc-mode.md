# ompadapter-rpc-mode

phase:    verify
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
plan: SELF-APPROVED (--auto), open question answered with the planner's (c): test #15
(real-omp credential-free frame lane) is AUTHORED here, guarded by a binary-identity
assertion (omp is ALSO oh-my-posh's binary name — proven on this host, omp/15.10.0);
libs CI runs the stub lanes; the real-omp proof is REQUIRED at PR-2's eden lane; the
base-image omp bake is a named follow-up in the .devcontainer estate (eden session).
CORRECTION from the planner: probe-2.json is the CLAUDE peer probe; the omp rpc
evidence = q3-frame-sequence-summary.md, q3-probe*.txt, q4-host-tool-frame-contract.md
+ omp.json.
Canonical plan = the planner report (task ac7a44ba55d3732a8), load-bearing points:
- One long-lived `omp --mode rpc` process/session; Ready on the REAL ready frame;
  negotiate_protocol v2; explicit --approval-mode (the security fix — q3-probe4
  watched bash run ungated); one PI_CODING_AGENT_DIR; Prompt/Steer/Abort → stdin
  frames; Close = EOF→drain→wait.
- NEW rpc.go (envelope, UNCONDITIONAL extension_ui_response — the stall is a DEADLOCK,
  select frames carry no timeout, rpc-mode.ts arms no timer; typed sticky-close
  sentinel) + hosttool.go (correlate on id NEVER toolCallId; result.content is an
  ARRAY; cancel rejects locally). Mirror claudeadapter's file names; two routers on
  purpose — extract at the third adapter, not before.
- Stub REWRITTEN (implementer-owned): one process, NDJSON both ways, ready-first,
  N turns, host_tool_call answering, no-timeout select emission.
- Version binding: rpc-types.ts byte-identical 17.2.5↔17.3.7 (sha1 f3a62ed4) — safe on
  the current pin; fixtures named rpc-17.3.7-*.jsonl; sessionDir never derived (omp
  owns the layout — the 17.2.9 bucket revert); approvalMode in NEITHER host-default
  list at EITHER version.
- Tests 1-8 per plan; dying tests deleted/inverted never left green (the never-rpc
  guards invert to always-rpc); apibaseline ompadapter section byte-identical.
- Risks: turnMu semantics invert (Send becomes non-blocking stdin write — load lane +
  Prompt-while-running error class must hold); bench-guard may need a reviewed
  re-record.
- Out of scope: peer plane (PR-1c), pins + eden lane + #17 real-model test (PR-2),
  host-uri schemes, rpc-ui/ACP/collab, shared router extraction.

## Proven
- RED (author, 014da5e/6657ffd): behavioral reds at the buildable commit (argv, resume
  layout, property inversion, 3-execs re-pin failing against the OLD stub for the
  right reason); compile-dep reds isolated (exactly the 2 feature symbols); 10
  single-defect mutations each killed by name; fixtures cited to probe captures
  line-by-line (2 reconstructed lines marked).
- GREEN (implementer, 9ed2a76 + a94196b bench re-record as a reviewed act): rpc.go/
  hosttool.go/spawn/ompadapter/normalize/stub rewritten; ALL reds green; apidiff
  byte-identical; 8 documented frame-contract decisions (grant-derived dialog answers
  — never invented approval; ask+resolution published; always-ask enforced; ids
  counter-matched to the probe); Linux lanes integration/lifecycle/load green with
  goleak; bench +20.7% B/op = the security fix's 2 argv tokens, re-baselined with the
  pre-existing drift proven not-ours via base-tree benchmark.
- FIX (author, 02cac9a): property generator excludes leading '-', scan is (flag,value)
  pair-aware WITH the resume generator still drawing flag-like values on purpose; 6
  argv break-tests; 22 lints → 0 with no weakening + one strengthening (EqualFold
  never-Approve); gates 5/5+11/11+6/6 PASS in-container (gitdir-mount environment fix
  recorded: unmounted gitdir = silent rc=128 abort that reads like a hang); mutate =
  design-skip (leaf=false), 5 credential-gated SKIPs = PR-2's lane.

## Blocked
-

## Blocked
-

## Next
Phase 4: adversarial verify of the whole rewrite.
