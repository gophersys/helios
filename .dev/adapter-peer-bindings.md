# adapter-peer-bindings

phase:    verify
repo:     gophersys/libs
branch:   feat/adapter-peer-bindings
worktree: ~/code/.worktrees/libs-adapter-peer-bindings
pr:       -
attempt:  0/2

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

## Next
Phase 4: adversarial verify (Opus), then PR-1c-ii.
