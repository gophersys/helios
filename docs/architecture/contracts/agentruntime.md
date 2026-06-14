# Contract — agentruntime

> Status: Frozen (ADR-0022 §4 + Consequences) · 2026-06-14 · The Milestone-B B3 PID-1 agent-pod
> runtime sidecar + the NATS/JetStream reactive bus. Frozen with the library built: the exported
> surface is mechanically recorded at `libs/go/agentruntime/.apibaseline` (the freeze made
> mechanical, ADR-0020) and the ADR-0020 8-dimension test taxonomy is green against a REAL embedded
> nats-server + a REAL nats container + a REAL agentsession subprocess. This is a **connector-shaped
> runtime library** (it spawns a harness behind the frozen `agentsession` Factory and bridges it onto
> a bus behind a consumer-defined `Bus` port). A breaking change to the surface requires a contract
> revision (ADR-0016 §1) + re-recording the `.apibaseline` — the cardinal sin otherwise (10 §9).
>
> Epistemic legend: ✅ ratified · 🔶 derived-but-settled · ⚠️ load-bearing assumption · 🧩 open fork.

## 1. Scope

✅ `agentruntime` is the **agent-pod PID-1 runtime sidecar**: the container's main process (the
`workspaceprovider` Entrypoint/workload-pod capability, ADR-0022 §4) on docker AND kubernetes. It
resolves its agent, spawns the harness **in-process** through the frozen `agentsession.Factory`,
pumps that session's normalized `Event` stream, and bridges it onto a **NATS/JetStream reactive
bus** over three per-agent subjects, every message carrying **OTel trace context**:

- **PUBLISHES** the sequenced `agentsession.Event` stream to `agent.<id>.events` (JetStream-durable,
  replay-by-`Seq` — the B5 gateway NATS→SSE bridge consumes this).
- **SUBSCRIBES** `agent.<id>.control` for the **soft control signal** (prompt/steer/abort/stop/kill)
  and maps each verb onto the `agentsession.Session` (+ a kill path via the active-agent registry).
- **PUBLISHES** periodic `agent.<id>.health` heartbeats the **thinned** orchestrator Probes.

✅ `Run(ctx)` IS the **graceful-shutdown state machine** (ADR-0022 Consequences): the caller passes
the `signal.NotifyContext` parent → a termination trigger yields a typed `TerminationReason` →
cancel → drain the in-flight turn (bounded) → close the session → flush OTel → return the reason. A
small HTTP surface (`/live`, `/health/{id}`) serves the kubelet probes.

It does **not** own (one concept, one home — it **CONSUMES** these frozen ports, never redefines
them):

- the harness spawn / the `Event` taxonomy / `Seq` ordering — **agentsession** (ADR-0008). The
  sidecar transports `agentsession.Event` **verbatim**; it never re-spells the taxonomy.
- the **hard** docker-or-kubernetes lifecycle / pod provisioning — **workspaceprovider** (ADR-0016/
  0022). The bus is only the **SOFT** signal; the docker/k8s API kills the container (ADR-0022 #4).
- credential storage/minting — **secrets** + Vault. The `agentsession.Spec` it carries holds an
  **opaque, loggable `secrets.Reference`** resolved server-side; no value ever rides a bus message.
- desired-state reconciliation — **orchestrator** (it Probes the heartbeats; it does not run here).

## 2. Construction (the spine)

```go
func New(configuration Config, dependencies Deps) (*Runtime, error)
```

✅ `New` is **PURE** (10 §9): no I/O, no clock read, no env read, no harness spawn (that is `Run`).
It validates the invariants — a present `AgentID`, every required port non-nil — and returns a typed
`*ConfigError` (`errors.KindInvalid`) on a violation so the composition root fails fast and loud.
(`Config`/`Deps` are the idiomatic Go exported type names HNS-1 rule 11 sanctions — a *package* or
*directory* named `config`/`deps` would not be.)

`Config` is the immutable, fully-resolved sidecar input (the configuration pattern): the `AgentID`
that scopes the three subjects + keys the registry + stamps every message; the `agentsession.Spec`
the harness is Opened with (passed through verbatim); `HeartbeatInterval`, `DrainTimeout`, and an
optional `InitialPrompt` (the batch/seed-prompt path; zero/empty selects the default or the
interactive path). It holds **no secret value** — only the `Spec`'s loggable `Reference`.

`Deps` is the injected hexagon; every field is required (a nil port is a `New`-time `ConfigError`):

| Port | Type | Role |
|---|---|---|
| `Sessions` | `agentsession.Factory` | the frozen Factory the sidecar Opens the harness through, in-process |
| `Bus` | `agentruntime.Bus` (consumer-defined) | the reactive-bus port — `natsbus.Adapter` in production, a fake in the fast lanes |
| `Observer` | `agentruntime.Observer` (consumer-defined) | the OTel/telemetry sink + the trace-carrier inject/extract; `Flush`ed at shutdown |
| `Clock` | `agentruntime.Clock` | the sidecar's ONLY time source (heartbeat cadence + `EmitTime` stamps) |

## 3. The ports (consumer-defined, ≤5 methods — 10 §9)

```go
// Bus — the SHAPE OF THE NEED, not a mirror of NATS. natsbus.Adapter is the real impl.
type Bus interface {
	PublishEvent(ctx context.Context, envelope EventEnvelope) error              // JetStream-durable, MsgId == Seq
	PublishHealth(ctx context.Context, heartbeat Heartbeat) error                // core NATS, best-effort liveness
	SubscribeControl(ctx context.Context, agentID AgentID, handle func(ControlMessage)) error // until ctx cancel
}

// Observer — log + flush + the W3C trace-carrier transform (OTel on EVERY message).
type Observer interface {
	Logf(ctx context.Context, format string, args ...any)
	Inject(ctx context.Context) OTelContext                           // active trace → carrier on publish
	Extract(ctx context.Context, carrier OTelContext) context.Context // carried trace → child ctx on consume
	Flush(ctx context.Context) error                                  // the OTel-flush shutdown step
}

type Clock interface{ Now() time.Time }
```

✅ `Bus` is realized ONCE by `natsbus` (the only place `github.com/nats-io/nats.go` is imported,
05 §1). ✅ `Observer` is realized by `otelobserver` over the frozen `observability.Provider` (the
only place `agentruntime` depends on `observability`, kept off the root so the port stays
consumer-defined).

## 4. The typed message protocol — three subjects (the minimal reactive contract)

✅ The wire codec is JSON (small, evolvable, `nats`-CLI-debuggable; the `agentsession.Event` it
carries marshals cleanly). The subject grammar has ONE home — `EventsSubject`/`ControlSubject`/
`HealthSubject(id)` — never re-spelled. **OTel context rides EVERY message** on all three subjects
(the `OTel OTelContext` field; the ADR-0022 invariant).

### 4.1 `agent.<id>.events` — `EventEnvelope` (sidecar → bus, JetStream-durable)

```go
type EventEnvelope struct {
	AgentID  AgentID            `json:"agentId"`
	Seq      uint64             `json:"seq"`      // the agentsession transcript offset; the JetStream replay key
	Event    agentsession.Event `json:"event"`   // the FROZEN normalized agentsession Event, transported verbatim
	OTel     OTelContext        `json:"otel,omitempty"`
	EmitTime time.Time          `json:"emitTime"` // the sidecar Clock instant the envelope was published
}
```

✅ **Sequencing / replay design.** `Seq` is the `agentsession` durable-transcript offset (`Seq ==
transcript offset`, the agentsession invariant). The sidecar pumps `Events(ctx, FromSeq(0))` and
publishes each event in `Seq` order. The `natsbus` adapter sets the JetStream **MsgId to the `Seq`**,
so JetStream de-dups exactly-once and a consumer (the B5 gateway) **replays the ordered stream from
any `Seq`** via JetStream durable replay — gap-free and dup-free by construction. The events stream
`EDEN_AGENT_EVENTS` captures `agent.*.events` (one stream, subject-filtered per agent).

### 4.2 `agent.<id>.control` — `ControlMessage` (orchestrator → sidecar, the SOFT signal)

```go
type ControlMessage struct {
	AgentID AgentID     `json:"agentId"`
	Verb    ControlVerb `json:"verb"`            // prompt|steer|abort|stop|kill
	Text    string      `json:"text,omitempty"`  // prompt/steer payload; empty for abort/stop/kill
	By      string      `json:"by,omitempty"`    // audit identity (user id or "policy:<name>")
	OTel    OTelContext `json:"otel,omitempty"`
}
```

✅ **Verb mapping** (ADR-0022 #4 vocabulary): `prompt`→`agentsession CommandPrompt`;
`steer`→`CommandSteer` (degrades per `CapSteer`); `abort`→`CommandAbort`; `stop`→a **graceful** drain
(drain the in-flight turn, close the session, exit `TerminationControlStop`); `kill`→an **immediate**
cancel via the active-agent registry (`TerminationControlKill`). An out-of-phase/unsupported verb is
logged and degrades per `agentsession`; it never panics the sidecar. The carrier on the message
**parents the verb's telemetry to the orchestrator's publish span** (`Observer.Extract`).

### 4.3 `agent.<id>.health` — `Heartbeat` (sidecar → bus, best-effort liveness)

```go
type Heartbeat struct {
	AgentID      AgentID            `json:"agentId"`
	Phase        HealthPhase        `json:"phase"`        // starting|running|draining|stopped (the SIDECAR phase)
	SessionState agentsession.State `json:"sessionState"` // the harness turn state
	LastSeq      uint64             `json:"lastSeq"`      // the highest event Seq published so far
	At           time.Time          `json:"at"`
	OTel         OTelContext        `json:"otel,omitempty"`
}
```

✅ The thinned orchestrator (ADR-0022 #4) **Probes THIS** — `LastSeq` lets it derive "is the stream
advancing?", `Phase` is the sidecar's own PID-1 phase (distinct from the `agentsession.State` it
carries alongside), `SessionState` is the harness turn state. Core NATS, no durability — the
orchestrator reads the latest, never a replay.

## 5. Lifecycle / state-machine guarantees (`Run` — the PID-1 contract)

✅ `Run(ctx) (TerminationReason, error)` is called ONCE per `Runtime`. It:

1. derives the agent ctx and **REGISTERS** it (the kill path);
2. **Opens** the harness session through `agentsession.Factory.Open` (in-process) — an Open error
   returns `TerminationFault` + a wrapped `KindUnavailable` error after flushing OTel;
3. starts the **heartbeat ticker** (first beat immediate) + the **control subscription**, seeds the
   `InitialPrompt` if set, then **PUMPS** the event stream → `recordAndPublish` per event;
4. on the **first termination trigger** — parent-ctx signal | `stop` verb | `kill` verb | the session
   reaching its own terminal — DRAINS the in-flight turn (`Close` bounded by `DrainTimeout`; a `kill`
   bypasses the drain by canceling first), publishes a `stopped` heartbeat, **FLUSHES OTel**, and
   returns the typed `TerminationReason`.

✅ **Reaping (goleak-clean).** `Run` owns the pump goroutine, the heartbeat ticker goroutine, and the
control subscription, and **joins ALL of them** (cancel-then-WaitGroup) before returning. No
goroutine, no NATS subscription, no harness process outlives `Run`. `CountOwned == 0` after Run.

✅ **`TerminationReason`** (closed, append-only): `signal`, `control-stop`, `control-kill`,
`session-end`, `fault` (+ the zero `unknown`, never returned by a clean Run). `IsGraceful()` is true
for signal/stop/session-end so `main()` maps it to exit 0.

✅ **HTTP probes.** `ProbeHandler()` returns a `*http.ServeMux`: `GET /live` (process liveness, 200
while serving, body reports active-agent count) and `GET /health/{id}` (per-agent readiness, 200
while the agent is registered+active, 503 once drained/exited — so a readinessProbe drains traffic
from a stopping pod). Read-only over the registry; safe to serve concurrently with `Run`.

## 6. The active-agent registry (the kill path)

✅ `activeAgent{id, cancel, active}` is the cancelable registration the `kill` verb consults to
cancel the agent's context immediately (the hard stop that bypasses a graceful drain), and the
liveness bit `/health/{id}` reads. Keyed by `AgentID` as a map so the docker-multiplexed dev path
(ADR-0022/Phase 4: "multiplexed on docker") and a future N-agent pod register without a structural
change — additive by construction (one-agent-per-pod is the k8s default, not a hard limit). Safe for
concurrent use (a control-goroutine `Kill` vs the run loop's register/deregister).

## 7. Invariants (load-bearing, gate-proven)

- ✅ **OTel on every message** — `Inject` stamps the carrier on every publish; `Extract` re-parents a
  consumed control verb. Proven non-vacuous by a weaken-to-confirm (drop the carrier → the
  propagation assertion fails).
- ✅ **`Seq`-ordered, gap-free, dup-free events** — the pump publishes in `Seq` order; JetStream
  MsgId == `Seq` de-dups. Proven against a REAL nats-server + a REAL agentsession subprocess (the
  integration lane); weaken-to-confirm by breaking the order.
- ✅ **No secret on any bus message** — the credential is an opaque `Reference` in the `Spec`,
  resolved server-side by agentsession; the canary no-leak property asserts it never reaches an
  envelope/heartbeat/control message/log/error.
- ✅ **Real substrate, never mocked** — the bus behavior is proven on a REAL embedded
  `nats-server/v2` (fast lanes) AND a REAL `nats` container (the integration lane); never a
  hand-rolled NATS-protocol fake.

## 8. Forks

- 🔶 **Embedded nats-server for the fast lanes + a container for integration.** The plan named "a
  real NATS"; the fast/lifecycle/load lanes boot a real in-process `nats-server/v2` (a real server,
  not a mock — millisecond startup, deterministic) and the integration lane additionally boots a
  real `nats:latest` container (docker-out-of-docker, the vaultadapter posture). Both exercise the
  same `natsbus.Adapter` against a real JetStream. (Settled: a real embedded server satisfies
  "no mocks"; the container proves the cross-process wire.)
- 🔶 **JSON wire codec.** Chosen over a binary codec for evolvability + `nats`-CLI debuggability; the
  protocol is small and the `agentsession.Event` marshals cleanly. (Settled; revisit only if a
  measured hot-path cost appears — the bench lane guards it.)
- 🔶 **`Observer` as a 4-method consumer port** rather than reusing `observability.Provider` (5
  methods) directly. The sidecar's need is narrower (log/flush + the carrier transform), and keeping
  the port consumer-defined keeps the root free of an `observability` import. `otelobserver` bridges.
