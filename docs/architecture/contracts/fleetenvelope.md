# Contract — fleetenvelope

> Status: **DRAFT for negotiation** · 2026-08-26 · The message spine of the Eden agent fleet.
> This is the 09 §4 step-1/2 artifact: one wire header reconciled from the producer and consumer
> obligations, with every unresolved tension recorded as an open fork (§11) rather than settled
> silently. **It is NOT frozen, and no agent may freeze it** — the freeze is Mateo's
> `.claude/rules/git-process.md` §5 gate ("a chart or contract PROMISE"), exercised only under
> §13 rule 4 with his verbatim words and a timestamp. §12 is the exact question.
>
> **This document has no library of its own, and that is deliberate.** The surface below lands
> **inside `libs/go/agentruntime`**, additively — measured delta **+12 printed `.apibaseline`
> lines (14 symbols), 0 removed, 0 reordered, 0 changed**. So freezing this draft produces a
> **contract revision `agentruntime` R2** (ADR-0016 §1) plus a small `agentsession` R2 for the
> serialization work of §8, and this text is retained here as the negotiation record. It is NOT
> a new `libs/go/fleetenvelope`: `agentruntime` already owns the fleet wire contract, and
> `libs/go/_ctl/lib.sh::_xlib_wire_literal_scan` actively enforces that ownership — its remedy
> line reads ✅ *"the wire contract lives once in the protocol owner."* Moving it would be the
> cardinal sin (10 §9) for no gain.
>
> **Authority to design this now.** `docs/plans/eden-rework-blueprint.md:1918` defers the fleet
> leg with the trigger *"Mateo schedules the fleet program"*, and states in the same cell:
> *"The architecture is already decided (agent-fleet rulings, 2026-08-18: role-pods, JetStream
> planes, frozen envelope, CRD controller); what is deferred is building it, not designing it."*
> The trigger fired on 2026-08-26, verbatim: *"we can kick off a lot of these things in parallel
> if we do api agreements up front."* This is the agreement.
>
> Epistemic legend (`docs/architecture/README.md` §3): ✅ verified · 🔶 hypothesis · ⚠️ corrected
> · 🧩 design choice. Every ✅ carries a `file:line`, a quoted ruling, or a stated measurement.

## 1. Scope

`fleetenvelope` is the **one home of the fleet wire header** — the fields every message on every
fleet plane carries, whatever its plane, direction or payload. It owns identity, causality, the
task chain, provenance, payload discipline and the refusal: a message whose header does not
validate never reaches a plane. 🔶

Six things, and no seventh:

1. **`MessageHeader`**, embedded by exactly four message types. ✅ Ruling R2 (2026-08-18):
   *"MessageHeader embedded ×4, no sixth 'envelope' (word taken by AES envelope encryption)."*
   The word is in fact taken **five** ways already — document frontmatter · `libs/go/envelope`
   (AES-256-GCM envelope *encryption*, ADR-0029) · `agentruntime.EventEnvelope` · the Evidence
   verification envelope · `edenhttp`'s HTTP response envelope — and HNS-1 (10 §5) bans an
   ambiguous name. The embedding is **anonymous**, so Go's `encoding/json` inlines the header's
   fields at the JSON top level and **no existing key moves**. "The library refuses a
   non-envelope message" is thereby a **compile-time** property, not a runtime check.
2. **Identity** — `AgentID`, `SessionID`, `MessageID`, and the grammar of each (§3).
3. **Causality** — `CausedBy`, `InReplyTo`, `RootID`, `Hop` (§4). `RootID` is the task chain and
   therefore the trace key (§5).
4. **`Intent`** — the ten-member write-plane vocabulary the semantic relay reads (§6).
5. **Payload discipline** — `MaxInlineBytes`, `MaxRelayBodyBytes`, `ArtifactRef`, `ArtifactStore`:
   spill, never truncate (§7).
6. **The serialization contract and its once-only freeze window** (§8).

It explicitly does **not** own (the consumer must not expect these here):

- **Subjects, streams, consumers, acknowledgement, dedup, backpressure** — `fleetbus.md`.
  This document never renders a subject and never names a stream policy.
- **The CRD, the pod, the role, parentage, the legal child set** — `agentfleet.md`. The header
  carries the `AgentID` the controller minted; it does not describe the pod, and **it does not
  carry the tree** (§4.2 is the whole argument).
- **Checkpoint composition, segment format, retention** — `agentcheckpoint.md`.
- **The harness Event taxonomy** — `agentsession.Event` is FROZEN
  (`contracts/agentsession.md`) and is transported **verbatim**, exactly as `agentruntime` does
  today ✅ (`libs/go/agentruntime/protocol.go:57`: *"the FROZEN agentsession taxonomy …
  agentruntime transports it, never redefines it (one concept, one home)"*).
- **Encryption, signing, secret material.** No field of any type below may hold a secret value.
  A credential reaches a harness through the `agentsession` credential seam, never a message.
- **Emitting telemetry.** Mateo's 2026-08-26 ruling puts the telemetry tap at a **bus consumer**,
  not in-process (§5.3). This library's obligation is to be *self-sufficient for telemetry* and
  to emit nothing itself.

It cites, never redefines: `agentsession.Event` / `State` / `Spec` / `Cursor` / `PeerMessage` /
`PeerPlane` (`contracts/agentsession.md`), `errors.Kind` / `errors.AsType` (`contracts/errors.md`),
`objectstorage.ObjectStore` (`contracts/objectstorage.md` — reached only through the one-method
shim of §7.3), and `orchestrator.Status` / `Tenancy` (`contracts/orchestrator.md`).

## 2. Contract

Package `agentruntime`. Every symbol below is **additive**; nothing existing is renamed, removed
or renumbered.

```go
// MessageHeader is the spine every fleet message embeds ANONYMOUSLY, so its fields inline at the
// JSON top level and no existing key moves. It carries NO secret and NO payload, and is therefore
// loggable in full — which is what makes the bus-consumer telemetry tap (§5.3) possible at all.
type MessageHeader struct {
	MessageID  MessageID   `json:"messageId"`            // globally unique, DETERMINISTIC; also the JetStream MsgId
	CausedBy   MessageID   `json:"causedBy,omitempty"`   // the message that DIRECTLY caused this — ONE hop up
	InReplyTo  MessageID   `json:"inReplyTo,omitempty"`  // pairs a response with its request; may be many hops from CausedBy
	RootID     MessageID   `json:"rootId"`               // the root of the whole chain; CONSTANT along it
	Hop        uint8       `json:"hop"`                  // relay depth from the root; ceiling MaxRelayHops
	Intent     Intent      `json:"intent"`
	Actor      Actor       `json:"actor"`                // who ULTIMATELY authored this
	EmitTime   time.Time   `json:"emitTime"`             // the injected Clock instant at publish
	Deadline   time.Time   `json:"deadline,omitempty"`   // WRITE plane only; zero == no deadline
	OTel       OTelContext `json:"otel,omitempty"`       // the W3C carrier; empty == un-traced (valid, unparented)
}

// MessageID is the causal join key AND the JetStream dedup key. Three deterministic forms:
//
//	observation : "<agentID>/<sessionID>/<seq>"   fully determined; a republish de-duplicates
//	relay       : "<agentID>/<ulid>"              minted once, retried VERBATIM
//	lifecycle   : "<agentID>/<kind>/<ulid>"
//
// Determinism is load-bearing twice: it makes two agents publishing Seq=1 inside the dedup window
// impossible to collide (today's silent loss), and it makes a REPUBLISH after a pod restart
// de-duplicate instead of duplicating.
type MessageID string

// MaxRelayHops is the LOOP BREAKER, not a depth limit. Tree DEPTH is unbounded by contract; this
// bounds a MESSAGE'S TRAVEL. A message that reaches the ceiling is refused LOUDLY: the relay
// publishes IntentFailed back up and drops it. Silence here would be an invisible routing cycle.
const MaxRelayHops uint8 = 32

// ActorKind is the closed taxonomy of who caused a message. Append-only (10 §9).
type ActorKind uint8

const (
	ActorHuman  ActorKind = iota // a person acting through the UI, AT THE ORCHESTRATOR
	ActorAgent                   // an agent's own conclusion
	ActorSystem                  // a platform actor (the retention pruner, the budget guard)
)

// Actor records WHO caused a message, so the header chain is an audit trail with no side lookup.
// ID holds a user id, an AgentID, "retention-pruner", or "break-glass:<user>" — NEVER a credential.
// The break-glass form is the whole audit mechanism for EDEN_GATEWAY_BREAK_GLASS=1 (default OFF).
type Actor struct {
	Kind ActorKind `json:"kind"`
	ID   string    `json:"id"`
}

// Intent is the write-plane vocabulary the semantic relay reads: what a message is FOR, and
// therefore which way it travels and whether this level must think about it. Closed taxonomy,
// append-only, EMITTED — so libs/go/_ctl/lib.sh's CAPABILITY-WIRED detector requires every
// non-zero member to reach a live emit position in this library. No member carries //eden:reserved.
type Intent uint8

const (
	IntentObservation      Intent = iota // up    · the pump, EVERY agentsession Event
	IntentAssign                         // down  · scoped work across a tree edge
	IntentReport                         // up    · a concluded result for a prior Assign
	IntentSteerAtSafePoint               // down  · HELD to the next turn boundary, then folded in
	IntentSteerPreemptive                // down  · interrupts the in-flight turn; effective now
	IntentQuestion                       // up    · a decision this level may not make
	IntentAnswer                         // down  · the decision; InReplyTo == the question
	IntentBudgetExhausted                // up    · the library hard-stopped; the PARENT decides
	IntentFailed                         // up    · cannot proceed (a fault, not a request)
	IntentLifecycle                      // audit · phase transitions + every pruner action
)

// Direction reports which way an Intent travels. It is real routing behaviour, not a lookup
// table: the relay refuses an up-intent addressed downward and vice versa.
func (i Intent) Direction() RelayDirection

// RelayDirection is the axis a message travels on a tree edge.
type RelayDirection uint8

const (
	DirectionUp    RelayDirection = iota // toward the parent
	DirectionDown                        // toward a member of the legal child set
	DirectionAudit                       // neither; a record, addressed to the archive
)

// RelayMessage is the durable WRITE plane's message: the semantic relay's unit. It is PROCESSED
// at every level — each level concludes, re-scopes, and routes down the affected branches. It is
// NEVER forwarded blindly and NEVER sent sideways.
type RelayMessage struct {
	MessageHeader `json:",inline"`

	From      AgentID       `json:"from"`
	To        AgentID       `json:"to"`                  // MUST be a tree NEIGHBOUR of From (§4.2)
	TeamID    string        `json:"teamId"`
	SessionID string        `json:"sessionId,omitempty"` // "" == the agent's primary session
	Scope     string        `json:"scope"`               // this level's re-scoping: which branch of its own context applies
	Subject   string        `json:"subject"`             // a one-line human summary; never a secret
	Body      string        `json:"body,omitempty"`      // <= MaxRelayBodyBytes
	Artifacts []ArtifactRef `json:"artifacts,omitempty"`
}

// EventEnvelope is the READ plane's message: one sequenced, verbatim agentsession.Event under the
// fleet header. Seq keeps its exact present meaning — the PER-SESSION transcript offset. It is NOT
// the replay cursor; the replay cursor is the JetStream stream sequence (fleetbus.md §6).
type EventEnvelope struct {
	MessageHeader `json:",inline"`

	AgentID   AgentID            `json:"agentId"` // the TRANSPORTING agent
	Seq       uint64             `json:"seq"`
	Event     agentsession.Event `json:"event"`
	Artifacts []ArtifactRef      `json:"artifacts,omitempty"`
}

// ControlMessage is the LIFECYCLE plane's message (core NATS): controller stop/kill and
// break-glass ONLY. ADR-0022 §4 is preserved, not silently re-classed. It holds no secret value.
type ControlMessage struct {
	MessageHeader `json:",inline"`

	AgentID   AgentID     `json:"agentId"`
	SessionID string      `json:"sessionId,omitempty"`
	Verb      ControlVerb `json:"verb"`
	Text      string      `json:"text,omitempty"`
}

// Heartbeat is the HEALTH subject's message (core NATS, LOSSY BY CONTRACT — liveness only; every
// DECISION reads the durable events stream). SessionState becomes the AGGREGATE (the
// least-advanced non-terminal session state) and is RETAINED rather than removed: a wire deletion
// is invisible to .apibaseline, so removing it would be a break no gate can see.
type Heartbeat struct {
	MessageHeader `json:",inline"`

	AgentID      AgentID            `json:"agentId"`
	Phase        HealthPhase        `json:"phase"`
	SessionState agentsession.State `json:"sessionState"` // DEPRECATED in the contract; the aggregate
	Sessions     []SessionHealth    `json:"sessions"`
	LastSeq      uint64             `json:"lastSeq"`      // the HIGHEST Seq across sessions
	At           time.Time          `json:"at"`
}

// SessionHealth is one session's liveness row. It is what makes 1..N sessions per pod observable
// without a second subject: the roster is a field, never a stream.
type SessionHealth struct {
	SessionID          string             `json:"sessionId"`
	HarnessResumeID    string             `json:"harnessResumeId"`
	State              agentsession.State `json:"state"`
	Turn               int                `json:"turn"`
	LastSeq            uint64             `json:"lastSeq"`
	LastCheckpointTurn int                `json:"lastCheckpointTurn"`
}

// MaxInlineBytes is the spill threshold: 256 KiB, four times under the nats-server default
// max_payload of 1 MiB. MaxRelayBodyBytes bounds a relay body at 8 KiB. Neither is a truncation
// point — over either bound the payload SPILLS to an artifact, or the publish fails loudly.
const (
	MaxInlineBytes    = 256 << 10
	MaxRelayBodyBytes = 8 << 10
)

// ArtifactRef addresses a spilled payload WITHOUT this library naming a store. Reference is the
// objectstorage canonical "<bucket>/<key>" form; Digest is the integrity witness the READER
// verifies. Content-addressed, so an identical re-spill is one object and a retry is a no-op PUT.
type ArtifactRef struct {
	Field       string `json:"field"`       // the path lifted, e.g. "event.tool.result"
	Reference   string `json:"reference"`   // "<bucket>/<key>"
	Bytes       int64  `json:"bytes"`
	ContentType string `json:"contentType"`
	Digest      string `json:"digest"`      // "sha256:<hex>"
}

// ArtifactStore is the consumer-defined spill port: ONE method, so agentruntime gains no vendor
// dependency and no new frozen-port edge. objectstorage.ObjectStore satisfies it through a shim
// bound at the composition root (§7.3).
type ArtifactStore interface {
	PutArtifact(ctx context.Context, key string, body []byte, contentType string) (reference string, err error)
}
```

`AgentID`, `OTelContext`, `ControlVerb` (and its five values), `HealthPhase` (and its four values),
`EventsSubject` / `ControlSubject` / `HealthSubject` and `EventsStreamName` **already exist and are
unchanged** ✅ (`libs/go/agentruntime/protocol.go`, `libs/go/agentruntime/.apibaseline` at libs
`8683fea`). This document adds to that file; it does not rewrite it.

## 3. Identity — three ids, one authority each

| | Value | Minted by | Lives as |
| --- | --- | --- | --- |
| `AgentID` | `agent-<lowercase ulid>`, 32 chars | **the controller**, into `status.agentID`, before any pod exists | the NATS subject token · the pod name · the object-store prefix · the ConfigMap name · the OTel `agent.id` |
| `SessionID` | `session-<harness>[-role][-phase]-<hex8>` | **the library** ✅ (`agentsession/identifiers.go:33-43`) | a **FIELD** on the message. **Never a subject token.** 1..N per agent |
| `HarnessResumeID` | harness-native opaque | **the harness** | `SessionHealth.HarnessResumeID`; what `--resume` is given |

✅ Canon ruling C4 (2026-08-18): *"controller-minted durable AgentID is THE authority (names pod,
MinIO prefix, NATS subjects; survives restarts); harness SessionIDs are session-scoped fields IN
the envelope, 1..N per agent; the in-memory agent-`<n>` counter dies."*

`agent-<ulid>` is legal **at once** as a DNS-1123 label, a NATS subject token and an object-store
key prefix — which is why one value serves five roles instead of five values needing a mapping
table. The `metadata.uid` witness that makes it durable across a GitOps re-apply belongs to
`agentfleet.md`; it is cited here because this header's uniqueness depends on it.

⚠️ **Two things are DELETED by this contract, and both are corrections rather than features:** the
`agent-<n>` in-memory counter (`manager.go:262-265`), and the **false doc comments** at
`orchestrator/types.go:251` and `gateway/registry.go:11-21` that assert an id equality **no code
enforces**. A comment that states an invariant nothing checks is the documentation form of a gate
that cannot fail.

## 4. Causality, and the tree that is deliberately not on the wire

### 4.1 The four causal fields, and why they are four

| Field | Answers | Shape |
| --- | --- | --- |
| `CausedBy` | what *directly* caused this | ONE hop up. The **edge**. |
| `InReplyTo` | which request this answers | may be many hops from `CausedBy` — which is exactly why it is a third field and not a reuse of the second |
| `RootID` | which whole chain this belongs to | **CONSTANT along the chain**, so audit is ONE query `rootId == X` instead of an O(depth) walk |
| `Hop` | how far this has travelled | the loop breaker |

`InReplyTo` also carries the permission `requestID` for `IntentAnswer`, which is how a permission
raised in one pod is resolved by a human in another without a new verb.

**There is no turn ordinal on the header, and that is deliberate.** Turn is a property of a
session, not of a message: it lives on `agentsession.Event.Turn` / `Event.TurnID`, on
`SessionHealth.Turn`, on `Agent.status.sessions[].turn`, on the checkpoint manifest, and as the
OTel attributes `turn.id` / `turn`. Putting it on the header would be a sixth home.

✅ For scale: a repo-wide grep for `CorrelationID|CausationID|MessageID|causal|traceparent` over
`libs/go` returns **no production hit outside `otelobserver`**. Today's tree has no causal
vocabulary at all.

### 4.2 ⚠️ There is NO tree address, and this reverses my own first draft

An earlier revision of this document proposed a `TreeAddress` — a slash-joined path of node names
— as the routing address. **The canonical design refuses exactly that**, and the refusal has three
independent reasons, each of which alone is sufficient:

1. **A subject is immutable once a message is stored; an agent is re-parentable.** Topology in an
   address is a lie the moment the tree changes.
2. A `team.<t>.agent.<a>.events` family would need a **second stream and would fork replay** — the
   cursor of `fleetbus.md` §6 would stop being single-valued.
3. ✅ The `eden-otel-debug` skill (`SKILL.md:114`) **explicitly forbids a flat tree-path
   attribute** and states that parentage is the W3C traceparent on the envelope. Adding a path
   attribute would require changing `contracts/agentruntime.md` first.

So a node is addressed **only by its `AgentID`**, and the tree lives in four other places:

| Concern | Home |
| --- | --- |
| parentage, durable and re-parentable | `Agent.spec.parentRef` — `""` == root (parent == the orchestrator) |
| parentage, per message | `CausedBy` / `RootID` + the W3C traceparent |
| **the legal child set** | derived **by the controller** from `spec.parentRef` across the namespace and rendered into the pod's ConfigMap (`/etc/eden/agent.json`). **A relay publish to a non-child is a LOUD typed error at the port, never a silent drop.** |
| observed depth | `AgentTeam.status.depth` — for the UI. **Never a wire field.** |

`RelayMessage.To` must therefore be **a tree neighbour of `From`** — the parent, or a member of
that rendered legal child set. That is the "no sideways bypass" rule made executable at the port
rather than asserted in prose.

**🧩 A frozen contract says something adjacent, and the reconciliation is a fork.**
`contracts/agentsession.md` freezes `PeerPlane`, whose `Roster` documentation reads ✅
(`libs/go/agentsession/peer.go`): *"Reachability defaults to a full MESH over TREE routing: the
tree is registry, authorization and audit, not a partition."* The fleet ruling forbids sideways
sends. The reconciling word is **defaults**: `PeerPlane` is a two-binding port (unix-socket now,
natsbus in the fleet slice), and the fleet binding **restricts reachability to tree edges**,
returns only the parent and the legal child set from `Roster`, and answers a non-adjacent `Send`
with the port's own `agentsession.UnreachableError` — which the frozen contract already defines as
its loudness guarantee. A restricted plane is a conformant plane. **This reading is open fork F1**;
if it is rejected, `agentsession` takes a contract revision instead.

## 5. The task chain is the trace — Mateo's ruling of 2026-08-26

> **Mateo, 2026-08-26** (AskUserQuestion decision prompt, interactive session `f9c810a8`),
> verbatim: *"Task=trace across the whole tree — One trace spans the entire orchestrator task
> through every delegated session."*

### 5.1 `RootID` IS the task id

The ruling asks for "a task id … so every session in the relay tree joins the task's single
trace". `RootID` already is that value, by construction and by definition: it is *"the root of the
whole chain — the human action, the schedule, or the orchestrator's assignment"*, it is
**constant along the chain**, and the design already maps it to the OTel semconv attribute
`messaging.message.conversation_id`. Every message of every delegated session in one orchestrator
task carries the same `RootID`.

**Naming a second `TaskID` field would be a second home for one fact** (10 §9), so this contract
does not add one. What it does add is the *statement* that `RootID` is the product's task key —
because a field whose product meaning is undocumented gets a duplicate invented beside it. If
Mateo intends a task that spans **several** root chains, that is a genuinely different field and
open fork F2 carries it.

### 5.2 ⚠️ "First-class traceparent fields" collides with the locked carrier — and the locked
carrier should win

The ruling says the envelope carries "a W3C traceparent (+ tracestate)" as **first-class fields**.
The locked design carries them inside `OTel OTelContext`, a `map[string]string`. I drafted typed
`TraceParent` / `TraceState` fields first, and then found the measured reason not to ✅:
`OTelContext` is `map[string]string` and OTel's `propagation.MapCarrier` is `map[string]string`,
**so a real propagator drops in as a TYPE CONVERSION with no contract change at all.** *"The
envelope was always shaped for this; only the adapter was missing."* Two typed fields would break
that property, and would fork W3C propagation into two homes the day `baggage` is wanted.

**Recommendation (open fork F3): keep the map.** The ruling's substance — one trace across the
whole tree, propagated by the envelope — is fully delivered by `RootID` + `OTel`, and the "first
class" half is delivered where it is load-bearing: `RootID` is a required, typed, indexed field.
This is flagged rather than obeyed silently because it is a direct instruction and Mateo may mean
the literal shape.

### 5.3 The long-trace mitigation, recorded so it is not rediscovered

A fleet task can run for hours, and every trace backend bounds a trace's span count and its
ingestion window. The mitigation is the design already chosen, stated explicitly:

- **Sessions are spans inside the task's trace, not separate traces.** Each session opens its own
  root span **joined by the propagated context**, so the task reads as one trace while no single
  span is held open for the task's life.
- **Cross-pod is a LINK, not a parent.** ✅ The OTel messaging semantic conventions name links the
  default correlation mechanism and state it is NOT RECOMMENDED to parent a process span on the
  message-creation context when processing happens inside another span. Links are attached **at
  span creation (`WithLinks`), never `AddLink`, because head sampling cannot see a link added
  later.**
- **`RootID` is an indexed attribute**, so the UI's "show me this task" query never depends on the
  whole trace being retrievable as one object. If a backend drops the tail of a long trace, the
  task view degrades to a `RootID` search over spans. This is precisely why `RootID` is not
  derived from the trace id.

### 5.4 Telemetry is a bus consumer, and that is why this header is fat

> **Mateo, 2026-08-26**, verbatim selection: *"Bus consumer"* — one telemetry service consumes
> JetStream → OTel, and the same consumer feeds UI streaming.

This is consistent with the locked 2026-08-18 ruling (*"OTel: from day one — exporter as a log
consumer"*), and it is the reason the header carries `Actor`, `RootID`, `InReplyTo` and `Intent`
rather than leaving them to a join. **A consumer outside the emitting process has no side
lookups.** Every attribute a span needs is in the header, or the span cannot be built. On this
wire, a field that "could be looked up" is a field that cannot.

The obligation this places on the bus — the telemetry consumer gets **its own durable consumer**
and never joins a delivery consumer's queue group — is stated in `fleetbus.md`, its home.

⚠️ **What is false today, and the break-test that proves it.** `otelobserver.Inject` only copies a
map previously stashed under a private context key; **nothing ever writes that key and nothing
generates a traceparent**, so `EventEnvelope.OTel` is `{}` in production — while
`agentruntimetest.FakeObserver` injects a canned traceparent, **so the suite passes throughout**.
And `libs/go/observability` has exactly one adapter, `slogadapter`, so no span can leave any
process. A green `otelobserver` test is currently evidence of nothing. **The break-test is exactly
this: assert a real traceparent on a published envelope and watch it fail today.**

## 6. `Intent` — ten members, and why not nine or eleven

The set was **enumerated from proof obligations, not designed**. `libs/go/_ctl/lib.sh`'s
CAPABILITY-WIRED detector fails any non-zero member of a closed, emitted taxonomy that never
reaches a live emit position, and the detector runs **per library** — so every member needs a
producer *in libs*, not only in an eden app. That constraint is what keeps the vocabulary honest.

| Member | Token | Direction | Producer |
| --- | --- | --- | --- |
| `IntentObservation` | `observation` | up | the pod's pump, for EVERY `agentsession.Event` |
| `IntentAssign` | `assign` | down | the relay path, when a level routes work down |
| `IntentReport` | `report` | up | the sidecar, on a concluded Assign |
| `IntentSteerAtSafePoint` | `steer-at-safe-point` | down | the relay path |
| `IntentSteerPreemptive` | `steer-preemptive` | down | the relay path |
| `IntentQuestion` | `question` | up | the sidecar |
| `IntentAnswer` | `answer` | down | the relay path |
| `IntentBudgetExhausted` | `budget-exhausted` | up | the sidecar |
| `IntentFailed` | `failed` | up | the sidecar |
| `IntentLifecycle` | `lifecycle` | audit | the phase emitter and every pruner action |

**`IntentQuery` is deliberately absent**: a query is an Assign whose expected output is an answer,
and a never-emitted member fails the gate. That is the rule the whole table obeys.

**The two steering strengths, mechanically** — ✅ Mateo's ruling (Batch B+C, 2026-08-18) named two
strengths and refused the names *suggestion*/*order*:

- `IntentSteerAtSafePoint` — the sidecar **HOLDS** it until `LegalControls` admits
  `CommandPrompt` (the turn boundary), then folds it into ongoing work. **The hold queue runs on a
  DEDICATED deliver goroutine, NEVER the pump goroutine** — a pump blocked in a stdin write
  deadlocks the child's stdout pipe permanently.
- `IntentSteerPreemptive` — maps to `CommandSteer` in `StateRunning`. On a harness with
  `CapSteer=Partial` it **degrades to Abort-then-Prompt, and the degrade is DECLARED, never
  silent.**
- `AgentTeam.spec.policy.steerDefault` decides which strength a bare human steer becomes.

**`ControlVerb` stays frozen at five** ✅ (`protocol.go:70-77`): `VerbPrompt`, `VerbSteer`,
`VerbAbort`, `VerbStop`, `VerbKill`. No sixth verb — no `VerbResolvePermission`, no
`VerbSteerInterrupt`. An `IntentAnswer` dispatches to `agentsession.Session.Resolve`, which the
frozen contract already defines as *a separate method gated on a pending RequestID, NOT a
`CommandKind`, and intentionally excluded from `LegalControls`* — so the dispatch is legal by the
frozen contract's own words, in exactly the state (`StateAwaitingPermission → {Abort}`) where a
Steer is illegal.

⚠️ **This is open fork F4, and it is an explicit CONFIRM request.** Mateo's words were "two
VERBS, two strengths". This design honours the count as two **`Intent` members** while leaving
`ControlVerb` untouched. If he meant two `ControlVerb` members, the taxonomy is re-sliced.

## 7. Payload discipline — spill, never truncate

✅ Ruling R6 (2026-08-18): *"spill-never-truncate (MaxInlineBytes 256KiB, ArtifactRef to MinIO)."*

### 7.1 The mechanism, exactly

The pump marshals and measures. Under `MaxInlineBytes` → publish. Over it → lift the largest
offending field **in the order `event.tool.result` → `event.extension` → `event.message.text`**,
store it, replace the field with an **`[eden:artifact:<digest>]`** marker, append the
`ArtifactRef`, re-marshal. If **still** over: emit `EventFailed{ReasonTransport}` naming the field
and the size, and **raise a session fault**. It does not log-and-continue — which is what
`runtime.go:196-198` does today.

`Artifacts` is read by the read plane's history resolver on day one, so it satisfies the
CONFIG-DEAD-STATE detector without an `//eden:reserved` opt-out. **The reader VERIFIES `Digest`.**

### 7.2 What was refused, and why

- **Truncation-with-marker** — the chain IS the audit trail, and `agentsession.Event.Extension` is
  contractually *"preserved VERBATIM, NEVER dropped"*. `agentsession` already holds this line at
  its own smaller bound ✅ (`peer.go:11-13`: *"A longer body is a LOUD typed error at Send — never
  a silent truncation, so the transcript stays verbatim within the bound and MsgID correlation is
  never broken by a digest."*).
- **Raising `max_payload`** — ✅ past 8 MiB the nats-server warns and reserves the right to
  reject: a latent upgrade break bought in exchange for nothing.

Three bounds coexist and must not be conflated: `agentsession.MaxPeerBodyBytes` (8 KiB, an
inter-session peer message inside one harness process) · `MaxRelayBodyBytes` (8 KiB, a fleet relay
body) · `MaxInlineBytes` (256 KiB, a whole marshalled message). Different wires, different bounds,
all loud.

### 7.3 ⚠️ `ArtifactRef` names a shape, not a store

The ruling's wording is "ArtifactRef to MinIO". This contract says *field, reference, size,
content type, digest* and stops there, because **MinIO's upstream is archived and the successor is
an open decision** ✅ (Batch A, 2026-08-18: *"MinIO proceed v1 behind the frozen objectstorage port
+ successor decision opened separately"*). A contract that names a vendor as a guarantee must be
revised when the vendor changes; one that names a shape need not be.

The seam that keeps it true: `ArtifactStore` is **one method**, and
`objectstorage.ObjectStore` satisfies it **through a shim bound at the composition root**. So
`agentruntime` stays SDK-free, gains no vendor dependency, and gains **no new frozen-port edge**.
`agentcheckpoint.md` owns the key grammar and the store binding.

⚠️ **One key-grammar contradiction is inherited and unresolved**: the design places spilled
artifacts at `agents/<agentID>/artifacts/sha256-<hex>` in one section and under
`.../sessions/<sessionID>/artifacts/` in another. The agent-level form is the one that lets
content-addressing dedup **across** sessions. It is open fork F5 and it is settled in
`agentcheckpoint.md`, not here.

## 8. Serialization — and the window that is open exactly once

✅ Ruling R1 (2026-08-18): *"json tags + marshallers BEFORE any byte is stored (once-only window:
0 streams, 0 messages, no bucket)."*

**The window is measured open.** ✅ `grep -c 'json:"' go/agentsession/types.go` at libs `8683fea`
returns **0**, and `EventKind`'s only method is `String()`. So the nested `event` object serialises
**today** with Go field names (`SessionID`, `TurnID`, `Kind`) and `Kind` as an **integer** — which
is the root cause of the SSE shape defect, and is what a header frozen over this payload would
freeze forever. ✅ The live probe found JetStream at **0 streams / 0 messages after 41 days** and no
eden bucket: *"THERE IS NOT ONE STORED BYTE TO MIGRATE. The moment the first durable envelope
lands, this stops being an edit and becomes a migration."*

**The fix is its own slice, and it comes FIRST**: json tags on `agentsession.Event` and every
payload struct, plus `MarshalText`/`UnmarshalText` on `EventKind`, `State`, `Capability` and
`Outcome`. **Both changes are `.apibaseline`-INVISIBLE**, so both are recorded **by hand** in
contract revision `agentsession` R2 and guarded by a new gate dimension (below). An invisible
change to a frozen surface is exactly the class of thing a mechanical gate cannot catch, which is
why the human record has to carry it.

**Schema home** — `libs/protocols/agentfleet/v1/`, which today holds only `.gitkeep` ✅:

```
libs/protocols/agentfleet/v1/
  message-header.schema.json      event-envelope.schema.json
  relay-message.schema.json       control-message.schema.json
  heartbeat.schema.json           checkpoint-manifest.schema.json
  agentsession-event.schema.json  *.d.ts   (the generated TypeScript mirror)

DRAFT   JSON Schema 2020-12 (matching schemas/document/v1)
$id     eden://protocol/agentfleet/v1/<name>
SOURCE  GENERATED from the Go types by `bash ./ctl.sh schema-record`
GATE    a NEW `schema` dimension in phase-gate architecture regenerates and diffs; any
        difference FAILS
```

**Go structs are the single AUTHORING home; `libs/protocols/agentfleet/v1` is the published
ARTIFACT home.** 🧩 **Protobuf/buf is explicitly REJECTED for the bus** — it would replace a frozen
hand-written type with generated code (a cardinal-sin baseline break) for zero gain, since the bus
is JSON over NATS and the frontend parses JSON. Protobuf/buf stays scoped to the Connect
request/response surface, and doc 02 §5 is amended to say so.

**Forward compatibility — two planes, two policies, both explicit:**

| Plane | Policy | Reason |
| --- | --- | --- |
| RELAY (write) | `additionalProperties: false` | *"an unknown field is a REJECT — a command you do not understand must not be half-executed"* |
| EVENT (read) | `Event.Extension` is the verbatim, never-dropped escape hatch | nothing a harness emits is lost |

**Validation runs at the TRUST BOUNDARY, not in every pod** — the relay ingress and the archive
reader. ⚠️ The reason is uncomfortable and belongs in the open: *"The bus has NO auth, NO TLS and
NO accounts today — any pod that reaches the Service can publish any subject and claim any
identity in the header."* Bus authn/authz is open fork F6 with a trigger.

**There is no `SchemaVersion` field on the wire**, and that is a decision rather than an omission:
the version lives in the schema `$id` and the `v1` path segment, and a v2 would be a new subject
and a new stream — the same way the estate versions everything else. Open fork F7 carries the
counter-argument.

### 8.1 The `.apibaseline` delta, and the re-record order

| Library | Delta |
| --- | --- |
| `agentruntime` | **+12 printed lines (14 symbols)** |
| `agentsession` | **+0** (json tags and `MarshalText` are invisible) |
| `orchestrator` | +1 (`const EnvAgentID`) |
| `agentcheckpoint` | NEW baseline |
| `edenhttp` | +1 (`ParseTransportCursor`) |
| `objectstorage` | +0 |

**TOTAL ≈ 19 ADDED · 0 REMOVED · 0 REORDERED · 0 CHANGED**, so `cmd_apidiff` prints *"exported
surface GREW (additive only) — non-breaking"* and exits 0. The order, which is not negotiable:

1. contract revisions and ADRs written and reviewed **first**;
2. `apidiff-record` lands in the **same** pull request as the code;
3. `phase-gate all` green **before** the pull request opens;
4. **BREAK-TEST apidiff once per new type** — delete `type RelayMessage`, confirm the cardinal-sin
   message, restore;
5. **BREAK-TEST the schema gate** — hand-edit a generated schema, confirm the drift gate fails,
   restore.

**Step 5 gets the harder proof, because it guards exactly what step 4 is blind to.**

## 9. ⚠️ An undeclared wire deletion this contract must not commit

Today's `ControlMessage` is `{AgentID, Verb, Text, By, OTel}` ✅, where `By` is documented as *"the
audit identity"*. The new shape in §2 **drops `By`** — `Actor` supersedes it — so the `by` JSON key
disappears from the wire.

`.apibaseline` collapses struct bodies (`type ControlMessage struct{ ... }`), so **apidiff cannot
see this**, and no gate in the estate can. That is the identical failure class the design
explicitly refuses for `Heartbeat.SessionState`, which is RETAINED for exactly this reason. The
deletion is therefore **declared here, in the human record**, and it is open fork F8: either
`By` is retained-and-deprecated like `SessionState`, or its removal is written into the
`agentruntime` R2 revision as a named wire break. It may not simply vanish.

## 10. Fake and conformance

`agentruntimetest` already exists and gains the fleet bindings:

- `agentruntimetest.FixedClock` (present ✅) and a `SequenceMinter` yielding readable relay ULIDs,
  so a causal chain is inspectable by eye and a golden file is stable.
- `agentruntimetest.SeededCanary` (present ✅) — the secret-leak needle the `secretscan` dimension
  asserts is absent from every surfaced artifact.
- `agentruntimetest.TraceParent` (present ✅) — and it is now the thing §5.4's break-test proves
  the production path does **not** produce.

`agentruntimetest.RunHeaderSuite(t, newFactory)` is the exported conformance suite. The properties,
each of which must be seen RED before it is green:

1. every minted header validates; a zero header does not;
2. all four message types round-trip byte-stably through `Encode`/`Decode`, and the header's
   fields appear **at the JSON top level** (the anonymous-embedding property — a named embed
   would silently nest them and break every existing key);
3. `MessageID` is deterministic in its observation form: the same `(agent, session, seq)` yields
   the same id, so a republish de-duplicates;
4. a relay preserves `RootID` and the `OTel` carrier while changing `MessageID`, `CausedBy` and
   `Hop` — the one property that makes a task one trace;
5. `To` outside `{parent} ∪ legalChildren` is a typed error — the no-sideways-bypass property;
6. `Hop` reaching `MaxRelayHops` produces `IntentFailed` back up and drops the message, and the
   error names the chain;
7. a body over `MaxRelayBodyBytes`, and a message over `MaxInlineBytes`, spill — and **no
   truncated message is ever produced**, asserted by refuting the negative;
8. every `Intent` member has a token, a `Direction`, and a totality test; an unknown member is a
   refusal, never a default (`Intent(0)` is `IntentObservation`, so a default-on-unknown would
   silently turn an unrecognised steering verb into an observation);
9. no surfaced error, no encoded message and no `String()` contains `SeededCanary`;
10. `Decode` of arbitrary bytes never panics — a `rapid` property over a fuzz corpus.

The fake weakens the SOURCE of ids and time, never the contract.

## 11. Open forks

Each is also recorded in `docs/architecture/open-decisions.md`, per `CLAUDE.md`'s rule that an
unmade decision lives there and never in prose alone.

| # | Fork | Options (recommendation first) | Blocks |
| --- | --- | --- | --- |
| F1 | **`PeerPlane` mesh-vs-tree.** The frozen `agentsession` port documents mesh reachability as its DEFAULT; the fleet forbids sideways sends. | (a) a binding may restrict reachability; the fleet binding is tree-only and answers a non-adjacent `Send` with the port's own `UnreachableError` — no revision needed (§4.2) · (b) `PeerPlane` promises mesh to every binding → `agentsession` takes a contract revision | the relay lane |
| F2 | **Is `RootID` the task id, or is a task bigger than one root chain?** | (a) `RootID` IS the task key; no second field (§5.1) · (b) a task spans several root chains → a distinct `TaskID` is required | the telemetry lane |
| F3 | **`OTel` map vs typed `traceparent`/`tracestate` fields.** Mateo's 2026-08-26 wording says first-class fields; the locked carrier is a map that IS `propagation.MapCarrier`. | (a) keep the map — a real propagator drops in as a type conversion with no contract change (§5.2) · (b) typed fields, accepting the conversion layer and a second home for W3C keys | the OTel lane |
| F4 | **Two steering strengths as `Intent` members with `ControlVerb` frozen at five?** Mateo said "two VERBS". | (a) confirm the `Intent` reading (§6) · (b) two `ControlVerb` members → F2/F6 of the slice plan are re-sliced with a taxonomy revision | the steering lane |
| F5 | **The spilled-artifact prefix**: agent-level vs session-level. | (a) agent-level — content-addressing only dedups across sessions if the prefix is shared · (b) session-level | the checkpoint lane |
| F6 | **Bus authn/authz.** No auth, no TLS, no accounts today; any pod on the Service can claim any identity. | (a) validate at the trust boundary now, NATS accounts before any non-Mateo tenant · (b) accounts now | nothing yet; it gates multi-tenancy |
| F7 | **A wire `SchemaVersion` field?** | (a) no — the version is the schema `$id` and the `v1` path; a v2 is a new subject and stream · (b) a version field, accepting that every reader must branch on it | nothing |
| F8 | **`ControlMessage.By`.** Its removal is invisible to `.apibaseline` (§9). | (a) retain-and-deprecate, exactly as `Heartbeat.SessionState` is retained · (b) remove it, written into the `agentruntime` R2 revision as a named wire break | the control lane |

## 12. THE FREEZE QUESTION — for Mateo, and for nobody else

Freezing is a §5 human gate. An agent may not exercise it, and this document may not be edited to
claim frozen status by anything other than Mateo's own words quoted with a timestamp (§13 rule 4).
The question is exactly this:

> **Do you freeze the fleet message spine at the surface in §2 — `MessageHeader` embedded
> anonymously by exactly four message types; causality as `MessageID` / `CausedBy` / `InReplyTo` /
> `RootID` / `Hop` with NO tree address on the wire; `Intent` closed at ten members;
> `ControlVerb` unchanged at five; `RootID` as the product's task key; `MaxInlineBytes` 256 KiB
> and `MaxRelayBodyBytes` 8 KiB with spill-never-truncate; and `ArtifactRef` naming a shape rather
> than a store — landing it as contract revision `agentruntime` R2 plus `agentsession` R2?**
>
> **YES** → the surface is frozen, `.apibaseline` is re-recorded as the freeze witness under the
> five-step order of §8.1, the new `schema` gate dimension is added and break-tested, and the
> parallel lanes start against a fixed target.
>
> **NO, with changes** → name the forks in §11 you rule differently; the draft is amended and
> re-refuted before the question is asked again.
>
> **Four forks cannot be delegated, because each changes §2's surface: F1** (it may put the
> *frozen* `agentsession` contract into revision), **F3** (a direct instruction of yours that the
> measured evidence argues against — please rule it explicitly), **F4** (it is a confirm request
> on your own words), and **F8** (an invisible wire deletion no gate can catch). F2, F5, F6 and F7
> may be delegated.

**Three gates ride on the same answer, and none of them is an agent's.**

1. **ADR-0030.** The fleet ADR is reserved at 0030 ✅ (Batch B+C, 2026-08-18: *"Fleet ADR takes
   number 0030 (fills the hole; messaging keeps 0032)"*) and does not exist —
   `docs/architecture/adr/` runs 0029 → 0031. A new ADR is separately Mateo-gated, so no agent has
   written it, and this contract cites the 2026-08-18 rulings directly rather than citing an ADR
   that is not there. **It should land in the same decision as the freeze**, so the authority chain
   stops dangling. The ADR must supersede `04-process-model.md` §7's no-negotiation clause and mark
   the upstream multi-agent rejection historical; the rationale — *tree-edge-only + a frozen header
   + semantic relay is not the feared free-for-all: no sideways negotiation, a legal child set
   enforced at the port, a hop ceiling that breaks cycles loudly* — is itself awaiting your
   confirmation.
2. **The serialization slice must land BEFORE the freeze**, not after (§8). Freezing a header over
   an untagged payload is the exact defect ruling R1 exists to prevent, and the window closes at
   the first stored byte.
3. ⚠️ **One precondition outranks this entire document.** Nobody has ever executed a real `Spawn`
   against the deployed orchestrator: the `agentgateway` image comment says it *"spawns no harness
   in-process"*, while the orchestrator binary opens the session in-process at `reconcile.go:159`,
   in a distroless image with no `claude` binary. **If neither has ever run end to end, that is a
   bigger finding than this design**, and it must reach you before any implementation slice starts.
   `agentfleet.md` carries it as an executable check rather than a footnote.
