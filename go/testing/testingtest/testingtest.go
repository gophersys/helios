// Package testingtest holds the public FAKES for testing's own ports (Clock,
// RandomSource) plus the *testing.T adapters. They live HERE, not in package
// testing, so production code that imports the fakes does not pull in stdlib
// "testing" (10 §6.1 <pattern>test convention). Per-pattern fakes (FakeSink, …)
// live in THEIR own <pattern>test; this package holds only the two universal fakes
// and the suite adapters.
package testingtest

import (
	"context"
	stdtesting "testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/internal/seedkey"
)

// FakeClock is virtual-time: it NEVER advances on its own. Tests drive time
// explicitly via Advance, which is what makes timeout/retry/backoff/hibernate
// logic deterministic. It implements dependencies.Clock exactly (Now + After);
// Advance is the test-only affordance, not part of the port. Concurrency: every
// method is goroutine-safe; Advance releases all After channels whose deadline it
// crosses, in deadline order, before returning. Zero start
// (NewFakeClock(time.Time{})) → the Unix epoch.
//
// FakeClock is a type ALIAS of the canonical virtual-time engine in the leaf
// dependenciestest package (one concept, one home — 10 §9): the public fake, the
// Runner's vended Clock, and every other <pattern>test fake are the SAME concrete
// type over the ONE frozen timeline algorithm (contract open question 6). Aliasing
// the leaf engine — rather than re-implementing a sibling — is what guarantees a
// single timeline, a single bug surface, and makes the §5 affordance
// fakes.Clock.(*testingtest.FakeClock).Advance(...) succeed on a Clock the core's
// Runner.Fakes() vends, with no import cycle (testing already imports dependencies).
type FakeClock = dependenciestest.Clock

// NewFakeClock builds a virtual FakeClock starting at start (zero start → the Unix
// epoch). It is the testing-side spelling of dependenciestest.NewClock — the single
// constructor onto the shared timeline engine.
func NewFakeClock(start time.Time) *FakeClock { return dependenciestest.NewClock(start) }

var _ dependencies.Clock = (*FakeClock)(nil)

// FakeRandomSource is a deterministic, reproducible byte stream from seed. NOT
// crypto-secure — tests only; production binds crypto/rand. Concurrency: Read is
// serialized; identical seed + identical Read call sequence ⇒ identical bytes,
// forever (a maintained, version-pinned guarantee — open question 6).
//
// Like FakeClock, it is a type ALIAS of the canonical leaf engine
// (dependenciestest.Random) so the public fake and the Runner's vended RandomSource
// are the same concrete type over the ONE frozen byte-stream algorithm — there is a
// single ChaCha8 stream and a single bug surface for the whole library graph.
type FakeRandomSource = dependenciestest.Random

// NewFakeRandomSource builds a deterministic entropy stream from a uint64 seed. The
// leaf engine is keyed by a [32]byte; seedkey.Derive is the single, frozen function
// (shared with the Runner-vended path) that spreads the uint64 seed across that key
// so the seed→stream mapping stays a pure, version-pinned function (open question 6).
// The exact bytes are pinned by TestFakeRandomSource_GoldenBytes; changing the
// derivation is a BREAKING change that may only ship behind a new constructor.
func NewFakeRandomSource(seed uint64) *FakeRandomSource {
	return dependenciestest.NewRandom(seedkey.Derive(seed))
}

var _ dependencies.RandomSource = (*FakeRandomSource)(nil)

// ── Adapters from stdlib testing into the assertion-free core ─────────────────.

// NewReport adapts *testing.T to testing.Report so a go test drives any Suite in
// one line; the core stays stdlib-testing-free. Skipf maps to t.Skipf.
//
//nolint:ireturn // contract §3: NewReport returns the testing.Report port; the tReport adapter is unexported by design.
func NewReport(t *stdtesting.T) testingpkg.Report {
	t.Helper()
	return tReport{t: t}
}

// tReport bridges the assertion-free Report onto *testing.T.
type tReport struct{ t *stdtesting.T }

func (r tReport) Errorf(format string, args ...any) { r.t.Helper(); r.t.Errorf(format, args...) }
func (r tReport) Fatalf(format string, args ...any) { r.t.Helper(); r.t.Fatalf(format, args...) }
func (r tReport) Skipf(format string, args ...any)  { r.t.Helper(); r.t.Skipf(format, args...) }

// NewHarness builds a standalone testing.Harness for wiring fakes into a library's
// own unit test outside RunSuite. Capabilities default to present.
//
//nolint:ireturn // contract §3: NewHarness returns the testing.Harness port; the tHarness adapter is unexported by design.
func NewHarness(t *stdtesting.T, opts ...HarnessOption) testingpkg.Harness {
	t.Helper()
	configuration := harnessConfig{epoch: time.Time{}, seed: 0, absentCaps: map[string]struct{}{}}
	for _, opt := range opts {
		opt(&configuration)
	}
	h := &tHarness{
		t:          t,
		clock:      NewFakeClock(configuration.epoch),
		random:     NewFakeRandomSource(configuration.seed),
		absentCaps: configuration.absentCaps,
		ctx:        context.Background(),
	}
	return h
}

// harnessConfig accumulates HarnessOption mutations.
type harnessConfig struct {
	epoch      time.Time
	seed       uint64
	absentCaps map[string]struct{}
}

// HarnessOption configures a standalone Harness built by NewHarness.
type HarnessOption func(*harnessConfig)

// WithSeed seeds the FakeRandomSource the Harness vends.
func WithSeed(seed uint64) HarnessOption {
	return func(c *harnessConfig) { c.seed = seed }
}

// WithEpoch anchors the FakeClock the Harness vends (zero → the Unix epoch).
func WithEpoch(epoch time.Time) HarnessOption {
	return func(c *harnessConfig) { c.epoch = epoch }
}

// WithoutCapability marks name as absent so Has(name) reports false — the seam a
// capability-gated case uses to skip cleanly.
func WithoutCapability(name string) HarnessOption {
	return func(c *harnessConfig) { c.absentCaps[name] = struct{}{} }
}

// tHarness is the standalone Harness. Capabilities default present: Has reports
// true unless WithoutCapability marked the name absent. Cleanup is registered on
// t.Cleanup so it runs LIFO at the end of the test (the stdlib guarantee).
type tHarness struct {
	t          *stdtesting.T
	clock      *FakeClock
	random     *FakeRandomSource
	absentCaps map[string]struct{}
	ctx        context.Context
}

// Clock and RandomSource return the port interfaces the Harness contract declares
// (contract §2/§3): the *FakeClock/*FakeRandomSource adapters are concrete here, but
// the Harness port vends them as their interfaces, so ireturn is wrong-for-contract
// for these two methods (they implement the frozen Harness interface).

//nolint:ireturn // contract §2/§3: Harness.Clock() returns the Clock port (the fake is vended as its interface).
func (h *tHarness) Clock() testingpkg.Clock { return h.clock }

//nolint:ireturn // contract §2/§3: Harness.RandomSource() returns the RandomSource port (the fake is vended as its interface).
func (h *tHarness) RandomSource() testingpkg.RandomSource { return h.random }

func (h *tHarness) Context() context.Context { return h.ctx }

// Has reports capability presence; defaults to present unless explicitly removed.
func (h *tHarness) Has(capability string) bool {
	_, absent := h.absentCaps[capability]
	return !absent
}

// Cleanup registers fn on the underlying *testing.T (LIFO at test end).
func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }

// AssertResult fails t if any case in r failed or panicked — the bridge from a
// structured Result back to go test's pass/fail. Skips do not fail t.
func AssertResult(t *stdtesting.T, r testingpkg.Result) {
	t.Helper()
	for _, line := range resultReport(r) {
		if line.fail {
			t.Errorf("%s", line.text)
		} else {
			t.Logf("%s", line.text)
		}
	}
}

// reportLine is one rendered diagnostic from a Result: a failing case yields a
// fail line, a skip yields an informational log line, a pass yields nothing.
type reportLine struct {
	fail bool
	text string
}

// resultReport is the pure decision core of AssertResult, factored out so the
// fail/skip routing is unit-testable WITHOUT failing a real *testing.T (a failing
// subtest unavoidably fails its parent). AssertResult is the thin *testing.T
// binding over this.
func resultReport(r testingpkg.Result) []reportLine {
	var lines []reportLine
	for _, c := range r.Cases {
		prefix := "conformance " + r.Suite + "/" + c.Name
		switch c.Outcome {
		case testingpkg.Fail:
			if c.Panic != "" {
				lines = append(lines, reportLine{fail: true, text: prefix + " PANICKED: " + c.Panic})
			} else {
				lines = append(lines, reportLine{fail: true, text: prefix + " FAILED: " + joinMessages(c.Messages)})
			}
		case testingpkg.Skip:
			lines = append(lines, reportLine{fail: false, text: prefix + " skipped: " + joinMessages(c.Messages)})
		case testingpkg.Pass:
			// A passing case produces no diagnostic line — nothing to report.
		}
	}
	return lines
}

func joinMessages(msgs []string) string {
	out := ""
	for i, m := range msgs {
		if i > 0 {
			out += "; "
		}
		out += m
	}
	return out
}
