//go:build lifecycle

package codeinsight_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/codeinsight/codeinsighttest"
)

// TestLifecycle_AnalyzerReusableNoOrphans is the full-object-lifecycle conformance (ADR-0020
// dimension (c)) for the codeinsight Analyzer. The Analyzer owns NO persistent external resource:
// each Analyze shells short-lived `git` children that exec.CommandContext reaps synchronously before
// it returns, so CountOwned is always 0. The probe proves the live object behaves (Use runs a real
// Analyze over a seeded on-disk repository), that the analyzer is REUSABLE (a second Analyze after
// "Close" still succeeds — Close is an idempotent no-op because there is no handle to release), and
// that no git child goroutine survives (the surrounding goleak.VerifyNone). Tagged //go:build
// lifecycle so the on-disk drive stays out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's git children would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_AnalyzerReusableNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c): every git child reaped

	report := &tReport{t: t}
	harness := &tHarness{ctx: context.Background(), t: t}
	libtesting.AssertLifecycle(context.Background(), harness, report, newAnalyzerProbe(t))
}

// analyzerProbe is the LifecycleProbe binding for the codeinsight Analyzer over a seeded on-disk
// repository walked by the real system-git History. The "owned resource" count is the live git child
// processes; since each Analyze reaps its children synchronously, it is always 0.
type analyzerProbe struct {
	analyzer *codeinsight.Analyzer
	closed   bool
}

// newAnalyzerProbe returns a LifecycleFactory that seeds a REAL on-disk repository and yields a fresh
// analyzer probe per run.
func newAnalyzerProbe(t *testing.T) libtesting.LifecycleFactory {
	//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
	return func(_ context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
		dir := codeinsighttest.NewRealRepo(t, codeinsighttest.CanonicalSeed())
		analyzer, err := codeinsight.New(
			codeinsight.Config{RepositoryPath: dir, Identifier: "lifecycle"},
			codeinsight.Deps{
				History:   codeinsight.NewSystemGitHistory(),
				Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
				Clock:     codeinsighttest.FixedClock{},
			},
		)
		if err != nil {
			return nil, nil, err
		}
		return &analyzerProbe{analyzer: analyzer}, func() {}, nil
	}
}

// Use exercises the live analyzer: it runs one real Analyze over the seeded repository and confirms
// a non-empty Report came back. It also proves REUSE — Use is called by the driver before Close, and
// the analyzer is immutable, so a later Analyze after Close still works.
func (p *analyzerProbe) Use(ctx context.Context) error {
	report, err := p.analyzer.Analyze(ctx)
	if err != nil {
		return err //nolint:wrapcheck // surfaced verbatim to the lifecycle Report.
	}
	if len(report.Entities) == 0 {
		return errLifecycleEmpty
	}
	return nil
}

// Close marks the probe closed. The analyzer owns no persistent resource, so Close is an idempotent
// no-op: the second call must also return nil (the double-close invariant). A real Analyze still
// succeeds after Close — immutability proves reuse — which Use already exercised.
func (p *analyzerProbe) Close(context.Context) error {
	p.closed = true
	return nil
}

// CountOwned reports the analyzer's live external resources. The analyzer reaps each git child
// synchronously within Analyze, so it owns nothing between calls — always 0.
func (p *analyzerProbe) CountOwned(context.Context) (int, error) { return 0, nil }

// errLifecycleEmpty signals an empty Report from a seeded repository (a real defect, not a lifecycle
// violation) to AssertLifecycle's Report sink.
var errLifecycleEmpty = lifecycleError("lifecycle: Analyze over a seeded repository returned no entities")

type lifecycleError string

func (e lifecycleError) Error() string { return string(e) }

// ── *testing.T adapters for the testing.Harness / testing.Report ports ───────────────────────────

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup and Context
// are exercised by AssertLifecycle; the deterministic-source accessors are part of the frozen
// 5-method port and are never called on this path.
type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
