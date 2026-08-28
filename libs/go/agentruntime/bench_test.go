package agentruntime_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
)

// The sinks below prevent the compiler from proving the benchmarked work dead and eliding it. `any`
// keeps them off any typed sentinel path (ADR-0020 §g); package-level so the optimizer cannot see
// across the benchmark boundary.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sink    any
	sinkStr string
)

// BenchmarkNew measures the pure construction spine (the per-pod cost paid once at sidecar boot):
// validate the invariants + wire the registry. It allocates the registry map; no I/O.
func BenchmarkNew(b *testing.B) {
	configuration := agentruntimetest.Config(nil)
	dependencies := agentruntime.Deps{
		Sessions: agentruntimetest.NewSessionsNoT(),
		Bus:      agentruntimetest.NewFakeBus(),
		Observer: agentruntimetest.NewFakeObserver(),
		Clock:    agentruntimetest.FixedClock{},
	}
	b.ReportAllocs()
	for b.Loop() {
		runtime, err := agentruntime.New(configuration, dependencies)
		if err != nil {
			b.Fatalf("New: %v", err)
		}
		sink = runtime
	}
}

// BenchmarkSubjectRender measures the subject-grammar render (called on every publish to route a
// message). It is the per-message addressing cost on the hot path.
func BenchmarkSubjectRender(b *testing.B) {
	id := agentruntime.AgentID("agent-bench-1")
	b.ReportAllocs()
	for b.Loop() {
		sinkStr = agentruntime.EventsSubject(id)
	}
}
