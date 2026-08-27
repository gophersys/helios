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
> (`contracts/fleetenvelope.md` §2, DRAFT) · subjects, durability classes, stream policy, delivery
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
> chart or contract PROMISE"; §13 rule 4 requires his verbatim words and a timestamp). §9 is the
> exact question. This contract additionally CANNOT freeze before `fleetenvelope` does — §9 Q4
> states that dependency.
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
| the wire header (`MessageHeader`), `TaskID`, `TraceParent`/`TraceState`, `MessageID`, `CausedBy`, `Address`, `MaxHops`, the four message types | `contracts/fleetenvelope.md` §2 | **DRAFT, unfrozen** | `libs/go/fleetenvelope` — TO BUILD |
| the four subjects and three durability classes · stream policy · delivery semantics, `MsgId` and dedup · the two sequence spaces and the history↔live stitch · backpressure · archive-then-publish · **the telemetry consumer's queue-group invariant** | `contracts/fleetbus.md` §3 · §4 · §5 · §6 · §7 · §8 · **§9.3** | **DRAFT, unfrozen** | `libs/go/fleetbus` — TO BUILD |
| the CRD kinds, the controller, the reconcile loop, identity and the uid witness, the agent profile | `contracts/agentfleet.md` | **DRAFT, unfrozen** | TO BUILD |
| the harness `Event` taxonomy (`EventKind`, payloads, `Seq == transcript offset`) | `contracts/agentsession.md` | FROZEN | built |
| the telemetry port (`Provider`, `Exporter`, `Record`, `Event`, `Field`, `Plane`, `Severity`) | `contracts/observability.md` | FROZEN | built (`slogadapter` only) |
| the OTLP wire and the OTel SDK | `libs/go/observability/oteladapter` | — | **does not exist** |
| checkpoint composition, segment format, archive retention, `manifest.lastStreamSeq` | `fleetcheckpoint` | **no document** — cited by `fleetbus.md` §6.1 and §8, not yet written | TO BUILD |
| the git process, the merge gate, attribution | `.claude/rules/git-process.md` | current | — |

⚠️ `fleetbus.md` §6.1 cites a `contracts/agentpod.md`. **No file of that name exists**; the
kubernetes control surface is `contracts/agentfleet.md`. That is a citation to correct in
`fleetbus`, not here — recorded so no reader of THIS document goes looking for it.

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
| 6 | `libs/go/fleetenvelope` | fleet-envelope lane | same split: contract DRAFT, library absent. |
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
	ExportBudget  time.Duration // bounded retry window; on expiry Run FAILS loudly (§5)
	TurnIdleLimit time.Duration // a turn span idle this long is closed as abandoned (§4.5)
	CauseWindow   int           // MessageID→span-id entries retained for parenting (§4.3)
}

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
- **A cross-pod messaging edge is a LINK given at span CREATION** (`WithLinks`), never `AddLink`,
  because head sampling can only consider information present at creation
  (`trace/span.go:37-40` at tag `trace/v1.45.0`), and never a parent — the messaging semconv states
  it is NOT RECOMMENDED to parent a Process span on the message-creation context.
  The one edge that IS a parent is the *delegation* edge, which is task control flow rather than a
  messaging hop — §4.3 separates the two.
- **Attributes reuse the existing vocabulary**: `agent.id`, `session.id`, `turn.id`, `turn`, `seq`,
  `messaging.message.id`, `messaging.destination.name` (SKILL.md §6), plus the semconv names
  `messaging.message.conversation_id`, `messaging.operation.name`, `messaging.operation.type`.
- **Every attribute comes from a header field or the transported `agentsession.Event`.** A consumer
  outside the emitting process has no side lookups — `fleetenvelope.md` §4.3 is explicit that this
  is why the header is fat.
- **No secret in an attribute.** `Field.Value` is a `Valuer`; a secret enters only as its redacted
  projection via `observability.Any` (`observability.md` §6 rationale 4).

Header source for the shared attributes, once: `agent.id` ← `MessageHeader.AgentID` ·
`session.id` ← `SessionID` · `turn` ← `Turn` · `seq` ← `Seq` · `messaging.message.id` ← `MessageID`
· `messaging.message.conversation_id` ← `TaskID` · `messaging.destination.name` ←
`EventStream.DestinationTemplate()`. `turn.id` comes from the transported
`agentsession.Event.TurnID` (`types.go:299`), the one attribute with no header field.

### 3.1 Transport and scaffolding

| message kind | OTel shape | span name | attributes | notes |
| --- | --- | --- | --- | --- |
| one delivery BATCH (the `Consume` callback's unit of work) | **span** (timed), `PlaneSelf` | `receive <destination-template>` | `messaging.destination.name`, `messaging.operation.name=receive`, `messaging.operation.type=receive`, `messaging.batch.message_count` | 🔶 The ONLY per-hop bus span, and it is O(batches), not O(messages). One span per envelope is unaffordable: `text-delta` is token-by-token (`types.go:247`). The name is COMPOSED from the accessor — the wildcard is never a literal here (§5). |
| each message in that batch | **link at creation** on the `receive` span | — | `messaging.message.id`, `messaging.message.conversation_id` | 🔶 `trace.Link{SpanContext, Attributes}` — an application id alone cannot form a link, so the link needs a real span context. When `TraceParent` is empty, or names a span this consumer never exported, the link is **OMITTED, never dangled** (§4.3). |
| one `SessionID`, first event → terminal | **span** (timed), `PlaneAgent` | `session` 🧩 | `agent.id`, `session.id`, `messaging.message.conversation_id`, `agent.address` 🧩 | 🧩 The session's root span (`fleetenvelope.md` §4.2 consequence 3: "each session opens a root span joined by the propagated context"). **The NAME is this document's proposal** — `session` is not in the skill's list. §9 Q3. |
| one `Turn` value, within a session | **span** (timed), `PlaneAgent`, child of `session` | `turn` | `agent.id`, `session.id`, `turn.id`, `turn` | ✅ Already the skill's own name: `{ span.session.id = "<sid>" && name = "turn" && duration > 30s }` (SKILL.md §4). Opens on the first event of a new `Turn`; closes on a terminal, the next `Turn`, or `TurnIdleLimit` (§4.5). |

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
| `RelayMessage` (write plane) | **span** (timed), `PlaneAgent` | `relay` 🧩 | `agent.id`, `agent.address`, `agent.parent.address`, `relay.intent`, `hop`, `caused.by`, `actor.kind`, `actor.id`, `actor.break_glass` | 🧩 The tree edge, and the ONLY place delegation parentage is observable. `Intent` is `fleetenvelope`'s closed five (`fleetenvelope.md` §2). `actor.break_glass` must be an attribute because an unrecorded bypass is worse than a recorded one (`fleetenvelope.md` §2, `Actor`). **The name is this document's proposal** — §9 Q3. |
| `ControlMessage` (control plane) | **none today** | — | — | ⚠️ Core NATS, no durability (`fleetenvelope.md` §2; ruling R3 of 2026-08-18, *"control (core NATS, ADR-0022 §4 preserved, lifecycle+break-glass only)"*; the type's home is `contracts/agentruntime.md` §4.2). A durable consumer **cannot read it** — core NATS delivers only to live subscribers. So a control verb is visible to telemetry ONLY through its EFFECT on the events plane. Making it a span requires the PUBLISHER to export, which contradicts the bus-consumer ruling. Fork F5. |
| `Heartbeat` (health plane) | **none** | — | — | ⚠️ Core NATS, best-effort liveness. A heartbeat is a GAUGE, and the port has no gauge. Liveness stays where it already works: the orchestrator Probes `Phase` + `LastSeq` (`contracts/agentruntime.md` §4.3). Putting heartbeats on the trace plane would be a second liveness home. |

### 3.4 ⚠️ Two open shape questions the table cannot settle alone

- **Span event vs zero-duration span.** `observability.Emit` produces a `Record{Event, Resource,
  TraceID, SpanID}` (`observability.md` §2) — a record CORRELATED to a span, i.e. structurally a
  span event. But SKILL.md §4's TraceQL pattern `{ name = "tool-end" && status = error }` matches a
  SPAN name in TraceQL, not an event name. **The `Record`→OTel mapping is `oteladapter`'s and
  `oteladapter` does not exist** (§1 TO BUILD 1), so this document states the shape it intends —
  span events — and records the tension as fork F1 rather than settling another library's design.
  Either rendering keeps every name and attribute in this table unchanged.
- **`messaging.message.id` = `MessageID`, not `Seq`.** SKILL.md §6 says `messaging.message.id`
  (= `Seq` as a string), which was correct when `Seq` was the only id and JetStream's `MsgId ==
  Seq` (`libs/go/agentruntime/natsbus/natsbus.go:126`). `fleetenvelope` mints a first-class
  `MessageID` and semconv defines `messaging.message.id` as *the system identifier for the
  message* — which `MessageID` is and `Seq` is not (`Seq` is a per-`(AgentID, plane)` cursor and
  rides as `seq`). This document uses `MessageID` and makes the SKILL.md §6 amendment part of the
  same change. Fork F2.

## 4. Task = trace

> **Mateo, 2026-08-26** (AskUserQuestion decision prompt, interactive session `f9c810a8`),
> verbatim: *"Task=trace across the whole tree — One trace spans the entire orchestrator task
> through every delegated session."*

### 4.1 What a trace is, and what it is not

✅ One **trace** = one `TaskID`. Every message of every delegated session in one orchestrator task
carries the same `TaskID` (`fleetenvelope.md` §2, §4.2 consequence 1). One **`session` span** is
the root of one harness session's contribution to that trace; one **`turn` span** is one turn
inside it. No span is held open for the task's life — §4.4 is why.

The joining mechanism is `fleetenvelope`'s and is cited, not restated:
`fleetenvelope.md` §4.2 consequence 3 (*"Sessions are spans inside the task's trace, not separate
traces. Each session opens a root span joined by the propagated context"*) and consequence 4 (the
long-trace mitigation: per-session root spans plus `TaskID` as an indexed attribute, deliberately
NOT derived from the trace id so that a dropped trace tail degrades to a `TaskID` search rather
than to nothing).

**The task-id shape is NOT an open question here.** `fleetenvelope` makes `TaskID`, `TraceParent`
and `TraceState` first-class typed header fields and supersedes `agentruntime`'s
`OTelContext map[string]string` (`fleetenvelope.md` §4.2 consequence 2, §9). This contract's whole
mapping DEPENDS on those three fields existing — that dependency is §9 Q4, not a fork of this
document.

### 4.2 What the pods do, and do not do

🔶 A fleet pod **stamps** `TraceParent`/`TraceState` on every message it mints or relays
(`fleetenvelope.Factory.Relay` preserves `TaskID` and `TraceParent` by contract —
`fleetenvelope.md` §2, conformance property 4). A pod **exports nothing**: no OTLP connection, no
SDK, no collector sidecar. A propagator is cheap; an exporter in every pod is N OTLP egress paths
from a namespace that has no observability stack.

### 4.3 ⚠️ How the consumer parents a span, and why the carrier's span-id is only advisory

This is the load-bearing derivation of the whole design, and getting it wrong produces a Tempo full
of dangling references.

If the pods do not export, then **any span-id a pod mints names a span that exists nowhere.** A
trace whose parent or link points at an unexported span-id is worse than an unparented trace: it
looks joined and is not. So:

- ⚠️ **`TraceParent`'s TRACE-ID half is authoritative.** It is what makes one task one trace, and
  the consumer honours it: every span it builds for a message carries that trace-id.
- ⚠️ **`TraceParent`'s SPAN-ID half is ADVISORY.** The consumer does not parent on it.
- 🔶 **The consumer parents on `CausedBy`.** `MessageHeader.CausedBy` names the `MessageID` this
  message answers (`fleetenvelope.md` §2, §4.1) — a message the consumer has ALREADY seen and has
  ALREADY emitted a span for, because the consumer emits every span. It keeps a bounded
  `MessageID → span-id` table (`Config.CauseWindow`) and parents from it.
- 🔶 **On a miss, it emits a LINK, never a fabricated parent and never a drop.** A miss is normal:
  out-of-order delivery, a cold start, or a cause older than the window. A link is honest about a
  relationship it can name but not nest.

**Delegation is a parent; a messaging hop is a link.** These look contradictory and are not. A
`RelayMessage` handing work DOWN a tree edge is task control flow — the child session's work
genuinely happens *inside* the parent's, and `fleetenvelope.md` §4.2.3's "joined by the propagated
context" is that nesting. A message arriving on the events plane at this consumer is the case the
messaging semconv addresses, and there a link is correct. §3's table says which is which per row.

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
3. ✅ **`messaging.message.conversation_id` (= `TaskID`) is an O(1) query key.** A TraceQL query
   `{ span.messaging.message.conversation_id = "<task>" }` returns every span of the task across
   every pod in one call. The alternative — walking the parent chain hop by hop — is O(depth) and
   fails entirely if one hop is missing. This is exactly why `fleetenvelope.md` §4.2 consequence 1
   makes `TaskID` NOT derived from the trace id.
4. ✅ **A hop ceiling is the loop breaker, and it is not this document's.**
   `fleetenvelope.MaxHops = 32`, refused loudly at the port with a `HopCeilingError` naming the
   address chain (`fleetenvelope.md` §2, §3). Depth is unbounded; TRAVEL is bounded. Conflating the
   two is how an unbounded tree becomes an unbounded loop. Cited, never re-set here.
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
   usable — a `TaskID` search over the spans that survive.

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

### 5.1 Its own durable, and the competition failure mode it avoids

✅ The obligation is `fleetenvelope`'s and is quoted rather than re-derived
(`fleetenvelope.md` §4.3): *"The obligation this places on `fleetbus` is stated there: the
telemetry consumer gets **its own durable consumer**, never a member of a delivery consumer's queue
group."*

🔶 **The failure mode, named so nobody re-creates it.** JetStream distributes a consumer's
deliveries among the members bound to THAT consumer. If the telemetry service shared a durable name
with any delivery path, each message would reach exactly ONE of them — so roughly half the fleet's
events would appear in Tempo and the other half in a browser, with neither side able to tell that
anything was missing. Nothing errors. The dashboards simply become wrong. That is one shared
config value away, which is why the durable name is a REQUIRED `Config` field with no default.

✅ Today there is no collision, because the SSE bridge opens an **ephemeral** consumer per request
with `nats.AckNone()` and `nats.BindStream(...)` (`libs/go/edenhttp/natssse/natssse.go:157-168`) —
ephemeral consumers have no durable name to share. The rule exists for the moment someone gives the
UI a durable one.

⚠️ **The wire-literal rule constrains this library's source.** `libs/go/_ctl/lib.sh`'s
`_xlib_wire_literal_scan` FAILS the `maintainability` gate if a subject format or the
`agent.*.<…>` wildcard appears as a string in more than one top-level lib's PRODUCTION code — the
remedy is to import the protocol owner and cite its helper. `fleettelemetry` therefore spells no
subject and no wildcard: §2's `EventStream.DestinationTemplate()` hands it over, and `fleetbus` must
export the accessor that renders it. **That is an obligation this document places on `fleetbus`,
which does not exist yet** (§1 TO BUILD 5).

### 5.2 Cursor and replay — three numbers that are not one number

⚠️ Three sequences travel together and mean different things:

| number | scope | home |
| --- | --- | --- |
| `MessageHeader.Seq` | monotonic per `(AgentID, plane)` — the replay + checkpoint cursor | `fleetenvelope.md` §4.1 |
| the **stream** sequence | monotonic per STREAM, counting every message from every agent | the bus |
| `agentsession.Event.Seq` | the durable transcript offset of one session | `agentsession` |

The durable's stored cursor is a **stream** sequence. `Delivery.StreamSequence` carries it
separately from the header's `Seq` for exactly that reason, and a resume is expressed in stream
sequences, never in `Seq`.

⚠️ **The distinction is not academic — today's code conflates it.**
`natssse.openConsumer` passes `nats.StartSequence(lastSeq+1)` where `lastSeq` is the SSE
`Last-Event-ID` (`natssse.go:157-168`), and the SSE id is set from `envelope.Seq`
(`natssse.go:179-182`). `nats.StartSequence` sets a JetStream **stream** sequence. The two are equal
only when the stream holds exactly one session's events from its first message — which is true of a
single-agent test fixture and false of a fleet. **This contract does not fix that; it belongs to
`edenhttp`/`natssse`.** What this contract fixes is that the telemetry consumer must not inherit it.

### 5.3 At-least-once, and what that costs

⚠️ JetStream redelivers on ack timeout. **OTel emission is NOT idempotent.** Rebuilding a span
after a redelivery mints a NEW span id, and Tempo stores spans by trace id without de-duplicating
them — so a redelivery yields a duplicate span inside a real trace, which silently inflates every
count and every duration percentile computed from it. Saying "JetStream is exactly-once" would be
false here: `MsgId` dedup protects the PUBLISH side, not this consumer's export side.

Three honest positions, and this document takes the second:

| # | position | cost |
| --- | --- | --- |
| a | accept duplicates | counts and percentiles derived from spans are wrong by an unknown factor |
| b | 🔶 **deterministic span ids** — derive the 8-byte span id from `hash(TraceID, MessageID, span-role)`, so a redelivery produces a byte-identical span | a hash collision merges two unrelated spans; the derivation becomes part of the wire contract |
| c | a de-dup table of exported `MessageID`s | unbounded state, and it is exactly the durable's own job done twice |

`Delivery.Redelivered` is on the port so the consumer can also STAMP `messaging.redelivered=true`,
making a duplicate visible in the store rather than merely present. Fork F3.

### 5.4 Fail loudly — never a silent drop

This is where the frozen port's shape forces the design, and it is the single most important
paragraph of §5.

⚠️ **`Provider.Emit` is non-blocking, best-effort and returns NO error** (`provider.go:13-17`;
`observability.md` §6 rationale 3 — "a dropped Event can never fail a phase"). **`Flush` is the ONLY
blocking call and the ONLY one that returns an error** (`provider.go:36-39`). So the consumer
**cannot learn from `Emit` that an export failed.** Therefore:

1. The consumer builds spans for a batch, then calls `Telemetry.Flush(ctx)`.
2. **It calls `Envelopes.Ack` ONLY after `Flush` returned nil.** An ack before a durable export is
   a silent drop — the message is gone from the durable and the span never reached Tempo.
3. On a `Flush` error it calls `Envelopes.Nak` with backoff. It never acks. It never logs
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

🔶 The `Tail` path is deliberately EXCLUDED from this discipline: `Tail.Publish` is best-effort per
subscriber and never gates an ack. A slow browser must never stall the telemetry export, and a
disconnected browser must never NAK a message.

## 6. The UI streaming read model

> **Mateo, 2026-08-26**, verbatim selection: *"Bus consumer"* — one telemetry service consumes
> JetStream → OTel, and the same consumer feeds UI streaming.

### 6.1 ⚠️ The platformgateway-vs-agentgateway discrepancy, stated rather than silently resolved

The ruling names `platformgateway` SSE. The code says otherwise, measured 2026-08-26:

| app | what it actually serves | evidence |
| --- | --- | --- |
| `apps/agentgateway` | `GET /sessions/{id}/events` — the SSE bridge, plus control/prompt/steer/abort/stop/kill | `internal/stateless/events.go:15-40`, handler at `:54-84`, driving `natssse.Bridge` |
| `apps/platformgateway` | the **connectors** domain and nothing agent-shaped: `connectors`, `me`, `ping`, `users` | `internal/api/v1/` — four domains + `mount.go` |

`platformgateway` carries **no agent-event surface today**. `agentgateway` is the app that does,
and its path is gate-proven against a real embedded nats-server and a real nats container
(`contracts/edenhttp.md` status header). This document does not pick one — §9 Q1 does.

### 6.2 Live tail and history, joined without a gap or a duplicate

🔶 Two shapes are possible, and they differ in whether "the same consumer feeds UI streaming" is
literally true:

- **α — two independent readers.** The gateway keeps opening its own ephemeral consumer (today's
  behaviour, `natssse.go:157-168`) and the telemetry consumer reads its own durable. No coupling,
  no handover, no gap risk. But the ruling's phrase is then false: two consumers, not one.
- **β — one durable, one hub.** The telemetry consumer publishes every delivery to `Tail`, and the
  gateway subscribes. The hub is LIVE-ONLY, so history must still come from a bus replay, and the
  join between the two is where a gap is born.

🔶 **The handover rule for β, which is the only part that needs stating:**

1. The client sends a cursor (`Last-Event-ID`, or `?from-seq=`; absent both, `CursorAll == 0` means
   full replay — `libs/go/edenhttp/sse.go:12-32`).
2. The gateway asks `Tail.Oldest(agent)`. If the hub holds nothing, it replays to live and
   subscribes.
3. Otherwise it replays from the cursor **up to and including** the hub's oldest sequence, then
   switches to the hub.
4. **Overlap is required; a gap is forbidden.** Replaying up to the oldest held sequence guarantees
   at least one duplicate at the seam. That is the correct trade: **duplicates are tolerated, gaps
   never**, because a client can discard a repeat and cannot invent a missing event.
5. ✅ The mechanism that makes both checkable already exists: the SSE frame id is the event `Seq`
   (`natssse.go:179-182`), and `Seq` is monotonic per session (`agentsession` invariant). A client
   discards any id ≤ the last it rendered, and detects a gap as a jump of more than one.

Fork F4 carries α vs β. Note that α is what is BUILT and β is what the ruling's wording implies.

## 7. Invariants (load-bearing)

Each row states whether it is provable TODAY. A row marked TO BUILD is a promise, not a property.

| # | invariant | tag | provable today? |
| --- | --- | --- | --- |
| I1 | The consumer is the ONLY process in the fleet that speaks OTLP. Pods stamp the carrier and export nothing. | 🔶 | TO BUILD — `oteladapter` does not exist (§1/1) |
| I2 | No span name contains an id. Bus span names use the SUBJECT TEMPLATE; identity rides as attributes. | ✅ rule | testable by a lint over span names once the library exists |
| I3 | A cross-pod messaging edge is a LINK given at CREATION, never `AddLink`, never a parent. | ✅ rule (`trace/span.go:37-40`) | TO BUILD |
| I4 | A link is OMITTED, never dangled: the consumer never references a span-id it did not export. | ⚠️ | TO BUILD — and this is what fails silently if I1 is violated |
| I5 | No secret reaches an attribute. `Field.Value` is a `Valuer`; `EventExtension` contributes only its byte count. | ✅ (`observability.md` §6.4) | the type system already enforces the general case |
| I6 | `Ack` happens only after a `Flush` that returned nil. | ⚠️ | TO BUILD — §5.4 |
| I7 | An export that cannot be flushed within `ExportBudget` FAILS the process. It is never acked and never logged-and-continued. | ✅ rule (ADR-0020 FAIL-NOT-SKIP) | TO BUILD |
| I8 | The telemetry durable name is never shared with a delivery consumer. | ✅ (`fleetenvelope.md` §4.3) | enforceable by `fleetbus`; no collision exists today |
| I9 | `fleettelemetry` spells no subject and no wildcard. | ✅ enforced | the detector is live today: `libs/go/_ctl/lib.sh:542` `_xlib_wire_literal_scan`, run by the `maintainability` verb |
| I10 | `go.opentelemetry.io/otel*` is imported ONLY by `oteladapter`. | ✅ rule (SKILL.md §5) | enforceable by depguard, and the ground is clean: `go.opentelemetry.io/otel` appears in eden only as `// indirect`, in `libs/go/workspaceprovider/go.mod:63-66` and `libs/go/orchestrator/go.mod:71-74`, both pinned v1.44.0. There is **no direct OTel dependency anywhere in eden today.** |
| I11 | The UI stream tolerates a duplicate and never a gap. | 🔶 | testable against a real nats-server, as `edenhttp` already does |
| I12 | No metric is emitted, because the port has no `Counter` and no `Histogram`. | ✅ (`observability.md` §6.1) | true today, by construction |

## 8. Forks

| # | fork | position A | position B | 🧩 resolution |
| --- | --- | --- | --- | --- |
| F1 | **`Record` → OTel shape.** Is an `Emit`ted record a span EVENT on the open span, or a zero-duration SPAN? | span event — matches `Record{TraceID, SpanID}`, which is a record correlated TO a span | zero-duration span — matches SKILL.md §4's `{ name = "tool-end" && status = error }`, which is a TraceQL span-name match | 🧩 **Open.** The decision is `oteladapter`'s, and `oteladapter` does not exist. §3 states the intent (span event); every name and attribute is unchanged under either. |
| F2 | **`messaging.message.id` source.** | `fleetenvelope.MessageID` — semconv's "system identifier for the message" | `Seq` — SKILL.md §6's current text, from when `Seq` was the only id | 🧩 **Recommend A**, and amend SKILL.md §6 in the same change. `Seq` keeps its own `seq` attribute. |
| F3 | **Duplicate spans on redelivery.** | accept duplicates | 🔶 deterministic span id from `hash(TraceID, MessageID, span-role)` | 🧩 **Recommend B** with `messaging.redelivered` stamped, so a duplicate is visible rather than merely present. §5.3. |
| F4 | **UI stream topology.** | α — the gateway keeps its own ephemeral consumer (what is BUILT) | β — one durable + a live hub, with the §6.2 handover (what the ruling's wording implies) | 🧩 **Open — §9 Q1 decides it together with which app serves it.** |
| F5 | **Control and health planes.** Core NATS has no durable read, so a durable consumer cannot observe them. | leave them off the trace plane; liveness stays the orchestrator's Probe | give them a durable plane so telemetry can read them | 🧩 **Recommend A for v1.** B is a `fleetbus` change, not a telemetry change. |
| F6 | **The `session` / `relay` span names.** Neither is in SKILL.md §6's list. | adopt them here and amend SKILL.md in the same change | reuse an existing name | 🧩 **Recommend A** — this contract is the vocabulary's home for fleet telemetry, and SKILL.md §6's own rule is that names come from the contract. §9 Q3. |
| F7 | **`agent.address` / `agent.parent.address` attributes.** SKILL.md §6 forbids inventing a flat tree-path attribute *"If a flat path attribute is wanted, change `contracts/agentruntime.md` first."* | adopt them, named after `fleetenvelope`'s own `Address`/`ParentAddress` fields, CONDITIONAL on that contract freezing | omit them; parentage is the traceparent only | 🧩 **Recommend A on freeze, not before.** The skill's precondition is "change the contract first", and `fleetenvelope` is that change. The forbidden name `agent.tree.path` is not used. |
| F8 | **The turn ordinal has two homes.** `MessageHeader.Turn uint64` and `agentsession.Event.Turn int`. | stamp `turn` from the HEADER — present on all four message types | stamp it from the Event — present only on events | 🧩 **Recommend A**, and a conformance property asserting the two agree on an `EventEnvelope`. |
| F9 | **The 2026-08-18 fleet SYNTHESIS still says the opposite.** ⚠️ *Corrected from an earlier framing:* the LOCKED 2026-08-18 ruling (*"OTel: from day one — exporter as a log consumer"*) and the 2026-08-26 bus-consumer ruling **AGREE**, as `fleetenvelope.md` §4.3 states. It is the SYNTHESIS text (an in-process `oteladapter` in every workload, cross-pod edges as links) that disagrees with both. | the two rulings govern; the synthesis text is superseded on this point and says so in writing | the synthesis is reopened | 🧩 **Recommend A** — §9 Q2 records it. A pod that mints a span context it never exports produces dangling links (§4.3), which is the technical reason as well as the procedural one. |

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

> ### Q3 — Do you accept the three names this document ADDS to the vocabulary?
>
> `session` (the session root span), `relay` (the tree-edge span), and the attributes
> `agent.address` / `agent.parent.address`. SKILL.md §6's rule is that span names come from the
> contract vocabulary and that a flat tree-path attribute requires the contract to change FIRST.
>
> - **(a) RECOMMENDED — accept all three, and amend `~/.claude/skills/eden-otel-debug/SKILL.md` in
>   the SAME change.** **Reason:** this contract is that vocabulary's home for fleet telemetry, so
>   adding here is the sanctioned path rather than an exception to it; and `fleetenvelope` making
>   `Address`/`ParentAddress` first-class typed fields is exactly the precondition the skill
>   demands. The forbidden name `agent.tree.path` is NOT used — the attributes are named after the
>   fields. Instrumentation that describes a contract it no longer matches is the false-context
>   failure the housekeeping rule exists to prevent, so the amendment must not lag.
> - **(b) Accept the span names, omit the address attributes.** Cost: the tree is then visible only
>   through span nesting, and a broken nesting hides it entirely.
> - **(c) Reject; reuse existing names.** There is no existing name for a session root or a relay.

> ### Q4 — The stated dependency: this contract cannot freeze before `fleetenvelope` does.
>
> Every attribute in §3 comes from a header field. The mapping is valid **only if `fleetenvelope`
> freezes with `TaskID`, `TraceParent` and `TraceState` as first-class required fields**
> (`fleetenvelope.md` §2, §4.2). If any of the three is dropped or reshaped in that freeze, §3 and
> §4 are wrong and this document is re-drafted, not patched. `fleetbus` is a second dependency: it
> owns the durable's mechanics and the `DestinationTemplate` accessor §5.1 requires, and **it has
> no document and no library on disk today** (§1 TO BUILD 5).
>
> - **(a) RECOMMENDED — one decision covers both contracts, `fleetenvelope` first.** **Reason:**
>   freezing this one first would freeze a mapping onto fields that are not yet promised, which is
>   the same class of error as citing an ADR that does not exist. `fleetenvelope.md` §11 already
>   notes that ADR-0030 is reserved and absent (`docs/architecture/adr/` runs 0029 → 0031,
>   verified) and should land in the same decision.
> - **(b) Freeze this contract conditionally**, with a re-refutation obligation on any
>   `fleetenvelope` change. Cost: a conditional freeze is not a freeze, and the phase gate cannot
>   express it.

> ### Q5 — Are metrics in scope for v1 at all?
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

> ### Q6 — What is the TRACE retention, given that no ruling covers it?
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
>   capacity change that should be measured rather than assumed. Mitigation 3 (`TaskID` as an O(1)
>   query key) is what keeps a task readable after its trace tail is evicted.
> - **(b) Align traces to 30 days.** Cost: a capacity change on the cloud object store, unmeasured.
> - **(c) Defer.** Cost: the first task longer than 7 days loses its head silently, and nobody
>   learns why.

**Answering Q1 and Q4 is mandatory for a freeze**, because Q1 changes §6's surface and Q4 is a
precondition on another contract. Q2, Q3, Q5 and Q6 may be delegated, but Q2 governs whether any
lane can start against §3.

**No part of this document is ratified.** Every ✅ marks a measured fact or a cited rule, never
Mateo's approval. As of 2026-08-26 the gate is **not individually exercised**.
