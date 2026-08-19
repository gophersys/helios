# ompadapter-rpc-mode

phase:    submit
repo:     gophersys/libs
branch:   feat/ompadapter-rpc-mode
worktree: ~/code/.worktrees/libs-ompadapter-rpc-mode
pr:       -
attempt:  1/2

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
HELD at phase 4 on a frame-contract decision (F1/F5). Verify round 1 (task
a4238b2552da4c1f4) verdict: NOT READY — 2 STOP-AND-REPORT + 3 send-backs. Gates
5/5+11/11+6/6 green; 4 of 7 break-tests bit; decision (b) ask+resolution ordering
proven no-wedge; close ladder/goroutines/fixtures all clean.
- F1 HIGH (SECURITY, reopens contract): rpc.go dialog answerer decides from bare tool
  NAME membership, discards grant Scopes AND the command on the dialog title's 2nd
  line — a bash grant scoped to "ls *" auto-approves "rm -rf /"; the library's
  permission.go scope check + riskClass clamp never run. My implementer direction
  ("derive from toolNames(spec.Grants)") is the flaw.
- F5 MEDIUM (reopens capability claim): CapPermissionPrompt:CapFull contradicts
  session.go:265-269 — the adapter discards the answer frame and substitutes its own
  verdict, so Session.Resolve(allow) returns ack=nil for a decision that reaches omp
  nowhere. Manifest lies OR Resolve must return Unsupported.
- Test-coverage send-backs (phase 2, AFTER the contract decision — they touch the same
  dialog path): F2 no test for the tunneled-steer guard (disabled → load 4s→224s, all
  green); F3 no positive-arm test (dialogTool→"" → every tool Denied, green); F4
  assertSameSentinel compares typed cause by VALUE not identity (per-call error passes).
- F6 real-omp lane #15 does NOT exist despite the plan claiming "AUTHORED here" — bare
  LookPath("omp") drives oh-my-posh's omp; add the binary-identity assert (this is why
  PR-1b's #15 must actually land or PR-2 owns it, stated).
- F7 bench baseline is GOMAXPROCS=-8 → vacuous PASS on any other CPU count (lib.sh, out
  of diff — ticket). F8 stale doc comments (per-turn-process model) in 5 test files.
  F9 capitalized-grant vocabulary denies all tools (PR-2 real-omp lane).

## Blocked
HELD at phase 4 on a frame-contract decision (F1/F5). Verify round 1 (task
a4238b2552da4c1f4) verdict: NOT READY — 2 STOP-AND-REPORT + 3 send-backs. Gates
5/5+11/11+6/6 green; 4 of 7 break-tests bit; decision (b) ask+resolution ordering
proven no-wedge; close ladder/goroutines/fixtures all clean.
- F1 HIGH (SECURITY, reopens contract): rpc.go dialog answerer decides from bare tool
  NAME membership, discards grant Scopes AND the command on the dialog title's 2nd
  line — a bash grant scoped to "ls *" auto-approves "rm -rf /"; the library's
  permission.go scope check + riskClass clamp never run. My implementer direction
  ("derive from toolNames(spec.Grants)") is the flaw.
- F5 MEDIUM (reopens capability claim): CapPermissionPrompt:CapFull contradicts
  session.go:265-269 — the adapter discards the answer frame and substitutes its own
  verdict, so Session.Resolve(allow) returns ack=nil for a decision that reaches omp
  nowhere. Manifest lies OR Resolve must return Unsupported.
- Test-coverage send-backs (phase 2, AFTER the contract decision — they touch the same
  dialog path): F2 no test for the tunneled-steer guard (disabled → load 4s→224s, all
  green); F3 no positive-arm test (dialogTool→"" → every tool Denied, green); F4
  assertSameSentinel compares typed cause by VALUE not identity (per-call error passes).
- F6 real-omp lane #15 does NOT exist despite the plan claiming "AUTHORED here" — bare
  LookPath("omp") drives oh-my-posh's omp; add the binary-identity assert (this is why
  PR-1b's #15 must actually land or PR-2 owns it, stated).
- F7 bench baseline is GOMAXPROCS=-8 → vacuous PASS on any other CPU count (lib.sh, out
  of diff — ticket). F8 stale doc comments (per-turn-process model) in 5 test files.
  F9 capitalized-grant vocabulary denies all tools (PR-2 real-omp lane).

## DECISION (Mateo, 2026-08-19): route omp dialogs THROUGH the library permission
chain; CapPermissionPrompt:Full stays (honest once F1 routes). F5 closed by F1's fix.

## History (fix round 1 detail below)
Fix round 1, TDD order:
- phase 2 (test author): pin RED — (F1) an omp select dialog surfaces as
  EventPermissionRequest carrying the COMMAND TEXT (title 2nd line), and the wire
  answer equals what Session.Resolve returns (Allow→Approve, Deny→Deny), NOT what
  bare-name grant membership would say — the scoped-grant-vs-rm-rf case must show the
  library DENY reaching the wire; deny-on-timeout when no Resolve arrives before omp's
  (absent) deadline → adapter's own bounded fallback. (F2) the tunneled-steer guard has
  a test (disabled → a decision frame reaches omp as conversation text). (F3) positive
  arm: a Resolve(Allow) yields wire Approve. (F4) assertSameSentinel by identity not
  value. (F6) the real-omp #15 lane exists with a binary-identity assert (oh-my-posh
  collision) OR the plan+PR body state plainly it lands at PR-2 — decide and pin.
- phase 3 (implementer): rewrite the dialog path — no grant-derived answer; surface
  EventPermissionRequest, await the library verdict, map Resolve→wire answer async,
  bounded deny-on-timeout; delete grantedTools/isGranted/dialogTool self-decision.
- then re-verify (round 2), PR. Also fix F8 stale doc comments; F7 bench-GOMAXPROCS is
  an out-of-diff ticket (lib.sh).

## Fix round 1 — landed (routing rewrite)
RED (author 8a19436/a553ef1): #1 command-in-ask, #2 rm-rf DENY-reaches-wire (drives
the REAL library + risk clamp), #5 human-Allow-reaches-wire, #3 timeout-deny, #4 guard,
#6 sentinel-by-identity, #7 verifyOmpBinary — all red for the right reason; F6 decision
(b): #15 real-omp lane is PR-2's, binary-identity guard here instead.
GREEN (implementer 377079c + lint 1755f85): adapter is NO LONGER a permission authority
— dialog() surfaces EventPermissionRequest with the command folded into Tool as
base(scope) so the library's scope-match+risk-clamp see it; library decides; Send maps
the eden:permission steer to the wire (Allow→Approve label, Deny→Deny), cancels the
6-min deny-on-timeout fallback; EventPermissionResolved drained with priority so the
2nd Prompt isn't refused; verifyOmpBinary rejects oh-my-posh, Spawn probes --version.
grantedTools/isGranted DELETED (no self-decision path survives; dialogTool remains ONLY as the title parser feeding the ask). Gates 5/5+11/11+6/6 green in-container;
apidiff byte-identical; cover-floor 84.4%; 2 credential-gated live SKIPs in integration_test.go (live token, real-omp binary) + 1 unrelated rapid Skip; the earlier '5/6' counts were stale (LiveAdvisor_AllowsLowRiskRead no longer exists).


## Fix round 1 CLOSED (fbbe326): F8 comments trimmed to rpc truth; fold-pin note added.
Verify round 2 READY. Flake ticketed (TurnOrdinalIncrements under parallel gates, not PR-1b's).
Ready to submit: routing security fix (library decides, adapter routes; rm-rf DENY reaches
the wire, human Allow reaches the wire, CapPermissionPrompt:Full honest) survived break-tests.
