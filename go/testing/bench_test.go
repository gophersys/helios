package testing_test

import (
	"context"
	gotest "testing"
	"time"

	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// sink is a package-level any so the compiler cannot prove the benchmarked results dead and
// elide the work being measured (ADR-0020 dimension (g)). `any` keeps it off any typed
// sentinel path. The performance lane (`ctl.sh bench` / `bench-guard`) records these at
// -benchmem -count=10 and benchstat guards HEAD vs .benchbaseline so a regression > +10%
// allocs/bytes fails.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot prove the result dead and elide the measured work.
var sink any

// BenchmarkNew measures the constructor spine — the pattern's pure New(Config, Deps). Every
// conformance run mints one Runner, so this is the hot construction path.
func BenchmarkNew(b *gotest.B) {
	configuration := testingpkg.Config{Seed: 7, RequireCapabilities: []string{"docker", "k3d"}}
	dependencies := testingpkg.Deps{Epoch: time.Unix(1700000000, 0).UTC()}
	b.ReportAllocs()
	for b.Loop() {
		r, err := testingpkg.New(configuration, dependencies)
		if err != nil {
			b.Fatalf("New: %v", err)
		}
		sink = r
	}
}

// BenchmarkFakes measures the per-Runner Fakes() bundle build (a fresh Clock + RandomSource),
// the seam a library's own unit test wires into its Deps.
func BenchmarkFakes(b *gotest.B) {
	r, err := testingpkg.New(testingpkg.Config{Seed: 1}, testingpkg.Deps{})
	if err != nil {
		b.Fatalf("New: %v", err)
	}
	b.ReportAllocs()
	for b.Loop() {
		sink = r.Fakes()
	}
}

// BenchmarkRunSuite measures the conformance execution spine over a small suite: build the
// per-case Harness, run the case under panic containment, accumulate the structured Result.
// This is the path engine/evidence drives per port.
func BenchmarkRunSuite(b *gotest.B) {
	r, err := testingpkg.New(testingpkg.Config{}, testingpkg.Deps{})
	if err != nil {
		b.Fatalf("New: %v", err)
	}
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "a", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
		{Name: "b", Run: func(_ int, h testingpkg.Harness, _ testingpkg.Report) { _ = h.Clock().Now() }},
	}
	suite := testingpkg.Suite[int]{Name: "bench", Cases: benchSeq(cases...)}
	b.ReportAllocs()
	for b.Loop() {
		sink = testingpkg.RunSuite(r, suite, factory)
	}
}

// BenchmarkFakeRandomSourceRead measures the deterministic entropy fill — the hot path a
// seeded subject reads through (UUIDs, jitter, nonces all funnel through Read).
func BenchmarkFakeRandomSourceRead(b *gotest.B) {
	rnd := testingtest.NewFakeRandomSource(42)
	buf := make([]byte, 64)
	b.ReportAllocs()
	for b.Loop() {
		if _, err := rnd.Read(buf); err != nil {
			b.Fatalf("Read: %v", err)
		}
		sink = buf
	}
}

// BenchmarkFakeClockAdvance measures virtual-time advancement with a registered waiter — the
// retry/backoff/hibernate driving path consumers exercise per simulated tick.
func BenchmarkFakeClockAdvance(b *gotest.B) {
	clock := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	b.ReportAllocs()
	for b.Loop() {
		ch := clock.After(context.Background(), time.Second)
		clock.Advance(time.Second)
		sink = <-ch
	}
}

// benchSeq turns a slice of cases into the iter.Seq the Suite expects.
func benchSeq[S any](cases ...testingpkg.Case[S]) func(yield func(testingpkg.Case[S]) bool) {
	return func(yield func(testingpkg.Case[S]) bool) {
		for _, c := range cases {
			if !yield(c) {
				return
			}
		}
	}
}
