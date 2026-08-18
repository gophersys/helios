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
- STUBS (implementer, f5da09f): both stub harnesses turn-driven; 1 process served 3
  turns (result lines 1→3 measured); all 5 lanes green at stated scope (unit/
  integration/lifecycle/load -race rc=0, ctl.sh lint 0 issues); 62 PASS unchanged.
- RED Round A (test author, aa34dbd/ac89336/b2fed0e/e742f87): tests 1-6 + re-pins all
  RED for R1 reasons in ghcr.io/gophersys/base — success result → kind=result
  IsTerminal=true (both adapters, incl. 2-turn case); requested Close → EventFailed
  "stream ended without a terminal"; Prompt 2 of 3 refused "illegal in state running";
  agentruntime advisor records allow-vote as DENY (correctness, not slowness);
  token-totality test proven able to fail on scratch (2 probes); controlframe suite
  proven to bite on BEHAVIOUR via naive-codec scratch (4/5 FAIL) and pass on the
  reference codec. EventTurnEnd spelled positionally so reds are behavioral, proven
  honest on scratch (bare const turns only the token test green).
- KNOWN STATE: claudeadapter test binary uncompilable until controlframe lands
  (sanctioned, own commit ac89336; package reds recorded at aa34dbd before it).

## Blocked
-

## Round A2 (928ab1e) — proven
- Tests 7-8 RED on REAL subprocesses: turn 1 ends the SESSION (kind result), Prompt 2
  refused "illegal in state COMPLETED" (correction: adapter lanes latch completed, not
  running — the scripted root test reaches running). claude load re-pin: 50/50 cycles
  fail at fan-out. omp lifecycle probe: session dead before Close. Shared drainer
  re-pin proven GREEN (deadline branch unmoved). 3 lanes verified needing NO change by
  running them. Incidental test-owned fix: lastKind rune-conversion bug (string(uint8))
  → .String(). Rename: TestIntegration_LiveClaude_HostToolReachesTerminal →
  _HostToolCompletesItsTurn (check eden/.ci for by-name references).
- HONEST GAPS for Round B: tests 7-8 assertion bodies past Prompt 2 are red by
  UNREACHABILITY (ordinals 0/1/2, one-process-served-every-turn, three-execs-one-ready,
  sole-terminal-is-requested-close, seq+leak) — Round B must show EACH green by name.
  claudeadapter reds ran inside a snapshot break window (controlframe absent) — re-run
  both commands WITHOUT the window after controlframe lands. Live arms still SKIP here
  (PR-2's lane). goleak has never seen a 3-turn lifetime.

## Round B (implementer) — landed
R1 implemented in full; judge fatals held (no emit off pump, no pump-side Send, no
guardControl bypass); apidiff delta = controlframe section, 4 lines, zero for
EventTurnEnd. All 6 formerly-unreachable assertions proven EXECUTED+BITING via
reversible break-probes; goleak clean over real 3-turn lifetimes, both adapters, no
new ignores. All 4 lanes RC=0 both libs (5 credential-gated live SKIPs named, PR-2's
lane). Design refinement beyond plan text, flagged+justified: turn ordinal advances
only on an admitted Prompt (multi-message claude turns otherwise counted 8 for 3);
conformance case still passes. Renamed live test: zero by-name references anywhere.
Architecture gate RED only when run explicitly (contract doc lives in eden;
pre-existing; PR lane never runs it — verified).
GATE RESIDUE, all test-owned: (1) claudeadapter_test.go TestNormalize_SampleStream
un-re-pinned — asserts IsTerminal count==1 over a success-result fixture, directly
contradicts R1 test 1; sole cause of every agentsession lane FAIL; fix = count
ev.Terminal != nil. (2) 13 lint issues in test files (9 misspell, 3 gocritic,
1 revive). Latent notes: agentsessiontest/conn.go:200 close-race coin flip (harmless
under R1); LedgerFold default-arm does not fold turn boundaries (real design question,
not Round B's).

## Final test round (5739775) — ALL GATES GREEN
Sample-stream re-pin counts ev.Terminal != nil + non-terminal + token render; proven
able to fail via scratch revert probe (FAIL with the old mapping). Lint 13→0, no
suppressions (token shadow renamed; ctx reordered to the package's own convention).
Phase gates 6/6 EXIT=0: implementation/testing/qa in BOTH libs, zero FAIL, zero
REQUIRED-BUT-ABSENT, docker-enabled runs. CORRECTIONS: live-skip count is SIX (adds
TestIntegration_LiveAdvisor_AllowsLowRiskRead). FOUND+TRACKED (not fixed, outside
ownership): _ctl/lib.sh integration dimension has no --- SKIP: assertion — a
substrate-unreachable skip printed PASS (proven via socket-denied NATS test) — task
opened, fold into PR-1c lane work. Machine note: docker VM disk hit 100% mid-run,
resolved non-destructively via bind-mount caches; the 9.35GB "dangling" image is the
LIVE devcontainer's (do not prune); 77 orphan volumes ~3.9GB = future cleanup.

## Next
Phase 4: dev-verifier adversarial refutation. Then cleanup pass, PR.
