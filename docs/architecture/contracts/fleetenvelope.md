# Contract — fleetenvelope

> Status: **DRAFT for negotiation** · 2026-08-26 · The message spine of the Eden agent fleet.
> This is the 09 §4 step-1/2 artifact: the producer-side and consumer-side obligations of ONE
> wire header, reconciled into one document, with the unresolved tensions recorded as open
> forks (§10) rather than settled silently. **It is NOT frozen, and no agent may freeze it** —
> the freeze is Mateo's `.claude/rules/git-process.md` §5 gate ("a chart or contract PROMISE"),
> exercised only under §13 rule 4 with his verbatim words and a timestamp. §11 is the exact
> question he must answer. Until he answers it, `bash ./ctl.sh phase-gate architecture` in
> `libs/go/fleetenvelope` is RED **by design** — `libs/go/_ctl/lib.sh::_gate_contract_frozen`
> requires a `Status: … Frozen` header, and a draft correctly fails it.
>
> **Authority to design this now.** `docs/plans/eden-rework-blueprint.md:1918` defers the fleet
> leg with the trigger *"Mateo schedules the fleet program"* and states in the same cell:
> *"The architecture is already decided (agent-fleet rulings, 2026-08-18: role-pods, JetStream
> planes, frozen envelope, CRD controller); what is deferred is building it, not designing it."*
> The trigger fired on 2026-08-26, verbatim: *"we can kick off a lot of these things in parallel
> if we do api agreements up front."* This document is the API agreement that unlocks the lanes.
>
> Epistemic legend (`docs/architecture/README.md` §3): ✅ verified · 🔶 hypothesis · ⚠️ corrected
> · 🧩 design choice. Every ✅ carries a `file:line` or a quoted ruling. A claim with neither is a
> proposal, not a fact.

## 1. Scope

`fleetenvelope` is the **one home of the fleet wire header**: the fields every message on every
fleet plane carries, whatever its plane, its direction or its payload. It owns identity, tree
routing address, causality, the task trace, the actor, payload discipline and the versioning
rule — and it owns the REFUSAL: a message that does not validate against this header never
reaches a plane. 🔶

It owns exactly six things:

1. **`MessageHeader`** — the embedded spine, and the reason the library exists. Ruling R2
   (2026-08-18): *"MessageHeader embedded ×4, no sixth 'envelope' (word taken by AES envelope
   encryption)."* The four embedders are §2's `EventEnvelope`, `ControlMessage`, `Heartbeat`
   and `RelayMessage`. There is no wrapper type named `Envelope`: `libs/go/envelope` already
   owns that word for DEK sealing under a KEK (root `CLAUDE.md`, ADR-0029), and two homes for
   one word is the cohesion failure this repository forbids.
2. **Identity** — `AgentID` (controller-minted, durable, restart-surviving) and `SessionID`
   (harness-scoped, 1..N per agent). Canon ruling C4 (2026-08-18): *"controller-minted durable
   AgentID is THE authority (names pod, MinIO prefix, NATS subjects; survives restarts); harness
   SessionIDs are session-scoped fields IN the envelope, 1..N per agent; the in-memory agent-<n>
   counter dies."*
3. **Routing** — `TreeAddress`, the parent edge, the hop counter and the hop ceiling. Routing is
   **semantic relay on tree edges**: *"A message is PROCESSED at every level (each level
   concludes, re-scopes, routes down affected branches); context lives at its level (worker=file,
   team=module, orchestrator=architecture). No sideways bypass."* (2026-08-18.)
4. **Causality and the task trace** — `Turn`, `Seq`, `CausedBy`, `TaskID`, `TraceParent`,
   `TraceState`. Mateo's ruling of 2026-08-26 (§4) makes TASK = TRACE across the whole tree.
5. **Payload discipline** — `MaxInlineBytes` and `ArtifactRef`: ruling R6, *"spill-never-truncate
   (MaxInlineBytes 256KiB, ArtifactRef to MinIO)"*. Restated store-agnostically in §6, because
   the store is an open decision and a contract may not name a vendor as a guarantee.
6. **Versioning and the freeze window** — ruling R1: *"json tags + marshallers BEFORE any byte is
   stored (once-only window: 0 streams, 0 messages, no bucket)."* §7 states what the window is
   and what closes it.

It explicitly does **not** own (the consumer must not expect these here):

- **Subjects, streams, consumers, acknowledgement, dedup, backpressure** — `fleetbus` owns the
  transport. This library never imports `nats.go`, never opens a connection, and never renders a
  subject. It hands `fleetbus` a validated value and takes one back.
- **Pod lifecycle, the CRD, the role, the profile** — `agentpod` owns those. The header carries
  the `AgentID` the controller minted; it does not describe the pod.
- **Checkpoint composition, segment format, retention** — `fleetcheckpoint` owns those. The
  header contributes exactly one field to the checkpoint's cursor (`Seq`), cited there, not
  redefined.
- **The harness Event taxonomy** — `agentsession.Event` is FROZEN (`contracts/agentsession.md`)
  and is transported verbatim, exactly as `agentruntime` does today
  (`libs/go/agentruntime/protocol.go:57` ✅ *"the FROZEN agentsession taxonomy … agentruntime
  transports it, never redefines it (one concept, one home)"*).
- **Encryption, signing, secret material.** No field of any type in §2 may hold a secret value.
  A credential reaches a harness through the `agentsession` credential seam
  (`contracts/agentsession.md` "Credential flow"), never through a message. `libs/go/envelope`
  is a different library about a different subject; the two never meet on this wire.
- **Emitting telemetry.** Mateo's ruling of 2026-08-26 puts the telemetry tap at a **bus
  consumer**, not in-process (§4.3). This library's obligation is therefore to be *self-sufficient
  for telemetry* — everything a span needs is IN the header — and to emit nothing itself. It does
  not import `observability`.

It cites, never redefines: `agentsession.Event` / `State` / `Spec` / `PeerMessage` / `PeerPlane` /
`Cursor` (`contracts/agentsession.md`), `errors.Kind` / `errors.AsType` (`contracts/errors.md`),
`objectstorage.ObjectRef` (`contracts/objectstorage.md`, cited by `fleetcheckpoint` and referenced
here only as the target type of an `ArtifactRef`), and `observability.Event` (`contracts/observability.md`,
the vocabulary the telemetry CONSUMER emits from a header — not from inside this library).

## 2. Contract

```go
// Package fleetenvelope is the one home of the Eden agent-fleet wire header: the fields every
// message on every fleet plane carries. Four message types embed MessageHeader — EventEnvelope,
// ControlMessage, Heartbeat, RelayMessage — and there is no fifth wrapper type: the word
// "envelope" belongs to libs/go/envelope (AES envelope encryption), so this library names the
// spine MessageHeader (ruling R2, 2026-08-18).
//
// The library REFUSES rather than repairs. A message whose header does not validate is a typed
// error at the boundary, never a best-effort delivery: the fleet's audit trail is the header
// chain, and a chain with one unvalidated link is not an audit trail.
//
// Module: github.com/gophersys/libs/go/fleetenvelope  (go 1.26)
//
// It does NOT own: subjects/streams/consumers (fleetbus), pod lifecycle (agentpod), checkpoint
// composition (fleetcheckpoint), the harness Event taxonomy (agentsession, transported verbatim),
// or any secret material. It imports errors and agentsession, and nothing else outside stdlib.
//
// Concurrency: New is PURE (no I/O, no clock read, no env read). A constructed *Factory is safe
// for concurrent use by many goroutines; every Mint call is independent and takes the injected
// Clock and Minter exactly once.
//
// Zero value: a zero MessageHeader is INVALID. Validate reports the first violated rule; it never
// returns a partially-accepted header.
package fleetenvelope

// SchemaVersion is the wire revision of MessageHeader. It is stamped on every message and it is
// the ONLY forward-compatibility mechanism on this wire (§7). v1 is the freeze candidate.
const SchemaVersion = 1

// MaxInlineBytes is the payload spill threshold: 256 KiB (ruling R6). A payload at or under it
// travels inline; a payload over it is stored by the producer and travels as an ArtifactRef.
// A payload is NEVER truncated and NEVER digested away — spill, never truncate.
const MaxInlineBytes = 256 << 10

// MaxHops is the relay hop ceiling. A message whose Hop reaches it is REFUSED loudly at the
// port with a HopCeilingError naming the address chain. The tree's DEPTH is unbounded by
// contract (2026-08-18 default: "unbounded tree depth in the contract"); the ceiling bounds a
// message's TRAVEL, which is what breaks a routing cycle. The two are different limits and
// conflating them is how an unbounded tree becomes an unbounded loop.
const MaxHops = 32

// AgentID is the controller-minted, durable fleet identity: agent-<ulid>. It names the pod, the
// object-store prefix and the NATS subject token, and it SURVIVES a restart (canon ruling C4).
// It is minted by the agentpod controller, never by an agent and never by this library.
type AgentID string

// SessionID is a harness session identity, scoped to one AgentID. One agent hosts 1..N sessions
// over its life; the id is a FIELD of the message, never part of the routing address (C4).
type SessionID string

// TaskID names one orchestrator task. Mateo's ruling of 2026-08-26: TASK = TRACE across the whole
// tree — every message of every delegated session in one task carries the SAME TaskID, and it is
// the indexed attribute a UI or a TraceQL query selects a whole task by (§4).
type TaskID string

// MessageID is the per-message identity minted by the Factory. It is the causality key: a reply
// sets CausedBy to the MessageID it answers, and the chain of CausedBy edges IS the audit trail.
type MessageID string

// TreeAddress is a node's ROUTING address in the relay tree: the slash-joined path of node names
// from the root, e.g. "orchestrator/backend/worker-3". It is distinct from AgentID, and the
// distinction is load-bearing: AgentID is durable identity, TreeAddress is position. The zero
// value is invalid; NewAddress validates the shape.
type TreeAddress string

// NewAddress constructs a validated TreeAddress from root-to-node segments. Pure; no I/O. An
// empty segment set, an empty segment, or a segment outside [a-z0-9-] is an InvalidError.
func NewAddress(segments ...string) (TreeAddress, error)

// Parent returns the address of this node's parent and whether one exists. The root has none.
func (a TreeAddress) Parent() (TreeAddress, bool)

// Depth reports the number of segments. The root is depth 1.
func (a TreeAddress) Depth() int

// IsChildOf reports whether a is an IMMEDIATE child of other. It is the legal-edge predicate the
// relay enforces: tree edges only, no sideways bypass (2026-08-18).
func (a TreeAddress) IsChildOf(other TreeAddress) bool

// ActorKind is the closed taxonomy of who caused a message. Append-only (10 §9).
type ActorKind uint8

const (
	ActorAgent      ActorKind = iota // an agent in the tree acted
	ActorHuman                       // a person acted, through the orchestrator (the ONLY human entry point)
	ActorPolicy                      // an automated policy acted (e.g. a budget rule)
	ActorController                  // the agentpod controller acted (mint, phase change, reap)
)

// Actor records WHO caused a message, so the header chain is an audit trail without a side
// lookup. BreakGlass marks the audited operational bypass: EDEN_GATEWAY_BREAK_GLASS=1, default
// OFF, every use recorded as Actor{Kind: ActorHuman, BreakGlass: true} (Batch B+C, 2026-08-18).
// ID holds a user id, an AgentID, a policy name or a controller name — NEVER a credential.
type Actor struct {
	Kind       ActorKind `json:"kind"`
	ID         string    `json:"id"`
	BreakGlass bool      `json:"breakGlass,omitempty"`
}

// MessageHeader is the spine every fleet message embeds. Every field is either required or has a
// stated meaning when absent; there is no field whose absence means "ask somewhere else", because
// the telemetry consumer (Mateo's 2026-08-26 bus-consumer ruling) has no side lookups available.
type MessageHeader struct {
	// --- versioning ---
	SchemaVersion int `json:"schemaVersion"` // == SchemaVersion at mint; §7 governs a mismatch

	// --- identity ---
	MessageID MessageID `json:"messageId"`           // minted per message; the causality key
	AgentID   AgentID   `json:"agentId"`             // the durable fleet identity (C4)
	SessionID SessionID `json:"sessionId,omitempty"` // the harness session; absent on a controller message

	// --- routing (tree edges only) ---
	Address       TreeAddress `json:"address"`                 // the EMITTING node's address
	ParentAddress TreeAddress `json:"parentAddress,omitempty"` // "" iff Address is the root
	Hop           uint8       `json:"hop"`                     // incremented on every relay; ceiling MaxHops

	// --- causality ---
	Turn     uint64    `json:"turn"`               // the emitting session's turn ordinal, 1-based
	Seq      uint64    `json:"seq"`                // monotonic per (AgentID, plane); the replay + checkpoint cursor
	CausedBy MessageID `json:"causedBy,omitempty"` // "" == root of a causal chain

	// --- the task trace (Mateo, 2026-08-26: TASK = TRACE across the whole tree) ---
	TaskID      TaskID `json:"taskId"`                // the same value across every session of one task
	TraceParent string `json:"traceparent,omitempty"` // W3C traceparent; "" == un-traced (valid, unparented)
	TraceState  string `json:"tracestate,omitempty"`  // W3C tracestate; vendor state, never a secret

	// --- provenance ---
	Actor    Actor     `json:"actor"`
	EmitTime time.Time `json:"emitTime"` // the injected Clock instant at mint; UTC
}

// Validate reports the FIRST violated rule as a typed error, or nil. It is total on a zero value
// (a zero header is invalid, never a panic) and it is the refusal the whole library exists for.
func (h MessageHeader) Validate() error

// Intent is the write-plane verb set: what a RelayMessage is for. It is the semantic-relay
// vocabulary — the thing a level reads to decide whether to conclude, re-scope and route down.
// The two steering members are Mateo's two strengths (Batch B+C, 2026-08-18), named in full per
// HNS-1 rather than as "suggestion"/"order". Closed taxonomy, append-only (10 §9). §10 fork F3
// carries the closure question.
type Intent uint8

const (
	IntentDelegate           Intent = iota // route work DOWN to the legal child set, re-scoped at this level
	IntentReport                           // route a conclusion UP to the parent
	IntentSteerAtSafePoint                 // non-preemptive: delivered at the next safe point, folds into ongoing work
	IntentSteerPreemptive                  // preemptive: interrupts the in-flight turn, effective now
	IntentBudgetExhausted                  // the library hard-stopped spend; the PARENT decides (kill/extend/re-scope)
)

// RelayMessage is the durable WRITE plane's message (agent.<id>.inbox, ruling R3): the semantic
// relay's unit. Body is agent prose, bounded by MaxInlineBytes; Artifact carries the spill.
type RelayMessage struct {
	MessageHeader `json:",inline"`

	Intent   Intent       `json:"intent"`
	To       TreeAddress  `json:"to"`                 // MUST be the parent or a member of the legal child set
	Body     string       `json:"body,omitempty"`     // UNTRUSTED agent prose, <= MaxInlineBytes
	Artifact *ArtifactRef `json:"artifact,omitempty"` // set iff the payload spilled; NEVER a truncation
}

// EventEnvelope is the events plane's message (agent.<id>.events): one sequenced, verbatim
// agentsession.Event under the fleet header. It SUPERSEDES agentruntime.EventEnvelope (§9).
type EventEnvelope struct {
	MessageHeader `json:",inline"`

	Event agentsession.Event `json:"event"` // the FROZEN taxonomy, transported verbatim
}

// ControlVerb is the lifecycle control axis, FROZEN AT FIVE (ruling R4, 2026-08-18). The five are
// exactly agentruntime's, value-for-value and token-for-token, because they are already on the
// wire (libs/go/agentruntime/protocol.go:70-77) and a renumbering would be a silent wire break.
// STEERING IS NOT HERE: the two strengths are Intent members on the WRITE plane (Batch B+C).
type ControlVerb uint8

const (
	VerbPrompt ControlVerb = iota // start a turn
	VerbSteer                     // interject (the LEGACY control-plane steer; see §10 fork F4)
	VerbAbort                     // cancel the turn
	VerbStop                      // graceful drain, close, exit
	VerbKill                      // immediate cancel
)

// ControlMessage is the control plane's message (agent.<id>.control, core NATS — lifecycle and
// break-glass ONLY, ADR-0022 §4 preserved). It holds no secret value.
type ControlMessage struct {
	MessageHeader `json:",inline"`

	Verb ControlVerb `json:"verb"`
	Text string      `json:"text,omitempty"` // prompt payload; empty for abort/stop/kill
}

// Heartbeat is the health subject's message (agent.<id>.health, core NATS, best-effort). LastSeq
// is the highest Seq the emitter published, so a probe derives "is the stream advancing?".
type Heartbeat struct {
	MessageHeader `json:",inline"`

	Phase        HealthPhase        `json:"phase"`
	SessionState agentsession.State `json:"sessionState"`
	LastSeq      uint64             `json:"lastSeq"`
}

// HealthPhase is the emitting runtime's own coarse phase, distinct from the agentsession.State of
// the turn it carries. Closed taxonomy, append-only. Values match agentruntime's, for the reason
// ControlVerb's do.
type HealthPhase uint8

const (
	PhaseStarting HealthPhase = iota
	PhaseRunning
	PhaseDraining
	PhaseStopped
)

// ArtifactRef addresses a spilled payload WITHOUT naming a store. It is deliberately a bucket +
// key + digest triple rather than an objectstorage.ObjectRef value, so this library stays free of
// the objectstorage import and the successor-store decision stays open (§6, open fork F5).
// fleetcheckpoint is the library that turns one of these into an objectstorage.ObjectRef.
type ArtifactRef struct {
	Bucket    string `json:"bucket"`
	Key       string `json:"key"`               // content-addressed: artifact/<sha256>
	SizeBytes int64  `json:"sizeBytes"`         // the FULL size; a reader that gets fewer bytes has a truncation
	SHA256    string `json:"sha256"`            // lowercase hex; the integrity witness
	MediaType string `json:"mediaType,omitempty"`
}

// Message is the read-side union every plane consumer decodes into. It is an INTERFACE with one
// unexported method, so the four types above are the closed set by the compiler rather than by a
// comment — a fifth message type is a deliberate contract revision, never an accident.
type Message interface {
	Header() MessageHeader
	isFleetMessage()
}

// Clock is the injected time source. The library never reads the wall clock (spine purity, 10 §4).
type Clock interface{ Now() time.Time }

// Minter mints one MessageID. The production binding is ULID; the test binding is deterministic.
// It is the ONLY source of message identity — a caller may not supply its own.
type Minter interface{ Mint() MessageID }

// Config is the resolved, immutable per-node configuration. Every field is read at New and never
// re-read: the node's own identity and position, and the ceiling it enforces.
type Config struct {
	AgentID  AgentID
	Address  TreeAddress
	Children []TreeAddress // the LEGAL CHILD SET; a Mint to any other address is refused
	MaxHops  uint8         // 0 == MaxHops
}

// Deps is the injected port record (the hexagon, ADR-0009 A).
type Deps struct {
	Clock  Clock
	Minter Minter
}

// New is the constructor spine. PURE: no I/O, no env read, no clock read. It validates Config and
// Deps and returns the concrete *Factory. A missing dependency or an invalid address is a
// ConfigError naming the field.
func New(configuration Config, dependencies Deps) (*Factory, error)

// Factory mints validated headers and messages for ONE node. Every Mint stamps SchemaVersion, a
// fresh MessageID, the node's AgentID and Address, the Clock instant, and the caller's causality
// and trace values — then Validates before returning. A Mint that would violate a rule returns a
// typed error and NO message: the library refuses, it does not repair.
type Factory struct{ /* unexported */ }

// MintRelay mints a RelayMessage. It REFUSES when to is neither the parent nor a member of the
// configured legal child set (UnroutableError) — the "no sideways bypass" rule enforced at the
// port, not in prose. It REFUSES when hop would reach the ceiling (HopCeilingError). When body
// exceeds MaxInlineBytes it REFUSES with a SpillRequiredError naming the size, so the caller
// stores the payload and re-mints with an ArtifactRef: the library never silently truncates and
// never silently writes to a store it does not own.
func (f *Factory) MintRelay(cause MessageHeader, to TreeAddress, intent Intent, body string, artifact *ArtifactRef, actor Actor) (RelayMessage, error)

// MintEvent mints an EventEnvelope for a verbatim agentsession.Event at the given turn and seq.
func (f *Factory) MintEvent(session SessionID, turn, seq uint64, task TaskID, trace TraceContext, event agentsession.Event) (EventEnvelope, error)

// MintControl mints a ControlMessage. An Actor with BreakGlass set is permitted and RECORDED; it
// is never silently dropped, because an unrecorded bypass is worse than a recorded one.
func (f *Factory) MintControl(target AgentID, verb ControlVerb, text string, actor Actor, task TaskID, trace TraceContext) (ControlMessage, error)

// MintHeartbeat mints a Heartbeat.
func (f *Factory) MintHeartbeat(session SessionID, phase HealthPhase, state agentsession.State, lastSeq uint64, task TaskID) (Heartbeat, error)

// TraceContext is the W3C pair carried as first-class fields rather than as a propagation map
// (§4.2 states why the map shape was rejected). Both members may be empty: an un-traced message
// is valid and simply unparented.
type TraceContext struct {
	TraceParent string
	TraceState  string
}

// Relay re-stamps a received message for the next hop DOWN or UP: it increments Hop, sets
// CausedBy to the received MessageID, replaces Address with this node's, and mints a fresh
// MessageID — while PRESERVING TaskID and TraceParent, which is what makes one task one trace.
// It is the semantic relay's one mechanical obligation; the SEMANTIC half (concluding and
// re-scoping) is the agent's, not the library's.
func (f *Factory) Relay(received MessageHeader, to TreeAddress, intent Intent, body string, artifact *ArtifactRef, actor Actor) (RelayMessage, error)

// Decode decodes one plane's bytes into the typed message and VALIDATES it. An undecodable
// payload, an unknown SchemaVersion, or a header that fails Validate is a typed error and no
// message — this is the "the library refuses non-envelope messages" guarantee, at the read side.
func Decode[M Message](payload []byte) (M, error)

// Encode marshals a validated message. It re-Validates first: a value mutated after Mint cannot
// reach the wire.
func Encode(message Message) ([]byte, error)
```

The typed error taxonomy is a set of distinct types — `ConfigError`, `InvalidError`,
`UnroutableError`, `HopCeilingError`, `SpillRequiredError`, `SchemaVersionError` — each carrying
the offending value (an address, a hop count, a size, a version), **never a body and never a
credential**, inspectable via `errors.AsType[…]` and classified by a stable `errors.Kind`
(`KindInvalid` / `KindNotFound` / `KindResourceExhausted` / `KindFailedPrecondition`). Callers
branch on type, never on a message substring (`contracts/errors.md`).

## 3. Routing — the tree is the only edge set

✅ The ruling (2026-08-18): *"Routing = semantic relay on tree edges. A message is PROCESSED at
every level (each level concludes, re-scopes, routes down affected branches); context lives at
its level (worker=file, team=module, orchestrator=architecture). No sideways bypass."*

Three mechanisms carry it, and each is executable rather than advisory:

| Property | Mechanism | Refusal |
| --- | --- | --- |
| tree edges only | `Config.Children` is the legal child set; `MintRelay`/`Relay` check `to` against it and against `Address.Parent()` | `UnroutableError` naming both addresses |
| cycles break loudly | `Hop` increments on every relay; the ceiling is `Config.MaxHops` | `HopCeilingError` naming the address chain |
| depth is unbounded | `TreeAddress` has no depth limit — the 2026-08-18 default *"unbounded tree depth in the contract"* | none; depth is not the bound |

**⚠️ This CONFLICTS with a frozen contract, and the conflict is named rather than resolved by
silence.** `contracts/agentsession.md` freezes `PeerPlane`, whose `Roster` documentation reads
(`libs/go/agentsession/peer.go` ✅): *"Reachability defaults to a full MESH over TREE routing: the
tree is registry, authorization and audit, not a partition."* The fleet ruling says the opposite
about reachability.

The reconciliation, and why it needs no revision of the frozen document: the word is **defaults**.
`PeerPlane` is an injected port with two bindings (the 2026-08-18 default: *"PR-1c PeerPlane =
two-binding port (unixsocket now, natsbus in fleet slice)"*). The unix-socket binding defaults to
mesh; the **fleet binding restricts reachability to tree edges**, returns only the parent and the
legal child set from `Roster`, and answers a non-adjacent `Send` with the port's own
`agentsession.UnreachableError` — which the frozen contract already defines as the loudness
guarantee. A restricted plane is a conformant plane. **This reading is a 🧩 design choice and it
is open fork F1**: if Mateo reads `PeerPlane` as promising mesh to every binding, the fleet
binding is non-conformant and `agentsession` needs a contract revision instead.

## 4. Causality and the task trace

### 4.1 The three orderings, which are not one thing

| Field | Scope | Monotonic in | Used by |
| --- | --- | --- | --- |
| `Turn` | one session | the session's turns, 1-based | `fleetcheckpoint` (a checkpoint is taken at each `Turn` boundary) |
| `Seq` | one `(AgentID, plane)` | that plane's publishes | replay, dedup, the checkpoint cursor |
| `CausedBy` | the whole tree | nothing — it is a DAG edge, not a counter | the audit trail |

`Seq` is the field `agentruntime` already publishes and de-dups on
(`libs/go/agentruntime/protocol.go:57-64` ✅). It keeps that meaning here.

### 4.2 TASK = TRACE — Mateo's ruling of 2026-08-26

> **Mateo, 2026-08-26** (AskUserQuestion decision prompt, interactive session `f9c810a8`),
> verbatim: *"Task=trace across the whole tree — One trace spans the entire orchestrator task
> through every delegated session."*

Consequences, each a property of §2's header:

1. **`TaskID` is first-class and required.** Every message of every session of one task carries
   the same value. It is the indexed attribute a UI or a TraceQL query selects a whole task by;
   it is *not* derived from the trace id, because a backend may drop or resample a trace and the
   product's own grouping key must survive that.
2. **`TraceParent` / `TraceState` are typed fields, not a propagation map.** 🧩 `agentruntime`
   carries `OTelContext map[string]string` today (`protocol.go:51` ✅). A map cannot be validated,
   admits a second home for the same two W3C keys, and lets a producer smuggle an arbitrary
   key onto an audited wire. Two typed fields can be validated against the W3C shape and are what
   the ruling asks for by name. `OTelContext` is therefore SUPERSEDED (§9), not carried alongside.
   **Open fork F2:** W3C `baggage` has no field. Adding one later is additive; adding it now
   would be a third home for propagation with no consumer.
3. **Sessions are spans inside the task's trace, not separate traces.** Each session opens a root
   span *joined by the propagated context*, so the task reads as one trace while no single span
   is held open for the task's life.
4. **The long-trace mitigation is recorded, because backends cap trace duration and size.** A
   fleet task can run for hours; Tempo and its peers bound a trace's span count and its ingestion
   window. The mitigation is the design above, stated so it is not rediscovered: **per-session
   root spans joined by the propagated `traceparent`**, plus **`TaskID` as an indexed attribute**
   so the UI's "show me this task" query never depends on the whole trace being retrievable as
   one object. If a backend drops the tail of a long trace, the task view degrades to a
   `TaskID` search over spans — which is why the field is not derived from the trace id.

### 4.3 Telemetry is a bus consumer, and that is why this header is fat

> **Mateo, 2026-08-26**, verbatim selection: *"Bus consumer"* — one telemetry service consumes
> JetStream → OTel, and the same consumer feeds UI streaming.

This is consistent with the locked 2026-08-18 ruling (*"OTel: from day one — exporter as a log
consumer"*), and it is the reason §2's header carries `Actor`, `TaskID`, `SessionID` and
`ParentAddress` rather than leaving them to a join. **A consumer outside the emitting process has
no side lookups.** Every attribute a span needs is in the header, or the span cannot be built. A
field that "could be looked up" is, on this wire, a field that cannot.

The obligation this places on `fleetbus` is stated there: the telemetry consumer gets **its own
durable consumer**, never a member of a delivery consumer's queue group.

## 5. Payload discipline — spill, never truncate

✅ Ruling R6 (2026-08-18): *"spill-never-truncate (MaxInlineBytes 256KiB, ArtifactRef to MinIO)"*.

The rule, and the one place this document departs from the ruling's wording:

- A payload of at most `MaxInlineBytes` travels inline in `Body`.
- A larger payload is stored by the PRODUCER before publish, and travels as an `ArtifactRef`.
- **A payload is never truncated, never summarised, and never replaced by a digest.**
  `agentsession` already holds this line for its own smaller bound
  (`libs/go/agentsession/peer.go:11-13` ✅ *"A longer body is a LOUD typed error at Send — never a
  silent truncation, so the transcript stays verbatim within the bound and MsgID correlation is
  never broken by a digest."*). This contract's `SpillRequiredError` is the same discipline at
  the fleet bound.
- **⚠️ `ArtifactRef` names no store.** The ruling says "to MinIO". This contract says *bucket, key,
  size, digest* and stops there, because the MinIO successor is an open decision (Batch A,
  2026-08-18: *"MinIO proceed v1 behind the frozen objectstorage port + successor decision opened
  separately"*). A contract that names a vendor as a guarantee has to be revised when the vendor
  changes; one that names a shape does not. Turning an `ArtifactRef` into an
  `objectstorage.ObjectRef` is `fleetcheckpoint`'s job, at the one seam that already owns the
  store.

Two bounds coexist and must not be conflated: `agentsession.MaxPeerBodyBytes` (8 KiB) bounds an
*inter-session peer message inside one harness process*; `fleetenvelope.MaxInlineBytes` (256 KiB)
bounds a *fleet relay body on the durable write plane*. Different wires, different bounds, both
loud.

## 6. Identity — minted once, witnessed by the controller

✅ Canon ruling C4 and the synthesis (2026-08-18): *"controller-minted `agent-<ulid>` +
`metadata.uid` witness (refuses GitOps-reapply id reuse); `agent-<n>` counter deleted."*

- `AgentID` has the form `agent-<ulid>`; `Validate` enforces the prefix and the 26-character
  Crockford-base32 body. It is minted by the `agentpod` controller — **this library validates the
  shape and never mints one**, so there is exactly one minting authority.
- The `metadata.uid` witness is the CRD's mechanism and lives in `agentpod`. It is cited here
  because it is what makes `AgentID` durable across a GitOps re-apply, which is the property this
  header depends on.
- `SessionID` is scoped to an `AgentID` and appears only as a field. It is never a subject token
  and never part of a `TreeAddress`.

## 7. Versioning — and the window that is closing

✅ Ruling R1 (2026-08-18): *"json tags + marshallers BEFORE any byte is stored (once-only window:
0 streams, 0 messages, no bucket)."*

The window is open **today** and this is what closes it: the first `EnsureStream`, the first
published message, the first checkpoint object. Verified open at the time of writing — the fleet's
streams do not exist, and the only fleet-shaped stream in the estate is `agentruntime`'s
`EDEN_AGENT_EVENTS` (`libs/go/agentruntime/protocol.go:30` ✅), which §9 addresses explicitly.

The rules, once frozen:

| Change | Allowed? | Mechanism |
| --- | --- | --- |
| add an OPTIONAL field with `omitempty` | ✅ additive | same `SchemaVersion`; old readers ignore it |
| add a member to the END of a closed taxonomy (`Intent`, `ControlVerb`, `ActorKind`, `HealthPhase`) | ✅ additive | same `SchemaVersion`; a reader that meets an unknown member REFUSES the message rather than defaulting it |
| rename a json tag, change a type, reorder an enum, remove a field | ❌ breaking | `SchemaVersion` bump + a contract revision (ADR-0016 §1) + re-recorded `.apibaseline` |
| make an optional field required | ❌ breaking | as above |

`Decode` REFUSES a `SchemaVersion` it does not know, with a `SchemaVersionError` naming both
versions. It does not "best-effort" an unknown version: a header the reader does not fully
understand is exactly the unvalidated link §1 forbids.

**An unknown enum member is a refusal, not a default.** This is the one place this contract is
stricter than Go's zero-value habit, and deliberately: `Intent(0)` is `IntentDelegate`, so a
default-on-unknown would silently turn an unrecognised steering verb into an instruction to
delegate work.

## 8. Fake and conformance

`fleetenvelopetest` is the public fake package (10 §4, `contracts/testing.md`), and it binds the
two injected ports deterministically:

- `fleetenvelopetest.FixedClock` — a fixed, advanceable `Clock`.
- `fleetenvelopetest.SequenceMinter` — a `Minter` yielding `msg-000001`, `msg-000002`, … so a
  golden file is stable and a causal chain is readable by eye.
- `fleetenvelopetest.Tree(...)` — builds a `Config` for a named node in a named tree, so a test
  states its topology in one line instead of hand-assembling addresses.
- `fleetenvelopetest.SeededCanary` — the secret-leak canary the `secretscan` dimension asserts is
  absent from every surfaced artifact (the `errorstest`/`agentruntimetest` precedent ✅).

`fleetenvelopetest.RunEnvelopeSuite(t, newFactory)` is the exported **two-binding** conformance
suite (08 §2): it runs the SAME property set over the deterministic fake bindings AND, in the
integration lane, over the production `ulidminter` + system clock bindings. The properties:

1. every minted header `Validate()`s, and a zero header does not;
2. `Encode` → `Decode` is byte-stable and value-identical for all four message types;
3. `MessageID` is unique across N mints (fake: monotonic; real: unique);
4. `Relay` PRESERVES `TaskID` and `TraceParent` and CHANGES `MessageID`, `Address`, `Hop`,
   `CausedBy` — the one property that makes a task one trace;
5. a `to` outside `{parent} ∪ Children` is `UnroutableError` — the no-sideways-bypass property;
6. `Hop` reaching the ceiling is `HopCeilingError`, and the error names the chain;
7. a body over `MaxInlineBytes` is `SpillRequiredError` carrying the true size, and **no
   truncated message is ever produced** — asserted by refuting the negative, not by inspecting a
   happy path;
8. an unknown `SchemaVersion` and an unknown enum member are each a refusal, never a default;
9. no surfaced error, no encoded message and no `String()` contains `SeededCanary`;
10. `Decode` of arbitrary bytes never panics (a `rapid` property over the fuzz corpus).

The fake weakens the SOURCE of ids and time, never the contract.

## 9. ⚠️ Consequences for an already-frozen surface — `agentruntime`

This is the largest consequence of this contract and it must be read before any lane starts.

`libs/go/agentruntime` **already exports the wire protocol this contract re-homes** — measured at
libs `8683fea`, `go/agentruntime/.apibaseline` ✅: `AgentID`, `OTelContext`, `EventEnvelope`,
`ControlMessage`, `ControlVerb`, `Heartbeat`, `HealthPhase`, `EventsStreamName`, `EventsSubject`,
`ControlSubject`, `HealthSubject`. Its contract is `contracts/agentruntime.md`, frozen, and
`libs/go/_ctl/lib.sh::_xlib_wire_literal_scan` actively enforces that **agentruntime owns the wire
contract** — its remedy line reads (✅ `lib.sh:694`): *"import
github.com/gophersys/libs/go/agentruntime and cite EventsStreamName / EventsSubject /
ControlSubject / HealthSubject; the wire contract lives once in the protocol owner."*

So this contract does not merely add a library. It **moves the wire contract's home**, and that
is a breaking change to a frozen surface — the cardinal sin (10 §9) unless it goes through
ADR-0016 §1. Three facts make the move the right answer rather than an avoidable one:

1. The four message types must embed one header (R2). `agentruntime`'s three cannot embed a type
   from a library that would then import `agentruntime` — the cycle is structural, not stylistic.
2. `agentruntime` is a **runtime** (the pod's PID-1 state machine); the wire header is **data**
   consumed by the controller, the relay, the checkpointer and the telemetry consumer, none of
   which want a PID-1 runtime in their dependency graph.
3. The blueprint already schedules `agentruntime`'s rework onto the fleet leg
   (`eden-rework-blueprint.md:1937` ✅ — *"the fleet leg lands — it is the agent-pod runtime and
   has no other consumer"*). This is that rework's largest item, surfaced now rather than
   discovered mid-lane.

**The migration, stated so no lane assumes it is free:** `agentruntime/protocol.go` is DELETED;
its eleven exported names move to `fleetenvelope` (types) and `fleetbus` (subjects and stream
name); `agentruntime` imports both; `contracts/agentruntime.md` takes a contract revision;
`agentruntime/.apibaseline` is re-recorded; `_xlib_wire_literal_scan`'s owner and remedy line move
with it. **None of that happens in this contract's own pull request**, and no other lane may
assume `agentruntime` has moved until it has.

## 10. Open forks — what Mateo must rule on, or delegate

| # | Fork | Options (recommendation first) | Blocks |
| --- | --- | --- | --- |
| F1 | **`PeerPlane` mesh-vs-tree.** The frozen `agentsession` port documents mesh reachability as the DEFAULT; the fleet ruling forbids sideways bypass. | (a) a binding may restrict reachability; the fleet binding is tree-only and answers a non-adjacent `Send` with the port's own `UnreachableError` — no revision needed (§3) · (b) `PeerPlane` promises mesh to every binding → `agentsession` takes a contract revision. | the relay lane |
| F2 | **W3C `baggage`.** | (a) no field in v1; additive later when a consumer exists · (b) add `Baggage string` now. | nothing |
| F3 | **Is `Intent` closed at five?** The five in §2 are the members with evidence (2 verbatim from the steering ruling, 3 derived from the semantic-relay and budget rulings). | (a) freeze at five; a sixth is a contract revision · (b) name more now (query/answer, permission round-trip, checkpoint marker). | the relay + steering lanes |
| F4 | **`VerbSteer` vs the two `Intent` steering members.** `ControlVerb` is frozen at five and one of them is `steer`; steering also exists as two `Intent` members on the write plane. Two homes for one concept. | (a) `VerbSteer` is DEPRECATED-IN-PLACE: kept for value stability, refused by the fleet relay, and the only legal steering path is the write plane (recommended — it preserves the frozen five without preserving two homes) · (b) renumber `ControlVerb` to four → a wire break · (c) keep both live → two homes. | the steering lane |
| F5 | **The `ArtifactRef`↔store seam.** | (a) shape-only `ArtifactRef` here, `objectstorage.ObjectRef` built in `fleetcheckpoint` (recommended; keeps the successor decision open) · (b) `fleetenvelope` imports `objectstorage`. | the checkpoint lane |
| F6 | **`MaxHops = 32`.** No ruling fixes a number; 32 is this document's proposal against an unbounded-depth tree. | (a) 32, revisable additively as `Config.MaxHops` already permits · (b) a measured number after the first real tree. | nothing (it is configurable) |

Each fork is recorded in `docs/architecture/open-decisions.md` as well, per `CLAUDE.md`'s rule
that an unmade decision lives there and never in prose alone.

## 11. THE FREEZE QUESTION — for Mateo, and for nobody else

Freezing this contract is a §5 human gate. An agent may not exercise it, and this document may
not be edited to say it is frozen by anything other than Mateo's own words quoted with a
timestamp (§13 rule 4). The question is exactly this:

> **Do you freeze `fleetenvelope` v1 at the surface in §2 — the `MessageHeader` spine embedded by
> exactly four message types, `Intent` closed at five members, `ControlVerb` unchanged at the
> five values already on the wire, `TaskID` + `traceparent`/`tracestate` as first-class required
> fields, `MaxInlineBytes` at 256 KiB with spill-never-truncate, and `ArtifactRef` naming a
> shape rather than a store — accepting that the freeze commits `agentruntime` to the §9
> migration and its own contract revision?**
>
> **YES** → the surface is frozen, `.apibaseline` is re-recorded as the freeze witness,
> `phase-gate architecture` goes green, and the five lanes of the parallelization map start
> against a fixed target.
>
> **NO, with changes** → name the forks in §10 you are ruling differently, and the draft is
> amended and re-refuted before the question is asked again.
>
> Answering also requires ruling F1 and F4, because both change §2's surface. F2, F3, F5 and F6
> may be delegated; F1 and F4 cannot, because one of them may put a *frozen* contract
> (`agentsession`) into revision and the other decides whether a frozen enum member becomes dead.

**A second gate rides on the same answer.** The fleet ADR is reserved at **0030** (Batch B+C,
2026-08-18: *"Fleet ADR takes number 0030 (fills the hole; messaging keeps 0032)"*) and does not
exist on disk — `docs/architecture/adr/` runs 0029 → 0031. A new ADR is separately Mateo-gated
(§5), so no agent has written it, and this contract cites the 2026-08-18 rulings directly rather
than citing an ADR that is not there. **Writing ADR-0030 is Mateo's, and it should land in the
same decision as the freeze**, so the contract's authority chain stops dangling.
