package observability_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// sink keeps the benchmarked work from being elided by the compiler. It is a package-
// level `any` (ADR-0020 dimension (g)) so the result is observed off the hot path and the
// optimizer cannot prove the construction dead; `any` keeps it off any errname sentinel
// path.
//
//nolint:gochecknoglobals // benchmark sink must be package-level so the compiler cannot elide the measured work.
var sink any

// benchExporter is a no-op Exporter so Flush benchmarks measure the library's drain, not
// a backend's wire.
type benchExporter struct{}

func (benchExporter) Export(context.Context, []observability.Record) error { return nil }

type benchClock struct{}

func (benchClock) Now() time.Time { return time.Unix(1700000000, 0).UTC() }

//nolint:ireturn // the bench helper hands back the frozen Provider port the benchmarks exercise.
func newBenchProvider(b *testing.B) observability.Provider {
	b.Helper()
	p, err := observability.New(
		observability.Config{ServiceName: "bench-svc", DefaultPlane: observability.PlaneSelf},
		observability.Deps{Exporter: benchExporter{}, Clock: benchClock{}},
	)
	if err != nil {
		b.Fatalf("New: %v", err)
	}
	return p
}

// BenchmarkNew measures the constructor spine — the pure New(Config, Deps) path the
// composition root runs once per component. The performance lane (`ctl.sh bench` /
// `bench-guard`, ADR-0020 dimension (g)) records this at -benchmem -count=10 and
// benchstat guards HEAD vs .benchbaseline so a > +10% time/allocs regression fails.
func BenchmarkNew(b *testing.B) {
	configuration := observability.Config{ServiceName: "bench-svc", DefaultPlane: observability.PlaneSelf}
	dependencies := observability.Deps{Exporter: benchExporter{}, Clock: benchClock{}}
	var p observability.Provider
	var err error
	b.ReportAllocs()
	for b.Loop() {
		p, err = observability.New(configuration, dependencies)
	}
	if err != nil {
		b.Fatalf("New: %v", err)
	}
	sink = p
}

// BenchmarkEmit measures the hottest path: one Event onto the stream (severity filter +
// plane stamp + resource copy + buffered append under the lock). Every component emit
// pays this.
func BenchmarkEmit(b *testing.B) {
	p := newBenchProvider(b)
	ctx := context.Background()
	ev := observability.Event{
		Name: "model.call", Severity: observability.SeverityInfo,
		Fields: []observability.Field{
			observability.String("phase", "implement"),
			observability.Int64("tokens.in", 1200),
		},
	}
	b.ReportAllocs()
	for b.Loop() {
		p.Emit(ctx, ev)
	}
	sink = p
}

// BenchmarkWith measures child-Provider derivation (the inherited-field allocation), the
// per-run/per-request scope a library stamps onto every Event.
func BenchmarkWith(b *testing.B) {
	p := newBenchProvider(b)
	f := observability.String("run.id", "run-123")
	var child observability.Provider
	b.ReportAllocs()
	for b.Loop() {
		child = p.With(f)
	}
	sink = child
}

// BenchmarkScope measures a span open+close (mint IDs + stamp duration from the Clock +
// emit the span Event), the per-phase / per-model-call cost.
func BenchmarkScope(b *testing.B) {
	p := newBenchProvider(b)
	ctx := context.Background()
	b.ReportAllocs()
	for b.Loop() {
		_, end := p.Scope(ctx, "phase.start", observability.String("phase", "implement"))
		end(observability.Outcome{})
	}
	sink = p
}

// BenchmarkLedgerEvent measures the T6 cost.ledger encoder — built once per phase/model
// call to ride the stream.
func BenchmarkLedgerEvent(b *testing.B) {
	l := observability.Ledger{
		RunID: "run-1", PhaseID: "implement", Model: "claude", Harness: "claudecode",
		TokensIn: 1200, TokensOut: 800, CacheHits: 200, CostMicros: 5000,
		Retries: 1, WallTime: time.Second,
	}
	var e observability.Event
	b.ReportAllocs()
	for b.Loop() {
		e = observability.LedgerEvent(time.Time{}, l)
	}
	sink = e
}
