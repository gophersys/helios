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
	Clock() Clock               // deterministic; advanced only inside a Case
	RandomSource() RandomSource // seeded, reproducible
	Has(capability string) bool // CapabilityManifest gate (02 §1)
	Cleanup(func())             // LIFO teardown, runs after the Case
	Context() context.Context   // the run ctx; deadlines/cancellation flow here
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
