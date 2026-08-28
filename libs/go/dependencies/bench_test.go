package dependencies_test

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// The sinks below keep the benchmarked results consumed so the compiler cannot prove the work
// dead and elide it. `any` keeps them off any sentinel-typed path (errname).
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide.
var (
	sink    any
	sinkInt int
)

// BenchmarkResolveZero measures the composition-root spine — Resolve filling every nil port of a
// zero Set with its real adapter. This is the hottest path the library has (every composition root
// calls it once at the edge). The performance lane (`ctl.sh bench` / `bench-guard`, ADR-0020
// dimension (g)) records this at -benchmem -count=10 and benchstat guards HEAD vs the
// .benchbaseline so a regression > +10% time or allocs fails.
func BenchmarkResolveZero(b *testing.B) {
	var s dependencies.Set
	b.ReportAllocs()
	for b.Loop() {
		s = dependencies.Resolve(dependencies.Set{})
	}
	sink = s
}

// BenchmarkResolveWired measures Resolve on an already-complete Set — the fast path where every
// port is non-nil and Resolve binds nothing (pure copy).
func BenchmarkResolveWired(b *testing.B) {
	in := dependencies.Resolve(dependencies.Set{})
	var s dependencies.Set
	b.ReportAllocs()
	for b.Loop() {
		s = dependencies.Resolve(in)
	}
	sink = s
}

// BenchmarkValidate measures the fail-fast wiring check the composition root (and narrowing
// Constructors) run on every New.
func BenchmarkValidate(b *testing.B) {
	in := dependencies.Resolve(dependencies.Set{})
	var err error
	b.ReportAllocs()
	for b.Loop() {
		err = dependencies.Validate(in)
	}
	// Store the error through the `any` sink so the result is consumed without naming a
	// package-level error-typed var (errname forbids `sinkErr`).
	sink = err
}

// BenchmarkRealRandomRead measures the entropy port's hot path — a 32-byte ID-sized read off the
// crypto/rand-backed adapter (the bytes every minted identifier consumes).
func BenchmarkRealRandomRead(b *testing.B) {
	r := dependencies.RealRandom(nil)
	p := make([]byte, 32)
	var n int
	b.ReportAllocs()
	for b.Loop() {
		var err error
		n, err = r.Read(p)
		if err != nil {
			b.Fatalf("Read error: %v", err)
		}
	}
	sinkInt = n
}

// BenchmarkRealClockNow measures the time port's hot path — the Now read every time-stamped event
// performs.
func BenchmarkRealClockNow(b *testing.B) {
	c := dependencies.RealClock()
	var t time.Time
	b.ReportAllocs()
	for b.Loop() {
		t = c.Now()
	}
	sink = t
}
