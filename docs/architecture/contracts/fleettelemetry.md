# Contract — fleettelemetry (DRAFT)

> Status: **DRAFT for negotiation** · 2026-08-26 · The fleet's telemetry tap: ONE durable
> JetStream consumer that reads the fleet's message planes, reconstructs OTel spans from them, and
> feeds the UI streaming read model from the same read. It is the 09 §4 step-1/2 artifact for the
> telemetry seam, written so four lanes — the OTel adapter, this bus consumer, the gateway SSE read
> model, and the fleet pods that stamp the carrier — build in parallel against a fixed target.
>
> **PRODUCERS:** the fleet pods. They STAMP the W3C carrier onto every message and export nothing
> (§4.4). **CONSUMER:** this one service. It is the only process in the fleet that speaks OTLP.
>
> **It CITES and never redefines:** the wire header and the four message types
> (`contracts/fleetenvelope.md` §2, DRAFT — note it is **additive to package `agentruntime`**, not a
> new library) · subjects, durability classes, stream policy, delivery
> semantics, dedup, the two sequence spaces, the history↔live stitch and backpressure
> (`contracts/fleetbus.md` §3-§8, DRAFT) · the telemetry consumer's queue-group invariant
> (`contracts/fleetbus.md` §9.3) · the harness event taxonomy (`contracts/agentsession.md`, FROZEN —
> `libs/go/agentsession/types.go:234-290`) · the telemetry port (`contracts/observability.md`,
> FROZEN — `Provider` is exactly 5 methods and is AT its ceiling) · the span and attribute
> vocabulary (`~/.claude/skills/eden-otel-debug/SKILL.md` §6). No second vocabulary is minted here.
>
> **The library does not exist.** There is no `libs/go/fleettelemetry`, no `oteladapter`, and no
> OTLP endpoint on any Eden workload. §1's TO BUILD table is the honest inventory; every claim in
> this document about a mechanism is a PROPOSAL until that table is empty.
>
> **Freezing is Mateo's gate and no agent exercises it** (`.claude/rules/git-process.md` §5, "a
> chart or contract PROMISE"; §13 rule 4 requires his verbatim words and a timestamp). §9 holds the
> exact questions — **eight**, two of which (`RootID` as the task key, and the `OTel` map versus
> typed W3C fields) were routed to this lane by name in `contracts/fleetenvelope.md` §11, so this
> document takes a position on them rather than deferring. This contract CANNOT freeze before
> `fleetenvelope` and `fleetbus` do; §9 Q8 states that order and why.
>
> Epistemic legend: ✅ ratified · 🔶 derived-but-settled · ⚠️ load-bearing assumption · 🧩 open fork.
> (This is the `contracts/` legend used by `agentruntime.md`, `edenhttp.md` and `codeinsight.md`.
> `contracts/fleetenvelope.md` uses the `docs/architecture/README.md` §3 legend instead, where ⚠️
> means "corrected". A tag in THIS document means what the line above says.)

## 1. Scope

🔶 `fleettelemetry` owns exactly two things, and the cohesion line around them is drawn tightly
because four documents meet here:

1. **The MAPPING** — message kind → OTel shape (span · span event · link) → span name → attributes.
   §3 is that mapping, exhaustive over every message kind and every `agentsession.EventKind` member.
2. **The UI streaming read model** — what a gateway serves from the SAME durable read, and how a
   live tail joins a history replay with no gap and no duplicate (§6).

It does **NOT** own — it consumes these and never redefines them:

**Statuses measured 2026-08-26** by listing
`/Users/mateo/code/.worktrees/eden-fleet-contracts/docs/architecture/contracts/` on branch
`docs/fleet-contracts` at `9fd66d9`. A CONTRACT existing and its LIBRARY existing are different
facts, and this table keeps them apart.

| Concept | Owner | Contract status | Library status |
| --- | --- | --- | --- |
| the wire header (`MessageHeader`) — `MessageID`, `CausedBy`, `InReplyTo`, `RootID`, `Hop`, `Intent`, `Actor`, `EmitTime`, `Deadline`, `OTel` — the three id grammars, the ten-member `Intent`, `MaxRelayHops`, and the four message types that embed it | `contracts/fleetenvelope.md` §2-§6 | **DRAFT, unfrozen** | **package `agentruntime`, ADDITIVE** — no separate library |
| the four subjects and three durability classes · stream policy · delivery semantics, `MsgId` and dedup · the two sequence spaces and the history↔live stitch · backpressure · archive-then-publish · **the telemetry consumer's queue-group invariant** | `contracts/fleetbus.md` §3 · §4 · §5 · §6 · §7 · §8 · **§9.3** | **DRAFT, unfrozen** | `libs/go/fleetbus` — TO BUILD |
| the CRD kinds, the controller, the reconcile loop, identity and the uid witness, the agent profile | `contracts/agentfleet.md` | **DRAFT, unfrozen** | TO BUILD |
| the harness `Event` taxonomy (`EventKind`, payloads, `Seq == transcript offset`) | `contracts/agentsession.md` | FROZEN | built |
| the telemetry port (`Provider`, `Exporter`, `Record`, `Event`, `Field`, `Plane`, `Severity`) | `contracts/observability.md` | FROZEN | built (`slogadapter` only) |
| the OTLP wire and the OTel SDK | `libs/go/observability/oteladapter` | — | **does not exist** |
| checkpoint composition, segment format, archive retention, `manifest.lastStreamSeq` | cited as `fleetcheckpoint.md` by `fleetbus.md` §6.1 and as `agentcheckpoint.md` by `fleetenvelope.md` §1 | **no document under either name** | TO BUILD |
| the git process, the merge gate, attribution | `.claude/rules/git-process.md` | current | — |

⚠️ **Three citations in the sibling drafts point at files that do not exist**, listed so no reader
of THIS document goes looking: `fleetbus.md` §6.1 cites `contracts/agentpod.md` (the kubernetes
control surface is `contracts/agentfleet.md`); and the checkpoint contract is cited under two
different names by the two siblings. Those are citations for THEM to correct, not this document.

**One word, two subjects — said once so no reader conflates them.** `libs/go/envelope` is **AES
envelope ENCRYPTION** (a DEK sealed under a KEK, ADR-0029, root `CLAUDE.md`). It has nothing to do
with a message envelope. `fleetenvelope` deliberately names its spine `MessageHeader` for exactly
this reason (`fleetenvelope.md` §1 item 1, ruling R2 of 2026-08-18). The two never meet on this wire.

### TO BUILD — none of this exists yet ✅

Measured 2026-08-26 against the working trees named in each row.

| # | item | owner lane | evidence it is absent |
| --- | --- | --- | --- |
| 1 | `libs/go/observability/oteladapter` — an `Exporter` over OTLP; the ONLY package allowed to import `go.opentelemetry.io/otel*` | OTel-adapter lane | `ls libs/go/observability/` returns one adapter directory: `slogadapter/`. **No span can leave any process today.** |
| 2 | real W3C propagation | OTel-adapter lane | `libs/go/agentruntime/otelobserver/otelobserver.go:64-92` — `Inject` copies a map out of a private context key and `Extract` filters a map into it. Neither parses nor mints a `traceparent`. **A green `otelobserver` test is evidence of nothing.** |
| 3 | `OTEL_EXPORTER_OTLP_ENDPOINT` on any Eden workload | infrastructure lane | `grep -rn OTEL_EXPORTER_OTLP_ENDPOINT infrastructure/apps/eden/` → zero hits across 13 manifests. |
| 4 | a homelab→cloud OTLP path, and a Tempo datasource in the cloud Grafana | infrastructure lane | recorded 2026-08-18 in `eden-otel-debug/SKILL.md` §1-2; the homelab `eden` namespace has no observability stack (removed 2026-08-09). ⚠️ Not re-measured for this document — re-verify before relying on it. |
| 5 | `libs/go/fleetbus` — the transport library this consumer binds | fleet-bus lane | **The CONTRACT exists** (`contracts/fleetbus.md`, 944 lines, DRAFT, branch `docs/fleet-contracts`) and is cited throughout this document. **The LIBRARY does not**; `phase-gate architecture` is RED by design until Mateo freezes the contract. |
| 6 | the `MessageHeader` additions to package `agentruntime` | fleet-envelope lane | `contracts/fleetenvelope.md` is DRAFT. **There is no `libs/go/fleetenvelope`** — §2 of that draft reads *"Package `agentruntime`. Every symbol below is additive"*, so the header lands in the EXISTING library and its `.apibaseline` is re-recorded (that draft's §8.1). |
| 7 | `libs/go/fleettelemetry` — this library | this lane | this document is the only artifact. |
| 8 | a fleet stream carrying a fleet message | fleet lane | `fleetenvelope.md` §7 records the once-only window as OPEN: 0 streams, 0 messages, no bucket. |

**The rule this table exists for** (`.claude/rules/git-process.md` opening line): *state what
EXISTS*. A document that describes unbuilt machinery as a property of the system is a green check
that verifies nothing.

## 2. Construction (the spine)

```go
// Package fleettelemetry is the Eden agent fleet's telemetry tap: one durable bus consumer that
// reconstructs OTel spans from the fleet's message planes and feeds the UI streaming read model
// from the same read. It is the ONLY process in the fleet that speaks OTLP (Mateo, 2026-08-26).
//
// Module: github.com/gophersys/libs/go/fleettelemetry  (go 1.26)
// HNS-1 slug: fleet-telemetry. Config/Deps are the idiomatic Go type names rule 11 exempts.
//
// It imports fleetenvelope (the header), agentsession (the transported taxonomy) and
// observability (the port). It NEVER imports nats.go — fleetbus binds the EventStream port — and it
// NEVER imports go.opentelemetry.io/otel* — oteladapter is the only import site of the SDK
// (observability.md §6 rationale 2; eden-otel-debug SKILL.md §5 "layer rule, non-negotiable").
package fleettelemetry

func New(configuration Config, dependencies Deps) (*Consumer, error)
```

🔶 `New` is **PURE** (10 §4): no I/O, no dial, no clock read, no env read, no subscription. It
validates `Config` and `Deps` and returns a typed `*ConfigError` (`errors.KindInvalid`) naming the
offending field, so the composition root fails fast and loud. All I/O lives in `Run(ctx) error`,
which is called once per `Consumer` and owns every goroutine it starts (the `agentruntime.Run`
precedent, `contracts/agentruntime.md` §5).

```go
// Config is the immutable, fully-resolved input. It holds NO port and NO live handle. It names no
// subject, no stream and no wildcard — those are fleetbus's (§1, and §5's literal rule).
type Config struct {
	ServiceName   string        // the consumer's own OTel service.name; required
	Durable       string        // the durable consumer name; required, and NEVER shared (§5)
	FlushBatch    int           // envelopes per Flush-then-Ack unit; 0 == a stated default
	AckWait       time.Duration // redelivery timeout; MUST exceed ExportBudget (§5)
	MaxAckPending int           // in-flight ceiling; bounds reconstruction memory (§5)
	ExportBudget  time.Duration // bounded retry window; on expiry Run FAILS loudly (§5.5)
	TurnIdleLimit time.Duration // a turn span idle this long is closed as abandoned (§4.5)
	CauseWindow   int           // MessageID→span-id entries retained for parenting (§4.3)
	UndecodableMax int          // undecodable messages per window before Run FAILS (§5.4);
	                            // required, no default — a default is how a schema break goes quiet
}

// New REFUSES, at construction, three configurations that would fail silently in production:
//   - a non-empty ConsumerPolicy.QueueGroup           -> the fleetbus §9.3 invariant (§5.1)
//   - AckWait <= ExportBudget                          -> the durable fights the retry loop (§5.5)
//   - an empty Durable or a zero UndecodableMax        -> no safe default exists for either
// Each is a *ConfigError naming the offending field. None is a warning.

// Deps is the injected hexagon. Every field is required; a nil port is a New-time ConfigError.
type Deps struct {
	Events    EventStream            // the durable read of the events plane; fleetbus binds it
	Telemetry observability.Provider // the FROZEN 5-method port (observability.md §2)
	Clock     Clock                  // the consumer's ONLY time source
}
```

🧩 **`Deps` gains a `Tail` port if and only if §9 Q1 selects topology β.** A port whose existence
depends on an unmade ruling does not belong in a spine presented as fixed, so it is described in
§6.2 and is deliberately absent here.

### The ports (consumer-defined, ≤5 methods — 10 §9)

```go
// EventStream is the SHAPE OF THE NEED and nothing more: ONE durable, non-queue-group read of the
// events plane. fleetbus owns everything behind it — the subject, the stream, the ConsumerPolicy,
// the dedup key, the ack discipline, the two sequence spaces (contracts/fleetbus.md §3-§6). This
// port does not restate any of it. Two methods.
type EventStream interface {
	// Consume opens the telemetry consumer's OWN durable consumer on the events stream and calls
	// deliver for each message until ctx ends. A non-nil return from deliver means "do NOT ack" —
	// the convention fleetbus already uses on SubscribeInbox (fleetbus.md §2) — which is how §5.3's
	// nak-and-retry is expressed without this library touching the transport.
	//
	// The fleetbus.Delivery it hands over is CITED, never redefined: it already carries StreamSeq
	// (the global position), Redelivery (>1 means the durable is retrying), Age, Ack and Nak
	// (fleetbus.md §2).
	Consume(ctx context.Context, deliver func(fleetbus.Delivery[fleetenvelope.EventEnvelope]) error) error

	// DestinationTemplate returns the SUBJECT TEMPLATE this consumer reads, for the bus span name
	// and the messaging.destination.name attribute. It is an ACCESSOR, not a literal:
	// fleettelemetry may not spell a subject wildcard in its own source (§5.1), so the one home
	// renders it and this port hands it over.
	DestinationTemplate() string
}

// Clock is the minimal injected time source (mirrors observability.Clock).
type Clock interface{ Now() time.Time }
```

⚠️ **`fleetbus.Subscriber` does not satisfy this port today, and the gap is specific.** Its four
methods are one per subject (`fleetbus.md` §2): `SubscribeEvents` is documented as opening an
**EPHEMERAL** per-agent consumer with `AckNone` and takes **no `ConsumerPolicy`**, while
`SubscribeInbox` is the only method that accepts one and it is inbox-only. `fleetbus.Delivery`
says so in its own words — *"Ack/Nak are nil on the events plane (AckNone) and non-nil on the inbox
plane."* But `fleetbus` §9.3 requires the telemetry consumer to hold **its own durable** with an
empty `QueueGroup`, and §5.4's at-least-once claim hands the consumer an idempotency obligation
that a `nil` `Ack` cannot discharge. **There is no method to open that consumer.** This is not a
defect this document may fix — it is `fleetbus`'s surface. Recorded as fork F10 and routed there.

⚠️ **`Telemetry` is the frozen `observability.Provider` itself, not a narrower consumer port.**
`agentruntime` defines its own 4-method `Observer` because its need is narrower than the port
(`contracts/agentruntime.md` §8, third fork). Here the need IS the port: this library emits, scopes,
inherits fields and flushes. `Provider` is **exactly 5 methods and is at the negotiated ceiling**
(`observability.md` §6 rationale 1; `libs/go/observability/provider.go:12-40`) — **no method can be
added to it**, which is precisely what forces §5's flush-then-ack design.

## 3. The mapping table

This is the centre of the document. Rules the table obeys:

- **A span name uses the SUBJECT TEMPLATE, never a concrete id** (`eden-otel-debug/SKILL.md` §6).
  Identity rides as attributes. Never widen an id into a span name.
- **A cross-pod messaging edge is a LINK given at span CREATION** (`WithLinks`), never `AddLink`.
  This is `fleetenvelope.md` §5.3's rule, cited: links are the semconv default correlation
  mechanism, it is NOT RECOMMENDED to parent a Process span on the message-creation context, and
  head sampling cannot see a link added later (`trace/span.go:37-40` at tag `trace/v1.45.0`).
- **Attributes reuse the existing vocabulary**: `agent.id`, `session.id`, `turn.id`, `turn`, `seq`,
  `messaging.message.id`, `messaging.destination.name` (SKILL.md §6), plus the semconv names
  `messaging.message.conversation_id`, `messaging.operation.name`, `messaging.operation.type`.
- **Every attribute comes from a header field, an envelope field, or the transported
  `agentsession.Event`.** A consumer outside the emitting process has no side lookups —
  `fleetenvelope.md` §5.4 is explicit that this is why the header is fat.
- **No secret in an attribute.** `Field.Value` is a `Valuer`; a secret enters only as its redacted
  projection via `observability.Any` (`observability.md` §6 rationale 4).

### 3.0 ⚠️ Where every attribute comes from — re-sourced against the CORRECTED header

`fleetenvelope` was corrected at sibling commit `9fd66d9`, and the correction removed four fields
an earlier revision of THIS table drew from. The mapping is re-walked here field by field so no row
sources a value that is not on the wire.

| attribute | source | note |
| --- | --- | --- |
| `messaging.message.id` | `MessageHeader.MessageID` | ✅ **Settled by the correction, not an open fork.** `MessageID` is globally unique, DETERMINISTIC, and IS the JetStream `MsgId` (`fleetenvelope.md:100-109`). SKILL.md §6's older text maps this to `Seq`; that text is now stale and is amended in the same change (§9 Q3). |
| `messaging.message.conversation_id` | `MessageHeader.RootID` | ✅ **Settled.** `fleetenvelope.md` §5.1: *"`RootID` IS the task id"* — constant along the chain, already mapped to this semconv name. There is **no `TaskID` field** and this document does not invent one (§9 Q4 takes a position on whether there should be). |
| `agent.id` | `EventEnvelope.AgentID` / `ControlMessage.AgentID` / `RelayMessage.From` | ⚠️ **NOT a header field.** The corrected `MessageHeader` has no `AgentID`; it sits on each message type. |
| `session.id` | `agentsession.Event.SessionID` (`types.go:298`) on the events plane; `RelayMessage.SessionID` / `ControlMessage.SessionID` elsewhere | ⚠️ `EventEnvelope` carries no `SessionID` of its own — the transported Event does. |
| `seq` | `EventEnvelope.Seq` | ⚠️ NOT a header field, and **not the replay cursor** — `fleetenvelope.md` §2 says so in the type's own comment. The cursor is the stream sequence (`fleetbus.md` §6). |
| `turn` / `turn.id` | `agentsession.Event.Turn` / `Event.TurnID` (`types.go:299-301`) | ✅ **The two-homes question is CLOSED by the correction.** `fleetenvelope.md` §4.1: *"There is no turn ordinal on the header, and that is deliberate … Putting it on the header would be a sixth home."* One home, and it is the Event. |
| `hop` | `MessageHeader.Hop` | 🔶 **Relay depth from the root, NOT tree depth** — say which, or the attribute lies. It is the loop-breaker counter against `MaxRelayHops = 32`. |
| `intent` | `MessageHeader.Intent` | The ten-member closed vocabulary (`fleetenvelope.md` §6). An `EventEnvelope` always carries `IntentObservation` — *"the pump, EVERY agentsession Event"*. |
| `actor.kind` / `actor.id` | `MessageHeader.Actor` | Three kinds: `ActorHuman`, `ActorAgent`, `ActorSystem`. `Actor.ID` carries the `break-glass:<user>` form, which is the whole audit mechanism for the bypass — it must reach an attribute. |
| `caused.by` / `in.reply.to` | `MessageHeader.CausedBy` / `InReplyTo` | `CausedBy` is ONE hop up (the edge); `InReplyTo` pairs a response with its request and may be many hops away. §4.3 uses `CausedBy` for parenting. |
| `messaging.destination.name` | `EventStream.DestinationTemplate()` | An accessor, never a literal (§5.1). |

⚠️ **Four attributes an earlier revision of this table carried are DELETED, and the deletion is
stated rather than silent.** `agent.address` and `agent.parent.address` had no source: the
corrected `fleetenvelope.md` §4.2 is titled *"There is NO tree address, and this reverses my own
first draft"*, and its third reason is that the `eden-otel-debug` skill (`SKILL.md:114`)
**explicitly forbids a flat tree-path attribute**. Proposing them was the exact thing the skill
forbids, and withdrawing them is a correction, not a concession. **`Hop` is the honest depth signal
that survives** — relay depth, not tree depth. The tree itself lives in `Agent.spec.parentRef` and
the controller-rendered legal child set (`fleetenvelope.md` §4.2), which a bus consumer cannot see.
Likewise `task.id` is deleted in favour of `RootID`, and the header `turn` in favour of the
Event's.

### 3.1 Transport and scaffolding

| message kind | OTel shape | span name | attributes | notes |
| --- | --- | --- | --- | --- |
| one delivery BATCH (the `Consume` callback's unit of work) | **span** (timed), `PlaneSelf` | `receive <destination-template>` | `messaging.destination.name`, `messaging.operation.name=receive`, `messaging.operation.type=receive`, `messaging.batch.message_count` | 🔶 The ONLY per-hop bus span, and it is O(batches), not O(messages). One span per envelope is unaffordable: `text-delta` is token-by-token (`types.go:247`). The name is COMPOSED from the accessor — the wildcard is never a literal here (§5). |
| each message in that batch | **link at creation** on the `receive` span | — | `messaging.message.id`, `messaging.message.conversation_id` | 🔶 `trace.Link{SpanContext, Attributes}` — an application id alone cannot form a link, so the link needs a real span context, parsed from `MessageHeader.OTel["traceparent"]`. When the carrier is empty (valid and unparented, `fleetenvelope.md` §2) or names a span this consumer never exported, the link is **OMITTED, never dangled** (§4.3). |
| one `session.id`, first event → terminal | **span** (timed), `PlaneAgent` | `session` 🧩 | `agent.id`, `session.id`, `messaging.message.conversation_id`, `hop` | 🧩 The session's root span. `fleetenvelope.md` §5.3, cited: *"Each session opens its own root span joined by the propagated context, so the task reads as one trace while no single span is held open for the task's life."* **The NAME is this document's proposal** — `session` is not in the skill's list. §9 Q3. |
| one `agentsession.Event.TurnID`, within a session | **span** (timed), `PlaneAgent`, child of `session` | `turn` | `agent.id`, `session.id`, `turn.id`, `turn` | ✅ Already the skill's own name: `{ span.session.id = "<sid>" && name = "turn" && duration > 30s }` (SKILL.md §4). The boundary is the Event's `TurnID`, which `fleetenvelope.md` §4.1 confirms is the ONE home of turn. Closes on a terminal, the next `TurnID`, or `TurnIdleLimit` (§4.5). |

### 3.2 `EventEnvelope` — one row per `agentsession.EventKind`

Read from `libs/go/agentsession/types.go:244-260` (the const block) and `:264-281` (the token
table). Sixteen members, append-only, never reordered. Every row below is a **span event on the
open `turn` span** unless the notes say otherwise, named by the member's stable lower-kebab token —
which is the vocabulary the skill already sanctions as a name (SKILL.md §6, first row).

| `EventKind` | token | OTel shape | span name | attributes (beyond the shared set) | notes |
| --- | --- | --- | --- | --- | --- |
| `EventSessionState` | `session-state` | span event on **`session`** | `session-state` | `session.state.from`, `session.state.to` | Session-scoped: it can arrive before any turn is open. It also DRIVES the `session` span — the first one opens it. |
| `EventMessageStart` | `message-start` | span event on `turn` | `message-start` | `message.role` | OPENS the `turn` span when `Turn` is new. |
| `EventThinkingDelta` | `thinking-delta` | **neither** — folded | — | folded onto `turn` as `thinking.delta.count`, `thinking.bytes` | ⚠️ Token-by-token. One record each is thousands per turn and destroys the store. Folding is a deliberate loss of per-delta granularity, stated rather than discovered. Reasoning content is redaction-eligible (`types.go:246`) — the TEXT is never an attribute, only its size. |
| `EventTextDelta` | `text-delta` | **neither** — folded | — | folded onto `turn` as `text.delta.count`, `text.bytes` | Same reasoning. The text itself lives in the transcript, not in a span. |
| `EventMessageEnd` | `message-end` | span event on `turn` | `message-end` | `message.role` | Closes the message; the folded delta counters are stamped here. |
| `EventToolStart` | `tool-start` | span event on `turn` | `tool-start` | `tool.name`, `tool.call.id`, `tool.grant.id` | `GrantID` ties the call to the allowlist entry that permitted it — the 07 §3 audit chain (`types.go:351-354`). |
| `EventToolUpdate` | `tool-update` | **neither** — folded | — | folded onto the matching `tool-end` as `tool.update.count` | Streamed partial results; volume, not information. |
| `EventToolEnd` | `tool-end` | span event on `turn` | `tool-end` | `tool.name`, `tool.call.id`, `duration`, `error`, `tool.update.count` | ✅ Duration rides as an ATTRIBUTE, exactly as SKILL.md §5's own `Emit` example does (`observability.Dur("duration", tool.Elapsed)`). Correlated to `tool-start` by `CallID`. `error` via `observability.Err` (redaction-safe). |
| `EventPermissionRequest` | `permission-request` | span event on `turn` | `permission-request` | `permission.request.id`, `tool.name` | The human/policy gate (ADR-0025). The WAIT is measured on the resolved row, not as a span duration. |
| `EventPermissionResolved` | `permission-resolved` | span event on `turn` | `permission-resolved` | `permission.request.id`, `permission.decision`, `permission.by`, `permission.wait` | `permission.wait` = resolved `Event.Time` − request `Event.Time`. `permission.by` is an audit identity, never a credential. |
| `EventUsage` | `usage` | span event on `turn` | `usage` | all four token kinds from `UsageMeter` | ⚠️ Token and cost figures ride as **Fields**, never as an OTel metric: the port has no `Counter` and no `Histogram` (`observability.md` §6 rationale 1; SKILL.md §5). §9 Q5 asks whether metrics are in scope at all. |
| `EventResult` | `result` | span event on `turn` | `result` | the authoritative `TokenLedger` fields | TERMINAL. Closes `turn` then `session` with `Outcome{Err: nil}`. |
| `EventFailed` | `failed` | span event on `turn` | `failed` | `error` (typed reason), the ledger | TERMINAL. Closes `turn` and `session` with `Outcome{Err: <reason>}` — the ONLY shape that sets span status error. |
| `EventAborted` | `aborted` | span event on `turn` | `aborted` | `terminal.by`, the ledger | TERMINAL. Closes with `Outcome{Err: nil}` plus `terminal.reason=aborted`. **An abort is not a fault** — recording it as an error makes every human stop look like an incident. |
| `EventExtension` | `extension` | span event on `turn`, or on `session` if no turn is open | `extension` | `extension.bytes` **only** | ⚠️ The payload is opaque harness bytes and is redaction-eligible (`types.go:314-319`). Its SIZE may be an attribute; its CONTENT may never be. |
| `EventThinkingProgress` | `thinking-progress` | **neither** — folded | — | folded onto `turn` as `thinking.tokens.estimate` (last value wins) | A pre-message heartbeat. `MessagePayload.Tokens` is an ESTIMATE for a live indicator, **never a billed figure** (`types.go:341-344`) — the billed number is `usage`. |

`IsTerminal()` (`types.go:326-328`) is the closing predicate: exactly one of `result` / `failed` /
`aborted` ends a session. It is `agentsession`'s, cited, never re-derived here.

### 3.3 The other three message types

| message kind | OTel shape | span name | attributes | notes |
| --- | --- | --- | --- | --- |
| `RelayMessage` (write plane) | **span** (timed), `PlaneAgent` | `relay` 🧩 | `agent.id` (= `From`), `relay.to`, `relay.direction`, `intent`, `hop`, `caused.by`, `in.reply.to`, `actor.kind`, `actor.id`, `team.id` | 🧩 The tree edge, and the ONLY place delegation is observable. `Intent` is `fleetenvelope`'s closed TEN (`fleetenvelope.md` §6); `Intent.Direction()` gives `relay.direction` as real routing behaviour, not a lookup table. `actor.id` carries the `break-glass:<user>` form — it must reach an attribute, because an unrecorded bypass is worse than a recorded one. **No address attribute**: a node is addressed only by its `AgentID` (§3.0). **The span NAME is this document's proposal** — §9 Q3. |
| `ControlMessage` (control plane) | **none today** | — | — | ⚠️ Core NATS, no durability (`fleetenvelope.md` §2; ruling R3 of 2026-08-18, *"control (core NATS, ADR-0022 §4 preserved, lifecycle+break-glass only)"*; the type's home is `contracts/agentruntime.md` §4.2). A durable consumer **cannot read it** — core NATS delivers only to live subscribers. So a control verb is visible to telemetry ONLY through its EFFECT on the events plane. Making it a span requires the PUBLISHER to export, which contradicts the bus-consumer ruling. Fork F5. |
| `Heartbeat` (health plane) | **none** | — | — | ⚠️ Core NATS, best-effort liveness. A heartbeat is a GAUGE, and the port has no gauge. Liveness stays where it already works: the orchestrator Probes `Phase` + `LastSeq` (`contracts/agentruntime.md` §4.3). Putting heartbeats on the trace plane would be a second liveness home. |

### 3.4 ⚠️ One open shape question the table cannot settle alone — and one now closed

**OPEN — span event vs zero-duration span.** `observability.Emit` produces a `Record{Event,
Resource, TraceID, SpanID}` (`observability.md` §2) — a record CORRELATED to a span, i.e.
structurally a span event. But SKILL.md §4's TraceQL pattern `{ name = "tool-end" && status =
error }` matches a SPAN name in TraceQL, not an event name. **The `Record`→OTel mapping is
`oteladapter`'s and `oteladapter` does not exist** (§1 TO BUILD 1), so this document states the
shape it intends — span events — and records the tension as fork F1 rather than settling another
library's design. Either rendering keeps every name and attribute in this table unchanged.

**CLOSED — `messaging.message.id` = `MessageID`, not `Seq`.** This was an open fork in an earlier
revision of this document; the `fleetenvelope` correction at `9fd66d9` settled it. SKILL.md §6 maps
the attribute to `Seq`, which was correct when `Seq` was the only id and JetStream's `MsgId == Seq`
(`libs/go/agentruntime/natsbus/natsbus.go:126`) — and `fleetbus.md` §5.1 shows that mapping is
itself the source of a silent multi-agent message loss. The corrected header mints a `MessageID`
that is globally unique, DETERMINISTIC, and IS the `MsgId`; semconv defines
`messaging.message.id` as *the system identifier for the message*, which `MessageID` is and `Seq`
is not. **The SKILL.md §6 line is now stale text** and is amended in the same change (§9 Q3).

## 4. Task = trace

> **Mateo, 2026-08-26** (AskUserQuestion decision prompt, interactive session `f9c810a8`),
> verbatim: *"Task=trace across the whole tree — One trace spans the entire orchestrator task
> through every delegated session."*

### 4.1 What a trace is — re-sourced against the corrected header

✅ One **trace** = one **`RootID`**, not a `TaskID`. `fleetenvelope.md` §5.1 rules it in one
sentence — *"`RootID` IS the task id"* — because `RootID` is *"the root of the whole chain: the
human action, the schedule, or the orchestrator's assignment"*, it is **constant along the chain**,
and it is already mapped to `messaging.message.conversation_id`. **There is no `TaskID` field and
this document does not invent one**; naming a second would be a second home for one fact (10 §9).

One **`session` span** is the root of one harness session's contribution to that trace; one
**`turn` span** is one turn inside it. No span is held open for the task's life — §4.4 is why.

The joining mechanism is `fleetenvelope`'s and is cited, not restated (`fleetenvelope.md` §5.3):
per-session root spans joined by the propagated context · cross-pod is a LINK, never a parent,
attached at creation · `RootID` as an indexed attribute, deliberately NOT derived from the trace id
so a dropped trace tail degrades to a `RootID` search rather than to nothing.

⚠️ **This paragraph replaces a WRONG one.** An earlier revision of this document asserted that
`fleetenvelope` made `TaskID`, `TraceParent` and `TraceState` first-class typed fields, and that
the task-id shape was therefore settled. The correction at sibling commit `9fd66d9` reversed all
three: `RootID` carries the task, and the W3C pair rides inside `OTel OTelContext` — a map.
**Both reversals are now live forks that the sibling lane assigned to THIS lane by name**
(`fleetenvelope.md` §11, owner column: F2 → *"the telemetry lane"*, F3 → *"the OTel lane"*).
§9 Q4 and Q5 take positions on them rather than deferring.

### 4.2 What the pods do, and do not do

🔶 A fleet pod **stamps the W3C carrier** — `MessageHeader.OTel["traceparent"]` and
`["tracestate"]` — on every message it mints or relays, and PRESERVES `RootID` unchanged along the
chain. A pod **exports nothing**: no OTLP connection, no SDK, no collector sidecar. A propagator is
cheap; an exporter in every pod is N OTLP egress paths from a namespace that has no observability
stack.

⚠️ **Nothing writes that carrier today, and the sibling draft states the break-test.**
`fleetenvelope.md` §5.4: *"`otelobserver.Inject` only copies a map previously stashed under a
private context key; nothing ever writes that key and nothing generates a traceparent, so
`EventEnvelope.OTel` is `{}` in production — while `agentruntimetest.FakeObserver` injects a canned
traceparent, so the suite passes throughout. … The break-test is exactly this: assert a real
traceparent on a published envelope and watch it fail today."* This document's §7 I1 and I4 are
unprovable until that break-test goes red and is then made green.

### 4.3 ⚠️ How the consumer parents a span, and why the carrier's span-id is only advisory

This is the load-bearing derivation of the whole design, and getting it wrong produces a Tempo full
of dangling references.

If the pods do not export, then **any span-id a pod mints names a span that exists nowhere.** A
trace whose parent or link points at an unexported span-id is worse than an unparented trace: it
looks joined and is not. So:

- ⚠️ **The carrier's TRACE-ID half is authoritative.** It is what makes one task one trace, and
  the consumer honours it: every span it builds for a message carries that trace-id.
- ⚠️ **The carrier's SPAN-ID half is ADVISORY.** The consumer does not parent on it.
- 🔶 **The consumer parents on `CausedBy`.** `MessageHeader.CausedBy` names the `MessageID` this
  message answers (`fleetenvelope.md` §2, §4.1) — a message the consumer has ALREADY seen and has
  ALREADY emitted a span for, because the consumer emits every span. It keeps a bounded
  `MessageID → span-id` table (`Config.CauseWindow`) and parents from it.
- 🔶 **On a miss, it emits a LINK, never a fabricated parent and never a drop.** A miss is normal:
  out-of-order delivery, a cold start, or a cause older than the window. A link is honest about a
  relationship it can name but not nest.

**Delegation is a parent; a messaging hop is a link.** These look contradictory and are not. A
`RelayMessage` carrying `IntentAssign` DOWN a tree edge is task control flow — the child session's
work genuinely happens *inside* the parent's, and `fleetenvelope.md` §5.3's "joined by the
propagated context" is that nesting. A message arriving on the events plane at this consumer is
the case the messaging semconv addresses, and there a link is correct. §3's table says which is
which per row.

🔶 **`CausedBy` is still on the corrected header, so this derivation survives the correction
intact** — it is one of the four causal fields `fleetenvelope.md` §4.1 keeps, described there as
*"ONE hop up. The edge."* `InReplyTo` is a THIRD field precisely because a reply may be many hops
from its cause; the consumer therefore parents on `CausedBy` and stamps `InReplyTo` as an
attribute, never as a parent.

### 4.4 Long-trace mitigations — and the one the artifacts do not answer

An agent task runs for hours across many pods. Five mitigations, four of which are settled:

1. ✅ **A single unbounded span is wrong**, for four independent reasons. A span is not exported
   until it ENDS, so a span open for the task's life is buffered and lost on any crash. Head
   sampling decides at CREATION (`trace/span.go:37-40`), so a span that has not ended cannot be
   sampled or dropped correctly. Alloy's pipeline is `otelcol.receiver.otlp` →
   `otelcol.processor.batch` → exporters (verified: `chart/values.yaml:27-45`), and a batch
   processor forwards COMPLETED spans — an open span contributes nothing to it. And a backend caps
   a trace's span count and ingestion window.
2. 🔶 **Per-turn spans under a session root.** Bounded duration, land continuously, survive a crash
   of everything after them. `turn` is already the skill's own span name.
3. ✅ **`messaging.message.conversation_id` (= `RootID`) is an O(1) query key.** A TraceQL query
   `{ span.messaging.message.conversation_id = "<rootID>" }` returns every span of the task across
   every pod in one call. The alternative — walking the causal chain hop by hop — is O(depth) and
   fails entirely if one hop is missing. `fleetenvelope.md` §4.1 makes the same argument for audit:
   *"CONSTANT along the chain, so audit is ONE query `rootId == X` instead of an O(depth) walk."*
   The trace and the audit trail therefore share one grouping key, which is why neither needs a
   second one.
4. ✅ **A hop ceiling is the loop breaker, and it is not this document's.**
   `fleetenvelope.MaxRelayHops = 32`, and its own comment is emphatic that it is *"the LOOP
   BREAKER, not a depth limit. Tree DEPTH is unbounded by contract; this bounds a MESSAGE'S
   TRAVEL."* A message that reaches it is refused loudly — the relay publishes `IntentFailed` back
   up and drops it. **The telemetry consequence:** `hop` as an attribute is therefore relay depth,
   never tree depth, and a row that calls it "depth" without saying which one is lying. Cited,
   never re-set here.
5. ⚠️ **The retention consequence — and the gap.** Verified in the real chart
   (`infrastructure/platform/services/observability/chart/`, this document re-read it):

   | fact | value | file |
   | --- | --- | --- |
   | chart | `eden-observability` v0.1.0 | `Chart.yaml:2,9` |
   | dependencies | alloy 1.10.0 ×2 (`alloyGateway` Deployment + `alloyLogs` DaemonSet), loki 7.0.0, tempo 1.24.4, grafana 10.5.15, prometheus 29.12.0 | `Chart.yaml:11-37` |
   | OTLP gateway | **Grafana Alloy, not an OTel Collector** — `otelcol.receiver.otlp` grpc `0.0.0.0:4317` / http `0.0.0.0:4318` → `otelcol.processor.batch` → `otelcol.exporter.otlp` → `tempo:4317`, `tls { insecure = true }` | `values.yaml:27-76`, and the same pipeline again in `values-cloud.yaml` |
   | Tempo trace retention | **`168h` (7 days)** | `values.yaml:229` |
   | Tempo storage | `backend: local`, `/var/tempo/traces`, 10Gi | `values.yaml:230-234` |
   | Tempo storage on the CLOUD overlay | `backend: s3`, bucket `eden-observability`, OCI endpoint, 5Gi local-path PVC — and **retention is NOT overridden**, so 168h stands there too | `values-cloud.yaml` |
   | sampling | **none configured anywhere**; the SDK default is already `ParentBased(AlwaysSample)` | `values.yaml:41-45` |

   **The consequence:** a task that runs longer than 168h has its earliest spans evicted before it
   finishes. The trace is then permanently partial, and mitigation 3 is what keeps the task view
   usable — a `RootID` search over the spans that survive.

   **The gap, stated rather than invented.** Mateo's Batch B+C ruling of 2026-08-18 set retention
   at *"30 days + 20GiB oldest-first ceiling, one home, per-team/agent overridable"* — and closed
   OD-9 **only for the agent-transcript class**. **There is NO ruling on TRACE retention.** 168h ≠
   30 days, and this document does not reconcile them by picking one. §9 Q6.

   ⚠️ Mateo's Batch A ruling (2026-08-18): **OTel exports to the CLOUD stack**, tailnet on the trace
   path accepted. The cluster-side facts behind that — Tempo v2.9.0 UP on context `cloud` namespace
   `observability` with **0 traces stored**, Grafana at `obsv.mateosegura.com` with **no Tempo
   datasource**, and the homelab `eden` namespace with **no observability stack** — are
   `eden-otel-debug/SKILL.md` §1's recorded verification of 2026-08-18. **This document did not
   re-measure them.** Re-verify before relying on any of them.

### 4.5 Closing a span nobody closed

🔶 A pod can die mid-turn. The consumer therefore closes an open `turn` span when
`Config.TurnIdleLimit` elapses with no event for it, stamping `turn.outcome=abandoned`, and closes
the enclosing `session` the same way. An abandoned turn is recorded as abandoned — **not as
success, and not as an error**, because neither is true and both are misleading. This is the
consumer's own decision and it needs a stated limit rather than an unbounded wait.

## 5. The durable-consumer read pattern

`fleetbus.md` owns this transport. This section cites it and adds only what is genuinely
telemetry's own: what the consumer does when the OTLP export FAILS (§5.3), and what it does with a
message it cannot decode (§5.4). Neither appears in `fleetbus`.

### 5.1 The invariant — cited, and what fleettelemetry must DO to satisfy it

✅ **The home is `fleetbus.md` §9.3**, and the property is quoted rather than re-derived:

> For a telemetry consumer T attached to stream S, and a delivery consumer D on the same stream:
> for every message M published to S, **D receives M** — and T's attachment changes neither the
> set nor the count of messages D receives.

`fleetbus` also owns the failure mode behind it (a queue group delivers each message to exactly one
member, so a tap inside one *takes a share* of the traffic rather than also seeing it) and the
mechanism (`ConsumerPolicy.QueueGroup`, which **MUST be empty for any telemetry consumer**). The
durable NAME is `fleetbus` fork B1; the invariant is not open. None of that is restated here.

**What `fleettelemetry` must DO, which is this document's part:**

1. Declare `ConsumerPolicy.QueueGroup == ""`. `New` validates it and returns a `*ConfigError` on a
   non-empty value — a queue group is refused at construction, not discovered in production.
2. Carry its own durable name as `Config.Durable`, **REQUIRED with no default.** A default is how
   two services end up sharing one name, and the whole failure mode is silent.

✅ **Today there is no collision, and here is the measured reason.** The SSE bridge opens an
**ephemeral** consumer per request with `nats.AckNone()` and `nats.BindStream(...)`
(`libs/go/edenhttp/natssse/natssse.go:157-168`) — an ephemeral consumer has no durable name to
share. The rule exists for the moment someone gives the UI a durable one.

⚠️ **The wire-literal rule constrains this library's source.** `libs/go/_ctl/lib.sh:542`'s
`_xlib_wire_literal_scan` FAILS the `maintainability` gate if a subject format or an
`agent.*.<…>` wildcard appears as a string in more than one top-level library's PRODUCTION code;
`fleetbus.md` §3.4 states the same invariant from its side and notes that the scanner's pattern
list does not yet know the inbox token exists. `fleettelemetry` therefore spells no subject and no
wildcard: §2's `EventStream.DestinationTemplate()` hands it over. **The obligation this places on
`fleetbus` is to export the accessor that renders it** — the contract exists (§1) and the accessor
is not in its §2 `Subscriber`, so this is fork F10 together with the durable-events gap.

### 5.2 The sequence spaces — cited, not re-derived

✅ **`fleetbus.md` §6 is the home**, and it is the section that document itself calls the one that
matters most. It owns: the two spaces (`fleetenvelope`'s per-session `Seq` versus JetStream's
global stream sequence, *"a publisher can compute `Seq` before it publishes and cannot know the
stream sequence until the server answers"*); the inverted frontend cursor preference (§6.2); the
history↔live stitch (§6.3); and the vacuous-test analysis plus the real duplicate-flood failure
mode in `natssse` (§6.4). This document restates none of it.

**Two consequences that are this consumer's own:**

- 🔶 It resumes in **stream sequences only**. `fleetbus.Delivery.StreamSeq` is the cursor; the
  envelope's `Seq` is an attribute (`seq`) and never a cursor. `fleetenvelope.md` §2 states the
  same rule in the type's own comment: `Seq` *"is NOT the replay cursor"*.
- ⚠️ It must not inherit the conflation `fleetbus` §6.4 measured in `natssse`. That defect belongs
  to `edenhttp`/`natssse`; what this contract owns is the refusal to copy it.

### 5.3 At-least-once, and what that costs — the part `fleetbus` hands over

✅ `fleetbus.md` §5.4 states the claim and then hands this consumer the obligation, verbatim:
*"At-least-once delivery with a deterministic dedup key. Never app-layer exactly-once. … outside
[the dedup window], a republish lands again and **the consumer's own idempotency — keyed on the
same `MessageID` — is what holds.**"*

⚠️ **This consumer's emission is NOT idempotent by default, and that is the cost.** Rebuilding a
span after a redelivery mints a NEW span id; Tempo stores spans under a trace id without
de-duplicating them, so the redelivery yields a duplicate span inside a real trace and silently
inflates every count and every duration percentile derived from it. The bus-side dedup protects the
PUBLISH side (`fleetbus` §5.2), not this export.

Three honest positions, and this document takes the second:

| # | position | cost |
| --- | --- | --- |
| a | accept duplicates | counts and percentiles derived from spans are wrong by an unknown factor, with no signal |
| b | 🔶 **deterministic span ids** — derive the 8-byte span id from `hash(traceID, MessageID, span-role)` | a hash collision merges two unrelated spans; the derivation becomes part of the telemetry contract |
| c | a de-dup table of exported `MessageID`s | unbounded state, and it is the durable's own job done twice |

**(b) is the answer `fleetbus` already points at.** Its deterministic `MessageID` is exactly the
stable input a deterministic span id needs — *"a REPUBLISH after a pod restart de-duplicates
instead of duplicating"* (`fleetenvelope.md` §2). The same property, carried one layer further.
`fleetbus.Delivery.Redelivery` (>1 means the durable is retrying) additionally lets the consumer
stamp `messaging.redelivered=true`, so a duplicate is **visible** in the store rather than merely
present. Fork F3.

### 5.4 An undecodable message, and a schema the reader does not know

**This appears nowhere in `fleetbus` or `fleetenvelope`, and it is the failure a telemetry consumer
is most likely to paper over.** `fleetenvelope`'s `Decode` REFUSES a header that does not validate
— that is its whole purpose. A telemetry consumer that then SKIPS what it cannot parse is a check
that cannot fail: the traces simply thin out and nothing says why.

🔶 Two failure classes, and they need opposite handling. Conflating them is the trap.

| class | example | retryable? | action |
| --- | --- | --- | --- |
| **transient** | the exporter is down; `Flush` returns an error | YES | NAK and retry within `ExportBudget`, then FAIL the process (§5.5) |
| **permanent** | the payload does not decode; the header fails `Validate`; the schema is one this reader does not know | **NO — never** | record loudly, advance, and FAIL on rate (below) |

⚠️ **A permanent failure must not be NAK'd.** An undecodable message will never become decodable,
so nak-and-retry is a poison pill: one bad message halts the entire telemetry tap forever, which
is a worse outcome than the bad message. So:

1. The consumer emits a `telemetry.undecodable` record carrying `stream.seq`, `error.kind` and —
   if the header decoded far enough — `messaging.message.id`. **Never the payload bytes**: they are
   untrusted, unvalidated and possibly secret-bearing, which is the same reason §3.2 lets
   `extension` contribute only its byte count.
2. It advances past the message.
3. **It FAILS the process when the undecodable count in a window exceeds a stated ceiling.** One
   corrupt message is an incident report; a rising rate is a schema break, and a tap that survives
   a schema break while emitting nothing is the false-green this repository treats as a defect
   class. The ceiling is a `Config` value with no default, for the same reason `Durable` has none.

This is neither a silent skip nor a poison pill, and naming both wrong answers is the point.

### 5.5 Fail loudly on export — never a silent drop

This is where the frozen port's shape forces the design, and it is the single most important
paragraph of §5, and it appears nowhere in `fleetbus`.

⚠️ **`Provider.Emit` is non-blocking, best-effort and returns NO error** (`provider.go:13-17`;
`observability.md` §6 rationale 3 — "a dropped Event can never fail a phase"). **`Flush` is the ONLY
blocking call and the ONLY one that returns an error** (`provider.go:36-39`). So the consumer
**cannot learn from `Emit` that an export failed.** Therefore:

1. The consumer builds spans for a batch, then calls `Telemetry.Flush(ctx)`.
2. **It calls `fleetbus.Delivery.Ack` ONLY after `Flush` returned nil.** An ack before a durable
   export is a silent drop — the message is gone from the durable and the span never reached Tempo.
3. On a `Flush` error it calls `Delivery.Nak(delay)` with backoff. It never acks. It never logs
   "export failed, continuing".
4. It retries within `Config.ExportBudget`. When that budget expires, **`Run` returns a wrapped
   `KindUnavailable` error and the process exits non-zero.** A telemetry consumer that cannot
   export and keeps running is a green check that verifies nothing — the FAIL-NOT-SKIP rule
   (ADR-0020) applied to a data path.
5. `Config.AckWait` MUST exceed `Config.ExportBudget`, or the durable redelivers a batch the
   consumer is still retrying and the two mechanisms fight. `New` validates the ordering and
   returns a `*ConfigError` naming both fields — a wrong ordering is refused at construction, not
   discovered in production.
6. `Config.MaxAckPending` bounds the un-acked window, and therefore the reconstruction state (open
   `turn` spans + the `CauseWindow` table). It is the memory ceiling, stated rather than implicit.

🔶 **If §9 Q1 selects topology β, the fan-out is EXCLUDED from this discipline.** A live-tail
publish would be best-effort per subscriber and would never gate an ack: a slow browser must never
stall the telemetry export, and a disconnected browser must never NAK a message. `fleetbus.md` §7.1
records the matching rule on its side — on the `events` plane, backpressure tells **nobody**, so one
runaway agent degrades only itself.

⚠️ **This whole subsection assumes `Delivery.Ack` is non-nil, and today it would not be.**
`fleetbus.md` §2 documents `Delivery`'s `Ack`/`Nak` as *"nil on the events plane (AckNone) and
non-nil on the inbox plane."* Every numbered step above needs a durable, explicitly-acked consumer
on the EVENTS stream, which `Subscriber` has no method to open. That is fork F10, and it is the
single largest thing this document needs from `fleetbus`.

## 6. The UI streaming read model

> **Mateo, 2026-08-26**, verbatim selection: *"Bus consumer"* — one telemetry service consumes
> JetStream → OTel, and the same consumer feeds UI streaming.

✅ **The stitch mechanics are `fleetbus.md` §6.3's and are cited, not re-derived.** One join point:
`GET /agents/{id}/history?from-turn=<n>` is served from the archive and returns `nextCursor ==
manifest.lastStreamSeq`; the client then opens `GET /agents/{id}/events?from-cursor=<streamSeq>`
and the consumer starts at `cursor+1`. **No gap and no duplicate, because the archive's last stream
position and the tail's first are adjacent by construction** — a property that holds only because
both halves are expressed in the SAME space, the stream sequence. `fleetbus` §6.2 additionally
rules that the SSE `id:` line carries the STREAM sequence and the payload's `seq` orders and
de-duplicates, and §6.4 names the non-vacuous test both halves need. This document adds nothing to
any of that.

What is left is the product question, and it is genuinely open.

### 6.1 ⚠️ The platformgateway-vs-agentgateway discrepancy, stated rather than silently resolved

The ruling names `platformgateway` SSE. The code says otherwise, measured 2026-08-26:

| app | what it actually serves | evidence |
| --- | --- | --- |
| `apps/agentgateway` | `GET /sessions/{id}/events` — the SSE bridge, plus control/prompt/steer/abort/stop/kill | `internal/stateless/events.go:15-40`, handler at `:54-84`, driving `natssse.Bridge` |
| `apps/platformgateway` | the **connectors** domain and nothing agent-shaped: `connectors`, `me`, `ping`, `users` | `internal/api/v1/` — four domains + `mount.go` |

`platformgateway` carries **no agent-event surface today**. `agentgateway` is the app that does,
and its path is gate-proven against a real embedded nats-server and a real nats container
(`contracts/edenhttp.md` status header). This document does not pick one — §9 Q1 does.

⚠️ Note also that `fleetbus` §6.3's endpoints are `/agents/{id}/history` and `/agents/{id}/events`,
while the built surface is `/sessions/{id}/events`. **`agentgateway` routes by SESSION id and the
fleet contract routes by AGENT id**, and one agent hosts 1..N sessions
(`fleetenvelope.md` §3). That is a real route-shape change riding on the same answer, and it is
named here rather than discovered during the move.

### 6.2 What the consumer must EXPOSE, and the one thing that decides it

🔶 Two topologies, differing only in whether *"the same consumer feeds UI streaming"* is literally
one process or one stream:

- **α — two independent readers.** The gateway's live half is a per-request ephemeral consumer
  (`fleetbus.Subscriber.SubscribeEvents`, which is documented as exactly that), and the telemetry
  consumer reads its own durable. **The consumer exposes NOTHING.** No fan-out, no hub, no
  backpressure path from a browser into the export path. The ruling's phrase is then a statement
  about the STREAM, not about one process.
- **β — one durable, one hub.** The telemetry consumer additionally fans out to live subscribers,
  and `Deps` gains a `Tail` port (§2). The hub is LIVE-ONLY, so history still comes from the
  archive exactly as §6.3 says — β changes only who serves the tail half, not the stitch.

**β's real cost, stated because it is the reason the question is not obvious:** it puts a
user-visible surface downstream of the export path. `fleetbus` §9.3 says that strengthens the
queue-group invariant — *"a silently-stolen message would be a missing event on someone's screen"* —
and it equally means a fan-out defect becomes a telemetry defect. α keeps the two failure domains
apart at the cost of literal fidelity to the ruling's wording. Fork F4; §9 Q1 decides it together
with which app serves the surface.

## 7. Invariants (load-bearing)

Each row states whether it is provable TODAY. A row marked TO BUILD is a promise, not a property.

| # | invariant | tag | provable today? |
| --- | --- | --- | --- |
| I1 | The consumer is the ONLY process in the fleet that speaks OTLP. Pods stamp the carrier and export nothing. | 🔶 | TO BUILD — `oteladapter` does not exist (§1/1) |
| I2 | No span name contains an id. Bus span names use the SUBJECT TEMPLATE; identity rides as attributes. | ✅ rule (SKILL.md §6) | testable by a lint over span names once the library exists |
| I3 | A cross-pod messaging edge is a LINK given at CREATION, never `AddLink`, never a parent. | ✅ rule (`fleetenvelope.md` §5.3; `trace/span.go:37-40`) | TO BUILD |
| I4 | A link is OMITTED, never dangled: the consumer never references a span-id it did not export. | ⚠️ | TO BUILD — and this is what fails silently if I1 is violated |
| I5 | No secret and no untrusted payload reaches an attribute. `Field.Value` is a `Valuer`; `extension` contributes only its byte count; an undecodable payload is never stamped. | ✅ (`observability.md` §6.4) + 🔶 (§3.2, §5.4) | the type system already enforces the general case |
| I6 | `Ack` happens only after a `Flush` that returned nil. | ⚠️ | TO BUILD — §5.5, and blocked on fork F10 (`Delivery.Ack` is nil on the events plane today) |
| I7 | A TRANSIENT export failure is NAK'd and retried within `ExportBudget`, then FAILS the process. A PERMANENT decode failure is recorded, advanced past, and FAILS on rate. Neither is ever a silent skip, and neither is ever a poison pill. | ✅ rule (ADR-0020 FAIL-NOT-SKIP) | TO BUILD — §5.4, §5.5 |
| I8 | The telemetry consumer holds its own durable with `ConsumerPolicy.QueueGroup == ""`, and its attachment changes neither the set nor the count of messages a delivery consumer receives. | ✅ (`fleetbus.md` §9.3 — its home, and it states the property in testable form) | assertable as written once `fleetbus` exists; no collision exists today because the SSE bridge is ephemeral |
| I9 | `fleettelemetry` spells no subject and no wildcard. | ✅ enforced | the detector is live today: `libs/go/_ctl/lib.sh:542` `_xlib_wire_literal_scan`, run by the `maintainability` verb |
| I10 | `go.opentelemetry.io/otel*` is imported ONLY by `oteladapter`. | ✅ rule (SKILL.md §5) | enforceable by depguard, and the ground is clean: `go.opentelemetry.io/otel` appears in eden only as `// indirect`, in `libs/go/workspaceprovider/go.mod:63-66` and `libs/go/orchestrator/go.mod:71-74`, both pinned v1.44.0. There is **no direct OTel dependency anywhere in eden today.** |
| I11 | The UI stream tolerates a duplicate and never a gap. | ✅ (`fleetbus.md` §6.3, §6.4) | its home; testable against a real nats-server as `edenhttp` already does |
| I12 | No metric is emitted, because the port has no `Counter` and no `Histogram`. | ✅ (`observability.md` §6.1) | true today, by construction |
| I13 | No attribute names a tree address. A node is addressed only by its `AgentID`; `hop` is relay depth and says so. | ✅ (`SKILL.md:114`; `fleetenvelope.md` §4.2) | enforceable by a name lint; **this document violated it in an earlier revision and the violation is recorded in §3.0** |

## 8. Forks

| # | fork | position A | position B | 🧩 resolution |
| --- | --- | --- | --- | --- |
| F1 | **`Record` → OTel shape.** Is an `Emit`ted record a span EVENT on the open span, or a zero-duration SPAN? | span event — matches `Record{TraceID, SpanID}`, which is a record correlated TO a span | zero-duration span — matches SKILL.md §4's `{ name = "tool-end" && status = error }`, which is a TraceQL span-name match | 🧩 **Open.** The decision is `oteladapter`'s, and `oteladapter` does not exist. §3 states the intent (span event); every name and attribute is unchanged under either. |
| ~~F2~~ | ~~`messaging.message.id` source~~ | — | — | ✅ **CLOSED by the `fleetenvelope` correction at `9fd66d9`.** `MessageID` is globally unique, deterministic, and IS the JetStream `MsgId`; `Seq` is explicitly not the cursor. SKILL.md §6's `Seq` mapping is now stale text, amended in the same change (§9 Q3). §3.0 carries the row. |
| F3 | **Duplicate spans on redelivery.** | accept duplicates | 🔶 deterministic span id from `hash(traceID, MessageID, span-role)` | 🧩 **Recommend B** with `messaging.redelivered` stamped from `fleetbus.Delivery.Redelivery`, so a duplicate is visible rather than merely present. §5.3 — and `fleetbus` §5.4 explicitly hands this consumer the obligation. |
| F4 | **UI stream topology.** | α — the gateway's live half is its own ephemeral consumer; the telemetry consumer exposes nothing | β — the telemetry consumer also fans out, and `Deps` gains a `Tail` port | 🧩 **Open — §9 Q1 decides it together with which app serves the surface, and with the session-id-vs-agent-id route shape of §6.1.** |
| F5 | **Control and health planes.** Core NATS is at-most-once (`fleetbus` §3.2 class D3), so a durable consumer cannot observe them. | leave them off the trace plane; liveness stays the controller's Probe | give them a durable plane so telemetry can read them | 🧩 **Recommend A for v1.** B is a `fleetbus` change (a new durability class), not a telemetry change. |
| F6 | **The `session` and `relay` span names.** Neither is in SKILL.md §6's list. | adopt them here and amend SKILL.md in the same change | reuse an existing name | 🧩 **Recommend A** — this contract is the vocabulary's home for fleet telemetry, and SKILL.md §6's own rule is that names come from the contract. §9 Q3. |
| ~~F7~~ | ~~`agent.address` / `agent.parent.address` attributes~~ | — | — | ⚠️ **WITHDRAWN, and the withdrawal is a correction of this document.** The corrected `fleetenvelope.md` §4.2 puts no tree address on the wire, and `SKILL.md:114` forbids a flat tree-path attribute by name. Proposing them was the exact thing the skill forbids. `hop` is the honest depth signal that survives. §3.0. |
| ~~F8~~ | ~~The turn ordinal has two homes~~ | — | — | ✅ **CLOSED by the correction.** `fleetenvelope.md` §4.1: there is no turn ordinal on the header, deliberately — *"Putting it on the header would be a sixth home."* Turn comes from `agentsession.Event`. |
| F9 | **The 2026-08-18 fleet SYNTHESIS still says the opposite.** ⚠️ *Corrected from an earlier framing:* the LOCKED 2026-08-18 ruling (*"OTel: from day one — exporter as a log consumer"*) and the 2026-08-26 bus-consumer ruling **AGREE** — both `fleetenvelope.md` §5.4 and `fleetbus.md` §9.1 say so. It is the SYNTHESIS text (an in-process `oteladapter` in every workload) that disagrees with both. | the two rulings govern; the synthesis text is superseded on this point and says so in writing | the synthesis is reopened | 🧩 **Recommend A** — §9 Q2 records it. A pod that mints a span context it never exports produces dangling links (§4.3), which is the technical reason as well as the procedural one. |
| **F10** | ⚠️ **`fleetbus.Subscriber` has no method to open the telemetry consumer it requires.** Its four methods are one per subject; `SubscribeEvents` is documented EPHEMERAL with `AckNone` and takes no `ConsumerPolicy`, `SubscribeInbox` is the only `ConsumerPolicy`-taking method and is inbox-only, and `Delivery.Ack`/`Nak` are *"nil on the events plane"*. But §9.3 requires a telemetry DURABLE with an empty `QueueGroup`, and §5.4 hands this consumer an idempotency obligation a nil `Ack` cannot discharge. | add a `SubscribeEventsDurable(ctx, policy, deliver)` (or let `SubscribeEvents` take a `ConsumerPolicy`) | keep the events plane strictly `AckNone` and have telemetry track its own cursor externally | 🧩 **Recommend A, and it is `fleetbus`'s call, not this document's.** B re-implements the durable's own job and reintroduces the cursor-space confusion `fleetbus` §6 exists to kill. **This fork also carries the `DestinationTemplate` accessor §5.1 needs.** Routed to the fleet-bus lane. |

Each fork also belongs in `docs/architecture/open-decisions.md` per `CLAUDE.md`'s rule that an
unmade decision lives there and never in prose alone. **That register edit is not this document's
to make** — it is a separate change, and no agent should assume it happened.

## 9. The freeze question

Freezing this contract is Mateo's `.claude/rules/git-process.md` §5 gate ("a chart or contract
PROMISE"). **No agent exercises it**, and this document may not be edited to say it is frozen by
anything other than Mateo's verbatim words quoted with a timestamp (§13 rule 4). Six questions,
each with named options and a recommendation.

> ### Q1 — Which app serves the UI stream, and with which topology?
>
> The ruling says *platformgateway* SSE. The code says `apps/agentgateway`
> (`internal/stateless/events.go:27`), while `apps/platformgateway/internal/api/v1/` holds
> `connectors`, `me`, `ping`, `users` and no agent surface (§6.1).
>
> - **(a) RECOMMENDED — `agentgateway` keeps it, topology α.** The ruling's word "platformgateway"
>   is read as "the gateway", and amended to name `agentgateway`. **Reason:** the surface exists,
>   is gate-proven against a real nats-server and a real nats container, and `platformgateway`'s
>   domain is user credentials — moving an agent transcript stream into the credential app mixes
>   two security domains and buys nothing. Under α the telemetry consumer and the SSE bridge are
>   two independent readers of one stream, which is simpler and cannot deadlock on a slow browser.
>   The cost: "the same consumer feeds UI streaming" is then a statement about the STREAM, not
>   about one process.
> - **(b) `agentgateway` keeps it, topology β** (one durable + a live hub, §6.2 handover). Literal
>   fidelity to the ruling. Cost: a handover seam that must be proven not to gap, and a hub whose
>   backpressure must never reach the ack path.
> - **(c) Move the surface to `platformgateway`.** Cost: it discards a working, gate-proven path
>   and mixes the connectors domain with agent transcripts.

> ### Q2 — Is the mapping table's span / event / link shape accepted?
>
> §3 as written: one `receive <template>` span per FETCH BATCH (never per envelope); a `session`
> span and a `turn` span per session and turn; the sixteen `EventKind` tokens as span EVENTS on the
> open span; four kinds FOLDED into counters (`text-delta`, `thinking-delta`, `thinking-progress`,
> `tool-update`); cross-pod messaging edges as LINKS AT CREATION; delegation as a PARENT resolved
> from `CausedBy`, with the carrier's span-id treated as advisory (§4.3).
>
> - **(a) RECOMMENDED — accept it, and record in writing that the bus-consumer ruling supersedes
>   the 2026-08-18 fleet SYNTHESIS's in-process `oteladapter` design.** **Reason:** the two RULINGS
>   already agree (`fleetenvelope.md` §4.3); only the synthesis text dissents, and it must be
>   marked superseded or a future lane will implement it. The technical reason is independent of
>   the procedural one: **a pod that mints a span context it never exports produces dangling
>   parents and links**, so "pods stamp, one consumer exports" is not merely cheaper — it is the
>   only shape that does not lie about its own graph. The folding of the four high-volume kinds is
>   a deliberate, stated loss of per-delta granularity; without it a single turn emits thousands of
>   records.
> - **(b) Accept with per-envelope bus spans.** Cost: `text-delta` is token-by-token; this is
>   O(tokens) spans and it will not survive contact with a real turn.
> - **(c) Reject the folding** and record every delta. Cost as in (b).

> ### Q3 — Do you accept the two span names this document ADDS to the vocabulary?
>
> `session` (the session root span) and `relay` (the tree-edge span). SKILL.md §6's rule is that
> span names come from the contract vocabulary, and neither is in its list.
>
> ⚠️ **A third proposal is WITHDRAWN before you answer it, and the withdrawal is a correction of
> this document, not a concession.** An earlier revision proposed `agent.address` and
> `agent.parent.address`. The corrected `fleetenvelope.md` §4.2 puts **no tree address on the
> wire**, and its third reason is that `SKILL.md:114` **forbids a flat tree-path attribute by
> name**. Proposing them was the exact thing the skill forbids. `hop` — relay depth from the root,
> never tree depth — is the honest signal that survives.
>
> - **(a) RECOMMENDED — accept both, and amend `~/.claude/skills/eden-otel-debug/SKILL.md` in the
>   SAME change.** **Reason:** this contract is that vocabulary's home for fleet telemetry, so
>   adding here is the sanctioned path rather than an exception to it. The amendment must not lag:
>   instrumentation that describes a contract it no longer matches is the false-context failure the
>   housekeeping rule exists to prevent. **The same amendment also corrects a now-stale line** —
>   SKILL.md §6 maps `messaging.message.id` to `Seq`, which the corrected header supersedes with
>   `MessageID` (§3.0).
> - **(b) Accept `session`, reject `relay`.** Cost: the tree edge becomes unobservable, and it is
>   the only place delegation is visible at all.
> - **(c) Reject; reuse existing names.** There is no existing name for a session root or a relay.

> ### Q4 — `RootID` as the task key: does a task ever span more than one root chain?
>
> **This is `fleetenvelope.md` §11 fork F2, and its owner column names THIS lane** — *"the
> telemetry lane"*. So this document takes a position rather than deferring.
>
> `fleetenvelope.md` §5.1 rules that `RootID` IS the task id: constant along the chain, already
> mapped to `messaging.message.conversation_id`, and *"naming a second `TaskID` field would be a
> second home for one fact"*. The open half is whether an orchestrator task can span **several**
> root chains.
>
> - **(a) RECOMMENDED — `RootID` IS the task key; no second field.** **Reason, from the seat that
>   can judge it:** the telemetry consumer has no side lookups (`fleetenvelope.md` §5.4), so it can
>   group only by what is on the wire. Under (a) the grouping is total — one query returns the
>   task. Under (b) the grouping **splits silently**, and this is the decisive point: *a partial
>   `conversation_id` group and a complete one are indistinguishable to every consumer.* There is
>   no cardinality field, no expected-chain-count, nothing that could make the split loud. A
>   grouping key that is sometimes incomplete, with no way to detect the incompleteness, is worse
>   than one that is always complete. It also costs nothing extra: `RootID` already serves the
>   audit trail's `rootId == X` query (`fleetenvelope.md` §4.1), so the trace and the audit share
>   one key instead of needing two.
> - **The obligation (a) carries, stated so it is not assumed away:** the relay must mint a fresh
>   `RootID` **only** at a genuine task origin, and never at an intermediate hop. If it ever does,
>   the task splits and nothing says so. The conformance property that makes this loud rather than
>   silent is: *every message reachable from a root chain carries that root's `RootID`* — a
>   `Relay`-preserves-`RootID` assertion, refuted by breaking the preservation and watching it
>   fail. Without that property (a) is an assumption; with it, it is a checked invariant.
> - **(b) A task spans several root chains → a distinct `TaskID` is required.** If you mean this,
>   it is a **new required header field plus a join**, not a convention — and it must be added
>   before the §8 freeze window closes, because a required field cannot be added afterwards. Say so
>   now and the cost is zero; say so later and it is a wire break.

> ### Q5 — The W3C carrier: keep the `OTel` map, or typed fields?
>
> **This is `fleetenvelope.md` §11 fork F3, and its owner column names THIS lane** — *"the OTel
> lane"*. Your 2026-08-26 wording asked for first-class `traceparent`/`tracestate` fields; the
> locked carrier is `OTel OTelContext`, a `map[string]string`.
>
> - **(a) RECOMMENDED — keep the map, AND close its validation hole in `MessageHeader.Validate()`.**
>   **Reason:** the measured property is decisive and cheap — `OTelContext` is `map[string]string`
>   and OTel's `propagation.MapCarrier` is `map[string]string`, so a real propagator drops in as a
>   **type conversion with no contract change at all**. Typed fields would break that and fork W3C
>   propagation into two homes the day `baggage` is wanted. **The map's one real cost is
>   validation**: nothing rejects an arbitrary key smuggled onto an audited wire, and today's
>   `otelobserver.Extract` merely FILTERS unknown keys away (`otelobserver.go:84-86`) — a silent
>   drop, which is the failure class this estate treats as a defect. **The middle path recovers it
>   for free:** have `Validate()` REFUSE a carrier holding any key outside `{traceparent,
>   tracestate}` with a typed error naming the key. That turns a silent filter into a loud refusal,
>   at mint rather than at extract, with no schema change and no second home. `baggage` is then an
>   additive widening of that key set when a consumer for it exists.
> - **(b) Typed `TraceParent`/`TraceState` fields.** Literal fidelity to your wording. Cost: a
>   conversion layer on every propagate, a second home for the two W3C keys, and the `baggage`
>   question reopened as a third field.
> - **Either way, one thing does not change:** §4.3's rule that the carrier's **trace-id is
>   authoritative and its span-id is advisory**, because a pod that stamps a span context and never
>   exports it names a span that exists nowhere. That is a property of the bus-consumer ruling, not
>   of the carrier's shape.

> ### Q6 — Are metrics in scope for v1 at all?
>
> Stated plainly rather than answered by inventing one: **`observability.Provider` has no `Counter`
> and no `Histogram`** — it is exactly five methods and is at its negotiated ceiling
> (`observability.md` §6 rationale 1; `provider.go:12-40`), so a method cannot be added.
> **No metric name is designed anywhere in this estate.** Token and cost figures ride as Fields on
> a `usage` / `cost.ledger` Event (SKILL.md §5; `observability.md` §7 Q8). The PIPE exists while the
> PRODUCER does not: Alloy already forwards OTLP metrics to Prometheus via `remote_write`
> (`values.yaml:43,50-51`).
>
> - **(a) RECOMMENDED — NO metrics in v1.** Traces and the Event stream only. **Reason:** adding a
>   metric would require either a sixth `Provider` method (forbidden — the ceiling is negotiated
>   and frozen) or a second pipe beside the stream, which is exactly the "three planes, one stack"
>   break `observability.md` §6 rationale 8 forbids. Percentiles derived from spans are available
>   from the trace store without a metric, and §5.3's duplicate question must be settled before any
>   count derived from spans is trustworthy.
> - **(b) Metrics in v1** via a new `Exporter`-side aggregation in `oteladapter`. Cost: an
>   aggregation the port cannot express, and metric names nobody has designed.

> ### Q7 — What is the TRACE retention, given that no ruling covers it?
>
> Verified: Tempo retention is **168h** (`chart/values.yaml:229`), not overridden by
> `values-cloud.yaml`. Mateo's 2026-08-18 Batch B+C ruling set **30 days + a 20GiB oldest-first
> ceiling** — but explicitly closed OD-9 **only for the agent-transcript class**. Traces are a
> different class and **have no ruling** (§4.4).
>
> - **(a) RECOMMENDED — traces keep 168h for v1; transcripts keep 30 days; the difference is
>   recorded as deliberate.** **Reason:** the two classes have different costs and different
>   consumers — a transcript is the product's own record and a trace is a debugging artifact — and
>   Tempo's storage is 10Gi local (5Gi + OCI S3 on the cloud overlay), so raising retention is a
>   capacity change that should be measured rather than assumed. Mitigation 3 (`RootID` as an O(1)
>   query key) is what keeps a task readable after its trace tail is evicted.
> - **(b) Align traces to 30 days.** Cost: a capacity change on the cloud object store, unmeasured.
> - **(c) Defer.** Cost: the first task longer than 7 days loses its head silently, and nobody
>   learns why.

> ### Q8 — The freeze ORDER, which is a dependency and not a preference
>
> Every attribute in §3 comes from a `fleetenvelope` header field or a `fleetbus` delivery fact.
> **This contract cannot freeze before both of those do**, and the reason is measured rather than
> procedural: an earlier revision of this document mapped from `TaskID`, `TraceParent`,
> `TraceState` and a `TreeAddress`, and the sibling correction at `9fd66d9` removed all four. A
> freeze taken one hour earlier would have frozen a mapping onto fields that do not exist.
>
> - **(a) RECOMMENDED — one decision covers all three, in the order `fleetenvelope` →
>   `fleetbus` → `fleettelemetry`.** **Reason:** the dependency is strictly one-directional, and
>   the two forks the sibling lane routed to this lane (Q4, Q5) must be answered *inside* the
>   `fleetenvelope` freeze, because both change its §2 surface. Note that `fleetenvelope` is
>   **additive to package `agentruntime`**, so its freeze also re-records
>   `libs/go/agentruntime/.apibaseline` — and `fleetenvelope.md` §9 flags one wire deletion
>   (`ControlMessage.By`) that `.apibaseline` structurally cannot see.
> - **(b) Freeze this contract conditionally**, with a re-refutation obligation on any sibling
>   change. Cost: a conditional freeze is not a freeze, and `phase-gate architecture` cannot
>   express one — `_gate_contract_frozen` reads the status header and nothing else.

**Answering Q1, Q4, Q5 and Q8 is mandatory for a freeze.** Q1 changes §6's surface; Q4 and Q5 were
routed to this lane by `fleetenvelope.md` §11 and both change ITS §2 surface, so they must be
answered inside that freeze rather than after it; Q8 is the order the other three depend on. Q2,
Q3, Q6 and Q7 may be delegated — but Q2 governs whether any lane can start against §3.

**No part of this document is ratified.** Every ✅ marks a measured fact or a cited rule, never
Mateo's approval. As of 2026-08-26 the gate is **not individually exercised**.
