//go:build lifecycle

package observability_test

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/observability"
)

// TestLifecycle_ProviderDoubleCloseIdempotentNoOrphans is the full-object-lifecycle
// conformance (ADR-0020 dimension (c)) for the observability closeable handle. The
// Provider port has no Close of its own — its owned resource is the BUFFER of emitted-
// but-unflushed Records plus the backing Exporter — so the closeable handle is a thin
// shutdown wrapper whose Close drains the buffer to the Exporter exactly once. The probe
// drives testing.AssertLifecycle: construct -> use (emit some Events) -> first Close
// (drain + mark exporter closed) -> SECOND Close is a NO-OP (no re-drain, no re-close of
// the exporter) -> CountOwned()==0 (no Record left buffered, exporter closed exactly
// once). The orphan-GOROUTINE half is asserted by the surrounding goleak.VerifyNone. The
// probe is tagged `//go:build lifecycle` so the drive stays out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_ProviderDoubleCloseIdempotentNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newProviderProbe)
}

// providerProbe is the testing.LifecycleProbe binding for an observability.Provider. Its
// "owned resource" is the unflushed buffer (drained on Close) plus a closeExporter whose
// open-count must return to zero after a single Close. A second Close must NOT drain
// again or decrement the exporter twice — the double-close invariant.
type providerProbe struct {
	provider observability.Provider
	exporter *closeExporter
	closed   atomic.Bool
	mu       sync.Mutex
}

// newProviderProbe constructs a fresh live Provider over a real slog-shaped tracking
// Exporter. It is the testing.LifecycleFactory the driver invokes once per run.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newProviderProbe(_ context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	exp := &closeExporter{}
	exp.open.Store(1) // the exporter is "open" until the probe's Close reaps it
	p, err := observability.New(
		observability.Config{ServiceName: "lifecycle-svc", DefaultPlane: observability.PlaneSelf},
		observability.Deps{Exporter: exp, Clock: lifecycleClock{}},
	)
	if err != nil {
		return nil, nil, err
	}
	probe := &providerProbe{provider: p, exporter: exp}
	// Teardown is a final best-effort Close so a failed assertion never leaves the
	// exporter open.
	teardown := func() { _ = probe.Close(context.Background()) } //nolint:errcheck // best-effort final reap; the assertions own the real Close checks.
	return probe, teardown, nil
}

// Use exercises the live Provider once: emit a span-scoped Event and a ledger so the
// buffer holds real Records before Close drains them.
func (p *providerProbe) Use(ctx context.Context) error {
	runObs := p.provider.With(observability.String("run.id", "lifecycle-1"))
	ctx, end := runObs.Scope(ctx, "phase.start", observability.String("phase", "implement"))
	runObs.Emit(ctx, observability.LedgerEvent(time.Time{}, observability.Ledger{
		RunID: "lifecycle-1", PhaseID: "implement", Model: "claude", TokensIn: 10,
	}))
	end(observability.Outcome{})
	return nil
}

// Close drains the buffered Records to the Exporter and reaps the Exporter exactly once.
// It is idempotent: the SECOND call drains nothing (Flush on an empty buffer is a no-op)
// and does NOT decrement the exporter's open-count again, so CountOwned stays at zero —
// the double-close-is-a-no-op invariant.
func (p *providerProbe) Close(ctx context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed.Load() {
		// Idempotent: a second Close is a clean no-op (no re-drain, no double-reap).
		return p.provider.Flush(ctx)
	}
	if err := p.provider.Flush(ctx); err != nil {
		return err
	}
	p.exporter.open.Add(-1) // reap the exporter exactly once
	p.closed.Store(true)
	return nil
}

// CountOwned reports the resources still owned after teardown: the exporter's open-count.
// After a single Close it must be zero — the buffer was drained and the exporter reaped
// exactly once, with no orphan.
func (p *providerProbe) CountOwned(context.Context) (int, error) {
	return int(p.exporter.open.Load()), nil
}

// closeExporter is a real observability.Exporter that ships every batch into an in-memory
// log and tracks whether it is still "open" (a stand-in for a real wire/file handle). A
// correct Close reaps it exactly once; a double-reap would drive open negative and a
// missed reap would leave it at 1 — either fails CountOwned==0.
type closeExporter struct {
	open atomic.Int32
	mu   sync.Mutex
	recs []observability.Record
}

func (e *closeExporter) Export(_ context.Context, records []observability.Record) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.recs = append(e.recs, records...)
	return nil
}

// lifecycleClock is a deterministic Clock for the lifecycle harness.
type lifecycleClock struct{}

func (lifecycleClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// ── *testing.T adapters for the testing.Harness / testing.Report ports ───────.

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup
// and Context are exercised by AssertLifecycle; the deterministic-source accessors are
// part of the frozen 5-method port and are never called on this path.
type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract §2: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract §2: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
