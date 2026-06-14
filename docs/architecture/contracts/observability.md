# Contract — observability

> Status: Frozen (ADR-0016) · 2026-06-13 · Reconciled from independent producer/consumer drafts (09 §4) and frozen with the library built: the exported surface is mechanically recorded at `libs/go/observability/.apibaseline` (the freeze made mechanical, ADR-0020), the slogadapter Exporter seam is conformance-tested, and the ADR-0020 8-dimension test taxonomy is green. A breaking change to the surface requires a contract revision (ADR-0016 §1) + re-recording the `.apibaseline` — the cardinal sin otherwise (10 §9).

## 1. Scope

`observability` is the universal **structured-Event** port: one OTel-aligned stream carrying P9's
three planes — (a) Eden's own runtime, (b) agent telemetry (runs, transcripts, tokens, gate
decisions, validation failures), (c) generated-system telemetry — secret-safe **by construction**.
It owns the `Event` vocabulary, the outbound `Provider` port (emit / scope / log / flush), span-like
phase/model-call scoping, severity filtering, resource stamping of `deployment.environment.name`
(10 §2), and the T6 token/cost ledger as a typed `Event`.

It explicitly does **not**: own a backend (that lives behind the `Exporter` seam — `oteladapter`,
`slogadapter`); promise an OTel-SDK-shaped public API (the `Event` vocabulary is the stable contract,
OTel is one adapter); read `EDEN_ENVIRONMENT`, any other env var, or a clock in `New` (spine purity,
10 §4; stage arrives frozen via `Config`, time via an injected `Clock`); or accept a bare `any`/`string`
for a field value (the only door for sensitive data is `Valuer`, so a raw secret cannot be telemetered).

## 2. Contract

```go
// Package observability is the Eden universal structured-Event port (10 §4, P9):
// one OTel-aligned stream carries all three planes — (a) Eden's own telemetry,
// (b) agent telemetry (runs, transcripts, tokens, gates), (c) generated-system
// telemetry — secret-safe by construction. Components EMIT Events into the
// outbound Provider; adapters (oteladapter, slogadapter) carry them to a backend
// behind the Exporter seam. The library owns the Event vocabulary and the
// emission contract; it does NOT own the backend and does NOT track the OTel SDK
// shape (Event is the stable contract; OTel is one adapter).
//
// Module: github.com/gophersys/libs/go/observability  (go 1.26)
//
// Concurrency: a Provider is safe for concurrent use from many goroutines; Emit,
// With, Scope, and Log may be called concurrently. With/Scope return values that
// share the underlying Exporter but carry independent inherited Fields/span
// state. Flush is the sole blocking call and is called at shutdown / run
// boundaries, never on the hot path.
//
// Zero value: a zero Event is a Debug Event on the Config.DefaultPlane with no
// fields and a zero Time (the adapter stamps "now"); an adapter renders it, never
// rejects it. Zero Config.MinSeverity == SeverityDebug == emit everything
// (fail-open on visibility, never silently dark). The zero Provider is NOT usable
// — obtain one from New.
//
// Errors: only New and Flush return errors. New returns a *ConfigError
// (inspectable via errors.AsType). Flush wraps the Exporter's I/O cause with %w.
// Emit/With/Scope/Log NEVER return an error — telemetry failure must not enter
// business logic (a dropped Event can never fail a phase).
package observability

import (
	"context"
	"time"
)

// ── Event: the one structured record every plane emits ──────────────────────

// Plane is the P9 telemetry plane an Event belongs to. It is STAMPED, never
// inferred, so a single backend partitions Eden's own signal from agent and
// generated-system signal without parsing payloads. Zero value is PlaneUnset so
// an unstamped Event visibly inherits Config.DefaultPlane rather than silently
// landing on plane (a).
type Plane uint8

const (
	PlaneUnset     Plane = iota // zero: inherit Config.DefaultPlane at Emit
	PlaneSelf                   // (a) Eden's own runtime
	PlaneAgent                  // (b) agent runs, transcripts, tokens, gate/validation events
	PlaneGenerated              // (c) the system Eden builds for the user
)

// Severity is the operator-facing level carried on an Event. The subordinate
// logging Sink (10 §4) rides this same stream rather than opening a second
// channel; logging is exactly the projection of Events at/above a level. Values
// map mechanically onto OTel SeverityNumber ranges in oteladapter. The zero
// value is SeverityDebug so an unstamped Event is never silently dropped.
type Severity uint8

const (
	SeverityDebug Severity = iota
	SeverityInfo
	SeverityWarn
	SeverityError
)

// Event is the single, immutable unit of the stream — a plain value: copyable and
// safe to construct from its zero value. Never mutate a delivered Event. Time is
// supplied by the injected Clock at the emit site (Scope) or left zero for the
// adapter to stamp; the library itself reads no clock (spine purity, 10 §4).
//
// Event carries NO secrets by construction: Fields holds only Valuer, whose
// redacted projection is the only thing that reaches the wire (see Field). The
// Name is the stable, low-cardinality OTel span/log name.
type Event struct {
	Time     time.Time // emission time; zero == "adapter stamps now"
	Plane    Plane     // P9 plane; PlaneUnset inherits Config.DefaultPlane at Emit
	Severity Severity
	Name     string  // stable, dotted, low-cardinality: "model.call", "phase.start", "cost.ledger", "gate.decision"
	Fields   []Field // structured attributes; order-preserving, append-only at the call site
}

// Field is one structured, redaction-safe attribute. Keys are OTel-attribute-
// shaped (dotted.lower.case). Value is a Valuer, never a bare any, so a
// secret-bearing type can enter ONLY as its already-redacted projection — the
// type system, not a runtime filter list, keeps secrets off telemetry (P9, 07 §2).
type Field struct {
	Key   string
	Value Valuer
}

// Valuer yields a telemetry-safe representation of an attribute. The secrets
// library's Secret satisfies it by returning secrets.Redacted; primitives are
// wrapped by the String/Int64/Float64/Bool/Dur/Err constructors below. This is
// the ONLY door onto the stream for a field value — there is no any-typed field
// and no String(key, secret.Reveal()) shortcut, by design.
type Valuer interface {
	// TelemetryValue returns a value safe to serialize to any backend. It MUST NOT
	// expose secret material; redaction is the implementer's contract.
	TelemetryValue() any
}

// ── Provider: the outbound port the hexagon depends on ──────────────────────

// Provider is the single port a consumer holds in its Deps (accept this
// interface; New returns the concrete impl). Exactly 5 methods — the negotiated
// ceiling (10 §9). Cross-cutting logic (resource stamping, severity filtering,
// Field inheritance, span timing) lives ONCE in the internal impl; an adapter
// implements only the Exporter seam.
type Provider interface {
	// Emit records one Event on the stream. Non-blocking and best-effort: an
	// adapter buffers or drops, it never blocks the caller's goroutine on I/O, and
	// it returns no error. ctx carries the active span (trace/span correlation)
	// and cancellation. An Event below Config.MinSeverity is filtered here.
	Emit(ctx context.Context, event Event)

	// With returns a child Provider carrying inherited Fields (request/run scope —
	// e.g. run.id). It allocates and inherits; it does not emit and does not open a
	// span. Cheap; use it for static scope a library stamps onto every Event.
	With(fields ...Field) Provider

	// Scope opens a correlated span for a unit of work (a phase, a model call). The
	// returned ctx carries the span; call the returned func when the unit completes
	// — it stamps duration (from the injected Clock) and outcome and emits the span
	// Event. Use it where duration/outcome matter; use With for plain inheritance.
	Scope(ctx context.Context, name string, fields ...Field) (context.Context, func(outcome Outcome))

	// Log emits an operator-facing leveled line as a SeverityN Event on the same
	// stream — logging (10 §4) is a VIEW over this Provider, not a parallel pipe.
	// This is the subordinate-Sink seam: logging depends on observability, never
	// the reverse, and one backend renders both leveled lines and structured Events.
	Log(ctx context.Context, sev Severity, message string, fields ...Field)

	// Flush drains buffered Events to the Exporter. It is the ONLY blocking method
	// and the ONLY one (besides New) that returns an error; honors ctx deadline and
	// is called at shutdown and at run/phase boundaries by the engine.
	Flush(ctx context.Context) error
}

// Outcome closes a Scope: success or a wrapped error, recorded on the span Event
// (never logged raw). Err == nil is success.
type Outcome struct {
	Err error // nil == success; wrapped via %w upstream, inspected via errors.AsType
}

// ── The constructor spine (10 §4) — PURE ────────────────────────────────────

// Config is the immutable, fully-resolved input (the configuration pattern):
// parsed at the edge and frozen. It holds NO ports and NO live handles.
// ServiceName/ServiceVersion/Environment/ResourceAttrs become the OTel Resource;
// Environment is stamped as deployment.environment.name — the Stable attribute,
// not the deprecated deployment.environment (10 §2). The library reads NO env;
// the stage value arrives only HERE, from the environment library at the
// composition root. Idiomatic Go type name, exempt from the HNS-1 slug rule.
type Config struct {
	ServiceName    string            // OTel service.name; required, validated by New
	ServiceVersion string            // OTel service.version
	Environment    string            // development|test|staging|production -> deployment.environment.name (10 §2)
	DefaultPlane   Plane             // plane stamped on Events emitted as PlaneUnset
	ResourceAttrs  map[string]string // extra static OTel resource attributes (no secrets)
	MinSeverity    Severity          // drop Events below this at Emit; zero == SeverityDebug == emit everything
}

// Deps is the injected record of ports (the hexagon). New consumes ports; it
// constructs none. logging is a CONSUMER of Provider (via Provider.Log), not a
// Dep here — it is subordinate, riding the stream, not wiring it. Idiomatic Go
// type name, exempt from the HNS-1 slug rule.
type Deps struct {
	Exporter Exporter // the outbound wire/stdout boundary; non-nil required
	Clock    Clock    // injected time source so New stays pure and Scope is deterministic
}

// Exporter is the single outbound boundary an adapter package implements
// (oteladapter -> OTLP, slogadapter -> stdout). The library owns batching,
// scoping, resource stamping, and severity filtering; the adapter owns ONLY the
// wire. Blocking I/O lives HERE, behind the Provider's non-blocking Emit, so the
// hot path never stalls on exporter I/O. Accept-interface seam.
type Exporter interface {
	// Export ships a batch of fully-formed, resource-stamped, already-redacted
	// Records. It may block; it is driven off the hot path by the internal buffer
	// and by Flush.
	Export(ctx context.Context, records []Record) error
}

// Record is the resource-stamped, correlation-stamped Event the Exporter ships.
// The library produces it; adapters translate it to OTLP or stdout. It is a plain
// value, safe to copy.
type Record struct {
	Event    Event
	Resource map[string]string // ServiceName, ServiceVersion, deployment.environment.name, ResourceAttrs
	TraceID  string            // "" when no active span
	SpanID   string            // "" when no active span
}

// Clock is the minimal injected time port (mirrors dependencies.Clock). It is the
// ONLY reason Scope can stamp duration without the library reading time.Now —
// keeping New pure (10 §4) and the fake deterministic.
type Clock interface{ Now() time.Time }

// New is the pure constructor spine: no I/O, no clock read, no env read. It
// validates Config (ServiceName required; returns *ConfigError otherwise),
// captures Deps, and returns the internal Provider impl (resource stamping +
// severity filtering + Field inheritance + span timing), concrete behind the
// Provider interface. The first Export happens only when the engine/composition
// root later calls Emit/Scope/Flush.
func New(configuration Config, dependencies Deps) (Provider, error) { /* ... */ return nil, nil }

// ConfigError reports an invalid Config (e.g. empty ServiceName, nil Exporter).
// Inspectable via errors.AsType[*ConfigError]; wraps any cause with %w.
type ConfigError struct {
	Field   string // the offending Config/Deps field
	Message string
}

func (e *ConfigError) Error() string { /* "<field>: <message>" */ return "" }

// ── Field constructors: the only doors onto the stream ──────────────────────

func String(key, value string) Field                 { return Field{} }
func Int64(key string, value int64) Field            { return Field{} }
func Float64(key string, value float64) Field        { return Field{} }
func Bool(key string, value bool) Field              { return Field{} }
func Dur(key string, value time.Duration) Field      { return Field{} }
func Err(err error) Field                            { return Field{} } // key "error"; value = redaction-safe error string
func Any(key string, v Valuer) Field                 { return Field{} } // for Secret and other Valuer-satisfying types

// ── T6: the token/cost ledger rides the stream as a typed Event ─────────────

// Ledger is the token/cost accounting payload for a Run/phase (T6, 04 §6). It is
// rendered to an ordinary "cost.ledger" Event on PlaneAgent by LedgerEvent, so
// FinOps (S9) and budget machinery read structured attributes off the SAME plane-
// (b) stream — no second pipe, no parallel meter, ordered with the phase/gate
// Events it belongs to. Centralizing the schema here makes it the library's
// responsibility, not each call site's. CostMicros is an integer (micro-units of
// account currency) to avoid float drift across millions of calls.
type Ledger struct {
	RunID      string
	PhaseID    string
	Model      string
	Harness    string
	TokensIn   int64
	TokensOut  int64
	CacheHits  int64         // cache-hit input tokens, metered separately for cost models
	CostMicros int64         // provider spend in micro-units of account currency
	Retries    int32
	WallTime   time.Duration
}

// LedgerEvent builds the canonical PlaneAgent "cost.ledger" Event at
// SeverityInfo. now is supplied by the caller's injected Clock (the library reads
// no clock); pass the zero time to let the adapter stamp.
func LedgerEvent(now time.Time, l Ledger) Event { return Event{} }
```

## 3. Fake

```go
// Package observabilitytest is the canonical public fake for the observability
// port (the testing pattern, 10 §4 / 08 §2). The conformance suite that ships
// alongside proves adapter ≡ fake substitutability. Kernel tests (engine,
// codingharness, testharness, evidence) inject *Provider directly and assert that
// a phase emitted "phase.start" / "cost.ledger" / "gate.decision" with the right
// Plane/Fields — without an OTel backend.
package observabilitytest

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// Provider is an in-memory, inspectable, concurrency-safe observability.Provider.
// It records every Event (honoring With-inheritance, Scope timing, and Log) so
// tests exercise the real semantics, not a degenerate stub.
type Provider struct {
	// unexported; mutex-guarded event log + inherited fields + clock.
}

// New returns a fake bound to a deterministic clock (defaults to a fixed instant
// if clock is nil), so Scope-duration assertions never flake.
func New(clock func() time.Time) *Provider { return &Provider{} }

func (p *Provider) Emit(ctx context.Context, e observability.Event)                  {}
func (p *Provider) With(fields ...observability.Field) observability.Provider        { return p }
func (p *Provider) Scope(ctx context.Context, name string, f ...observability.Field) (context.Context, func(observability.Outcome)) {
	return ctx, func(observability.Outcome) {}
}
func (p *Provider) Log(ctx context.Context, sev observability.Severity, msg string, f ...observability.Field) {}
func (p *Provider) Flush(ctx context.Context) error { return nil }

// Events returns a snapshot copy of everything emitted, in order (With-inherited
// Fields already merged), for assertion.
func (p *Provider) Events() []observability.Event { return nil }

// Find returns the Events whose Name == name (e.g. "cost.ledger") for assertions.
func (p *Provider) Find(name string) []observability.Event { return nil }

// Ledgers decodes the T6 "cost.ledger" Events back into typed Ledgers so a budget
// test asserts tokens/retries/cost directly.
func (p *Provider) Ledgers() []observability.Ledger { return nil }

// AssertNoSecrets fails if any recorded Field's TelemetryValue() contains canary —
// the type-level leak guard, exercised by the conformance suite.
func (p *Provider) AssertNoSecrets(canary string) error { return nil }

// FailingExporter is an observability.Exporter that errors on Export, for testing
// the Flush error path (the only error path on the Provider).
type FailingExporter struct{ Err error }

func (f FailingExporter) Export(context.Context, []observability.Record) error { return f.Err }
```

## 4. Conformance suite

The suite is exported from `observabilitytest` so the real adapter-backed Provider
and the fake prove substitutability against the same properties (08 §2).

```go
// Run drives any observability.Provider produced by newProvider through the
// substitutability properties. The real adapter and observabilitytest.Provider
// must both pass identically.
func Run(t *testing.T, newProvider func(observability.Config, observability.Deps) (observability.Provider, error))
```

Properties asserted:

- **Purity of New** — `New` performs no I/O, reads no clock and no env; a panicking `Clock`/`Exporter` does not panic until first emit/flush. Empty `ServiceName` / nil `Exporter` is the only `New` error (a `*ConfigError`, inspectable via `errors.AsType`).
- **Emit is non-blocking and error-free** — `Emit`/`With`/`Scope`/`Log` return no error and never block on `Exporter` I/O (a slow `Exporter` does not stall the caller); the buffer absorbs or drops.
- **Severity filtering** — an Event below `Config.MinSeverity` is dropped at `Emit`; zero `MinSeverity` emits everything.
- **Plane stamping** — an Event emitted as `PlaneUnset` lands on `Config.DefaultPlane`; an explicit `Plane` is preserved unchanged.
- **Resource stamping** — every shipped `Record` carries `service.name`, `service.version`, `deployment.environment.name` (= `Config.Environment`, 10 §2), and `ResourceAttrs`.
- **With inheritance** — Events emitted through `obs.With(f...)` carry the inherited Fields ahead of the call-site Fields, order-preserving; the parent Provider is unaffected.
- **Scope timing & correlation** — `Scope` returns a ctx carrying a span; the close func stamps a duration computed from the injected `Clock` and the `Outcome`, and the span Event plus enclosed Events share `TraceID`/`SpanID`.
- **Secret-safety by type** — there is no field path accepting a bare `any`/`string`; a `Valuer` whose `TelemetryValue()` redacts (the secrets `Secret`) never renders its raw material; `AssertNoSecrets(canary)` holds across every Field.
- **Flush is the sole blocking/error call** — `Flush` drains buffered Events and surfaces an `Exporter.Export` failure wrapped via `%w` (reachable by `errors.AsType`/`Unwrap`); after `Flush`, no buffered Event is lost.
- **T6 ledger rides the stream** — `LedgerEvent` produces a `PlaneAgent` `"cost.ledger"` Event at `SeverityInfo`, ordered with surrounding phase/gate Events; `Ledgers()` round-trips it.
- **Zero-value safety** — a zero `Event` is a Debug Event on `DefaultPlane` that an adapter renders, never rejects; no accessor panics.

## 5. Usage

```go
// ── apps/backend composition root: the ONLY place the stage axis branches ────
func main() {
	ctx := context.Background()

	stage, _ := environment.Detect(os.Getenv)            // axis A (10 §7.1)
	deps := wiring.For(stage)                              // the one switch on stage

	// The adapter is bound HERE, not in business code: OTLP in staging/production,
	// collector-less slog locally. Both satisfy observability.Exporter.
	exporter := oteladapter.New(deps.OTLPEndpoint)        // or slogadapter.New(os.Stdout)

	obs, err := observability.New(
		observability.Config{
			ServiceName:    "eden-backend",
			ServiceVersion: build.Version,
			Environment:    stage.String(),               // -> deployment.environment.name (10 §2)
			DefaultPlane:   observability.PlaneSelf,
			MinSeverity:    observability.SeverityInfo,
		},
		observability.Deps{Exporter: exporter, Clock: realClock{}},
	)
	if err != nil {
		var cfgErr *observability.ConfigError
		if errors.AsType(err, &cfgErr) { /* inspect cfgErr.Field */ }
		log.Fatal(err)
	}
	defer obs.Flush(ctx) // the sole blocking call; drains the buffered tail (ledger, gate Events)

	app := backend.New(env.Config, backend.Deps{Telemetry: obs /* accept-interface */})
	plat.Up(ctx, app)
}

// ── kernel: engine walks the phase chain, holds mutable run-state ────────────
func (e *Engine) runPhase(ctx context.Context, p Phase) error {
	// Static run scope rides every Event via With; the span rides via Scope.
	runObs := e.obs.With(observability.String("run.id", e.runID))
	ctx, end := runObs.Scope(ctx, "phase.start",
		observability.String("phase", p.Name()),
	)

	out, err := e.codingHarness.Implement(ctx, p.Spec()) // emits on PlaneAgent through the same obs

	// A gate decision rides the stream.
	runObs.Emit(ctx, observability.Event{
		Plane: observability.PlaneAgent, Severity: observability.SeverityInfo,
		Name:   "gate.decision",
		Fields: []observability.Field{observability.Bool("gate.passed", err == nil)},
	})

	// T6: the cost ledger rides the SAME stream — FinOps reads it off plane (b),
	// ordered with the phase span and gate Event above (one pipe, one schema).
	runObs.Emit(ctx, observability.LedgerEvent(e.clock.Now(), observability.Ledger{
		RunID: e.runID, PhaseID: p.Name(),
		Model: out.Model, Harness: out.Harness,
		TokensIn: out.TokensIn, TokensOut: out.TokensOut,
		CacheHits: out.CacheHits, CostMicros: out.CostMicros,
		Retries: out.Retries, WallTime: out.Elapsed,
	}))

	end(observability.Outcome{Err: err}) // stamps duration + outcome from the injected Clock
	return err
}

// ── another library (evidence) logging through the subordinate Sink ──────────
// logging is a VIEW over Provider: Log emits a leveled Event on the same stream;
// a Secret is carried ONLY as its redacted Valuer — there is no Reveal() shortcut.
func (v *GoTestEvidence) record(ctx context.Context, obs observability.Provider, verdict string, tokenRef secrets.Secret) {
	obs.Log(ctx, observability.SeverityInfo, "gate evidence emitted",
		observability.String("verdict", verdict),
		observability.Any("token", tokenRef), // Secret.TelemetryValue() == secrets.Redacted
	)
}
```

## 6. Design rationale

1. **Five methods on `Provider`, no more (10 §9).** `Emit` / `With` / `Scope` / `Log` / `Flush` is the whole promised surface — exactly the negotiated ceiling. There is no `Span`/`Counter`/`Histogram`: OTel's span/metric machinery lives in `oteladapter` behind the `Exporter` seam, so this library never promises to track the OTel SDK's shape. `With` (cheap static inheritance) and `Scope` (a timed span with an `Outcome`) are kept distinct because the engine uses span timing while in-library code wants plain `run.id` inheritance — different jobs, both real call sites. See Q1.
2. **`Exporter` is the single lower seam; cross-cutting logic lives once.** Resource stamping, severity filtering, `With` inheritance, and `Scope` timing live in the internal Provider impl. An adapter implements only `Export([]Record)` — batch-shaped because that is how OTLP and slog adapters actually ship. This is what makes `oteladapter`/`slogadapter` thin and the conformance suite tractable (08 §2). See Q3.
3. **`Emit`/`With`/`Scope`/`Log` are non-blocking and error-free; `Flush` is the sole blocking/error call.** The hot path (every model/tool call, inside phase loops) must never stall a caller on exporter I/O or grow error handling, and a dropped Event can never fail a phase. Backpressure/drop is the `Exporter`+buffer's contract. `Flush` (the real I/O boundary the engine awaits at run/shutdown) and `New` (construction validation) are the only `error` channels — matching the `errors` contract's `errors.AsType` discipline.
4. **Secret-safety is in the TYPE, not a filter list.** `Field.Value` is a `Valuer`; the only doors are the `String/Int64/…/Any` constructors. There is no `any`-typed field and no `String(key, secret.Reveal())` shortcut, so a `secrets.Secret` reaches the wire only as its redacted projection `secrets.Redacted` (= `"secrets.Secret(REDACTED)"`) — redaction-by-construction (P9, 07 §2), aligned with `secrets.md`. `AssertNoSecrets` makes the conformance suite enforce it. See Q2.
5. **`Plane` is a stamped enum (P9), not inferred.** The three planes are first-class on every Event so one OTel stack partitions (a)/(b)/(c) without payload parsing; `Config.DefaultPlane` lets `apps/backend` default to `PlaneSelf` and the kernel override per Event to `PlaneAgent`. Zero is `PlaneUnset` so an unstamped Event visibly inherits the default rather than silently landing on plane (a). See Q5.
6. **The library reads no clock and no env (spine purity, 10 §4).** `Clock` is injected in `Deps` so `Scope` stamps duration deterministically and `New` stays pure; `Time: zero → adapter stamps` covers ad-hoc `Emit`. `deployment.environment.name` arrives via `Config.Environment` from the composition root, never an `EDEN_ENVIRONMENT` read — that boundary belongs to the `environment` pattern (10 §2). Two patterns must not own one fact. See Q4.
7. **T6 ledger is a typed `Event`, not a parallel meter.** `Ledger`+`LedgerEvent` put token/cost accounting on the same plane-(b) `"cost.ledger"` Event FinOps already consumes (S9, 04 §6), ordered with the `phase.start` span and `gate.decision` Event it belongs to. One pipe, one schema owned here; cost predictability depends on that ordering, which a separate metrics pipe would desynchronize.
8. **`logging` is a subordinate Sink, never a peer port.** `Provider.Log` is the seam: logging rides this stream as leveled Events, pinning the dependency direction (logging → observability) and guaranteeing one backend renders both leveled lines and structured Events (10 §4). There is no `Logger` dependency and no second channel — or the "three planes, one stack" invariant (P9) is already broken at the library level. See Q1.
9. **Closed, small, additive-only enums.** `Plane` and `Severity` are closed `uint8` sets consumers branch on without string parsing; growing them is a reviewed, backward-compatible append, never a removal — the cardinal-sin rule (10 §9). The classification a consumer needs *beyond* plane/severity lives in the stable dotted `Name`, not a parallel `Kind` taxonomy. See Q6.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| Q1 | Span/scope shape: `With(fields) Provider` (field inheritance) vs `Scope(ctx, name, fields) (ctx, func(Outcome))` (timed span). | `With` only — spans are expressed as `KindModelCall`/`KindToolCall` Events with start/end Fields; the adapter reconstitutes OTel spans. | `Scope` only — the engine needs span-like phase/model-call scoping that stamps duration + outcome from an injected Clock. | 🧩 **Kept BOTH, exactly at the 5-method ceiling.** They are different jobs: `With` is cheap static inheritance (a library stamps `run.id` on every Event, no span); `Scope` is a timed correlated span the engine's `runPhase` genuinely needs (duration + `Outcome` + trace/span correlation). The consumer's real call site (`Engine.runPhase` in §5) requires `Scope`; in-library scoping needs `With`. Hand-rolling spans as start/end Field pairs (producer) pushes correlation bookkeeping onto every call site. `Emit/With/Scope/Log/Flush` = 5; no split needed. |
| Q2 | Field value type: producer's sealed union `Value interface{ isValue() }` (constructor-only, no `Secret`) vs consumer's `Valuer{ TelemetryValue() any }` (a `Secret` rides as its redacted projection). | Sealed `Value` reachable only via `String/Int64/…`; a `*secrets.Secret` has no constructor, so it cannot be stamped. | `Valuer` so `secrets.Secret` is carried as its already-redacted value; `Any(key, Valuer)` is the door for it. | 🧩 **Took the consumer's `Valuer`.** Both achieve redaction-by-construction (no bare `any`, no `Reveal()` shortcut), but the producer's *sealed* union physically cannot carry a `Secret` — and the kernel's real call sites (evidence logging a token ref, §5) must telemeter a `Secret`'s redacted projection. `Valuer` admits exactly the redacted projection and nothing raw; `secrets.Secret` satisfies it via `TelemetryValue() == secrets.Redacted` (= `"secrets.Secret(REDACTED)"`, the sentinel `secrets.md` open-question #8 ratified). The primitive constructors are retained as the only door for non-`Valuer` values, so the secret-leak vector the producer guarded against stays closed. |
| Q3 | Lower adapter seam: producer's `Sink{Write(Event); Close}` (per-Event) vs consumer's `Exporter{Export([]Record)}` (batch, resource-stamped). | `Sink.Write(ctx, Event)` non-blocking + `Close` drain; the adapter moves one Event at a time. | `Exporter.Export(ctx, []Record)`; the library does batching/scoping/resource-stamping and ships `Record`s. | 🧩 **Took the consumer's `Exporter` + `Record`.** A batch seam matches how OTLP (`oteladapter`) and slog (`slogadapter`) actually ship and lets the library own batching once rather than forcing every adapter to re-buffer. `Record` carries the resource map + trace/span IDs so the adapter only translates, never re-stamps. The producer's load-bearing intent — one thin lower seam where blocking I/O is quarantined — is fully preserved; only granularity changed (batch vs per-Event). The name `Sink` is freed for logging's projection (the subordinate-Sink relationship is expressed via `Provider.Log`, so no separate `Sink` interface is needed at all). |
| Q4 | Time source: producer's "adapter stamps now" (library reads no clock) vs consumer's injected `Clock` in `Deps`. | No `Clock`: `Event.Time == zero` → the adapter stamps, keeping `New` pure with one fewer port. | Inject `Clock` so `Scope` stamps duration deterministically and the fake doesn't flake. | 🧩 **Took the consumer's injected `Clock`, AND kept producer's zero-Time fallback.** `Scope` duration stamping needs *a* clock; reading `time.Now` in the library would break purity (10 §4), so the clock must be an injected port (mirrors `dependencies.Clock`) — read at call time, never in `New`, so `New` stays pure and the fake is deterministic. Producer's `Time: zero → adapter stamps` is retained for ad-hoc `Emit` where the caller supplies no time. Both concerns satisfied; `Deps` gains one port. |
| Q5 | Is a `Plane` enum on every Event required? | Absent — used `Kind` (Message/ModelCall/ToolCall/Phase/Gate/Ledger) for classification; no plane axis. | Required — P9's three planes must be first-class so one backend partitions (a)/(b)/(c) without parsing. | 🧩 **Adopted `Plane` (consumer).** P9 mandates the three-plane partition (02 §1 Transcript on plane (b); 10 §2). Without a per-Event plane, the partition collapses into one undifferentiated stream — the consumer's non-negotiable. Added `PlaneUnset` as the zero so an unstamped Event visibly inherits `Config.DefaultPlane` rather than silently landing on plane (a). |
| Q6 | Producer's `Kind` enum (closed Event classification, branch without parsing `Name`). | Keep `Kind` — consumers branch on a closed `uint8` instead of string-matching `Name`. | Absent — classification rides the stable dotted `Name` (`"phase.start"`, `"cost.ledger"`); plane + severity are the only enums. | 🧩 **Rejected `Kind`.** It is a second closed taxonomy parallel to the stable `Name`, and the two must stay in lockstep forever (a `KindGate` Event with `Name != "gate.decision"` is a contradiction the type system can't catch). One-concept-one-home (README): `Name` already carries the classification, low-cardinality and OTel-span-shaped, and `Plane`/`Severity` carry the orthogonal axes. The producer's real need — branch without parsing free-form strings — is met by stable, documented `Name` constants the kernel matches exactly (e.g. `Find("cost.ledger")` in the fake). If a closed classification proves load-bearing later it is an additive const, non-breaking. |
| Q7 | `New` validation error type. | Returns an `error`; "errors.AsType to inspect Kind". | Returns a `ConfigError` inspectable via `errors.AsType`. | 🧩 **Took the consumer's typed `*ConfigError`** (carrying the offending `Field` + `Message`, wrapping any cause with `%w`), matching the `errors.md` discipline (typed, `errors.AsType`-first) and `configuration.md`'s `*ParseError` precedent. `Flush` likewise wraps its `Exporter` cause with `%w`. The producer's "inspect via `errors.AsType`" intent is honored; only the concrete type is pinned. |
| Q8 | `Ledger` field set: producer's cost-shaped (`CostMicros`, `CacheReadIn`) vs consumer's run-shaped (`RunID`, `PhaseID`, `Harness`, `Retries`, `WallTime`). | `{TokensIn, TokensOut, CacheReadIn, CostMicros, Model}` — cost/FinOps shape. | `{RunID, PhaseID, Model, Harness, TokensIn, TokensOut, CacheHits, Retries, WallTime}` — run/correlation shape. | 🧩 **Merged into the superset.** Both views are needed: FinOps (S9) needs `CostMicros` (integer micro-units, no float drift — producer); the run/budget machinery needs `RunID`/`PhaseID`/`Harness`/`Retries`/`WallTime` for correlation and abort decisions (04 §6 — consumer). The Run entity (02 §2) explicitly carries "token/cost ledger, retries" together, so the superset is the faithful schema. `CacheReadIn` is renamed `CacheHits` (consumer's name) but keeps the producer's "cache-hit input tokens" semantics. |
| Q9 | Redaction sentinel + `Valuer` conformance seam: this draft hardcoded `"***REDACTED***"` and assumed `secrets.Secret` satisfies `observability.Valuer`, but `secrets.md` ratified `secrets.Redacted = "secrets.Secret(REDACTED)"` (its open-question #8) and originally exposed no `TelemetryValue()`. | n/a | n/a | 🧩 **cross-contract reconciliation, post-draft.** Replaced every `"***REDACTED***"` literal with `secrets.Redacted` and dropped the false "matching secrets.md" wording; the conformance seam is closed in `secrets.md` (`Secret.TelemetryValue() any` returns `Redacted`, structurally satisfying this draft's `Valuer` without `secrets` importing `observability`). |
