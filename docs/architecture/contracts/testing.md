# Contract draft — testing

> Status: Draft for negotiation (WS1, not frozen) · 2026-06-12 · Reconciled from independent producer/consumer drafts (09 §4). Freezes at the contract-PR gate after review.

## 1. Scope

`testing` is the **meta-pattern**: it does not define a domain port and nothing injects it into a
`Deps`. It owns exactly (a) the **canonical fakes** for the two universal deterministic ports every
hexagon's `Deps` needs — `Clock` and `RandomSource`, whose port *interfaces* are owned by the
`dependencies` pattern (10 §4, `dependencies.md`), not here; and (b) the reusable
**conformance-suite** construct that proves `adapter ≡ fake` for any port (08 §2), closing the
fakes-drift-from-reality failure mode by *executing* substitutability rather than asserting it. It
does **not** own per-pattern fakes (`FakeSink`, `FakeSecretProvider`, …) — those live in each
pattern's own `<pattern>test` package; this library owns only the *shape* they conform to. The core
`package testing` imports neither stdlib `testing` nor any assertion library, so the kernel
(`engine`, `testharness`) can run suites inside shipped static binaries to mint Evidence (10 §6.1,
07 §4).

## 2. Contract

```go
// Module: github.com/gophersys/libs/go/testing  (go 1.26)
//
// Package testing is the meta-pattern. It vends the canonical FAKES of the two
// universal deterministic ports (Clock, RandomSource — the interfaces are owned by
// the dependencies pattern, 10 §4) via a pure constructor, and owns the
// conformance-suite construct that proves adapter ≡ fake substitutability (08 §2).
//
// It intentionally imports NEITHER stdlib "testing" NOR any assertion library:
// assertion is delegated to the Report sink so engine/testharness can execute
// suites inside shipped, CGO_ENABLED=0 binaries to mint Evidence (10 §6.1, 07 §4).
// The *testing.T -> Report and *testing.T -> Harness adapters live in package
// testingtest, never here.
package testing

import (
	"context"
	"iter"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// ── The two universal deterministic ports (interfaces owned elsewhere) ──────
// The Clock and RandomSource port INTERFACES are owned by the `dependencies`
// pattern (10 §4, dependencies.md) — one concept, one home (cohesion contract).
// This library does NOT re-declare them; it references dependencies.Clock /
// dependencies.RandomSource and owns only their canonical FAKES (testingtest,
// §3) and the conformance-suite construct. The dependencies shapes are:
//
//	dependencies.Clock        — Now() time.Time; After(ctx, d) <-chan time.Time
//	dependencies.RandomSource — Read(p []byte) (n int, err error)  (io.Reader-shaped)
//
// Aliases below are convenience re-exports of the dependencies-owned interfaces,
// NOT independent definitions; a fake satisfying these satisfies dependencies'.

// Clock aliases dependencies.Clock so the suite/fake signatures read locally; the
// canonical definition (Now + After(ctx, d)) lives in dependencies.md.
type Clock = dependencies.Clock

// RandomSource aliases dependencies.RandomSource (the io.Reader-shaped entropy
// port); the canonical definition lives in dependencies.md.
type RandomSource = dependencies.RandomSource

// ── The conformance-suite construct (the reusable core) ─────────────────────

// Harness is handed to every Factory and Case. It vends the deterministic sources
// a subject wires into its own Deps, plus capability gating so an adapter that
// legitimately lacks an optional capability SKIPS rather than fails. Cleanup runs
// LIFO after the case. Exactly 5 methods — the ceiling, spent, not speculative.
type Harness interface {
	Clock() Clock                  // deterministic; advanced only inside a Case
	RandomSource() RandomSource    // seeded, reproducible
	Has(capability string) bool    // CapabilityManifest gate (02 §1)
	Cleanup(func())                // LIFO teardown, runs after the Case
	Context() context.Context      // the run ctx; deadlines/cancellation flow here
}

// Report is the assertion sink the core depends on instead of *testing.T. Three
// methods: a failure-then-continue, a failure-then-abort-case, and a skip. The
// *testing.T adapter and the structured-Result recorder both satisfy it.
type Report interface {
	Errorf(format string, args ...any) // record failure, continue the case
	Fatalf(format string, args ...any) // record failure, abort THIS case only
	Skipf(format string, args ...any)  // capability/precondition skip
}

// Factory builds the subject-under-test for one conformance case. It is the single
// seam a pattern library implements twice — once binding its fake, once binding its
// real adapter — so the SAME Suite runs over both. S is the port being tested
// (e.g. observability.Sink). Called once per case for isolation.
type Factory[S any] func(ctx context.Context, h Harness) (subject S, err error)

// Case is one black-box assertion over a freshly built subject. Pattern libraries
// author cases; the suite never re-authors them on the consumer side.
type Case[S any] struct {
	// Name is the stable subtest label.
	Name string
	// Run executes the assertion. Capability-gated cases call h.Has(...) and
	// report.Skipf(...) to skip cleanly instead of failing.
	Run func(subject S, h Harness, report Report)
}

// Suite is the reusable conformance construct: a named, ordered set of Cases over
// a port S. A pattern library exports ONE Suite[S] per port (e.g.
// observabilitytest.SinkSuite); both the fake's test and every adapter's test run
// THAT value through RunSuite. One definition site ⇒ drift is structurally
// impossible (08 §2). Zero value is an empty, runnable suite.
type Suite[S any] struct {
	// Name labels the port under test, e.g. "observability.Sink".
	Name string
	// Cases iterates the conformance assertions in a stable, caller-defined order
	// (iter.Seq, Go 1.23+). Reusing range-over-func lets large suites stream cases
	// without materialising a slice; a plain slice is yieldable via slices.Values.
	Cases iter.Seq[Case[S]]
}

// ── The constructor spine (pure) ────────────────────────────────────────────

// Config is the immutable, fully-resolved knob set for a conformance run and the
// fakes the Runner vends. Zero value is valid and deterministic (rationale 4).
type Config struct {
	// Seed deterministically seeds the RandomSource handed to cases. Zero is legal.
	Seed uint64
	// RequireCapabilities lists CapabilityManifest entries (02 §1) the run expects;
	// a case gated on an absent capability is reported as a skip, never a failure.
	RequireCapabilities []string
	// CaseTimeout bounds a single case; zero means inherit the run context only.
	CaseTimeout time.Duration
	// FailFast stops the run at the first failing case.
	FailFast bool
}

// Deps is the injected hexagon. It carries only an Epoch so the fakes the Runner
// vends are reproducible across processes — the Epoch is INJECTED, never read from
// the host clock, which is what keeps New pure. Zero Epoch → the Unix epoch (a
// fixed, reproducible anchor), never time.Now.
type Deps struct {
	// Epoch is the instant a vended FakeClock starts from before any Advance.
	Epoch time.Time
}

// Runner vends deterministic fakes and executes Suites. It is concrete (accept
// interfaces, return concrete). New is the pattern spine: PURE — no I/O, no clock
// read, no env read; it only fixes the deterministic starting state in Config/Deps.
// Errors are wrapped with %w and inspected via errors.AsType.
type Runner struct{ /* unexported: epoch, seed, policy */ }

func New(configuration Config, dependencies Deps) (*Runner, error)

// Fakes returns a fresh, deterministic bundle for direct wiring into a subject's
// own Deps outside a suite run (e.g. a library's own unit test). Returned concrete.
func (r *Runner) Fakes() Fakes

// Fakes is the concrete (returned, not interface) bundle the Runner builds.
type Fakes struct {
	Clock  Clock        // a *testingtest.FakeClock under the hood
	Random RandomSource // a *testingtest.FakeRandomSource under the hood
}

// RunSuite executes every Case of suite against subjects built by factory, once per
// case for isolation. It NEVER lets a panic escape: a panicking case is recorded as
// a failed case (Panic non-empty) and the run continues (M2: one bad adapter case
// must not abort a 50-task run). It returns a machine-readable Result the
// engine/evidence layer folds into a GoTestEvidence envelope without parsing stdout.
func RunSuite[S any](r *Runner, suite Suite[S], factory Factory[S]) Result

// Result is the structured outcome consumed by engine/evidence (02 §2).
type Result struct {
	Suite   string
	Passed  int
	Failed  int
	Skipped int
	Cases   []CaseResult
}

// CaseResult is one case's outcome. Panic is non-empty iff the case panicked.
type CaseResult struct {
	Name     string
	Outcome  Outcome
	Messages []string
	Panic    string
}

// Outcome is the tri-state a gate reads: Skip ≠ Fail (02 §1 graceful degradation).
type Outcome int

const (
	Pass Outcome = iota
	Fail
	Skip
)
```

## 3. Fake

```go
// Module: github.com/gophersys/libs/go/testing, package testingtest.
// The public fakes for testing's own ports (Clock, RandomSource) plus the
// *testing.T adapters live HERE, not in package testing, so production code that
// imports the fakes does not pull in stdlib "testing" (10 §6.1 <pattern>test
// convention). Per-pattern fakes (FakeSink, …) live in THEIR own <pattern>test;
// this package holds only the two universal fakes and the suite adapters.
package testingtest

import (
	"context"
	stdtesting "testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/testing"
)

// FakeClock is virtual-time: it NEVER advances on its own. Tests drive time
// explicitly via Advance, which is what makes timeout/retry/backoff/hibernate
// logic deterministic. It implements dependencies.Clock exactly (Now + After);
// Advance is the test-only affordance, not part of the port. Concurrency: every
// method is goroutine-safe; Advance releases all After channels whose deadline it
// crosses, in deadline order, before returning. Zero start
// (NewFakeClock(time.Time{})) → the Unix epoch.
type FakeClock struct{ /* unexported: mu, now, waiters */ }

func NewFakeClock(start time.Time) *FakeClock

func (c *FakeClock) Now() time.Time                                              { return time.Time{} }
func (c *FakeClock) After(ctx context.Context, d time.Duration) <-chan time.Time { return nil }
func (c *FakeClock) Advance(d time.Duration)                                     {} // THE affordance: move virtual time

var _ dependencies.Clock = (*FakeClock)(nil)

// FakeRandomSource is a deterministic, reproducible byte stream from seed. NOT
// crypto-secure — tests only; production binds crypto/rand. Concurrency: Read is
// serialized; identical seed + identical Read call sequence ⇒ identical bytes,
// forever (a maintained, version-pinned guarantee — see open question 6).
type FakeRandomSource struct{ /* unexported: mu, prng state */ }

func NewFakeRandomSource(seed uint64) *FakeRandomSource

func (r *FakeRandomSource) Read(p []byte) (int, error)

var _ dependencies.RandomSource = (*FakeRandomSource)(nil)

// ── Adapters from stdlib testing into the assertion-free core ───────────────

// NewReport adapts *testing.T to testing.Report so a go test drives any Suite in
// one line; the core stays stdlib-testing-free. Skipf maps to t.Skipf.
func NewReport(t *stdtesting.T) testing.Report

// NewHarness builds a standalone testing.Harness for wiring fakes into a library's
// own unit test outside RunSuite. Capabilities default to present.
func NewHarness(t *stdtesting.T, opts ...HarnessOption) testing.Harness

type HarnessOption func(*harnessConfig)

func WithSeed(seed uint64) HarnessOption
func WithEpoch(epoch time.Time) HarnessOption
func WithoutCapability(name string) HarnessOption

// AssertResult fails t if any case in r failed or panicked — the bridge from a
// structured Result back to go test's pass/fail. Skips do not fail t.
func AssertResult(t *stdtesting.T, r testing.Result)
```

## 4. Conformance suite

Signature: `RunSuite[S any](r *testing.Runner, suite testing.Suite[S], factory testing.Factory[S]) testing.Result`.
A pattern library exports `XxxSuite() testing.Suite[Port]` once; the consumer runs it twice —
once with the fake factory, once with the adapter factory — and passing both *is* the
substitutability proof (08 §2).

Properties asserted by the construct itself (independent of any particular port's cases):

- **Per-case isolation** — `factory` is invoked once per case; no case observes another case's
  subject state.
- **Deterministic ordering** — cases run in the order `Suite.Cases` yields; reruns with the same
  `Config.Seed` and `Deps.Epoch` are bit-identical (the `evidence`/`testharness` reproducibility
  requirement, 02 §2, 07 §4).
- **Panic containment** — a panicking case becomes a `CaseResult{Outcome: Fail, Panic: …}`; the run
  continues and no panic escapes `RunSuite` (M2: one bad adapter case ≠ a dead 50-task run).
- **Capability gating** — a case that calls `h.Has(cap)==false` then `report.Skipf` is recorded
  `Skip`, counted in `Result.Skipped`, and never as `Fail` (02 §1 graceful degradation).
- **Determinism injection** — every subject receives `h.Clock()`/`h.RandomSource()`; no host clock
  or env is read anywhere in a run, so the same suite over fake and adapter compares like-for-like.
- **Same-value substitutability** — the fake's test and each adapter's test import and run the *one*
  exported `Suite` value; the construct provides no path to fork the cases per side.
- **Structured outcome** — `RunSuite` returns a `Result` (counts + per-case outcome + captured
  panic) the engine folds into a `GoTestEvidence` envelope without parsing test stdout.

## 5. Usage

```go
// ── Call site 1: a pattern library closes the fakes-drift loop ──────────────
// libs/go/secrets/secrets_conformance_test.go. secrets exports ONE
// SecretProviderSuite(); testing runs it over BOTH the fake and the real adapter.
func TestSecretProvider_FakeAndAdapter_Conform(t *testing.T) {
	r, err := testingpkg.New(
		testingpkg.Config{Seed: 1},
		testingpkg.Deps{Epoch: epoch},
	)
	if err != nil { t.Fatal(err) }

	suite := secrets.SecretProviderSuite() // pkg-owned testing.Suite[secrets.SecretProvider]

	fake := func(ctx context.Context, h testingpkg.Harness) (secrets.SecretProvider, error) {
		return secretstest.NewFakeProvider(seededValues), nil
	}
	adapter := func(ctx context.Context, h testingpkg.Harness) (secrets.SecretProvider, error) {
		return vaultadapter.New(vaultadapter.Config{ /* … */ },
			vaultadapter.Deps{Clock: h.Clock()})
	}

	testingtest.AssertResult(t, testingpkg.RunSuite(r, suite, fake))
	testingtest.AssertResult(t, testingpkg.RunSuite(r, suite, adapter))
	// PASS on both ⇒ unit tests that mock secrets are now trustworthy (08 §2).
}

// ── Call site 2: a kernel library wires the fake Clock into its own test ─────
// libs/go/testharness must emit Evidence with deterministic timestamps so two
// clean-room runs of one artifact are bit-identical (02 §2, 07 §4).
func TestTestHarness_EmitsDeterministicEvidence(t *testing.T) {
	h := testingtest.NewHarness(t, testingtest.WithEpoch(epoch), testingtest.WithSeed(7))
	th, _ := testharness.New(cfg, testharness.Deps{Clock: h.Clock()})
	ev := th.Run(h.Context(), artifact, spec)
	// ev.Provenance.Timestamp derives from FakeClock — reproducible, not wall-clock.
}

// ── Call site 3: backend composition root binds the PRODUCTION ports ────────
// The fake never reaches here; this is the SHAPE the fake mirrors (10 §2: stage
// selects injected wiring at the composition root only).
func main() {
	deps := backend.Deps{
		Clock:  realclock.System(),  // a real dependencies.Clock
		Random: cryptorand.Source(), // crypto/rand-backed dependencies.RandomSource
	}
	_ = deps
}

// ── In-library: driving virtual time in a consumer's own retry test ─────────
func TestRetry_FiresOnSchedule(t *testing.T) {
	r, _ := testingpkg.New(testingpkg.Config{Seed: 7}, testingpkg.Deps{Epoch: epoch})
	fakes := r.Fakes()
	svc, _ := myservice.New(cfg, myservice.Deps{Clock: fakes.Clock, Random: fakes.Random})
	fakes.Clock.(*testingtest.FakeClock).Advance(30 * time.Second) // fire the retry; no wall sleep
	_ = svc
}
```

## 6. Design rationale

1. **`testing` is a meta-pattern, not a port** (10 §4). Nothing injects a `testing.Provider` into
   any `Deps`. It owns the canonical **fakes** of the two ports production code *does* inject —
   `Clock` and `RandomSource`, whose interfaces are owned by `dependencies` (10 §4,
   `dependencies.md`), referenced here as type aliases, never redefined — plus the conformance-suite
   construct every other `<pattern>test` reuses. That is its whole reason to be a library rather
   than scattered helpers.
2. **One `Suite[S]` value, imported by both sides, closes fakes-drift** (08 §2). The fake's test and
   each adapter's test run the *same* `Suite` through `RunSuite`; there is no second copy to drift.
   Substitutability isn't asserted, it's executed against shared cases — the mechanical closure 08
   §2 promises.
3. **The core imports neither stdlib `testing` nor an assertion library.** Assertion is delegated to
   the 3-method `Report` sink; `*testing.T` is adapted in `testingtest`. This lets `engine`/
   `testharness` run suites inside *shipped* kernel code to mint Evidence (07 §4) without dragging
   the test framework into a `CGO_ENABLED=0` static binary (10 §6.1) or forking the suite for
   production. This is the consumer's load-bearing demand and it wins the `T`-vs-`Report` conflict.
4. **Zero values are valid and deterministic** (10 §4 purity). `Config{}` → seed 0; `Deps{}` →
   Unix-epoch start; `FakeClock` zero-start → epoch. Never `time.Now()`, never real entropy. A fake
   that silently reads the wall clock is the exact bug class this pattern abolishes, so the zero
   value must be reproducible, not convenient.
5. **`FakeClock` is virtual time with explicit `Advance`.** It implements `dependencies.Clock`
   (`Now` + `After`) and never self-advances; an `After` channel fires only when `Advance` crosses
   its deadline. The kernel's `testharness`, the orchestrator's reconcile loop, and any
   retry/backoff/hibernate logic depend on this determinism.
6. **`Harness` is the subject's wiring seam, ≤5 methods.** It vends `Clock`/`RandomSource` for the
   subject's own `Deps`, gates capabilities (`Has`), owns LIFO teardown (`Cleanup`), and exposes the
   run `Context`. Five methods exactly — at the `interfacebloat` ceiling (10 §9), none speculative.
7. **Capability gating, not capability failure** (02 §1). `Harness.Has` + `Report.Skipf` map onto
   `CapabilityManifest`: an adapter that legitimately lacks an optional capability *skips* those
   cases (counted in `Result.Skipped`) rather than failing — the same graceful degradation the
   engine and gate read, so a partial adapter does not look broken.
8. **`RunSuite` returns a structured `Result` and captures panics** (02 §2, M2). The engine folds a
   conformance run into a `GoTestEvidence` envelope without parsing stdout; a panicking adapter case
   becomes data (`CaseResult.Panic`), not a stack-unwind that kills a 50-task run.
9. **`RandomSource` stays one method (`Read`), io.Reader-shaped.** crypto/rand and the fake then
   interchange directly (production binds crypto/rand by construction). Typed randomness (`Uint64`,
   UUIDs, jitter) is a thin helper built on `Read` — putting it on the port would break the
   crypto/rand substitution and bloat the interface for one convenience.
10. **Generics, not `any`+casts.** `Suite[S]`/`Factory[S]`/`Case[S]` give adapter authors
    compile-time proof their factory yields the exact port; a stringly-typed registry would push
    that to runtime and invite the drift this pattern eliminates.
11. **Per-pattern fakes stay in their own `<pattern>test`** (cohesion contract). `testing` maintains
    `FakeClock`/`FakeRandomSource` and the suite construct forever; it does **not** absorb
    `FakeSink`/`FakeSecretProvider`, or the dependency graph inverts and `testing` becomes a
    god-library.

## 7. Open questions

| # | Question / conflict | Producer position | Consumer position | Reconciler resolution 🧩 |
|---|---|---|---|---|
| 1 | Assertion sink: bind to a `testing.TB`-shaped interface vs an assertion-free `Report`? | `T` interface (5 methods: `Helper`/`Errorf`/`Fatalf`/`Logf`/`Cleanup`) so the suite runs under `go test`, fuzz, bench, and the kernel testharness. | 3-method `Report` (`Errorf`/`Fatalf`/`Skipf`); core must NOT import stdlib `testing` so suites run inside shipped binaries to mint Evidence. | 🧩 **Consumer.** The static-binary + Evidence-minting requirement (10 §6.1, 07 §4) is load-bearing and the producer's goal (run outside `go test`) is *better* served by an sink the core doesn't import `testing` for. Added `Skipf` for capability gating; dropped `Helper`/`Logf` (re-added on the `*testing.T` adapter where they belong). `Cleanup` moved onto `Harness`, not the sink — that is where teardown is scoped. |
| 2 | Subject-construction seam: `Factory(ctx, T)` vs `Factory(ctx, Harness)`? | `Factory[S](ctx, T) (subject, teardown)` — returns its own teardown. | `Factory[S](ctx, Harness) (subject, error)` — Harness vends deterministic sources + capability gate. | 🧩 **Consumer's `Harness`**, with the producer's error/teardown concern preserved: factory returns `(S, error)` (a failed wiring is a failed case, not a panic), and teardown moves to `Harness.Cleanup` (LIFO), keeping cleanup co-located with the case that registers it rather than the construction tuple. |
| 3 | `Suite` as a `struct{Cases map}` (producer) vs `interface{Cases() iter.Seq}` (consumer)? | Struct with `Cases map[string]func(...)`, sorted at Run for determinism. | `Suite`/`Case` interfaces returning `iter.Seq[Case]`. | 🧩 **Hybrid, simpler side kept.** `Suite[S]` stays a struct (producer, simpler), but `Cases` is `iter.Seq[Case[S]]` not a map — a map's iteration order is nondeterministic and re-sorting by key is a footgun; `iter.Seq` gives caller-defined stable order and streams large suites. `Case[S]` is a struct, not an interface (no second method to justify). |
| 4 | `Clock` shape: producer `Now/Since/After/Sleep(ctx)` vs consumer `Now/Since/NewTimer`. | `After(d) <-chan` + `Sleep(ctx, d) error`. | `NewTimer(d) (<-chan, func() bool)` (stoppable), no `Sleep`. | 🧩 **Merged to 4 methods:** `Now`, `Since`, `NewTimer` (consumer — the stop func prevents fake-timer leaks; `After` is `NewTimer` minus the stop), `Sleep(ctx, d) error` (producer — the cancellable blocking seam, honoring ctx-first 10 §9). Under the 5-method ceiling; no split needed. — **superseded by row 10**: `Clock` is now a 2-method alias of `dependencies.Clock` (Now + After); this row is historical. |
| 5 | `RandomSource`: `Read` only (producer) vs `Read`+`Uint64` (consumer)? | `Read(p)` only — io.Reader-compatible so crypto/rand interchanges. | add `Uint64()` for seeded-PRNG ergonomics. | 🧩 **Producer.** One method keeps the crypto/rand substitution intact (a 2-method port has no stdlib production adapter). `Uint64`/UUID/jitter are helpers built on `Read` in `testingtest`, not port methods — rationale 9. Consumer's ergonomic need is met without widening the port. |
| 6 | Fake-determinism stability guarantee. | Identical `Config` ⇒ identical timeline/bytes **forever**; changing the stream is a *breaking change*, frozen at v1, only changed behind a new constructor. | (implied: reproducible across clean-room runs.) | 🧩 **Accepted as a frozen invariant.** The byte/timeline algorithm of `FakeClock`/`FakeRandomSource` is part of the contract: a change is breaking (golden tests pin it), gated by `buf breaking`-equivalent semver discipline (10 §9), and only ever introduced behind a new constructor — never "improved" in a minor. |
| 7 | `Deps` content: empty `struct{}` (producer) vs `Deps{Epoch time.Time}` (consumer)? | `Deps struct{}` — fakes take no impure inputs; uniform spine, additive. | `Deps{Epoch}` so vended fakes are reproducible across processes; Epoch is injected, never read. | 🧩 **Consumer.** An *injected* `Epoch` is not impure (it is data, not a clock read), and it makes cross-process reproducibility explicit at the spine rather than hidden in `Config`. The producer's purity guarantee is unbroken: `New` still performs no I/O, clock, or env read. |
| 8 | Where does the `testing.T` capability live — `Wrap(t)` returning the suite `T` (producer) vs `Report(t)`/`Harness(t)` adapters (consumer)? | `testingtest.Wrap(*testing.T) testing.T`. | `testingtest.NewReport`, `NewHarness`, `AssertResult` adapters. | 🧩 **Consumer's adapter set**, renamed to avoid shadowing the package-level `Report`/`Harness` *types*: `NewReport`, `NewHarness`, plus `AssertResult` (Result→pass/fail bridge). The producer's one-liner ergonomics survive as `NewReport(t)` / `NewHarness(t)`. |
| 9 | `RunSuite` as a free function (consumer) vs `Suite.Run` method (producer)? | `func (s Suite[S]) Run(ctx, t, factory)`. | `func RunSuite[S](ctx, r, suite, factory) Result`. | 🧩 **Consumer's free function.** Go methods cannot add type parameters beyond the receiver's, and threading the `*Runner` (epoch/seed/policy) + returning `Result` is cleaner as a generic free function. `RunSuite[S](r, suite, factory) Result` — ctx flows through `Harness.Context()`/`Config.CaseTimeout`, so it is not a separate parameter. |
| 10 | `Clock`/`RandomSource` ownership + shape: this draft re-declared both port interfaces and claimed sole ownership ("owned HERE and nowhere else"), with a 4-method `Clock` (`Now`/`Since`/`NewTimer`/`Sleep`) that diverges from `dependencies.Clock`'s `Now`/`After`. | n/a | n/a | 🧩 **cross-contract reconciliation, post-draft.** 10 §4 and `dependencies.md` own the port *interfaces*; `testing` owns only their canonical **fakes** + the suite construct. The re-declarations are replaced by type aliases of `dependencies.Clock`/`dependencies.RandomSource`, so the signatures match exactly (`Clock` = `Now` + `After(ctx, d)`); `FakeClock` implements that 2-method port with `Advance` as the test-only affordance. Supersedes this table's row 4 (which had reconciled to a 4-method `Clock` before the `dependencies` ownership was settled). The "owned HERE and nowhere else" claim is struck. |
