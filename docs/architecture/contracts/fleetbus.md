# Contract — fleetbus

> Status: **DRAFT for negotiation** · 2026-08-26 · The transport of the Eden agent fleet.
> This is the 09 §4 step-1/2 artifact for the bus: the four subjects, the two streams, their
> policies, the consumers that read them, and the delivery semantics that decide whether a fleet
> message arrives — reconciled into one document, with the unresolved parameters recorded as open
> forks (§11) rather than settled silently. **It is NOT frozen, and no agent may freeze it.** The
> freeze is Mateo's `.claude/rules/git-process.md` §5 gate (*"a chart or contract PROMISE"*),
> exercised only under §13 rule 4 with his verbatim words and a timestamp. §12 is the exact
> question he must answer. Until he answers it, `bash ./ctl.sh phase-gate architecture` in
> `libs/go/fleetbus` is RED **by design** — `libs/go/_ctl/lib.sh:1216` ✅ requires a
> `Status: … Frozen` header and a draft correctly fails it. A header that claimed otherwise would
> turn that gate green over an unfrozen contract, which is the exact class of defect this
> repository treats as worse than no gate at all.
>
> **This document is the CONSUMER-side half of a pair.** `contracts/fleetenvelope.md` is the
> SPINE — the wire header every fleet message embeds. This document **cites it and never
> redefines a header field.** Where a fact belongs to the header, the citation points there.
>
> **Authority to design this now.** The fleet architecture was ruled on 2026-08-18 (role-pods,
> JetStream planes, frozen envelope, CRD controller); the build trigger fired on 2026-08-26,
> verbatim: *"we can kick off a lot of these things in parallel if we do api agreements up
> front."* This is the transport half of that agreement.
>
> Epistemic legend (`docs/architecture/README.md` §3): ✅ verified · 🔶 hypothesis · ⚠️ corrected
> · 🧩 design choice. Every ✅ carries a `file:line` or a quoted ruling. A claim with neither is a
> **proposal**, and this document marks it as one rather than letting it read as a decision.
>
> **Measurement basis.** Every `libs/go/…` citation is read through
> `git -C libs show origin/main:<path>` at libs `8cb1543`-era `origin/main`. The working tree of
> the `libs` submodule in this checkout is 301 commits stale and a line number read from it is
> not evidence.

## 1. Scope

`fleetbus` is the **one home of the fleet transport**: how a validated `fleetenvelope` message
reaches another node, what durability that costs, what happens when it cannot, and where a reader
resumes. It owns the wire's *addressing and delivery*; it owns none of the wire's *content*.

It owns exactly six things:

1. **The four subjects** — `agent.<id>.events`, `agent.<id>.control`, `agent.<id>.health`,
   `agent.<id>.inbox` — and the ONE file every literal lives in (§3).
2. **The two streams** — `EDEN_AGENT_EVENTS` and `EDEN_AGENT_INBOX` — their policies, and the
   **owner** of their creation, which is the controller and not the pod (§4).
3. **Delivery semantics** — at-least-once with a deterministic dedup key, the `PubAck` that is
   read rather than discarded, and what a duplicate means differently on each plane (§5).
4. **The two sequence spaces** — the envelope's per-session `Seq` and JetStream's global stream
   sequence — and the single join point where history hands off to the live tail (§6).
5. **Backpressure** — which side of each plane is told to stop, and how loudly (§7).
6. **The consumers** — the events tail, the inbox durable, the control subscription, and the
   telemetry tap that must never compete with any of them (§9).

It explicitly does **not** own:

- **Any header field.** `MessageHeader`, `MessageID`, `AgentID`, `RootID`, `CausedBy`, `InReplyTo`,
  `Hop`, `Seq`, `Deadline`, `Intent`, `Actor`, `OTelContext`, `ControlVerb`, `ArtifactRef` and the
  four message types are `contracts/fleetenvelope.md` §2. This library takes a validated value and
  puts it on a subject. It never mints, never repairs, never reads a body. **In particular the
  message's expiry is `MessageHeader.Deadline`, a header field, and this library reads it — it does
  not carry a second expiry of its own.**
- **The archive.** Segment format, manifest composition and retention are
  `contracts/agentcheckpoint.md`. This document states only the *ordering* rule between the
  archive write and the publish (§8), because the ordering is a property of the pump, not of
  either store.
- **The pod lifecycle and the CRD.** `Agent.status.lastStreamSeq` / `lastInboxSeq` and the
  `Suspended` phase are `contracts/agentfleet.md`'s fields; this document states what the bus
  REQUIRES of them and cites them by name.
- **The NATS server itself.** ADR-0022 §2 puts the server out-of-band under Argo. §4.5 states
  exactly where that boundary falls and why a *stream* is on this side of it.
- **Authentication and authorization.** There is none today (§3.5). This document states that
  plainly rather than implying a guarantee the substrate does not provide.

It cites, never redefines: `MessageHeader` / `EventEnvelope` / `RelayMessage` / `ControlMessage` /
`Heartbeat` / `Intent` (ten members, `IntentFailed` among them) / `AgentID` / `MessageID` /
`Deadline` (`contracts/fleetenvelope.md` §2 — the spine is **additive to package `agentruntime`**,
so the Go references below are `agentruntime.<T>`), `errors.Kind` / `errors.AsType`
(`contracts/errors.md`), `agentsession.Event` (`contracts/agentsession.md`, FROZEN, transported
verbatim), `edenhttp.SSEStream` / `edenhttp.CursorAll` (`contracts/edenhttp.md`,
`libs/go/edenhttp/sse.go:15` ✅), and `observability.Event` (`contracts/observability.md` — the
vocabulary the telemetry CONSUMER emits from a header, never emitted from inside this library).

## 2. Contract

The surface is in **two packages, deliberately**, and the split is the whole answer to "where does
a wire literal live".

### 2.1 The subject and stream names — ADDITIVE to `agentruntime/protocol.go`

`contracts/fleetenvelope.md` §2 is explicit that the spine is **additive** to package
`agentruntime` and that *"`EventsSubject` / `ControlSubject` / `HealthSubject` and
`EventsStreamName` already exist and are unchanged ✅ … This document adds to that file; it does
not rewrite it."* The transport's names follow the same rule, into the same file, for the reason
§3.4 gives: **`libs/go/_ctl/lib.sh::_xlib_wire_literal_scan` (`lib.sh:665-698` ✅) fails the
maintainability gate when a protocol literal appears in a string in more than one library's
production code.** One file, one library, cited by everyone else.

```go
package agentruntime // ADDITIVE — three of the four formats are already here (protocol.go:20-22 ✅)

const (
	subjectEventsFormat  = "agent.%s.events"   // unchanged (protocol.go:20 ✅)
	subjectControlFormat = "agent.%s.control"  // unchanged (protocol.go:21 ✅)
	subjectHealthFormat  = "agent.%s.health"   // unchanged (protocol.go:22 ✅)
	subjectInboxFormat   = "agent.%s.inbox"    // NEW (R3) — the ONE new leaf token
)

// The wildcard forms the two streams capture. Same rule: one home, never re-spelled.
const (
	eventsSubjectWildcard = "agent.*.events" // unchanged (natsbus.go:41 ✅, moved to the owner)
	inboxSubjectWildcard  = "agent.*.inbox"  // NEW
)

// InboxSubject renders the durable WRITE plane's subject for one agent (agent.<id>.inbox). It is
// the new leaf token of ruling R3 and the reason the relay does NOT overload the control subject.
// EventsSubject / ControlSubject / HealthSubject already exist unchanged (protocol.go:35-41 ✅).
func InboxSubject(id AgentID) string

// EventsStreamName is unchanged (protocol.go:31 ✅) — the value is already on the wire and a
// rename would be a silent wire break. InboxStreamName is NEW, and it is a SEPARATE stream rather
// than a second subject on the events stream because the two need OPPOSITE discard policies (§4.2).
const EventsStreamName = "EDEN_AGENT_EVENTS" // unchanged
const InboxStreamName  = "EDEN_AGENT_INBOX"  // NEW
```

### 2.2 The transport — `fleetbus`

`fleetbus` **cites** the six names above and never re-spells one. Everything below is new surface.

```go
// Package fleetbus is the one home of the Eden agent-fleet TRANSPORT: the two JetStream streams
// and their policies, the consumers that read them, and the delivery semantics that decide whether
// a fleet message arrives. It is the CONSUMER half of the pair whose SPINE is the fleet header
// (contracts/fleetenvelope.md, package agentruntime): this library never mints a header, never
// repairs one, and never reads a body.
//
// It holds NO subject literal and NO stream-name literal. It imports agentruntime and cites
// EventsSubject / ControlSubject / HealthSubject / InboxSubject / EventsStreamName /
// InboxStreamName — the wire contract lives once in the protocol owner (§2.1, lib.sh:694 ✅).
//
// Module: github.com/gophersys/libs/go/fleetbus  (go 1.26) — see §11 fork B12 on the placement.
//
// Three durability classes over four subjects (§3). The events plane is durable for REPLAY and
// never acknowledged; the inbox plane is durable for DELIVERY and explicitly acknowledged; the
// control and health subjects are core NATS and at-most-once. Conflating "durable" with
// "delivered" is the mistake this split exists to prevent.
//
// Concurrency: New is PURE (no dial, no I/O, no env read, no clock read) over already-dialed
// handles — the composition root owns the connection lifecycle, exactly as natsbus does today
// (libs/go/agentruntime/natsbus/natsbus.go:71-86). A constructed publisher/subscriber is safe for
// concurrent use.
//
// Zero value: a zero StreamPolicy is INVALID and is refused by CreateStream and RequireStream —
// there is no defaulted limit, because the defect this contract exists to fix is a stream created
// with no limits at all (natsbus.go:96-102).
package fleetbus

// ── §4 stream policy — a declared value with one home ────────────────────────

// Discard is what a stream does when a limit is reached. The two members are not interchangeable
// and the choice is the loudest decision in this contract (§4.3).
type Discard uint8

const (
	DiscardOldest Discard = iota // drop the OLDEST message; the reader sees a silent gap
	DiscardNewest                // refuse the NEWEST message; the PUBLISHER gets an error
)

// Storage and Replicas are INHERITED from today's build, not decided here: natsbus.go:99 already
// sets FileStorage, and infrastructure/apps/eden/06-nats.yaml:56 already runs one replica. They
// appear as fields so a policy value is complete and comparable, never so they read as new rulings.
type Storage uint8

const (
	StorageFile Storage = iota // inherited (natsbus.go:99)
	StorageMemory
)

// StreamPolicy is the COMPLETE declared shape of one stream. Every limit is explicit: there is no
// zero-means-default field, because the defect being fixed is a stream created with three limits
// silently unset (natsbus.go:96-102 sets Name/Subjects/Storage/Retention/Discard and nothing else).
type StreamPolicy struct {
	Name              string
	Subjects          []string
	Discard           Discard
	MaxBytes          int64         // the stream's byte ceiling; 0 is INVALID here, never "unlimited"
	MaxAge            time.Duration // 0 is INVALID
	MaxMsgsPerSubject int64         // the FLEET-SAFETY knob (§4.4); 0 is INVALID
	Duplicates        time.Duration // the dedup window; the one home of the value (§5.4)
	Storage           Storage       // inherited
	Replicas          int           // inherited
}

// EventsStreamPolicy and InboxStreamPolicy return the two DECLARED policies of §4.1. They are
// functions rather than exported variables so no caller can mutate the fleet's limits in place.
func EventsStreamPolicy() StreamPolicy
func InboxStreamPolicy() StreamPolicy

// Provisioner splits stream creation from stream verification, because they belong to different
// processes. Gap G12: today EnsureStream is called by the agent POD's composition root
// (natsbus.go:95), so the FIRST POD TO BOOT creates the fleet's stream, with whatever limits that
// pod's build happened to carry — which is how EDEN_AGENT_EVENTS exists today with no MaxAge, no
// MaxBytes and no MaxMsgs at all.
type Provisioner interface {
	// CreateStream is the CONTROLLER's verb, and only the controller's. It creates or updates the
	// stream to exactly policy. It is idempotent on an identical policy and it UPDATES on a
	// differing one — the controller is the reconciler, so converging the limits is its job.
	CreateStream(ctx context.Context, policy StreamPolicy) error

	// RequireStream is the POD's verb, and it is a StreamInfo read plus a comparison — never a
	// create. An absent stream is a StreamMissingError NAMING THE STREAM; a stream whose limits
	// differ from policy is a StreamPolicyMismatchError NAMING THE STREAM AND THE FIELD. Either
	// FAILS THE POD AT BOOT. A pod that silently created what it needed is a pod that silently
	// decided the fleet's retention.
	RequireStream(ctx context.Context, policy StreamPolicy) error
}

// ── §5 publishing — the PubAck is read ───────────────────────────────────────

// PublishReceipt is the JetStream PubAck, KEPT. Today it is discarded: natsbus.go:124 reads
// `_, err = a.jetStream.Publish(...)`, so the one field that reports a swallowed duplicate is
// thrown away at the call site. StreamSeq is the message's global position and is the only place
// a publisher can learn it (§6).
type PublishReceipt struct {
	Stream    string
	StreamSeq uint64
	Duplicate bool // JetStream suppressed this publish as a duplicate inside the Duplicates window
}

// DedupKey renders the JetStream message id for one header: the deterministic key of §5.2. It is
// a package function rather than an adapter detail so a test can assert the key WITHOUT a server,
// and so the two planes' key shapes have one home.
func DedupKey(header agentruntime.MessageHeader) string

// Publisher is the write side. Four methods; the two durable planes return a receipt and the two
// core-NATS planes cannot (there is no acknowledgement to return).
type Publisher interface {
	// PublishEvent appends one EventEnvelope to agent.<id>.events with MsgId == DedupKey(header).
	// A suppressed duplicate is a COUNTED, non-fatal outcome (Receipt.Duplicate is true, error is
	// nil): republishing after a pod restart is the idempotency this key exists for.
	PublishEvent(ctx context.Context, envelope agentruntime.EventEnvelope) (PublishReceipt, error)

	// PublishRelay appends one RelayMessage to agent.<id>.inbox. A suppressed duplicate here is a
	// LOUD typed DuplicateDirectiveError naming the MessageID — because a directive delivered zero
	// times is a lost instruction, and on this plane silence is indistinguishable from success.
	PublishRelay(ctx context.Context, message agentruntime.RelayMessage) (PublishReceipt, error)

	// PublishControl publishes to agent.<id>.control over CORE NATS. At-most-once by design:
	// ADR-0022 §4 is preserved, and the reconcile loop IS the retry, so no durability is needed.
	PublishControl(ctx context.Context, message agentruntime.ControlMessage) error

	// PublishHealth publishes to agent.<id>.health over CORE NATS. Best-effort liveness.
	PublishHealth(ctx context.Context, heartbeat agentruntime.Heartbeat) error
}

// ── §6 the two sequence spaces ───────────────────────────────────────────────

// StreamSeq is the JETSTREAM GLOBAL POSITION of a message. It is NOT fleetenvelope's Seq and the
// two are never assigned to one another. It DOES NOT EXIST AT PUBLISH TIME — the server assigns
// it — which is precisely why it is not and can never be an envelope field. It is read from
// message.Metadata().Sequence.Stream on the consumer side, it is the SSE `id:` line, and it is the
// resume cursor a reconnect sends back.
type StreamSeq uint64

// StreamStart means "deliver everything the stream still holds". It is 0, matching the zero
// convention edenhttp already uses (edenhttp.CursorAll, sse.go:15 ✅) — cited, not redefined.
const StreamStart StreamSeq = 0

// Delivery is one consumed message plus the transport facts a consumer needs and the envelope
// cannot carry. Ack/Nak are nil on the events plane (AckNone) and non-nil on the inbox plane.
type Delivery[M agentruntime.Message] struct {
	Message    M
	StreamSeq  StreamSeq     // the global position — the resume cursor, never the envelope's Seq
	Redelivery uint32        // 1 on first delivery; >1 means the durable consumer is retrying
	Expired    bool          // clock.Now() is past header.Deadline; the input to the ack-and-drop rule
	Ack        func() error
	Nak        func(delay time.Duration) error
}

// ── §9 consumers ─────────────────────────────────────────────────────────────

// AckMode is the acknowledgement discipline of one consumer.
type AckMode uint8

const (
	AckNone     AckMode = iota // the events tail: a log reader, never a queue worker
	AckExplicit                // the inbox durable: one ack per message, never a range
)

// ConsumerPolicy is the declared shape of one consumer. Its FIELDS are settled; several of its
// VALUES are OPEN and are recorded in §11 forks B1-B7 rather than defaulted here. A field with an
// open value is present so the ruling has one place to land, not so it can be quietly guessed.
type ConsumerPolicy struct {
	Durable        string        // "" == ephemeral (events tail); non-empty == durable (inbox, telemetry)
	FilterSubject  string        // the per-agent subject; the fleet-safety property of §6.3 depends on it
	AckMode        AckMode
	Start          StreamSeq     // StreamStart == deliver all; else deliver from Start+1
	AckWait        time.Duration // OPEN — fork B5
	MaxDeliver     int           // OPEN — fork B4
	MaxAckPending  int           // OPEN — fork B6
	QueueGroup     string        // MUST be empty for any telemetry consumer (§9.3) — the invariant
}

// NOTE — there is NO expiry field here. A message's expiry is agentruntime.MessageHeader.Deadline
// ("WRITE plane only; zero == no deadline", contracts/fleetenvelope.md §2), so the ack-and-drop of
// §9.2 reads the HEADER. A consumer-wide deadline would be a second home for one concept and would
// let the transport overrule a sender's stated deadline, which it has no standing to do.

// Subscriber is the read side. Four methods, one per subject. Each deliver callback returns an
// error; on the inbox plane a returned error means "do not ack", which is how a redelivery is
// requested without the caller touching the transport.
type Subscriber interface {
	// SubscribeEvents opens an EPHEMERAL PUSH consumer on agent.<id>.events with AckNone, bound to
	// EventsStreamName, delivering all from StreamStart or from Start+1. Already per-agent
	// subject-filtered — the property natssse.go:112 has today and §6.4 shows is load-bearing.
	SubscribeEvents(ctx context.Context, id agentruntime.AgentID, from StreamSeq, deliver func(Delivery[agentruntime.EventEnvelope]) error) error

	// SubscribeInbox opens a DURABLE consumer on agent.<id>.inbox with explicit ack. A message past
	// its header Deadline on a REDELIVERY is acked-and-DROPPED and an IntentFailed naming the
	// MessageID is published (§9.2) — an expired directive is never re-run silently and never
	// redelivered forever.
	SubscribeInbox(ctx context.Context, id agentruntime.AgentID, policy ConsumerPolicy, deliver func(Delivery[agentruntime.RelayMessage]) error) error

	// SubscribeControl subscribes to agent.<id>.control over core NATS. A DECODE FAULT IS
	// SURFACED, never swallowed: today natsbus.go:161-163 bare-`return`s on a JSON decode fault,
	// contradicting its own port documentation at ports.go:26-28 ("delivered as a non-nil error to
	// the sidecar's logger, never dropped silently").
	SubscribeControl(ctx context.Context, id agentruntime.AgentID, deliver func(agentruntime.ControlMessage) error) error

	// SubscribeHealth subscribes to agent.<id>.health over core NATS. The subject finally gets a
	// consumer: the controller's Probe.
	SubscribeHealth(ctx context.Context, id agentruntime.AgentID, deliver func(agentruntime.Heartbeat) error) error
}

// ── construction ─────────────────────────────────────────────────────────────

// Deps injects the already-dialed handles. New dials nothing (the natsbus precedent, natsbus.go:71).
type Deps struct {
	Conn      *nats.Conn
	JetStream nats.JetStreamContext
	Clock     Clock
}

// New is the constructor spine. PURE. It validates the handles and returns the concrete *Bus,
// which satisfies Publisher, Subscriber and Provisioner.
func New(configuration Config, dependencies Deps) (*Bus, error)
```

The typed error taxonomy is a set of distinct types — `StreamMissingError`,
`StreamPolicyMismatchError` (carrying the stream, the field, the wanted value and the found value),
`DuplicateDirectiveError` (carrying the `MessageID`), `MessageExpiredError` (carrying the
`MessageID` and the age), `BackpressureError` (carrying the subject and the limit hit) and
`UnavailableError` — each inspectable via `errors.AsType[…]` and classified by a stable
`errors.Kind` (`KindNotFound` / `KindFailedPrecondition` / `KindAlreadyExists` /
`KindResourceExhausted` / `KindUnavailable`). **No error carries a body and none carries a
credential.** Callers branch on type, never on a message substring
(`contracts/errors.md`).

**Every interface is at or under the 5-method ceiling** (10 §9): `Provisioner` 2, `Publisher` 4,
`Subscriber` 4. The split into three ports is not decoration — `Provisioner.CreateStream` belongs
to a process (the controller) that never publishes, and `RequireStream` belongs to a process (the
pod) that must never create.

## 3. The four subjects and the three durability classes

### 3.1 Ruling R3, stated and reconciled

✅ Ruling R3 (2026-08-18): *three planes, four subjects.*

| const | value | plane | transport | carries | state |
| --- | --- | --- | --- | --- | --- |
| `subjectEventsFormat` | `agent.%s.events` | READ | **JetStream** | `EventEnvelope` | unchanged (`protocol.go:20` ✅) |
| `subjectControlFormat` | `agent.%s.control` | LIFECYCLE | **core NATS** | `ControlMessage`, five verbs | unchanged (`protocol.go:21` ✅) |
| `subjectInboxFormat` | `agent.%s.inbox` | WRITE | **JetStream** | `RelayMessage` (its `Intent` is the verb) | **NEW — the one new leaf token** |
| `subjectHealthFormat` | `agent.%s.health` | LIFECYCLE | **core NATS** | `Heartbeat` | unchanged (`protocol.go:22` ✅); finally gets a consumer |

🧩 **The arithmetic, reconciled rather than left to read as an error.** R3 says *three planes* and
names *four subjects*. The three PLANES are **read, write and lifecycle**; `health` is the fourth
SUBJECT and it belongs to the lifecycle plane. It is a separate subject and not a separate plane
because its producer, its transport class and its consumer are all lifecycle: the pod emits it, it
is core NATS, and the controller's Probe reads it. Nothing in the product reads a heartbeat.

### 3.2 The three durability classes

Four subjects, three classes. The classes are the useful abstraction because **"durable" and
"delivered" are different properties and the estate has already conflated them once.**

| class | subjects | durability | acknowledgement | what it guarantees |
| --- | --- | --- | --- | --- |
| **D1 — durable for REPLAY** | `events` | JetStream, 72h | **none** (`AckNone`) | the record survives the pod; a reader can re-read from any position. It does NOT guarantee that any particular reader saw any particular message. |
| **D2 — durable for DELIVERY** | `inbox` | JetStream, 720h | **explicit, per message** | the message is retried until it is acknowledged or until it expires loudly. |
| **D3 — at-most-once** | `control`, `health` | core NATS, none | none | the message is delivered now or not at all. |

D1 is why the events stream is a **log**, not a queue: `natssse.go:158` ✅ already opens its
consumer with `nats.AckNone()`, and that is correct — an SSE reader that acked would be claiming a
delivery guarantee the browser on the other end cannot honour.

D2 is why the inbox needed a **new subject** rather than a second use of an existing one. A relay
directive must be retried; an observation must not be.

### 3.3 EXPLICITLY REJECTED — overloading `control`

The rejected alternative was to carry the tree-edge relay on `agent.<id>.control` and promote that
subject to durable-and-acked. It is rejected for two independent reasons, either of which is
sufficient:

1. **Two concepts in one home.** `control` is the controller's lifecycle axis — stop, kill and the
   audited break-glass. The relay is the product's semantic tree edge. Putting both on one subject
   makes every consumer of either one a consumer of both, and makes "who may publish here" a
   question with two answers.
2. **It changes ADR-0022 §4 without naming it.** ADR-0022 §4 states the control subject's
   contract, and `protocol.go:14-17` ✅ carries that contract in the code: control is the *soft
   control signal*, best-effort, because **the reconcile loop IS the retry, so no durability is
   needed here.** Promoting it to durable-and-acked would silently repeal that. **ADR-0022 §4 is
   PRESERVED**, and the preservation is deliberate rather than incidental: the control plane stays
   core NATS, at-most-once, controller stop/kill and break-glass ONLY.

### 3.4 One home for every wire literal — and the gate that does not know about the inbox yet

✅ `libs/go/_ctl/lib.sh:665-698` — `_xlib_wire_literal_scan` fails the maintainability gate when a
protocol literal appears inside a Go string in **more than one top-level library's production
code**. Its remedy line reads (`lib.sh:694` ✅): *"the wire contract lives once in the protocol
owner."*

All four subject formats and both wildcards therefore live in **exactly one file**, and that file is
`agentruntime/protocol.go` — where three of the four already are (`protocol.go:20-22` ✅) and where
the scanner already names `agentruntime` as the owner. The inbox format, the inbox wildcard,
`InboxSubject` and `InboxStreamName` land there **additively** (§2.1), for the same reason
`contracts/fleetenvelope.md` §2 puts the spine there: *"This document adds to that file; it does not
rewrite it."* **`fleetbus` therefore holds ZERO subject literals**; it imports `agentruntime` and
cites the four renderers and the two stream names, exactly as `natsbus` does today
(`natsbus.go:38-39` ✅ — *"the kept producer-side alias, never a re-spelled literal (one concept, one
home)"*).

⚠️ **This reverses an earlier reading of this contract's own pair.** An earlier revision of
`fleetenvelope.md` §9 proposed DELETING `agentruntime/protocol.go` and moving subjects and stream
names into new libraries. The current spine does not: it is additive and states the three renderers
and `EventsStreamName` are *"already exist and are unchanged."* The invariant — one file, one
library — is identical either way; the FILE is not, and this document now names the one the spine
actually chose.

⚠️ **The scanner does not yet know the inbox exists.** Its `wire_patterns` array (`lib.sh:672-674`
✅) lists exactly six patterns: `EDEN_AGENT_EVENTS`, the three `agent.%s.<leaf>` formats and the
three `agent.*.<leaf>` wildcards — **`agent.%s.inbox`, `agent.*.inbox` and `EDEN_AGENT_INBOX` are
absent.** So on the day the inbox token lands, a duplicated inbox literal would pass a green gate.
The scanner must be extended in the SAME change that introduces the token. A gate that does not
know about the concept it is supposed to protect is the "green check that verifies nothing" this
repository treats as a defect class, not an oversight. Recorded as fork **B11**.

### 3.5 Security — who may publish on these subjects, stated plainly

**Stated plainly, because a contract that omits this reads as a guarantee.**

✅ The bus has **NO authentication, NO TLS and NO accounts today.**
`infrastructure/apps/eden/06-nats.yaml:27-44` ✅ is a plain ClusterIP Service on 4222/8222 and
`06-nats.yaml:75-78` ✅ starts the server with `--jetstream --store_dir --http_port` and nothing
else. **Any pod that can reach the Service can publish any subject and claim any identity in the
header.** No subject in §3.1 is protected from any workload in the namespace.

The consequence for this contract is a placement rule, not a mechanism:

> **Header validation runs at the TRUST BOUNDARY — the relay ingress and the archive reader — not
> in every pod.**

Validating in every pod would spread a check across N places while providing no additional
guarantee, since a pod that reaches the Service is already inside the perimeter the check would be
defending. Two boundaries are where an untrusted claim actually becomes consequential: the relay
ingress (where a message enters the tree and gets routed) and the archive reader (where a message
becomes the record). Both already have a reason to refuse, so neither is a new check.

The refusal itself belongs to the spine (`contracts/fleetenvelope.md` §2 — the header's own
validity rules); this contract decides only *where* it runs.

**Bus authn/authz is an open fork with a trigger, and its ONE home is the spine's fork F6**
(*"No auth, no TLS, no accounts today; any pod on the Service can claim any identity"*), whose
option (a) is exactly the placement stated above plus **NATS accounts before any non-Mateo
tenant.** §11 row **B9** is that same fork seen from the transport side and exists to state the
transport's obligations under each option — **it is not a second fork and it is not ruled
separately.** The trigger is written down because a security item with no trigger is a security
item that never fires.

## 4. Stream policy

### 4.1 The two declared policies

| STREAM | SUBJECTS | Retention/Discard | MaxBytes | MaxAge | MaxMsgsPerSubject | Duplicates |
| --- | --- | --- | --- | --- | --- | --- |
| `EDEN_AGENT_EVENTS` | `agent.*.events` | **DiscardOld** | **2 GiB** | **72h** | **200000** | **2m** |
| `EDEN_AGENT_INBOX` | `agent.*.inbox` | **DiscardNew** | **256 MiB** | **720h** | **20000** | **2m** |

Declared total **2.25 GiB** — under the **5 Gi** PVC (`infrastructure/apps/eden/06-nats.yaml:25`
✅ `storage: 5Gi`), and far under the **22.8 GiB** the server auto-sized itself to (§4.6).

`Storage: File` and `Replicas: 1` are **INHERITED from today's build and are not decided here.**
`natsbus.go:99` ✅ already sets `Storage: nats.FileStorage`; `06-nats.yaml:56` ✅ already sets
`replicas: 1`, with the manifest's own comment (`06-nats.yaml:6-7` ✅) recording that *"ONE replica
at v0 … a NATS cluster is a later concern behind the same `nats` Service name."* They appear in
`StreamPolicy` so a policy value is complete and comparable, never so they read as new rulings.

### 4.2 Why two streams and not one with two subjects

The two need **opposite discard policies** (§4.3). `Discard` is a stream-level setting in
JetStream, not a per-subject one, so one stream cannot hold both. The separation is forced by the
substrate, and it is also correct on its own terms: the two have different retention horizons
(72h against 720h) and different byte budgets, and a runaway on one must not evict the other.

### 4.3 DiscardNew on the inbox — fail-loudly applied to a retention policy

**Dropping the OLDEST relay message is an invisible hole in a causal chain; refusing the NEWEST is
a loud, handleable error at the sender.**

That is the whole reason. The write plane's messages are directives, and a directive's causal
chain is the audit trail (`contracts/fleetenvelope.md` §1: *"the chain of `CausedBy` edges IS the
audit trail"*). `DiscardOld` on that plane removes a link from the middle of a chain and leaves
every remaining link looking intact — the reader sees a `CausedBy` pointing at a `MessageID` that
is simply not there, with no signal distinguishing "evicted" from "never sent". `DiscardNew`
converts the same resource exhaustion into a `BackpressureError` at the publisher, in the caller's
own stack frame, where a decision can still be made.

This is the FAIL-NOT-SKIP rule of ADR-0020 applied to a retention setting: a limit that is reached
must be reached loudly.

`DiscardOld` on the **events** plane is the opposite call for the opposite reason, and it is
correct there: the events stream is a bounded window over a record whose durable home is the
archive (§8). Losing the oldest tail of a 72-hour window costs a replay depth, not a record.

### 4.4 `MaxMsgsPerSubject` IS the fleet-safety knob

The subject is **per-agent**. Therefore a per-subject cap makes one runaway agent **degrade
ITSELF** instead of evicting every other agent's history.

This is the single most important line in this section, because without it the two streams are
shared-fate: with only a stream-wide `MaxBytes` and `DiscardOld`, one agent emitting at ten times
everyone else's rate silently evicts the other agents' messages first — the loudest producer wins
and the quiet agents lose their history. `MaxMsgsPerSubject` bounds each agent's own slice, so the
failure is contained to the agent that caused it and is visible on that agent's own replay depth.

### 4.5 Who owns the stream — gap G12, and ADR-0022 §2 head-on

⚠️ **Today the wrong process owns it.** `EnsureStream` is called by the agent POD's composition
root (`natsbus.go:88-95` ✅ — *"the explicit, separate EnsureStream(ctx) step the composition root
calls once at startup"*), and its `AddStream` sets `Name`, `Subjects`, `Storage`, `Retention` and
`Discard` — **and nothing else** (`natsbus.go:96-102` ✅). So the **first pod to boot** creates the
fleet's stream with **no MaxAge, no MaxBytes and no MaxMsgs**, and every later pod tolerates what
it finds (`natsbus.go:103-110` ✅ treats name-in-use as a no-op). The fleet's retention policy is
therefore currently decided by a scheduling race.

**Decision: the CONTROLLER creates the streams.** The pod's call becomes `RequireStream` — a
`StreamInfo` read and a comparison that **FAILS THE POD AT BOOT if the stream is absent or its
limits differ, naming the stream** (and, on a mismatch, the field and both values). A pod never
creates and never repairs.

**ADR-0022 §2, head-on.** ADR-0022 §2 puts the supporting stack out-of-band under Argo, and this
decision has to be reconciled with it rather than around it:

> **The NATS SERVER is substrate and stays out-of-band under Argo. A STREAM inside it is this
> application's schema — the analogue of a database migration.**

The boundary is the same one the estate already draws for Postgres: the server is operated by
GitOps; the schema inside it belongs to the application that owns the data and is converged by
that application's reconciler. Putting a stream's limits in a Kubernetes manifest would put an
application schema in the operator's hands and split a versioned decision across two repositories.

### 4.6 Server flags are MANDATORY, and per-stream `MaxBytes` alone is not enough

✅ Measured: `"max_storage": 24495590400` — JetStream auto-sized itself to **22.8 GiB**, which is
**4.5×** its own 5 Gi PVC. The cause: `local-path` is an unquota'd host directory, so `df` inside
the pod reports the **node root filesystem**, and JetStream sizes its file store from what `df`
tells it.

Therefore the nats StatefulSet MUST carry:

```
--max_file_store=4GB
--max_memory_store=1GB
```

⚠️ **Neither flag is present today.** `infrastructure/apps/eden/06-nats.yaml:75-78` ✅ carries
exactly `--jetstream`, `--store_dir=/data/jetstream` and `--http_port=8222`.

**Per-stream `MaxBytes` alone is NOT enough.** The two policies in §4.1 bound the two streams this
contract declares — they say nothing about a third stream. **One hand-made stream would take the
node down**: created by hand or by a future adapter with no limits, it would grow into the 22.8 GiB
the server believes it has, fill the node's root filesystem, and take every workload on that node
with it. The server flag is the only bound that applies to a stream this contract has never heard
of. This is the same reasoning as §4.4 one level up: the per-object cap contains the object, the
substrate cap contains the objects nobody declared.

## 5. Delivery semantics, `MsgId` and dedup

### 5.1 ⚠️ The defect, named — gap G8

Three facts, each measured, that combine into a silent message loss:

1. `natsbus.go:126` ✅ — `nats.MsgId(strconv.FormatUint(envelope.Seq, 10))`. The dedup key is the
   envelope's `Seq`, and nothing else.
2. `Seq` is **per-session**, not global. `protocol.go:60` ✅ documents it as *"the agentsession
   transcript offset"*. Every agent's first event is `Seq=1`.
3. There is **ONE shared stream** capturing `agent.*.events` (`natsbus.go:41` ✅).

So two different agents publishing their `Seq=1` within the dedup window are, to JetStream, the
same message — and **one of them is silently dropped.** No error is returned to either publisher,
because `natsbus.go:124` ✅ reads `_, err = a.jetStream.Publish(...)`: **the `PubAck` is
discarded**, and `PubAck.Duplicate` is the one field that would have said so.

The comment above that call (`natsbus.go:112-113` ✅) describes the behaviour as *"exactly-once
de-dup"*. It is not exactly-once, and on a multi-agent stream it is not even correct.

### 5.2 Decision — a deterministic key that is unique forever

**`nats.MsgId(string(header.MessageID))`.** The key is the header's own `MessageID`, and the
`MessageID` is deterministic **by the spine's definition, not by this document's** —
`contracts/fleetenvelope.md` §2 states the three forms (observation, relay, lifecycle) and says the
field is *"the causal join key AND the JetStream dedup key."* This document cites that and does not
restate the forms; a key shape spelled in two contracts is a key shape that can diverge in one.

What `fleetbus` owns is the transport consequence, and it is two properties that are different and
both required:

- **unique forever** — this is what stops the §5.1 collision. Two agents at `Seq=1` no longer
  produce one key, because the agent id is part of it.
- **idempotent on republish** — this is what makes the archive-then-publish retry of §8 safe. A
  random key would give the first property and lose the second, and the second is the one an
  at-least-once transport depends on.

⚠️ **An earlier revision of this section carried an obligation that the spine has since discharged.**
It read that `fleetenvelope`'s `Minter` was a zero-argument mint and therefore could not produce
`<agentID>/<sessionID>/<seq>`. The current spine has no `Minter` port at all: it defines `MessageID`
itself as deterministic and names the three forms. The gap is closed, so it is **not** carried into
§11 as an open fork. `DedupKey(header)` survives in §2 as the one place the mapping from header to
`MsgId` is written down and testable without a server — a convenience with one home, not a
workaround for a missing port.

### 5.3 `PubAck.Duplicate` is READ, and it means different things on the two planes

| plane | duplicate outcome | reason |
| --- | --- | --- |
| `events` (READ) | **counted**, non-fatal, `Receipt.Duplicate == true`, `error == nil` | a re-published observation is the idempotency the key exists for; the record is already durable. |
| `inbox` (WRITE) | **LOUD typed `DuplicateDirectiveError`** naming the `MessageID` | **because a directive delivered zero times is a lost instruction.** On this plane, a suppressed publish and a successful one are indistinguishable to the sender unless the receipt is read. |

The asymmetry is the point. The same transport fact — "the server suppressed this" — is benign on
a log and is a lost instruction on a queue.

### 5.4 The claim, stated exactly

**At-least-once delivery with a deterministic dedup key.** Never app-layer exactly-once.

`Duplicates: 2m` is a **declared value with one home** (§2 `StreamPolicy.Duplicates`, §4.1's
table) rather than a server default nobody wrote down. It is the width of the window inside which
the deterministic key suppresses a republish; outside it, a republish lands again and the consumer's
own idempotency — keyed on the same `MessageID` — is what holds. Saying "exactly-once" would be
claiming a property the window's finite width cannot provide.

### 5.5 ⚠️ RETIRE THE FALSE GREEN

✅ `libs/go/agentruntime/natsbus/integration_test.go:49-52` documents
`TestIntegration_EmbeddedNATS_DurableReplayBySeq` as proving, verbatim: *"the MsgId==Seq de-dup
holds on a real JetStream."*

It runs on a **real** JetStream, and it is a genuine durability test. But it drives **exactly ONE
agent** — `agentruntimetest.AgentID`, a single constant — and one agent is **the single condition
under which the §5.1 collision is invisible.** With one agent on the stream, `Seq` *is* globally
unique, so the assertion passes with the defect fully intact.

The test is not wrong; its **claim** is. It proves replay-by-`Seq` for one agent. It does not
prove the dedup key is sound, and its comment says it does. That comment must be corrected in the
same change that fixes the key, and the test's claim narrowed to what it actually establishes.
This is the pattern this repository names explicitly: a check that silently does nothing is worse
than no check, because it is believed.

## 6. The two sequence spaces, and the history↔live stitch

**This is the section that matters most.** Every other section describes a policy; this one
describes the place where two independently-correct designs produce a defect when they meet.

### 6.1 The two spaces

| space | meaning | where it lives |
| --- | --- | --- |
| `Seq` | the per-**SESSION** transcript offset. Ordering, dedup, and the checkpoint's per-session cursor. STAYS on the envelope, unchanged, frozen. | `agentruntime.EventEnvelope.Seq` (cited, not redefined — the spine names THIS section as the cursor's home) |
| **stream sequence** | JetStream's **global position** in the stream. **It does not exist at publish time, so it is NEVER an envelope field.** It IS the SSE `id:` line and the resume cursor, read from `message.Metadata().Sequence.Stream`. | `fleetbus.StreamSeq`, `Agent.status.lastStreamSeq` (`contracts/agentfleet.md`), `manifest.cursor.streamSeq` (`contracts/agentcheckpoint.md`) |

The one-sentence test that separates them: **a publisher can compute `Seq` before it publishes and
cannot know the stream sequence until the server answers.** A value the producer cannot know is
not a producer-side field, and every attempt to make it one produces the bug in §6.4.

### 6.2 ⚠️ The frontend's preference is INVERTED for the cursor

✅ `apps/frontend/src/lib/gateway/sse.ts:192-193` reads, verbatim:

```
// Prefer the seq from the data payload (authoritative); fall back to the id: line.
const resolvedSeq = Number.isFinite(data.seq) ? data.seq : seq;
```

For **display and de-duplication within one session**, that preference is right: `data.seq` is the
transcript offset the UI orders by.

For the **resume cursor**, it is exactly backwards. The `id:` line carries the STREAM sequence; the
payload's `seq` carries the SESSION offset. Sending `data.seq` back as `Last-Event-ID` asks the
server to resume from a *stream* position that was computed as a *session* offset — which is §6.4's
bug, entered from the client side. The two uses must be separated: the payload's `seq` orders and
de-duplicates; the `id:` line, and only the `id:` line, resumes.

### 6.3 THE STITCH — one join point, no gap, no duplicate

```
GET /agents/{id}/history?from-turn=<n>     →  ... , nextCursor == manifest.lastStreamSeq
                                                        │
                                                        ▼
GET /agents/{id}/events?from-cursor=<streamSeq>  →  live tail from streamSeq+1
```

The history endpoint is served from the **archive** and returns `nextCursor` equal to the
manifest's `lastStreamSeq` — the stream position of the last event the archive contains. The client
then opens the live endpoint at that cursor, and the consumer starts at `cursor+1`.

**ONE join point. No gap, because the archive's last stream position and the tail's first are
adjacent by construction. No duplicate, for the same reason.** The property that makes it work is
that both halves are expressed in the SAME space — the stream sequence — which is possible only
because the archive records the stream sequence alongside the transcript offset.

🔶 **The transport-side cursor seam is not the one edenhttp has today.** `edenhttp.ResolveCursor`
(`libs/go/edenhttp/sse.go:17-33` ✅) reads `Last-Event-ID` or `?from-seq=` and returns a `uint64`
documented as *"the LAST SEEN sequence"* in the transcript-offset sense. The fleet needs a
stream-sequence cursor with a distinct query name (`from-cursor`) so the two spaces are not silently
interchangeable at the HTTP boundary. Whether that is a new function, a renamed one, or a second
parameter is fork **B12**. `edenhttp.CursorAll == 0` (`sse.go:15` ✅) is reused as the zero
convention either way, cited and not redefined.

### 6.4 ⚠️ THE VACUOUS TEST, NAMED — and the real failure mode

**All three source designs proposed the same test:** two AGENTS interleaved on one stream,
reconnect, assert the resumed set.

**That test cannot fail.** `natssse.go:112` ✅ opens the consumer with
`subject := agentruntime.EventsSubject(agentID)` — the consumer is **already per-agent
subject-filtered**. Agent B's events can therefore **never appear on agent A's stream at all**, so
the assertion "A's resumed set contains no B events" passes trivially, with the cursor bug fully
intact. Three independent designs proposed a test whose result is determined before the code under
test runs.

**The real failure mode is DUPLICATES, not foreign events.** `natssse.go:113` ✅ calls
`b.openConsumer(subject, lastSeq)`, and `openConsumer` (`natssse.go:157-163` ✅) turns that value
into `nats.StartSequence(lastSeq+1)` — **a STREAM position**. But `lastSeq` arrived as a
per-session transcript offset. The two agree only while the stream holds one session's events and
nothing else. Once **other agents advance the stream**, the stream sequence runs far ahead of any
one session's offset, so a reconnect at "session offset 40" seeks to **stream position 41** — far
BEHIND the client's true position — and the client is **flooded with a replay of everything since**.
The subject filter means the flood is all the client's own events, which is exactly why it reads as
a harmless duplicate rather than as a cursor fault.

**The non-vacuous assertion has two parts, and both are required:**

- **(a)** no-gap **AND** no-duplicate **across the history→live stitch** — the duplicate half is
  the half the vacuous test omits, and it is the half that fails.
- **(b)** **two SESSIONS inside ONE agent.** This is the topology that separates the two spaces
  while staying inside one subject filter: session 2's `Seq` restarts while the stream sequence
  keeps climbing, so a consumer that confuses them resumes at the wrong place. Two agents cannot
  produce this, because the filter removes the interference before the assertion sees it.

## 7. Backpressure — who is told to stop, and how loudly

### 7.1 On the bus

| plane | mechanism | who is told |
| --- | --- | --- |
| `inbox` | `DiscardNew` | the **SENDER**, with a loud handleable `BackpressureError` (§4.3) |
| `events` | `DiscardOld` + `MaxMsgsPerSubject` 200000 | **nobody** — and that is the design: one runaway agent degrades **only itself** (§4.4) |

### 7.2 In-process — `agentsession`, unchanged and cited

The harness-side backpressure is already built, already frozen, and this contract changes none of
it. It is recorded here because a reader tracing a slow consumer needs to know where the next
buffer is:

- Each subscriber gets a `chan Event` of `liveBufferSize = 256`
  (`libs/go/agentsession/broadcaster.go:11` ✅).
- `publish` **NEVER blocks**. On a full channel it sets `sub.demoted = true`
  (`broadcaster.go:68` ✅) and stops feeding that subscriber.
- The stream then **`catchUp`s** by re-opening a durable transcript replay from `nextSeq-1` and
  re-attaching (`libs/go/agentsession/stream.go:143-153` ✅ —
  `l.openReplay(ctx, l.nextSeq-1)` then `l.session.broadcaster.reattach(...)`).
- **Events are re-read from the durable transcript, never skipped.** A slow subscriber loses its
  place in the live tail and gets it back from the record; it never loses an event.

### 7.3 The SSE bridge

`fetchTimeout = 1s` per fetch (`natssse.go:34` ✅), so the pump loop wakes even on a silent stream.
`onFetchGap` (`natssse.go:197-213` ✅) branches exactly three ways:

| condition | action |
| --- | --- |
| clean disconnect (`ctx.Err() != nil`) | `return (true, nil)` — a client disconnect is a clean end of a long-lived stream, not a fault to propagate |
| timeout (`nats.ErrTimeout` / `context.DeadlineExceeded`) | emit `sse.Heartbeat()` if the cadence elapsed, and **keep pumping** |
| anything else | `sse.Comment(errors.KindOf(wrapped))` + return a wrapped **`KindUnavailable`** |

The first branch is the one that looks like a swallowed error and is not: `ctx.Err()` is the
disconnect signal, and the code says so at `natssse.go:192-194` ✅.

### 7.4 ⚠️ KNOWN UNFIXED RISK — the frontend reconnect

✅ `apps/frontend/src/lib/gateway/sse.ts:34-35, 53, 114-117` — the reconnect delay is
`retryMs = options.retryMs ?? 500`, applied as a **fixed 500 ms `setTimeout`**. There is **no
jitter, no cap and no backoff**, and the retry counter is used only to choose a status string.

**At fleet scale this is a self-inflicted thundering herd.** A gateway restart drops every open
stream at once; every client returns at the same 500 ms mark, in phase, and keeps returning in
phase until the gateway is up — which is the load pattern most likely to keep it from coming up.

**No slice addresses it.** It is recorded here rather than fixed here because it is a frontend
change and this is a transport contract — but it is recorded, because an unfixed risk that nobody
wrote down is indistinguishable from a risk nobody found. Fork **B8**.

## 8. Archive-then-publish — the ordering rule

### 8.1 The rule, stated exactly

> **THE PUMP ORDERS ARCHIVE-THEN-PUBLISH. The turn's archive segment is written BEFORE the
> publish.**

### 8.2 ⚠️ Why the opposite order loses data permanently

`libs/go/agentruntime/runtime.go:223-224` ✅ — the publish path is:

```go
if err := r.bus.PublishEvent(ctx, envelope); err != nil {
    r.observer.Logf(ctx, "agentruntime: agent %q publish event seq=%d error: %v", ...)
}
```

It **logs a publish error and continues**. Its own doc comment (`runtime.go:205-207` ✅) justifies
this as *"a transient publish failure is surfaced and the pump continues so the harness is not
blocked"* — and the reasoning holds only under an assumption the comment states one line earlier:
*"the durable JetStream append is the consumer's replay source."*

**The in-pod transcript is memory-only.** So when the publish fails, the event exists in exactly
one place — a process that is about to exit — and it is **permanently lost from every replay**. The
log line records that a message was lost; it does not recover it. Not blocking the harness is the
right call; making JetStream the *only* durable copy is what turns a transient fault into permanent
loss.

Archive-then-publish removes the assumption instead of removing the tolerance. The publish may
still fail and the pump may still continue, because the record is already durable elsewhere.

### 8.3 The consequence, under NATS-node-down

| property | value | why |
| --- | --- | --- |
| **RPO for the record** | **0** | the turn's segment is already durable in object storage before `PublishEvent` is attempted |
| **RTO** | node recovery | nothing is lost while the node is down; the live tail is unavailable, not gone |

Behaviour on the way down:

1. The pod's `PublishEvent` fails.
2. The pod raises the `ArchiveReachable` and `BusAttached` conditions and, after a **bounded retry
   window**, enters `PhaseDraining` (`agentruntime.HealthPhase`, cited — `protocol.go:119` ✅ for
   the value's provenance).
3. The controller marks the Agent **`Suspended`, NOT `Failed`.** The distinction is load-bearing:
   `Failed` is a terminal verdict about the agent's work; the agent's work is fine and its
   transport is not. A `Suspended` agent resumes; a `Failed` one is reaped.
4. The read plane's **live tail 503s**, but **HISTORY STILL WORKS** — because history is served
   from the **archive**, not from a JetStream replay.

**That last decoupling is deliberate, not incidental.** If history were served by replaying
JetStream, a bus outage would take the product's entire past with it and RPO=0 would be a claim
about a store nobody could read. Serving history from the archive is what makes the RPO=0 claim
observable by a user during the outage.

## 9. The telemetry consumer — Mateo's ruling of 2026-08-26

### 9.1 The ruling

> **Mateo, 2026-08-26**, verbatim selection: *"Bus consumer"* — one telemetry service consumes
> JetStream → OTel, and the same consumer feeds UI streaming.

This is consistent with the locked 2026-08-18 ruling (*"OTel: from day one — exporter as a log
consumer"*), and it is why the telemetry seam is here and not inside the emitting library.

### 9.2 The corollary that makes it work — cited, not restated

A consumer outside the emitting process **has no side lookups.** Every attribute a span needs must
be in the header, or the span cannot be built. `contracts/fleetenvelope.md` §5.4 states that
obligation and lists the fields that discharge it; this document does not restate them, because
one concept has one home.

What `fleetbus` owes in return is the subject of §9.3.

### 9.3 THE INVARIANT — a telemetry tap never joins a delivery consumer's queue group

**The telemetry consumer gets ITS OWN durable consumer and NEVER joins a delivery consumer's queue
group.**

A NATS queue group distributes each message to exactly **one** member. A telemetry tap that joined
a delivery consumer's queue group would therefore not "also see" the traffic — it would **take a
share of it**, and every message it took would be a product message the real consumer never
received. Nothing would error. The traffic would look healthy and a fraction of it would silently
go only to telemetry.

Stated as a testable property, which is the form that can actually fail:

> For a telemetry consumer T attached to stream S, and a delivery consumer D on the same stream:
> for every message M published to S, **D receives M** — and T's attachment changes neither the
> set nor the count of messages D receives.

`ConsumerPolicy.QueueGroup` (§2) exists so this is expressible in a value and assertable in a
test: **for any telemetry consumer, `QueueGroup` MUST be empty.** The durable name is fork **B1**;
the invariant is not open.

The same consumer feeds UI streaming per the ruling. That does not weaken the invariant — it
strengthens the reason for it, because the consumer now sits in front of a user-visible surface and
a silently-stolen message would be a missing event on someone's screen.

## 10. Conformance obligations

`fleetbustest.RunBusSuite(t, newBus)` is the exported **two-binding** conformance suite (08 §2): the
SAME property set over an in-memory fake and, in the `//go:build integration` lane, over a REAL
embedded nats-server with JetStream — never a mock of the NATS protocol (ADR-0016 §2, and the
`natsbus` integration precedent at `integration_test.go:4-19` ✅).

**Every obligation below carries the break-test that must be SEEN RED FIRST.** A test that has
never been observed failing is not evidence that the property holds; it is evidence that the test
ran. The break is applied to a COMMITTED tree and reverted — `git restore` on uncommitted work
destroys it.

| # | The obligation — what a test must PROVE | The break-test that must be seen RED first |
| --- | --- | --- |
| **O1** | Every subject literal and both stream names appear in exactly ONE library's production code; `fleetbus` contains none of them. | Re-spell `"agent.%s.inbox"` inside `fleetbus`'s own production code. `_xlib_wire_literal_scan` must FAIL naming both libraries. **It does not fail today** — the pattern list omits the inbox (fork B10), so this break-test is ALSO the acceptance test for extending the scanner. |
| **O2** | `RequireStream` FAILS THE POD AT BOOT when the stream is absent, and when any declared limit differs, and the error NAMES the stream (and, on a mismatch, the field and both values). | Delete the stream between `CreateStream` and pod boot → must be `StreamMissingError`. Then create it with `MaxAge` one hour short → must be `StreamPolicyMismatchError`. A pod that boots green in either case is the G12 defect intact. |
| **O3** | Two DIFFERENT agents publishing their `Seq=1` inside the `Duplicates` window both land, and both are readable. | Revert the dedup key to `MsgId(Seq)` (today's `natsbus.go:126` ✅) → the test must show ONE message on the stream where two were published. If it still shows two, the test is driving one agent and is the §5.5 vacuous shape again. |
| **O4** | `PubAck.Duplicate` is READ, and a duplicate on the WRITE plane is a loud typed `DuplicateDirectiveError` naming the `MessageID`, while a duplicate on the READ plane is counted and non-fatal. | Discard the `PubAck` (`_, err =`, today's `natsbus.go:124` ✅) → the write-plane duplicate assertion must fail because the outcome is no longer observable. This is the exact line that makes today's loss silent. |
| **O5** | Across the history→live stitch there is **no gap AND no duplicate**, asserted over **two SESSIONS inside ONE agent**. | Feed the live cursor from `EventEnvelope.Seq` instead of the stream sequence → the second session must produce DUPLICATES. §6.4: a two-AGENT topology cannot make this red, because `natssse.go:112`'s subject filter removes the interference first. **A test that stays green under this break is vacuous and must be rewritten, not trusted.** |
| **O6** | On `EDEN_AGENT_INBOX` at `MaxBytes`, the SENDER receives a typed `BackpressureError` and no message is lost from the middle of a chain. | Flip the inbox to `DiscardOldest` → publishes must start succeeding while earlier messages vanish, and the chain assertion (`CausedBy` resolves to a present message) must fail. That failure IS §4.3's "invisible hole", made visible once. |
| **O7** | A redelivered inbox message past its header `Deadline` is **acked and DROPPED**, and an `IntentFailed` naming the `MessageID` is published. | Remove the expiry branch → the message must redeliver until `MaxDeliver` and NO `IntentFailed` must appear. A silent stop at `MaxDeliver` is the failure this obligation exists to forbid. |
| **O8** | `MaxBytes` on `EDEN_AGENT_EVENTS` is hit **LOUDLY**, never as a silent `DiscardOld` gap that reads to a consumer as a short read. | Remove `MaxBytes` from the policy → **the test HANGS**, because the stream never reaches a limit and the assertion waits forever. **A hang is a FAILURE, not an inconclusive run**, and the suite must bound the wait and report it as one. A break-test whose red state is "still running" is the easiest kind to mistake for a pass. |
| **O9** | A malformed frame on `agent.<id>.control` is SURFACED as a typed error to the caller and never stalls a later message. | Restore the bare `return` of `natsbus.go:161-163` ✅ → the error assertion must fail while the "later messages still arrive" assertion still passes. That combination is exactly today's state: the port documentation at `ports.go:26-28` ✅ promises the first and the adapter delivers only the second. |
| **O10** | A telemetry consumer attached to a stream changes **neither the set nor the count** of messages the delivery consumer receives. | Give the telemetry consumer the delivery consumer's `QueueGroup` → the delivery consumer must receive strictly FEWER messages than were published. Nothing errors in that state, which is why the count, not an error, is the assertion. |
| **O11** | Under a dead bus, the turn's archive segment is already durable (**RPO = 0**), `GET /agents/{id}/history` still serves, the live tail 503s, and the controller marks the agent **Suspended, not Failed**. | Reorder the pump to publish-then-archive → kill the bus mid-turn → the history assertion must fail for the turn in flight. That is `runtime.go:223-224`'s ✅ current behaviour with a memory-only transcript, and it is permanent loss, not a delayed write. |
| **O12** | The nats StatefulSet declares `--max_file_store` and `--max_memory_store`, and the running server reports a `max_storage` at or under the declared file store. | Remove the flags from the manifest → the assertion must read back `24495590400` (22.8 GiB) ✅, the measured auto-size. This obligation is a MANIFEST assertion in `infrastructure/`, not a Go test, and it must be scheduled there (§12) — an obligation with no runner is an obligation that never runs. |

**Two properties are deliberately NOT asserted, and the omission is stated so it is not read as an
oversight.** There is no exactly-once assertion, because §5.4 claims at-least-once and a test
asserting a property the contract does not claim would either fail correctly or pass by accident.
And there is no assertion that a telemetry span carries a real `traceparent`: the spine records
(`contracts/fleetenvelope.md` §5.4 ⚠️) that nothing writes the trace carrier today and that the
existing `otelobserver` suite passes on a canned value — that break-test belongs to the spine, and
duplicating it here would create a second home for one refutation.

## 11. Open forks — what Mateo must rule on, or delegate

**Forks B1–B7 exist because a grep of all seven design artifacts for these parameters returned
ZERO hits.** They are the consumer knobs no source decided. Each row's recommendation is **this
document's proposal awaiting ruling — not a decision.**

| # | Fork | Options (recommendation first) | Blocks |
| --- | --- | --- | --- |
| **B1** | **The durable consumer NAME** for the inbox delivery consumer and for the telemetry tap. | (a) 🔶 delivery: `inbox-<agentID>`, per-agent; telemetry: `telemetry-events` and `telemetry-inbox`, fleet-wide. Reasoning: the filter is per-agent, so a per-agent durable makes `lastInboxSeq` a per-agent fact `Agent.status` already carries, and one agent's slow ack cannot stall another's. The telemetry taps are fleet-wide because a tap is one service. · (b) one fleet-wide delivery durable — rejected in the reasoning above, recorded so the rejection is visible. | the relay lane, the telemetry lane |
| **B2** | **`AckPolicy`** on the inbox durable. | (a) 🔶 `AckExplicitPolicy`. Reasoning: `AckAll` acknowledges a RANGE, so acking message N silently acks every directive below it — including ones the sidecar never processed. That is precisely the "delivered zero times" loss §5.3 forbids. · (b) `AckAllPolicy` for throughput — rejected: the inbox is a low-volume directive plane where throughput is not the constraint. | the relay lane |
| **B3** | **`DeliverPolicy`** on the inbox durable. | (a) 🔶 `DeliverByStartSequence` with `OptStartSeq = inboxSeq+1` on restore, `DeliverAll` on a first attach. Reasoning: symmetric with the events plane's existing rule (`natssse.go:157-163` ✅), and it is the only policy that makes the checkpoint's `inboxSeq` load-bearing rather than decorative. · (b) `DeliverNew` — rejected: it discards everything published while the pod was down, which is the failure the durable plane exists to prevent. | the relay lane, the checkpoint lane |
| **B4** | **`MaxDeliver`.** | (a) 🔶 **proposal: 5** — NOT a measured number. Reasoning: the header `Deadline` ack-and-drop is the real terminator (an expired directive is dropped loudly regardless of attempt count), so `MaxDeliver` is a secondary guard against a poison message and a small value is safe. · (b) unlimited, relying on the header `Deadline` alone — rejected: a message that fails to decode never ages out of *failing*, it only ages out of *mattering*. | the relay lane |
| **B5** | **`AckWait`.** | (a) 🔶 **proposal: 30s** — NOT a measured number. Reasoning: the sidecar acks when the directive is ENQUEUED onto the session, not when the turn completes, so `AckWait` bounds enqueue latency and must not be sized against turn duration. Sizing it against a turn would make every long turn look like a failed delivery. · (b) a value derived from a measured p99 enqueue latency once one exists — strictly better, and unavailable today. | the relay lane |
| **B6** | **`MaxAckPending`.** | (a) 🔶 **proposal: 64 per agent** — NOT a measured number. Reasoning: the in-process live buffer is 256 (`broadcaster.go:11` ✅) and the inbox is a far lower-volume directive plane; a smaller pending window makes backpressure appear at the durable consumer, where it is visible and handleable, rather than in the pod's memory, where it is not. · (b) match 256 for symmetry — rejected: symmetry between a high-volume observation buffer and a low-volume directive queue is a false analogy. | the relay lane |
| **B7** | **FlowControl / IdleHeartbeat.** | (a) 🔶 use a **PULL** consumer for the inbox, which makes both moot. Reasoning: flow control and idle heartbeats exist to rescue a PUSH consumer from a stall it cannot see; a pull consumer gets the same property from the bounded fetch loop the SSE bridge already runs (`natssse.go:34` ✅ `fetchTimeout = 1s`, `natssse.go:215-221` ✅). One mechanism, already proven in this estate. · (b) push with `FlowControl(true)` + `IdleHeartbeat(5s)` — two more knobs to tune for a property (a) gets structurally. | the relay lane |
| **B8** | **Frontend reconnect: fixed 500 ms, no jitter, no cap, no backoff** (`sse.ts:53, 114-117` ✅). A KNOWN UNFIXED RISK — no slice addresses it. | (a) 🔶 exponential backoff with full jitter and a cap, in the frontend slice. · (b) accept it at current scale and re-open at N concurrent streams — needs an N, and nobody has one. | nothing today; it is a fleet-scale availability risk (§7.4) |
| **B9** | **Bus authn/authz and TLS — the TRANSPORT SIDE of the spine's fork F6, not a second fork.** None exists (`06-nats.yaml:27-44, 75-78` ✅). **Trigger: before any non-Mateo tenant.** Ruled ONCE, in `fleetenvelope.md` §11 F6. | (a) 🔶 F6(a) — validate at the trust boundary now (§3.5), NATS accounts with per-agent credentials + subject permissions before any non-Mateo tenant, so the header's identity claim is checked against the connection's. · (b) mTLS only — encrypts the hop, authorizes nothing. · (c) NetworkPolicy only — a perimeter, not an identity. | nothing today; it blocks multi-tenancy absolutely |
| **B10** | **`_xlib_wire_literal_scan` does not know the inbox exists.** Its pattern list (`lib.sh:672-674` ✅) omits `agent.%s.inbox`, `agent.*.inbox` and `EDEN_AGENT_INBOX`, so a duplicated inbox literal would pass a green gate on the day the token lands. | (a) 🔶 extend the pattern list in the SAME change that introduces the token. · (b) leave it — an ungated invariant, which this repository treats as worse than an absent one. | the maintainability gate's honesty on the new token |
| **B11** | **The cursor seam at the HTTP boundary.** `edenhttp.ResolveCursor` (`sse.go:17-33` ✅) returns a value documented as *"the LAST SEEN sequence"* in the transcript-offset sense; the fleet needs a STREAM-sequence cursor. | (a) 🔶 a distinct `from-cursor` query name and a distinct function, so the two spaces cannot be silently interchanged at the boundary (§6.2's inversion is exactly that mistake). · (b) reuse `from-seq` with new semantics — rejected: an unchanged name with changed meaning is undetectable at every call site. | the gateway lane, the frontend lane |
| **B12** | **Where the transport port SHIPS.** The subject/stream names are settled (§2.1, additive to `agentruntime/protocol.go`); the port's packaging is not. `natsbus` is a sub-package of `agentruntime` today (`natsbus.go:18-20` ✅). | (a) 🔶 a top-level `libs/go/fleetbus` — which is what this document's own filename implies, since `_gate_contract_frozen` resolves `contracts/${EDEN_LIB_NAME}.md` (`lib.sh:1183-1184` ✅), so a `fleetbus.md` with no `fleetbus` library gates nothing. · (b) an `agentruntime/fleetbus` sub-package — cheaper, but then this document must be renamed or folded into `agentruntime.md`, and a contract no gate can reach is the defect class this document's status header opens on. | the gate's ability to bind to this document at all |

**Two forks an earlier revision of this document carried are CLOSED by the current spine, and are
recorded here as closed rather than deleted, so a reader of the earlier draft is not left looking
for them:**

- **The deterministic-`MessageID` production seam** — closed. The spine now defines `MessageID`
  itself as deterministic with three named forms (§5.2); there is no `Minter` port to amend.
- **The encoding of an expired-message report** — closed. `IntentFailed` is a real member of the
  spine's ten-member `Intent` (`contracts/fleetenvelope.md` §2, §6), so §9.2's failure notice needs
  no new taxonomy member and no ruling here.

Each open fork is recorded in `docs/architecture/open-decisions.md` as well, per `CLAUDE.md`'s rule
that an unmade decision lives there and never in prose alone. **B9 is recorded as a pointer to
`fleetenvelope` F6, not as a duplicate entry** — one decision, one home.

## 12. THE FREEZE QUESTION — for Mateo, and for nobody else

Freezing this contract is a `.claude/rules/git-process.md` §5 human gate. An agent may not exercise
it, and this document may not be edited to say it is frozen by anything other than Mateo's own
words quoted with a timestamp (§13 rule 4). The question is exactly this:

> **Do you freeze `fleetbus` v1 at the surface in §2 — four subjects with `agent.<id>.inbox` as the
> one new leaf token, added ADDITIVELY to `agentruntime/protocol.go` beside the three that are
> already there, and `control` left at ADR-0022 §4's at-most-once lifecycle plane; two streams
> with the §4.1 limits (`EDEN_AGENT_EVENTS` DiscardOld/2 GiB/72h/200000, `EDEN_AGENT_INBOX`
> DiscardNew/256 MiB/720h/20000, both `Duplicates: 2m`); the CONTROLLER as the streams' sole
> creator with the pod's `RequireStream` failing at boot on an absent or divergent stream;
> `--max_file_store=4GB --max_memory_store=1GB` as mandatory server flags; at-least-once delivery
> with a deterministic `MessageID` dedup key and `PubAck.Duplicate` read as a loud error on the
> write plane; the stream sequence as the ONLY resume cursor with the history→live stitch joining
> at `manifest.lastStreamSeq`; and the telemetry consumer holding its own durable with an empty
> queue group — accepting that the freeze commits the §5.5 test-claim correction, the §8.2 pump
> reordering, and the `natsbus`/`natssse` rework the §5 and §6 defects require?**
>
> **YES** → the surface is frozen, `.apibaseline` is recorded as the freeze witness,
> `phase-gate architecture` goes green, and the relay, controller, gateway and telemetry lanes
> start against a fixed target.
>
> **NO, with changes** → name the forks in §11 you are ruling differently, and the draft is amended
> and re-refuted before the question is asked again.
>
> **Answering also requires ruling B12**, because it is the only fork that changes a surface
> outside this document: it decides whether a library named `fleetbus` exists at all, and therefore
> whether `_gate_contract_frozen` can ever bind to this file. **B9 is NOT ruled here** — it is the
> spine's fork F6, ruled once, there. **B1–B7 and B10–B11 may be delegated**: each carries a
> recommendation and its reasoning, and none of them changes an exported surface. **B8 may be
> deferred but not dropped** — it is a known unfixed risk with no owning slice.

**Two gates ride on this answer.** The fleet ADR is reserved at **0030** (Batch B+C, 2026-08-18:
*"Fleet ADR takes number 0030 (fills the hole; messaging keeps 0032)"*) and does not exist on disk.
A new ADR is separately Mateo-gated (§5), so no agent has written it, and this contract cites the
2026-08-18 rulings directly rather than citing an ADR that is not there. And the two mandatory
server flags of §4.6 are an `infrastructure/` change — GitOps, Argo, the operator's repository —
which is a different gate from this contract's freeze and must be scheduled as its own, because a
frozen contract whose substrate flag never landed is a promise about a cluster state that is not
true.
