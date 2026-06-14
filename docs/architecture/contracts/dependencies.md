# Contract — dependencies

> Status: Frozen (ADR-0016) · 2026-06-13 · Reconciled from independent producer/consumer drafts
> (09 §4 step 2) and frozen with the library built: the exported surface is mechanically recorded
> at `libs/go/dependencies/.apibaseline` (the freeze made mechanical, ADR-0020) and the ADR-0020
> 8-dimension test taxonomy is green. The **universal port set** — the hexagon's outbound edges
> (ADR-0009 A): `Clock`, `RandomSource`, `Sink`, plus the wiring discipline (`Resolve`, `Validate`)
> that keeps every consuming library's `New(configuration, dependencies)` pure. A breaking change
> to the surface requires a contract revision (ADR-0016 §1) + re-recording the `.apibaseline` —
> the cardinal sin otherwise (10 §9).

## 1. Scope

This pattern owns the **universal port set** — the outbound edges of the hexagon (ADR-0009 A) — that nearly every Eden library receives at construction: `Clock` (time), `RandomSource` (entropy), and `Sink` (emit-a-record-outward). It owns the canonical interfaces, the real host-backed adapters, and the wiring discipline (`Resolve`, `Validate`) that keeps every consumer's `New` pure.

It does **not** own any one library's wiring (each declares its own `Deps` struct by *narrowing* these ports), does **not** own domain ports (`Secrets`, `Models`, `Platform` — those belong to their defining pattern), and imports **no other Eden pattern** so the whole graph can depend on it without a cycle. `Sink` carries `any`, not `observability.Event`, precisely to keep this package a leaf.

## 2. Contract

```go
// Package dependencies defines the universal port set — the hexagon's outbound edges
// (ADR-0009 A) — plus the discipline every per-library Deps type obeys.
//
// It is an import-only LEAF: it depends on no other Eden pattern (not configuration,
// not observability, not errors), so the entire library graph can import it without a
// cycle. It owns the SMALL, STABLE ports nearly every Eden library needs — Clock,
// RandomSource, Sink — and the wiring helpers (Resolve, Validate). It does NOT own
// domain ports (Secrets, Models, Platform): those are declared by the pattern that
// consumes them and are added by each library to its OWN Deps struct. This package is
// the floor of the hexagon, not the ceiling.
//
// This package has no New of its own: dependencies is the SECOND ARGUMENT to every
// other library's spine — New(configuration, dependencies) -> (Component, error) — not
// a component with its own constructor. Resolve/Validate are the surface it offers; the
// spine it serves lives in each consuming library.
package dependencies

import (
	"context"
	"io"
	"time"
)

// ---- Universal ports (each ≤5 methods; accept-interfaces-return-concrete) ----

// Clock is the universal source of "now" and of time-based waiting. No component may
// call time.Now / time.After / time.Sleep directly; it asks the injected Clock, which
// is what makes every time-dependent component deterministic under a fake.
//
// Implementations must be safe for concurrent use.
type Clock interface {
	// Now returns the current instant. It is monotonic-aware: the returned time
	// carries a monotonic reading per the stdlib time contract. Cannot block, so it
	// takes no context.
	Now() time.Time
	// After returns a channel that delivers once after d has elapsed on this Clock's
	// timeline. It honors ctx cancellation so a blocking select unwinds cleanly on
	// shutdown; on cancellation the channel is never sent on.
	After(ctx context.Context, d time.Duration) <-chan time.Time
}

// RandomSource is the universal entropy port: a stream of cryptographically-suitable
// random bytes for IDs, jitter, sampling, and shuffles. It mirrors io.Reader exactly,
// so *math/rand/v2.ChaCha8, crypto/rand, and a seeded test source are all drop-in with
// zero adapter code.
//
// Read must fill p completely or return a non-nil error (the io.ReadFull contract that
// crypto/rand guarantees), and must be safe for concurrent use.
type RandomSource interface {
	Read(p []byte) (n int, err error)
}

// Sink is the universal "emit one structured record outward" port — the seam the
// observability and logging patterns adapt. dependencies owns only the minimal verb so
// it stays a leaf; the rich Event type lives in the observability library, which
// supplies a Sink adapter over this port. record is typed any ON PURPOSE: typing it as
// observability.Event would force this leaf to import observability and invert the
// graph.
//
// Implementations must be safe for concurrent use.
type Sink interface {
	// Emit hands one record outward. It is best-effort and must NOT block business
	// code on a slow backend; it honors ctx cancellation. A nil error means accepted,
	// not delivered.
	Emit(ctx context.Context, record any) error
}

// Set is the composition-root currency: the bundle of every universal port, assembled
// once at the edge. It is a struct of interfaces, never an interface itself — there is
// no Dependencies interface to bloat. Per-library Deps structs are built BY NARROWING
// this: a component that only needs time declares a Deps holding just a Clock, never
// the whole Set (see §5). Set is shared read-only after assembly.
//
// The zero Set is INVALID by design: a nil port is a wiring bug, not a default.
// Defaulting is an explicit, opt-in step (Resolve), never silent on field access.
type Set struct {
	Clock  Clock
	Random RandomSource
	Sink   Sink
}

// Resolve returns a copy of s with any nil universal port replaced by its real,
// host-backed adapter (system clock, crypto/rand entropy, discard sink). It is one of
// two sanctioned ways to obtain real defaults (RealClock/RealRandom/DiscardSink being
// the per-port form), and it is pure in the constructor-purity sense: it allocates
// adapter VALUES whose methods touch the environment at call time, but Resolve itself
// performs no I/O, reads no clock, and reads no env.
//
// Call Resolve ONLY at the composition root — never inside a component's New. Binding
// defaults inside New would read the wall clock at construction, the exact impurity the
// spine (10 §4) forbids. Resolve never overwrites a non-nil port: explicit wiring
// always wins, so an injected fake Clock survives.
func Resolve(s Set) Set {
	if s.Clock == nil {
		s.Clock = RealClock()
	}
	if s.Random == nil {
		s.Random = RealRandom(nil)
	}
	if s.Sink == nil {
		s.Sink = DiscardSink()
	}
	return s
}

// Validate reports the first nil universal port as a typed error, for composition roots
// (and component Constructors checking the ports they NARROWED in) that prefer to fail
// loudly on an unwired dependency rather than silently default. Returns nil when every
// universal port is non-nil. Pure: no I/O.
func Validate(s Set) error {
	switch {
	case s.Clock == nil:
		return &MissingPortError{Port: "Clock"}
	case s.Random == nil:
		return &MissingPortError{Port: "RandomSource"}
	case s.Sink == nil:
		return &MissingPortError{Port: "Sink"}
	default:
		return nil
	}
}

// MissingPortError reports an unwired universal port. Inspect it structurally via
// errors.AsType[*dependencies.MissingPortError](err) (Go 1.26); component Constructors
// wrap it with %w when reporting a narrowed port.
type MissingPortError struct{ Port string }

func (e *MissingPortError) Error() string { return "dependencies: missing port " + e.Port }

// ---- Real providers: the ONLY place wall-clock / crypto entropy is bound. ----
// Each returns an adapter VALUE; the value's METHODS (not these constructors) touch the
// environment, so calling them is pure. They are invoked by the composition root and
// passed INTO a Set / a library's Deps — NEVER called inside a component's New.

// RealClock returns a Clock backed by the operating-system wall clock and timers.
func RealClock() Clock { return systemClock{} }

// RealRandom returns a RandomSource backed by entropy; a nil entropy reader means
// crypto/rand.
func RealRandom(entropy io.Reader) RandomSource { /* wrap entropy, default crypto/rand */ return cryptoRandom{} }

// DiscardSink returns a Sink that drops every record — the safe default when a component
// is wired without observability (tests, smoke binaries).
func DiscardSink() Sink { return discardSink{} }

// systemClock, cryptoRandom, and discardSink are the real adapters, UNEXPORTED on
// purpose: business code has no public type to bind against and must go through the
// injected port, so the real-vs-fake decision has exactly one seam (the providers
// above, called at the composition root).
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }
func (systemClock) After(ctx context.Context, d time.Duration) <-chan time.Time { /* ctx-aware timer */ return nil }

type cryptoRandom struct{ /* entropy io.Reader, default crypto/rand */ }

func (cryptoRandom) Read(p []byte) (int, error) { /* io.ReadFull(entropy, p) */ return len(p), nil }

type discardSink struct{}

func (discardSink) Emit(ctx context.Context, record any) error { return nil }
```

## 3. Fake

```go
// Package dependenciestest provides the canonical, controllable fakes for every
// universal port (the testing pattern, 10 §4), plus a one-call Fakes() helper. Every
// library's test wires THESE shared fakes — never ad-hoc local ones — so "fake ≡ real"
// is provable by the single shared conformance suite (§4). Fakes ship WITH the frozen
// contract (09 §4), before any consumer implements.
package dependenciestest

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// Clock is a manually-advanced fake clock. Now is frozen until Advance is called; After
// channels fire when Advance crosses their deadline. Use NewClock for a chosen epoch.
// Safe for concurrent use.
type Clock struct{ /* mu, now, pending After timers */ }

func NewClock(start time.Time) *Clock                                            { return &Clock{} }
func (c *Clock) Now() time.Time                                                  { return time.Time{} }
func (c *Clock) After(ctx context.Context, d time.Duration) <-chan time.Time     { return nil }
func (c *Clock) Advance(d time.Duration)                                         { /* moves now forward, fires due timers */ }

// Random is a deterministic, seedable entropy source (math/rand/v2.ChaCha8 under the
// hood) so randomized code paths are reproducible. Safe for concurrent use.
type Random struct{ /* mu, src */ }

func NewRandom(seed [32]byte) *Random            { return &Random{} }
func (r *Random) Read(p []byte) (int, error)     { return len(p), nil }

// RecordingSink captures every emitted record for assertions. Records returns a snapshot
// copy. Safe for concurrent Emit.
type RecordingSink struct{ /* mu, records []any */ }

func (s *RecordingSink) Emit(ctx context.Context, record any) error { return nil }
func (s *RecordingSink) Records() []any                             { return nil }

// Fakes returns a dependencies.Set with every universal port populated by a fake —
// pinned to a fixed instant and seed — plus handles to each fake so a test can drive it.
// The test analogue of dependencies.Resolve; callers override individual fields as
// needed.
func Fakes() (set dependencies.Set, clock *Clock, random *Random, sink *RecordingSink) {
	clock = NewClock(time.Unix(0, 0).UTC())
	random = NewRandom([32]byte{})
	sink = &RecordingSink{}
	return dependencies.Set{Clock: clock, Random: random, Sink: sink}, clock, random, sink
}
```

## 4. Conformance suite

The testing pattern (10 §4) ships one port-substitutability suite. A consuming library never re-tests the ports; it calls this once to prove its wired adapter set is interchangeable with the fakes.

```go
// RunPortSuite asserts every universal port honors its contract, for BOTH the real
// adapters and the dependenciestest fakes, proving substitutability (08 §2).
func RunPortSuite(t *testing.T, newSet func() dependencies.Set)
```

Properties asserted:
- **Clock.Now monotonic-aware & non-decreasing** — successive `Now()` calls never go backward; the returned time carries a monotonic reading.
- **Clock.After fires after d / respects cancellation** — the channel delivers once when the timeline reaches `d`; a cancelled `ctx` leaves the channel un-sent and unwinds the select.
- **RandomSource full-read** — `Read` fills `p` entirely or returns a non-nil error; never a short read with `err == nil`.
- **Sink.Emit best-effort & non-blocking** — `Emit` returns without blocking on a slow/absent backend; honors `ctx` cancellation; `nil` error means accepted.
- **Concurrency safety** — every port survives the race detector under concurrent calls (`Now`/`Read`/`Emit` from N goroutines).
- **Resolve purity & idempotence** — `Resolve` performs no I/O, fills exactly the nil ports, never overwrites a non-nil port, and `Resolve(Resolve(s)) == Resolve(s)`.
- **Validate completeness** — `Validate` returns a `*MissingPortError` naming the first nil port and `nil` for a full Set; the error is recoverable via `errors.AsType`.

## 5. Usage

```go
// --- Site 1: apps/backend composition root — the ONLY place real ports are bound. ---
// stage selects WIRING (values); platform selects ADAPTERS; neither is read inside any New.
func main() {
	stage, _ := environment.Detect(os.Getenv)

	// Real universal ports are constructed HERE, explicitly, at the edge. Resolve fills
	// any unset port with its real adapter; still pure (adapters touch env at call time).
	base := dependencies.Resolve(dependencies.Set{
		Sink: observability.AsSink(telemetryProvider), // observability adapts its Event → the any Sink
	})

	env, _ := environment.Resolve(stage /* secrets, etc. */)

	// Each library NARROWS the universal Set into its own Deps — it receives only the
	// ports it uses, plus its own non-universal ports (Secrets here, owned by backend).
	app, err := backend.New(env.Config, backend.Deps{
		Clock:   base.Clock,
		Sink:    base.Sink,
		Secrets: env.Secrets,
	})
	if err != nil {
		var missing *dependencies.MissingPortError
		if errors.AsType(err, &missing) { /* report which port */ }
	}
	_ = app
}

// --- Site 2: a kernel library (engine) consuming the universal ports by NARROWING. ---
// engine needs deterministic time (timeouts, run timestamps) and entropy (run IDs). It
// declares its OWN Deps holding only those ports plus a kernel-specific one. New stays
// PURE: it validates the ports it was handed, binds NO real adapter, reads no clock/env.
package engine

import "github.com/gophersys/libs/go/dependencies"

type Deps struct {
	Clock  dependencies.Clock          // narrowed: time only...
	Random dependencies.RandomSource   // ...plus entropy for run IDs
	Models agentconfiguration.Resolver // a kernel-specific port, owned by engine
}

func New(configuration Config, dependencies Deps) (*Engine, error) {
	if deps.Clock == nil {
		return nil, fmt.Errorf("engine: %w", &dependencies.MissingPortError{Port: "Clock"})
	}
	return &Engine{clock: deps.Clock, capacity: configuration.Capacity}, nil // no clock read, no env read
}

// --- Site 3: engine_test.go — deterministic by construction. ---
func TestEngineTimeout(t *testing.T) {
	set, clock, _, _ := dependenciestest.Fakes()
	e, _ := engine.New(cfg, engine.Deps{Clock: set.Clock, Random: set.Random, Models: fakeResolver})
	go e.Run(ctx, spec)
	clock.Advance(30 * time.Second) // drive the timeout without real waiting
	// assert e timed out
}
```

## 6. Design rationale

1. **The package owns only what is truly universal and stays a leaf** (10 §4, rationale 1.). `Clock`, `RandomSource`, `Sink` — every library needs time, entropy, and an emit-seam. `Sink.Emit(ctx, record any)` is typed `any` specifically so this package never imports `observability`; the rich `Event` lives there and adapts *into* the `any` Sink, so the dependency arrow points the right way. Domain ports (`Secrets`, `Models`, `Platform`) are declared by their owning pattern and added to each library's own `Deps`.
2. **`Set` is a struct of interfaces, never a `Dependencies` interface** (10 §9, "accept interfaces, return concrete"; `interfacebloat` max 5). Each port is a ≤2-method interface; the record carrying them is concrete and embeddable. There is no god-interface to re-stub.
3. **Per-library `Deps` NARROWS the universal set** (10 §7.1 composition root). A component declares a `Deps` holding only the ports it touches (engine: `Clock` + `Random`), so it cannot accidentally reach a port it does not use. `Set` is composition-root currency, not a mandatory embed (see open question 1).
4. **Real-port binding is an explicit provider, never inside any `New`** (10 §2 hard rule, 10 §4 spine). `RealClock`/`RealRandom`/`DiscardSink` and `Resolve` allocate adapter values whose *methods* touch the environment at call time — pure in the constructor-purity sense — but they are called only at the composition root. Defaulting inside `New` would read the wall clock at construction, the impurity the spine forbids.
5. **Real adapters are unexported** (10 §4). `systemClock`/`cryptoRandom`/`discardSink` have no public name, so business code physically cannot reach the real environment except through the injected port. The real-vs-fake seam is exactly the providers, called once at the edge.
6. **`context.Context` is first on the methods that can block, absent on those that cannot.** `Clock.After` and `Sink.Emit` honor cancellation so blocking selects in `engine`/`testharness` unwind on shutdown; `Clock.Now` and `RandomSource.Read` (io.Reader-shaped) stay context-free — ceremony there is noise.
7. **`RandomSource` is `io.Reader`-shaped and nothing more** (10 §4). No `Int63`/`Float64`. Convenience belongs in `math/rand/v2.New(rng)` at the call site; widening the port would make it un-fakeable in one line and couple us to a numeric API forever.
8. **The zero `Set` is deliberately invalid; `Resolve` and `Validate` make the choice explicit.** A nil port is a wiring bug. A composition root that wants real defaults calls `Resolve`; one that wants fail-fast calls `Validate`. Never both-and-silent on field access.
9. **Missing-port errors are typed and `%w`-wrappable** (errors pattern; `errors.AsType`, Go 1.26). A composition-root or narrowing mistake surfaces structurally via `*MissingPortError`, not as a nil panic at first use.
10. **One canonical fake per port, in `dependenciestest`, shipped WITH the contract** (testing pattern 10 §4; 09 §4). Shared fakes — not ad-hoc local ones — are what let the single conformance suite prove fake ≡ real; consumers write tests against `dependenciestest.Fakes()` on day one.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| 1 | Per-library `Deps`: **embed `dependencies.Set`** vs **narrow to the ports used**? | Embed `Set` so a future universal port lands everywhere additively and the floor is uniform. | Narrow: a `Deps` holds only the ports the component touches, so it can't reach an unused port. | 🧩 **Narrow.** It honors "accept the minimum interface" and matches every real call site (engine takes `Clock`+`Random`, backend takes `Clock`+`Sink`). `Set` stays composition-root currency. Cost: adding a universal port is not auto-propagated — but per-library `Deps` lists are tiny and explicit, and a uniform embed forces components to carry ports they ignore, the anti-pattern `interfacebloat` guards. Embed is permitted where a library genuinely uses the whole `Set`; it is not the default. |
| 2 | Does `dependencies` own a **`Sink`** port? | No — owning `Sink`/`Secrets`/`Telemetry` would invert the graph (force importing `observability`). | Yes — `Sink.Emit(ctx, record any)` with `any`, which keeps the package a leaf. | 🧩 **Own `Sink`, with `any`.** The consumer's `any` typing dissolves the producer's only objection: no `observability` import, graph stays leaf, and the catalogue line literally reads "`Clock`, `RandomSource`, `Sink`, …" (10 §4). `Secrets`/`Telemetry`/`Platform` remain domain ports owned elsewhere — producer's broader point upheld. |
| 3 | Does the package have its **own `New` spine**? | No — `dependencies` is the *argument* to every other spine, not a component; surface is `Resolve`/`Validate`. | Yes — `New(RealConfig, Set) -> (Set, error)` "for spine-shape conformance." | 🧩 **No own `New`.** The spine (10 §4) is for components that get constructed; `dependencies` is the second *argument* to that spine system-wide. A `New` returning a `Set` is ceremony with no component behind it. `Resolve` (default) + `Validate` (check) are the surface. Consumer's `RealConfig` is absorbed into `RealRandom(entropy)`, so the composition root still passes resolved values in without env reads. |
| 4 | **Real-port construction**: per-port `Real*` providers, a one-call `Real()`, or `Resolve()`? | `Resolve(Set)` fills nils with unexported adapters; one entry point. | Per-port `RealClock`/`RealRandom`/`DiscardSink` + a one-call `Real(RealConfig)`. | 🧩 **Keep both forms, drop `Real()`.** Per-port `RealClock`/`RealRandom`/`DiscardSink` (consumer) give precise control; `Resolve(Set)` (producer) is the one-call fill-the-nils path and replaces the consumer's `Real()` (which duplicated it). Both are pure and both are composition-root-only. |
| 5 | **`Clock` surface**: `Now()` only, or `Now()` + `After(ctx, d)`? | `Now()` only — minimal port, mirrors `time.Now`. | `Now()` + `After(ctx, d)` — needed for deterministic timeouts. | 🧩 **`Now()` + `After(ctx, d)`** (2 methods, well under 5). `After` is load-bearing at real call sites (`engine`/`testharness` timeouts must be drivable by `FakeClock.Advance`); without it those components reach for `time.After` directly and become non-deterministic — the exact failure the port exists to prevent. |
| 6 | **Missing-port error shape**: typed `*MissingPortError` vs sentinel `ErrMissingPort`? | Typed `*MissingPortError{Port}` — names the port, AsType-inspectable. | Sentinel `ErrMissingPort` + unexported `*missingPortError`. | 🧩 **Typed exported `*MissingPortError{Port}`.** It carries which port is missing and is recoverable via `errors.AsType` (Go 1.26, the inspection idiom in the ground rules), strictly richer than a bare sentinel; component Constructors wrap it with `%w`. |
