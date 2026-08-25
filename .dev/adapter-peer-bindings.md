# adapter-peer-bindings

## READINESS PROVEN on the post-repin toolchain (2026-08-25 ~15:55)
Full gate in base:latest with govulncheck 1.7.0 installed (the post-repin world): phase-gate
implementation rc=0, testing rc=0, qa rc=0 — every dimension PASS incl. apidiff no-break, vuln,
sast, secretscan, cover-floor, no-shortcuts, evidence bundle. Toolchain verified honestly: a cp to
/usr/local/bin failed, but `go install` had overwritten the image's own binary at /home/dev/go/bin
which PRECEDES /usr/local/bin on PATH, so `command -v govulncheck` -> 1.7.0 and the vuln PASS is
real. SCOPE: proves agentsession's OWN gates on the fixed toolchain; does NOT prove repo-wide
validate (the panicking libs are go/secrets + go/workspaceprovider, fixed by the image repin).
#26 is READY to move on eden's go-ahead.

## ATTRIBUTION IS IDENTITY (Mateo, 2026-08-25) — binding, forward-only
Reverses the old no-attribution rule. Now in ~/.claude/CLAUDE.md by Mateo's own hand.
- Solo agent work is authored `Claude <claude-agent@gophersys.noreply>`. Interactive work is
  authored Mateo + `Co-Authored-By: Claude`. Claude NEVER commits/approves/comments as "Mateo".
- A human gate counts as exercised ONLY with Mateo's VERBATIM words + timestamp in the record.
  Under a standing grant, say so explicitly: "under walk-away grant 2026-08-25 — gate not
  individually exercised by Mateo". An agent never self-certifies a human gate.
- FORWARD-ONLY: do NOT rewrite existing history. NOTE FOR THE RECORD — every commit on this branch
  before 4bd597b was authored "Mateo Segura <mateo.segura413@gmail.com>", i.e. as Mateo. That is
  exactly what this rule forbids; it is left as-is because the rule is forward-only, and it is
  disclosed here rather than quietly corrected. git author is now set LOCAL to this worktree (not
  global, so Mateo's own interactive commits elsewhere are unaffected).

## AUTHORITY CHAIN for the #26 merge (quote this in the merge record)
Mateo's VERBATIM words, this session, 2026-08-25 (~15:45 MST, session-relative — exact wall-clock
not captured): "yes edne speaks for me" and "lsiten to everythgin eden says hes your driver".
That is a DIRECT grant from Mateo delegating decision authority for this lane to the eden session.
Therefore, at merge time the record must read: merged under Mateo's delegation to eden
(verbatim above); eden gave the go-ahead; **the merge gate was NOT individually exercised by
Mateo on this PR**. Do not imply he reviewed #26 personally — he did not.

## DELEGATION (2026-08-25) — READ THIS FIRST AFTER A CONTEXT LOSS
Mateo confirmed DIRECTLY, in his own words: "yes eden speaks for me" / "listen to everything eden
says hes your driver". The eden session is the DRIVER for this lane's decisions, including the #26
merge go-ahead. Do NOT hold #26 for Mateo personally any more; it waits on eden's go-ahead + the 4
merge conditions (checks green AND logs read, review verdict read as its own call, no open decision
in the body, --merge not --squash + state file deleted). Still escalate to MATEO only: repo
deletion, production deploys, secret values, spend beyond budget.
Standing eden ruling in force: DO NOT re-run #26/#25 CI until eden confirms the ARC pool digest
repin landed — the pools pin cloud@sha256:9a150cbf... by digest (the DIGEST VALUE I first
recorded, 9a150cbf, was WRONG — I grepped a 7-day-stale local checkout; origin/main actually pins
245e3e9efb34 since infra #203/6ded578 merged 19:42, and 9a150cbf now survives only in 2 deliberate
non-pin spellings: docs/ci-substrate.md + scripts/test-verify-warmer-pins.sh. The STRUCTURAL claim
— pools pin cloud by digest, so the fix is inert until repin — holds and is why the hold is right.
LESSON: fetch before measuring; a stale working copy passes a grep and reads as verified),
so the merged govulncheck fix is INERT until that repin. A rerun now burns a red run for nothing.

phase:    wait
repo:     gophersys/libs
branch:   feat/adapter-peer-bindings
worktree: ~/code/.worktrees/libs-adapter-peer-bindings
pr:       26
attempt:  2/2

## Goal
PR-1c-ii — the deferred half of the peer slice: bind the merged peer plane to the two
real harnesses so a running agent can actually send and receive.
- claudeadapter/peer.go: ride NATIVE cross-session messaging (the execution-proven
  contract: --name <id>, --settings '{"crossSessionInbound":"accept"}', the receiver's
  delivery-triggered result event carries origin{msg_id,name,body,...}, sender's
  SendMessage tool result carries the same msg_id). Normalize inbound to
  EventPeerMessage / outbound acceptance to EventPeerSent.
- ompadapter/peer.go: eden_peer_send / eden_peer_list host tools on the merged rpc
  host-tool router; the library-owned plane carries the traffic.
- Both bindings: ZERO .apibaseline delta (unexported); CapPeerMessaging claude=Partial
  (cross-harness send from a claude model is v1-out-of-scope), omp per its plane role.
Live proof is eden's harness lane at PR-2 (libs CI has no credential/harness).

## Plan
plan: SELF-APPROVED (--auto) with ONE COORDINATOR OVERRIDE (below). Canonical plan =
planner report (task a523f9ad0b54cd914). Load-bearing findings:
- STRUCTURAL: an adapter CANNOT reach the plane — Adapter.Spawn carries no PeerLink and
  Pool.Open calls Spawn (pool.go:81) BEFORE joinPeer (:95). So the eden_peer_send /
  eden_peer_list HostTool DEFINITIONS live in the LIBRARY (new unexported
  agentsession/peer_hosttool.go), injected by Pool.Open into its own COPY of
  spec.HostTools (never mutate the caller's slice), gated on Deps.Peer!=nil &&
  Spec.Name!="" && the adapter's CapPeerMessaging status. They ride omp's already-merged
  host-tool router unchanged. controlframe.DecodePeer exists with NO caller — this PR is
  its caller, in the home already documented for it.
- MEASURED CORRECTION to the contract memory (now fixed there): result.origin is the ONLY
  inbound form on stream-json stdout — 0 <cross-session-message> wrappers, 0 type:"user"
  events across all three captures. Parse origin; never scrape text. EventPeerMessage is
  emitted immediately BEFORE the EventTurnEnd the same result line produces.
- claudeadapter scan() becomes a select-pump over (lines, peerEvents, done) — the events
  chan is unbuffered and the scanner is its sole sender, so a Send-goroutine write would
  race; shape copied from the proven ompadapter pump() resolved-channel pattern.
- Zero .apibaseline delta: buildArguments unexported in BOTH adapters (verified). What
  WOULD break it: any new package dir (each emits a ## header) or any new exported
  symbol. The baseline is BLIND to a new field on an exported struct — so apidiff is
  never the only guard; the manifest-truthfulness test is.
- Risks: the HELD sender-side receipt was never captured (the Accepted:false arm is
  unverified in libs — eden PR-2 settles it); the plane cannot see native traffic
  (Orchestrator.received is a silent no-op on an unknown id, so native msg_ids
  corroborate nothing — accepted, not fixed); kill-switch envs disable native messaging
  observably but nothing fails on it; --name collisions go live natively before the
  plane can refuse them (Spawn precedes Join); two unrelated clocks (claude dialogExpiry
  5m vs peerplane DeliveryDeadline 30s); SendMessage is NOT auto-granted and the adapter
  must not widen --allowedTools (it is not a permission authority — the merged omp
  dialog ruling).

## COORDINATOR OVERRIDE of the planner's open question
The planner recommended amending the MERGED peer_pair_harness_test.go claude-omp pair to
one direction (claude→omp unreachable, CapPartial). REJECTED: Mateo ruled FULL MESH v1 at
the design gates, explicitly choosing the recovery path — "the library recovers the failed
native send from the tool_use INPUT {to, message} and routes it over the bus", accepting
the model-visible-failure caveat. The merged obligation stays as authored; A3 (claude→omp)
MUST deliver. The recovery honors the structural constraint: the ADAPTER only surfaces the
failed-send + recovered payload as a normalized fact; the LIBRARY (which holds peerLink)
does the routing. Capability is declared by what the proof arm supports, and the
model-visible failure is documented as a known caveat in code + PR body.

## Proven
- RED (author, 1a9e37d behavioural + d3548a4 compile-dep): 16 tests; fixtures copied
  VERBATIM from the committed captures with provenance headers (2 derived files state
  their edits). Reds verbatim: origin→PeerMessage 0-got; bypass-accept 4 expected 0-got;
  argv missing --name/--settings; send-receipt both arms 0-got; omp inbound leaked the
  RAW `eden:peer:` frame + 0x1f separator to the model (the exact leak); host tools not
  injected; manifest CapAbsent on both; canary arms 0-got; recovery surfaced-then-ROUTED
  0-got with review-c receiving nothing. Bite proofs: a result-keyed (naive) normalizer
  makes the HELD control fail 1 and bypass fail 5 — the control discriminates; the
  3 missing seams reproduce byte-for-byte from absence alone.
- CORRECTIONS to the plan (measured): the bypass-accept capture has 5 result lines, 4
  with origin and ONE without (the plan said 2 origin-less; the second lives in a
  different capture). peer-send-unreachable.jsonl is DERIVED — the failure body is
  quoted from probe-2.json's P1 ADDRESSABILITY finding (measured, never captured as a
  raw stream line); its envelope is byte-copied from the real success line. Whether a
  failed SendMessage sets is_error is UNVERIFIED — test 12 asserts the digest still
  carries the failure text and asserts nothing about ToolOutcome.

## Blocked
-

## SEAMS the implementer adds (exactly these; export_test.go documents each)
1. claudeadapter newPipeConn(spec, io.Reader, io.WriteCloser) *processConn — the analog
   of the merged ompadapter.RPCConnForTest; takes the Spec because a conn that does not
   know its own Name cannot tell a delivery meant for it from one that is not.
2. claudeadapter peerEnvelope(from, msgID, replyTo, body string, verified bool) string —
   the pure model-facing renderer; verified renders explicitly in BOTH directions.
3. agentsession peerHostTools(name string, plane PeerPlane, link PeerLink) []HostTool in
   the new unexported peer_hosttool.go; nil link → typed errors.KindUnavailable never a
   panic; nil plane or empty name → empty set.
NORMATIVE LITERALS the reds pin (contract, not preference):
  tools "eden_peer_send"/"eden_peer_list"; send args {"to","body"} → answer
  {"msg_id":"<the id the PLANE minted>"}; Detail discriminators "send-receipt-unparsed"
  (accepted natively, id unreadable — NEVER re-routed) vs "native-send-unreachable" (the
  full-mesh recovery — the library DOES route it); argv --name <name> --settings
  {"crossSessionInbound":"accept"} as ONE raw element; wire envelope
  <eden-peer-message …verified="true|false"…>body</eden-peer-message> — never
  "eden:peer:" and never 0x1f in front of the model.

## GREEN (implementer df534fe..1c40725 + author lints 70031dd)
All 21 tests green by name incl. 11b (recovered send DELIVERED through the real
Pool→pump→deliver→plane to review-c) and 12 (native failure still reported to the model
— both halves). Gates: implementation 5/5, testing 11/11 (real docker+k3d integration),
qa 6/6; apidiff ZERO delta; goleak clean over the new select-pump + channels; gofumpt
dual + -extra clean. Author's lint round proved assertion force UNCHANGED by replaying
the refactored tests against the pre-implementation tree (each arm still bites at the
same line). Implementer's design decisions recorded: recovery triggers on any
success:false receipt (never prose-matching); routing outcome stamped onto the ONE
published event (routed → MsgID=plane-minted + Accepted:true, Detail kept as
provenance); Detail literals + peerEnvelope spelled per-package (zero-baseline-delta
wins over one-home; counterparts documented); cross-addressed deliveries refused
KindInvalid; eden_peer_list renders the five roster fields explicitly (never
json.Marshal of []Peer). Known: HELD sender-side receipt still uncaptured (derived
fixture; is_error unverified — branching is on success only); architecture gate's
contract-doc dimension resolves only when mounted at eden/libs (path artifact).

## Verify round 1: SEND BACK — 1 HIGH (security), 1 HIGH (test gap), 2 MEDIUM deadlock, 1 LOW
Core survived attack (full-mesh delivery, frame-unwrap, injection-copy, manifest guard,
result-keying bite all break-tested red). NOT survived:
- F1 HIGH (SECURITY): peerEnvelope (claudeadapter/peer.go:192-210 + ompadapter/peer.go:
  100-118) concatenates the untrusted body with NO escaping; the only guard is an
  EXACT-BYTE strings.Contains("</eden-peer-message>"). `</eden-peer-message >` (space —
  valid XML close grammar), newline/tab/UPPERCASE variants, a nested opening tag, a raw
  0x1f, and the literal `eden:peer:` all slip past → a peer body forges a
  from="root" verified="true" delivery to the RECEIVING model (prompt-injection). Fix:
  ESCAPE (<,>,& in body; " in from/msg_id/reply_to), NOT a wider blocklist. Implementer
  = peerEnvelope escaping (both adapters); test author = the crafted-body arm.
- F2 HIGH (test gap / check-that-cannot-fail): isRecoveredSend (peer_session.go:183-186)
  has NO arm for Detail=="send-receipt-unparsed" — deleting the Detail clause keeps all 8
  packages green while a natively-ACCEPTED send gets DOUBLE-delivered. Test author: third
  table arm {Accepted:false, Detail:"send-receipt-unparsed"} → wantRouted:false.
- F3 MEDIUM: routeRecoveredSend (peer_session.go:163) calls peerLink.Send on the PUMP
  goroutine (both Sends ignore ctx; socket blocks handshakeTimeout 10s, in-proc is an
  unbounded inbox push) — violates the invariant stated twice (peer.go:72-74,
  peer_session.go:67-70). Route off the pump or bound it.
- F4 MEDIUM: claude queuePeerEvent (peer.go:253-276) blocks under writeMu; Close needs
  writeMu → with F3, a wedged pump makes Close UNKILLABLE (deadlock). omp releases
  writeMu before queuePeerEvent — match it. Implementer.
- F5 LOW: claudeadapter/leak_test.go:11-14 doc now false (peer_conn_test drives real
  scan+readLines goroutines in the fast suite). Test author.
Verifier method notes accepted: cover-floor first-read void (concurrent breaks),
re-ran serially 11/11; count is 20 new tests not 21; harness lane authored-not-run
(claude→omp full mesh proven only vs in-memory plane; real proof owed at eden PR-2).

## Fix round 1 — implementer landed (5c11d37..d9c4643)
F1 escaping in BOTH adapters (escapePeerBody &→&amp; first then <>,  escapePeerAttr on
from/msg_id/reply_to) — 7 attack bodies (space/newline/tab/uppercase close, nested tag,
0x1f, eden:peer:, attr-close) all render INERT; escaping IS the boundary now, the
exact-byte guard stays defense-in-depth. F4 writeMu moved off Send into the leaf writers
(matches ompadapter writeFrame). F3 recovered send routed on the DEDICATED deliver
goroutine (session.recoveredSends chan; deliverLoop→routeRecoveredOnBus→peerLink.Send);
pump only discriminates + enqueues non-blocking, publishes EventPeerSent VERBATIM.
Audit: the ONLY peerLink.Send is on the deliver goroutine; no pump-side plane Send; all
s.emit pump-only. goleak clean; 30x -race stress no hang; bounded Close; apidiff zero.
BEHAVIOR NOTE (verify-2 + PR-2): the recovered EventPeerSent is now verbatim
(Accepted:false, Detail:native-send-unreachable, no plane MsgID) — the plane's OWN
reconciler tracks the bus delivery/bounce, so no info lost; but harness A3 (claude→omp)
must correlate via RECEIVER ARRIVAL, not the sender's stamp. No in-CI test red today.

## Fix round 1 — test author landed (cdc42f6, cd7b614, d85a8fc)
F1 crafted-body arms BOTH adapters (8+3 sub-arms each; omp got PeerEnvelopeForTest in
export_test.go): bite proven vs the pre-escape renderer — space/newline/tab/UPPER close,
nested tag, and quote-in-from each forged live structure incl. verified="true"; HEAD all
PASS. F2 third arm bite proven: deleting the Detail clause routes an unparsed-receipt
send (double delivery); HEAD PASS. F5 leak doc corrected. gofumpt -extra clean. All 3
phase-gates GREEN in-container (testing 11/11 incl. real docker+k3d+kind; qa incl.
gremlins>=0.75). Cover: claudeadapter 81.9%, ompadapter 85.0%.
STANCE FLAGGED for verify-2: escaping is STRUCTURAL only — raw 0x1f and literal
"eden:peer:" survive as INERT body content (cannot forge grammar; arms assert one open +
one close tag, no raw angle bracket, verbatim round-trip via html.UnescapeString).
Byte-stripping would be an ADDITIONAL spec. Also: escapePeerAttr leaves < > in attr
values (inert-in-quotes, upstream name/id validation excludes them); only " asserted.
EventPeerSent verbatim form: no existing assertion expected the old re-stamp — nothing
updated, consistent.

## Verify round 2 — SEND BACK (new root cause, not the same fix)
Gates all green in-container (impl 5/5, testing 11/11, qa 6/6). F2 CLOSED (bite replicated),
F4 CLOSED (writeMu leaf-only, 30x -race clean), F5 CLOSED (doc true). BUT the escaping
closed only the BODY; identity fields stay forgeable — the round-1 fix treated a symptom.

- V1 HIGH (REOPEN F1, decode side): controlframe EncodePeer joins 5 header fields with 0x1f;
  DecodePeer SplitN on 0x1f. A 0x1f INSIDE a header field (from / reply_to) shifts boundaries
  → forges verified="true" + from="root" to the receiving model. Reach: peerplane register/
  serveJoin apply NO grammar check to a joining peer's NAME (peerNameRE guards only local
  Pool.Open Spec.Name); reply_to free-rides wire→EncodePeer. controlframe.go:85-89 doc ASSERTS
  0x1f "never appears in a validated peer name" — FALSE. This PR is DecodePeer's first caller.
- V2 HIGH (REOPEN, attr side): escapePeerAttr leaves < > RAW; the "upstream validation excludes
  them" stance is false (V1). A > in from/msg_id/reply_to forges a 2nd opening tag + live
  unquoted verified=true. Existing attr arm only greps QUOTED verified="true" — blind to it.
- V3 MED (test gap): removing the F3 or F4 fix stays GREEN — neither deadlock fix is guarded.
- V4 MED (F3 residue, PRE-EXISTING): pump-side s.peerLink.Received (pump.go:116→client.go:184)
  takes a mutex + synchronous conn.Write — the port contract says it MUST NOT block. client.go
  not in this diff → scope call: bound it or record accepted+follow-up.
- V5 MED (silent drop = FAIL-LOUDLY violation): recoveredSends 8-buffer overflow drops with NO
  event/log/bounce; D1's verbatim EventPeerSent makes a dropped recovery byte-identical to a
  delivered one — the exact silent-hold the plane exists to prevent. MUST go loud.
- V6 MED (D1 stale doc): types.go:262 + peer.go:23-24 say Accepted==false means "accepted but
  bounced"; now it has 3 meanings, 2 contradict that. Detail literals are branched-on contract,
  documented as "redacted reason" — fix the exported doc.

## The fix (root cause, ONE abstraction)
Body = free text → ESCAPE (done, holds per D2). Identity fields (from,to,msg_id,reply_to) =
VALIDATE to a safe alphabet at INGRESS (no 0x1f, < > " &), so neither serializer (controlframe
0x1f wire OR model envelope) can read a field byte as structure. Escaping one serializer is the
fix-that-must-be-repeated; validating at the boundary is the fix that isn't.

## Fix round 2 — landed (impl 686d309..3053748, tests be91ba2/4208d6f), on origin 4208d6f
V1 CLOSED at root: ONE ValidatePeerField grammar in internal/controlframe (rejects <0x20, 0x7f,
< > " &) over from/to/msg_id/reply_to; enforced at register/serveJoin/serveSend ingress + defensive
DecodePeer re-check; controlframe doc now says ENFORCED not asserted. Adapters refuse an undecodable
peer frame (KindInvalid) instead of leaking it to the model. Proven over a REAL unix socket
(ServeJoin/ServeSend refuse hostile 0x1f/<>/"). V2 CLOSED: escapePeerAttr escapes < > too. V5 CLOSED:
overflow publishes a distinct branched-on Detail (native-send-unrecovered) — loud, not silent. V4
CLOSED contained (client.go only, ~35 lines): clientLink.Received now a queue push + forwardReceipts
writer goroutine reaped by Close (pump can't wedge); goleak-proven. V6 CLOSED: types.go/peer.go docs
tell the truth about all 4 Accepted==false meanings + Detail-as-contract. V3 CLOSED: both guard arms
PASS -race on host AND compile clean (go vet rc=0); F3 arm fails if Seq stops advancing, V5 arm fails
if a dropped recovery is byte-identical to a routed one. apidiff: +1 internal line, zero removed/changed.
All 3 gates green per-dimension (impl 5/5, testing 11/11, qa 6/6). cover: controlframe 95.7%.
RESIDUAL flagged by implementer for round-3 ruling: routeRecoveredOnBus (peer_session.go:224) still
swallows an ASYNC peerLink.Send error (same silent-drop class as V5 but only when the bus hand-off
call itself errors; the deliver goroutine has no emit path — surfacing needs the pump's main range
loop to become a select over a feedback channel, a change to the most load-bearing loop). Impl judged
it out-of-list; round 3 rules ship-blocking vs tracked-follow-up.

## Verify round 3 — V1-V6 CLOSED, one contained blocker (V7)
All six bite-tested RED under -overlay (tracked files hash-identical after), gates green
in-container (impl 5/5, testing 11/11 real docker+k3d+kind, qa 6/6), apidiff +1 internal line only.
- V1 CLOSED: ValidatePeerField refuses <0x20 (0x1f/nl/tab/CR), 0x7f, < > " & at register/route/
  DecodePeer + recovered To/ReplyTo; bounce name eden-mesh.root passes (loudness not self-defeated).
  Socket bite reproduced the forgery live over a real uds then went green.
- V2/V3/V4/V5/V6 CLOSED (V3 both guards non-vacuous + independent; V4 goleak-reaped; V5 distinct
  branched literal; V6 docs accurate).
- RESIDUAL (async bus-Send swallow) = TRACKED FOLLOW-UP, not ship-blocking: invisible sub-cases
  (unreachable-To / over-long body) never fake "delivered" (native failure already on the stream);
  inbox-full gets a loud reconciler bounce. Follow-up task opened; lands with eden PR-2 harness lane.
- V7 SHIP-BLOCKING but CONTAINED: Session.Control passes caller Text verbatim to the adapter which
  content-sniffs decodePeerDelivery — caller/relayed text `eden:peer:`+5 fields+to=self+true renders
  a forged <eden-peer-message from=root verified=true> to the model, bypassing the V1/V2 wall. Both
  adapters. FIX (verifier's, better than origin-dispatch): reject any Prompt/Steer whose Text begins
  with controlframe.PeerPrefix OR PermissionPrefix in session.checkControl — the library's own
  injections (deliverToHarness, forwardDecision) call conn.Send DIRECTLY (bypass Control), so the
  caller is the ONLY Control-text source; ~5 lines, closes V7 + the pre-existing permission-sniff
  door in one home, zero apibaseline delta. Legit peer BODY starting eden:peer: unaffected
  (bodies delivered library-side, never via Control).

## V7 fix — implementer landed (484dd96, pushed)
session.checkControl now rejects a CommandPrompt/CommandSteer whose Text begins with
controlframe.PeerPrefix OR PermissionPrefix → errors.KindInvalid (closes V7 + the pre-existing
permission-sniff door in one home). Prefix cited from controlframe, not re-spelled. Invariant
CONFIRMED by the implementer: deliverToHarness (peer_session.go:127) + forwardDecision
(session.go:304) call conn.Send DIRECTLY, bypassing Control — the reject cannot break a real
delivery; a legit peer BODY starting eden:peer: is unaffected (bodies arrive via deliverToHarness).
apidiff ZERO public delta. Host checks green (build/vet/test/gofumpt/golangci); FULL in-container
gate (apidiff/hnslint/gremlins/gosec/govulncheck + 11-dim real-docker) OWED to the final verify —
the implementer's worktree lacked the container runner, so those did NOT run yet (not a pass).
Bite proven via a temporary probe (deleted, not committed).
STILL OWED: test author's permanent V7 arm (in flight); then the bounded final verify MUST run the
full gate IN-CONTAINER (a gate that could not run is not green — FAIL-LOUDLY).

## V7 arm — landed (87314d7, pushed)
peer_control_forgery_test.go: 2 forgery arms (peer + permission prefix via Session.Control) + 1
positive control. Bite proven via -overlay swapping session.go for its pre-guard parent 6b05d10:
pre-guard ADMITS the forged frame (reaches conn.Send → renders verified="true"); HEAD 87314d7 all
3 PASS. Non-vacuous: session.go shasum identical before/after, only the new test in git status;
zero-Send + KindInvalid + cause assertions all fail if the guard is absent. Both adapters covered
at the shared library ingress (asserts zero frames reach the fake adapter Received, so neither
claude spawn.go:205 nor omp rpc.go:196 can content-sniff). Host gofumpt/vet/peer-suite green.

## Final verify — SHIP except one MEDIUM (in-container, @00a7eff)
Gates GREEN in fresh base:latest, real docker.sock, all pinned tools: impl 5/5 (apidiff no-break),
testing 11/11 (integration RAN 193 pass / 5 skip — the 5 are the live-token harness runs owed to
eden PR-2, a documented env property, NOT a silent skip), qa 6/6 (mutate skip by-design leaf=false).
Guard correctness SHIP: checkControl rejects PeerPrefix|PermissionPrefix for Prompt|Steer, prefixes
cited from controlframe, HasPrefix set == sniffer trigger EXACTLY (no gap), no second Send door
(4 conn.Send sites enumerated; only Control carries caller text and it is guarded). apidiff zero
PUBLIC delta. No V1-V6 regression (59 peer arms + 5 ingress arms green by name).
SEND BACK — F-V7a (MEDIUM, check-that-cannot-fail): peer_control_forgery_test.go drives only
CommandPrompt; the guard's Steer half is UNTESTED — deleting `|| Kind==CommandSteer` leaves the
suite GREEN while a forged Steer (StateRunning, the PRIMARY running-turn delivery verb) reaches
Send and renders verified="true". Guard impl is CORRECT; only the arm is incomplete.

## F-V7a — closed (2d2ada1, pushed)
TestControl_RefusesForgedSteerInRunningTurn: forged CommandSteer (peer + permission prefix) in
StateRunning (the load-bearing state — CanControl(Running,Steer)==true, so the forged Steer is
admitted when the guard's Steer clause is absent). Asserts KindInvalid + zero internal-prefix frame
reaches Send. BITE proven: overlay-delete `|| Kind==CommandSteer` → the Steer arm goes RED (forged
Steer admitted), Prompt arms + positive stay green; session.go hash-identical, git status clean.
Production UNCHANGED since the 00a7eff in-container gate (only test + state-file commits added), so
that gate stands; the PR's own libs CI is the authoritative in-container re-run on the final SHA.

## PR-1c-ii OPEN as libs #26; phase 6 wait
CI RED — but a repo-wide CI-ESTATE regression, NOT this PR (phase-7 causation: SURFACED not caused).
Root cause = runner-image tool-version mismatch surfaced after #24 merged green 08-24:
(1) golangci-lint rejects the .ci-generated .golangci.yml (exit 3, additional property
'allow-parallel-runner' not allowed) + 'parallel golangci-lint is running' panic;
(2) govulncheck panics scanning go/secrets + go/workspaceprovider (exit 2, unexpected *ast.KeyValueExpr).
Proof not-mine: zero lint findings in any agentsession file; agentsession verb-record/shellcheck/
project.json all ok; unrelated PR #25 fails the IDENTICAL validate with the same allow-parallel-runner
rejection; deterministic (re-run won't clear). Full gate ran GREEN in-container at the pre-final SHA
with correct tool versions. Surfaced: PR #26 comment + eden back-channel handoff (eden owns .ci +
runner image; not touching it from this feature worktree to avoid colliding with eden's concurrent
.ci work). #26 is ready-to-merge on its own merits.

## BLOCKER ROOT-CAUSED + FIX OPEN (.devcontainer #102)
CORRECTION: my first diagnosis (golangci rejecting allow-parallel-runner) was WRONG — that exit-3 is
libs' own NEGATIVE SELF-TEST (go/_ctl/lib_test.sh:222) injecting the bad key on purpose. Retracted on
PR #26 publicly.
REAL CAUSE (execution-proven, real ctl.sh vuln verb, in base:latest): GO_VERSION->1.27.0 on 08-24 but
GOVULNCHECK_VERSION stayed 1.1.4 -> govulncheck 1.1.4 cannot parse the go1.27 AST -> panic
(unexpected expr: *ast.KeyValueExpr) on go/secrets + go/workspaceprovider under GOWORK=off -> vuln
verb dies -> pr tier red on EVERY libs PR (#25 identical), content-independent.
  1.1.4 panic | 1.7.0 rc=0 "[ok] vuln: OK" on workspaceprovider, secrets, agentsession.
FIX: .devcontainer PR #102 (pin 1.1.4->1.7.0 + stale-tracker annotation). .devcontainer validate
green IN-CONTAINER rc=0. Mateo authorized taking eden's estate work (eden offline).
SYSTEMIC: upstreams.txt tracked the pin via github-release, but golang/vuln STOPPED publishing
releases after v1.1.4 — github marks v1.1.4 latest while real stream moved to TAGS (v1.7.0). The
resolver answered CORRECTLY with a frozen value = green-check-that-verifies-nothing, in the version
supply chain. Global asks handed to eden: audit ALL github-release rows, add a github-tag datasource,
and a STALENESS ALARM (fail loudly when a tracker's value is frozen while upstream tags moved).

## Blocker RESOLVED on main (my #102 was redundant — CORRECTED RECORD)
CORRECTION-2: the superseding PR was EDEN's #103 (merged, 440f6c8), not Mateo hand-landing it — the
gh timeline actor reads MateoSegura because eden acts under his account. Eden also DID the global
audit (all 25 github-release rows swept: govulncheck was the ONLY frozen one, no second live freeze)
and opened #104 feat/go-proxy-datasource (go-proxy, NOT github-tag — `go install` fetches through
proxy.golang.org so the proxy decides the bytes; 5 pins move, all resolve to what they already hold;
GREMLINS+BENCHSTAT excluded by measurement). The STALENESS ALARM is explicitly NOT done and eden is
not claiming it — still open for the other 19 rows.
The govulncheck fix LANDED ON MAIN via eden #103: 968bd0b (pin 1.1.4->1.7.0) + 64f1495
(no-autobump, killing the weekly revert). Mateo closed my #102 at 21:54 as redundant; I REOPENED IT
BY MISTAKE at 22:07 without checking who closed it or why — my error, now re-closed with an
explanation and the branch deleted (both fix halves proven reachable from main first). The
"dead CI trigger" was NOT an Actions failure: GitHub reported mergeable=CONFLICTING because my branch
collided with the superior main version of its own change. Main's row note is better than mine (it
names the go module proxy that `go install` reads as the true upstream = the datasource the row awaits).
MERGED != IN EFFECT: base:latest still shipped govulncheck 1.1.4 at 22:15 (verified by running the
binary in the pulled image, not by reading a manifest). build-and-push 32903645215 (sha 440f6c8,
contains both fix commits) IN PROGRESS; the prior 21:20 run FAILED. Monitoring. libs #26 stays red
until that image publishes.
GIT-PROCESS v1 REFUTED by eden (26 findings) — I have stopped citing it; my earlier audit against v1
stands only for the parts eden confirmed (branch names/lanes valid; the §8 eden-PR-2 split RATIFIED).

## .devcontainer #102 — closed redundant (superseded on main)
pr-review REQUEST_CHANGES caught a REAL defect in my fix and was RIGHT: my "stale/manual" note sat in
field 4 (free text) but collect_bumps branches on FIELD 2 only, so the weekly resolver would have
read releases/latest->1.1.4, diffed vs 1.7.0, and written bump 1.7.0 -> 1.1.4 — silently reverting
the fix every Monday inside a batched PR. Verified the claim in the resolver source myself before
accepting. FIXED 2cc503e: field2 -> no-autobump, reason in field4, row moved to its own labelled
section. PROVEN: resolve-upstream.sh GOVULNCHECK_VERSION refuses loudly, ZERO bump lines, no 1.1.4;
validate rc=0; upstream-coverage 21/21.
CI-TRIGGER STUCK: no workflow run fires for 2cc503e or bef951d (both on origin; pull_request trigger,
no path filter; runner pool healthy, no Terminating pods). gh run rerun only replays the OLD sha
(5763252), so the PR still shows the pre-fix REQUEST_CHANGES. The correction is NOT yet CI-validated
— do not read #102's red review as current. Needs a real trigger (or eden/Mateo to investigate the
Actions trigger gap) before merge.

## BLOCKED — #102 CI trigger + merge + base:latest rebuild
Blocked on eden repinning the runner image (golangci config reconcile + govulncheck pin). When the
image is fixed, re-run #26's failed jobs (gh run rerun --failed); expect green. Then phase 8: STOP
for Mateo's end-review (do NOT merge; delete this state file in the final pre-merge commit + prove gone).

## Next
Wait on eden's runner-image fix; re-run #26 CI; hold at phase 8 for Mateo.