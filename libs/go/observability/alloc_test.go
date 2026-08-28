package observability_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// ── ENFORCEMENT TOOTH (ADR-0020 dimension (b): allocation budgets) ────────────.
//
// Emit is the system's hottest path: every component emit pays it. The contract
// (Record.Resource is SHARED + READ-ONLY) lets Emit stamp the immutable resource
// map BY REFERENCE rather than deep-copying it per event. This test pins that as a
// hard allocation ceiling so the per-event map copy can never silently return: the
// old impl did `make(map[string]string, N)` + a range-copy on every Emit, which
// allocates at least one object per call and blows the bound below.
//
// This is the allocation-budget arm the audit's enforcement gap called for — a
// `testing.AllocsPerRun`-style ceiling on a documented hot path, not merely the
// relative bench-guard regression check (which bakes the avoidable alloc into the
// baseline as the accepted floor and so is blind to it).

// emitAllocBudget is the hard ceiling on allocations per Emit on the root Provider.
// With the resource map shared by reference and a pre-built Event (no per-call Field
// merge at the root), a steady-state Emit allocates nothing on the hot path; the
// buffer append amortizes to zero over the AllocsPerRun loop. The per-event resource
// copy (the bug) allocated a map per call, exceeding this bound.
const emitAllocBudget = 0

// TestEmitAllocationBudget asserts allocs-per-Emit stays at or below emitAllocBudget.
//
// WEAKEN-TO-CONFIRM: restore the deleted per-emit copy in impl.emit —
//
//	res := make(map[string]string, len(p.state.resource))
//	for k, v := range p.state.resource { res[k] = v }
//	p.state.push(&Record{Event: e, Resource: res, ...})
//
// and AllocsPerRun returns >= 1 (one map allocation per Emit), failing this test.
// The test is therefore non-vacuous: it FAILS under the old per-copy code and PASSES
// only with the by-reference share.
//
// This test runs SERIALLY (no t.Parallel): testing.AllocsPerRun panics if called from a
// parallel test, and it reads a process-wide heap counter that a concurrent sibling would
// perturb, so the alloc budget must be measured on a quiescent allocator.
//
//nolint:paralleltest // testing.AllocsPerRun panics under t.Parallel() and needs a quiescent allocator (see doc above).
func TestEmitAllocationBudget(t *testing.T) {
	// A multi-key resource map: the deep copy the fix removes allocated a populated
	// map per Emit, so the budget is non-trivially exceeded under the old code (a
	// single-key map would still allocate, but a realistic resource makes the regression
	// unmistakable).
	p, err := observability.New(
		observability.Config{
			ServiceName:    "alloc-budget-svc",
			ServiceVersion: "1.2.3",
			Environment:    "test",
			DefaultPlane:   observability.PlaneSelf,
			ResourceAttrs: map[string]string{
				"service.instance.id": "instance-7",
				"deployment.region":   "us-east-1",
				"host.name":           "node-42",
			},
		},
		observability.Deps{Exporter: noopAllocExporter{}, Clock: fixedAllocClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	ctx := context.Background()
	// A pre-built Event so the measured op is ONLY the emit spine (severity filter,
	// plane stamp, resource stamp, buffered append) — not Event/Field construction.
	// At the root the inherit slice is empty, so no per-call Field merge happens.
	ev := observability.Event{
		Name:     "model.call",
		Severity: observability.SeverityInfo,
		Plane:    observability.PlaneSelf,
		Fields: []observability.Field{
			observability.String("phase", "implement"),
			observability.Int64("tokens.in", 1200),
		},
	}

	avg := testing.AllocsPerRun(2000, func() {
		p.Emit(ctx, ev)
	})

	if avg > emitAllocBudget {
		t.Fatalf("Emit allocates %.2f objects/op, budget is %d: the hot-path resource map "+
			"must be shared by reference, not deep-copied per Emit (see Record.Resource — "+
			"SHARED + READ-ONLY)", avg, emitAllocBudget)
	}
}

type noopAllocExporter struct{}

func (noopAllocExporter) Export(context.Context, []observability.Record) error { return nil }

type fixedAllocClock struct{}

func (fixedAllocClock) Now() time.Time { return time.Unix(1700000000, 0).UTC() }
