# agentsession-multi-turn

phase:    fix
repo:     gophersys/libs
branch:   feat/agentsession-multi-turn
worktree: ~/code/.worktrees/libs-agentsession-multi-turn
pr:       -
attempt:  2/2

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

## Verify round 1 (send-backs) + fix round
Verifier: R1 largely CONFIRMED (9 break-tests bit; 3 retirements true; apidiff exactly
4 lines; -race x5 clean; the promptPending mechanism survived the race hunt: refused
Steer does not arm, concurrent Prompts advance exactly once). REFUTED: F1 HIGH
permission-first turn loses its ordinal (AwaitingPermission detour eats the arming);
F2 HIGH session terminal replays only the LAST turn's ledger (300/1 for a 100+200+300
session) while flagged Cumulative; F3 ompadapter.go:100-103 false stdin comment still
present; F4 types.go:255 EventResult doc row now false; F5 4 commit subjects >72 chars
(libs rule) — scripted reword rebase BEFORE the PR; F7 contract-text deferral to eden
S5 goes in the PR body. ENV: gofumpt v0.10(amd64 image)/v0.11(arm64) skew — test files
now dual-clean (b175c8a); if CI runs the amd64 image other diffs may format-differ.
RED PINS (b175c8a): TestTurn_PermissionFirstTurnKeepsItsOwnOrdinal (got ordinal 1/2
ids, want 2/3); TestClose_SessionTerminalSumsThePerTurnLedgers + ...DeltaFlagged...
(both 300/1 want 600/3; the pair forbids branching on Cumulative). Author's open point
for the implementer: claude's result ledger may be cumulative AT SOURCE (num_turns,
total_cost_usd) — reconcile per-turn deltas vs sums without double counting.

## Fix round — landed (17273c7, 03a44b4, e97ded6)
F1: turn-opening edge = Running OR AwaitingPermission, only an ARMED edge consumes;
arming still strictly post-guardControl. F2: pump-local turnLedgerSum accumulates every
EventTurnEnd; requested-close terminal carries the session total; constraints held (no
emit off pump, no pump-side Send, no locks). F3 false stdin sentence deleted (one home
= spawn.go). F4 EventResult row reworded. All 3 pins GREEN; root -race 35 PASS;
adapters unit+integration green; 6/6 phase gates EXIT=0; gofumpt dual-version clean;
subjects 66/66/57 chars. SOURCE-SHAPE RECONCILIATION (evidence-read): omp per-turn by
construction (fresh process+normalizer, Turns:1 hardcoded — Cumulative:true flag
proven NOT the discriminator); claude result totals ITS OWN exchange (input/cache
columns sum exactly per-message; num_turns = API iterations in one exchange); delta
subtraction forbidden by both pin pairs AND the adapter integration assertions.
RESIDUAL for PR-2's live lane: no second real-claude result capture exists — if live
claude proves cumulative-across-prompts, the fix is a normalizer delta, stated in the
invariant comment. LEFTOVERS (recorded, unclaimed): emitTerminalFailed carries no
ledger (unbidden death = zero accounting); LedgerFold does not fold EventTurnEnd
(EventFailed path folds zero); types.go:303 Turn doc says per-message.

## Verify round 2: STOP-AND-REPORT — 2 blockers, both NEW information
F1-F4 closures all CONFIRMED by break-tests. NEW: B1 HIGH — unbidden death emits a
terminal with NO ledger; R1 CREATED the loss (pre-R1 zero was correct; now 3 paid
turns seal as 0 while the Close path on the identical session seals 600). B2 — the
amd64 CI tier is RED: agentruntime/turnend_test.go not dual-gofumpt-formatted (the
"dual-version clean" claim covered only agentsession). Also: (3) the fix regressed
the -1 cost sentinel to 0 ("billed unknown reads as free"); (4) types.go:415
Cumulative doc names the claude result as session-to-date — the OPPOSITE of the
invariant, on the contract surface; (5) boundary-only turn loses its ordinal —
edge-enumeration has failed twice, derive the advance AT ARM TIME instead; (6)
types.go:303 "per message" one-worder; (7) invariant comment overgeneralizes (output
column does not reconcile — state it); (8) pre-existing budget-authority dead on real
adapters → ticketed. Attempt 2/2 justified: new findings, exact fixes.

## Next
FINAL attempt: test author pins B1 + sentinel + boundary-only-ordinal RED and fixes
B2 formatting; implementer greens B1 (pass the sum to emitTerminalFailed) + sentinel
(-1 preserved when no turn reported) + arm-time ordinal + docs (4/6/7). Verify round
3 LIMITED to these closures. Any further HIGH = hard stop, report to Mateo.
