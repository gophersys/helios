# adapter-peer-bindings

phase:    fix
repo:     gophersys/libs
branch:   feat/adapter-peer-bindings
worktree: ~/code/.worktrees/libs-adapter-peer-bindings
pr:       -
attempt:  1/2

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

## Next
Test author: F1 crafted-body arm (bite vs pre-escape) + F2 double-delivery arm (bite vs
deleting the Detail clause) + F5 leak doc + the ONE gofumpt fix in peer_canary_test.go
(newSpecRecordingAdapter first arg on its own line — implementer's file is clean, this
is a test-file format the impl gate trips on). Then re-verify round 2 (Opus, bounded),
PR-1c-ii.
