package errors_test

import (
	"testing"

	"github.com/gophersys/libs/go/errors"
)

// The package-level sinks below keep the benchmarked construction observable so the compiler
// cannot prove the result dead and elide the work being measured (errcheck's check-blank also
// forbids `_ = errors.New(...)`); an `any` sink keeps them off the errname sentinel path.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sinkValue any
	sinkKind  errors.Kind
)

// BenchmarkNew measures the constructor spine — the hottest path in the error model (every
// failure return mints one). The performance lane (`ctl.sh bench` / `bench-guard`, ADR-0020
// dimension (g)) records this at -benchmem -count=10 and benchstat guards HEAD vs the
// .benchbaseline so a regression > +10% time or allocs fails.
func BenchmarkNew(b *testing.B) {
	var e *errors.Error
	b.ReportAllocs()
	for b.Loop() {
		e = errors.New(errors.KindNotFound, "resource not found")
	}
	sinkValue = e
}

// BenchmarkWrap measures the wrap path (classify + preserve chain), the second hot path.
func BenchmarkWrap(b *testing.B) {
	cause := errors.New(errors.KindUnavailable, "upstream down")
	var e *errors.Error
	b.ReportAllocs()
	for b.Loop() {
		e = errors.Wrap(errors.KindInternal, "while serving request", cause)
	}
	sinkValue = e
}

// BenchmarkKindOf measures the inspection path (the transport boundary switches on it).
func BenchmarkKindOf(b *testing.B) {
	err := errors.Wrap(errors.KindConflict, "outer", errors.New(errors.KindNotFound, "inner"))
	var k errors.Kind
	b.ReportAllocs()
	for b.Loop() {
		k = errors.KindOf(err)
	}
	sinkKind = k
}
