package testing_test

import (
	"context"
	"errors"
	"sync/atomic"
	gotest "testing"

	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// These are the ALWAYS-ON (untagged) tests of the library's AssertLifecycle driver — the
// lifecycle-conformance machinery testing OWNS (lifecycleconformance.go). The heavy
// goroutine-owning probe lives in the `//go:build lifecycle` lane; here we drive the driver
// with lightweight in-memory probes so every branch of AssertLifecycle (construct/use/
// first-close/second-close/CountOwned) is exercised in the fast unit run, and a mutation to
// any of those branches is killed. Each assertion has a paired negative-control proving the
// driver actually reports the violation (non-vacuity).

// recordingReport is a testing.Report that records whether any failure was raised, WITHOUT
// touching a *testing.T (so a deliberate failure in a negative-control does not fail the real
// test). Skipf does not set failed. Shared by the untagged AssertLifecycle tests here and the
// `//go:build lifecycle` goroutine-probe test.
type recordingReport struct{ failed atomic.Bool }

func (r *recordingReport) Errorf(string, ...any) { r.failed.Store(true) }
func (r *recordingReport) Fatalf(string, ...any) { r.failed.Store(true) }
func (r *recordingReport) Skipf(string, ...any)  {}

// scriptedProbe is a fully in-memory testing.LifecycleProbe whose every leg is scripted, so
// each AssertLifecycle assertion can be exercised AND violated. counts.close tracks how many
// times Close was invoked (the driver must call it exactly twice: first + idempotent second).
type scriptedProbe struct {
	useErr      error
	firstClose  error
	secondClose error
	countErr    error
	ownedAfter  int
	closeCalls  atomic.Int32
	usedCalls   atomic.Int32
}

func (p *scriptedProbe) Use(context.Context) error {
	p.usedCalls.Add(1)
	return p.useErr
}

func (p *scriptedProbe) Close(context.Context) error {
	if p.closeCalls.Add(1) == 1 {
		return p.firstClose
	}
	return p.secondClose
}

func (p *scriptedProbe) CountOwned(context.Context) (int, error) {
	return p.ownedAfter, p.countErr
}

// driveLifecycle runs AssertLifecycle over a fixed probe and reports whether it raised any
// failure on a recording sink (without touching a real *testing.T).
func driveLifecycle(t *gotest.T, probe testingpkg.LifecycleProbe) bool {
	t.Helper()
	rep := &recordingReport{}
	harness := testingtest.NewHarness(t)
	factory := func(context.Context, testingpkg.Harness) (testingpkg.LifecycleProbe, func(), error) {
		return probe, func() {}, nil
	}
	testingpkg.AssertLifecycle(context.Background(), harness, rep, factory)
	return rep.failed.Load()
}

// TestAssertLifecycle_CleanProbePasses: a probe that uses cleanly, closes idempotently, and
// owns nothing afterward must raise NO failure — and must have been used once and closed
// exactly twice (first + the idempotent second).
func TestAssertLifecycle_CleanProbePasses(t *gotest.T) {
	t.Parallel()
	probe := &scriptedProbe{ownedAfter: 0}
	if driveLifecycle(t, probe) {
		t.Fatal("a clean probe must NOT raise a failure")
	}
	if got := probe.usedCalls.Load(); got != 1 {
		t.Fatalf("Use must be called exactly once; got %d", got)
	}
	if got := probe.closeCalls.Load(); got != 2 {
		t.Fatalf("Close must be called exactly twice (first + idempotent second); got %d", got)
	}
}

// TestAssertLifecycle_UseErrorIsReported: a probe whose Use leg errors must be reported (the
// "use succeeds on the live object" assertion). Negative control for the clean-pass test.
func TestAssertLifecycle_UseErrorIsReported(t *gotest.T) {
	t.Parallel()
	if !driveLifecycle(t, &scriptedProbe{useErr: errors.New("use failed")}) {
		t.Fatal("AssertLifecycle did not report a failing Use leg")
	}
}

// TestAssertLifecycle_FirstCloseErrorIsReported: a probe whose FIRST Close errors must be
// reported (the "first Close succeeds" assertion).
func TestAssertLifecycle_FirstCloseErrorIsReported(t *gotest.T) {
	t.Parallel()
	if !driveLifecycle(t, &scriptedProbe{firstClose: errors.New("close failed")}) {
		t.Fatal("AssertLifecycle did not report a failing first Close")
	}
}

// TestAssertLifecycle_NonIdempotentSecondCloseIsReported: a probe whose SECOND Close errors
// must be reported — the cardinal double-close invariant (the second Close must be a no-op).
func TestAssertLifecycle_NonIdempotentSecondCloseIsReported(t *gotest.T) {
	t.Parallel()
	if !driveLifecycle(t, &scriptedProbe{secondClose: errors.New("not idempotent")}) {
		t.Fatal("AssertLifecycle did not report a non-idempotent second Close")
	}
}

// TestAssertLifecycle_OrphanResourceIsReported: a probe still owning a resource after
// teardown must be reported (CountOwned()!=0 → orphan leak).
func TestAssertLifecycle_OrphanResourceIsReported(t *gotest.T) {
	t.Parallel()
	if !driveLifecycle(t, &scriptedProbe{ownedAfter: 3}) {
		t.Fatal("AssertLifecycle did not report a probe that still owns resources after teardown")
	}
}

// TestAssertLifecycle_CountErrorIsReported: a probe whose CountOwned errors must be reported
// (the "CountOwned after Close failed" branch).
func TestAssertLifecycle_CountErrorIsReported(t *gotest.T) {
	t.Parallel()
	if !driveLifecycle(t, &scriptedProbe{countErr: errors.New("count failed")}) {
		t.Fatal("AssertLifecycle did not report a CountOwned error")
	}
}

// TestAssertLifecycle_ConstructErrorIsReported: a factory that fails to construct must be
// reported as a construct failure (the first, fatal branch), and the probe legs must NOT run.
func TestAssertLifecycle_ConstructErrorIsReported(t *gotest.T) {
	t.Parallel()
	rep := &recordingReport{}
	harness := testingtest.NewHarness(t)
	factory := func(context.Context, testingpkg.Harness) (testingpkg.LifecycleProbe, func(), error) {
		return nil, nil, errors.New("construct failed")
	}
	testingpkg.AssertLifecycle(context.Background(), harness, rep, factory)
	if !rep.failed.Load() {
		t.Fatal("AssertLifecycle did not report a construct failure")
	}
}
