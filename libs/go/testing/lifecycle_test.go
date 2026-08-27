//go:build lifecycle

package testing_test

import (
	"context"
	"sync"
	"sync/atomic"
	gotest "testing"

	"go.uber.org/goleak"

	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// The full-object-lifecycle dimension (ADR-0020 (c)) for THIS library is special: the
// library IS the home of testing.AssertLifecycle + the LifecycleProbe port. So its
// lifecycle conformance is to drive AssertLifecycle over a real, closeable probe and prove
// the driver enforces the construct -> use -> first Close -> SECOND Close is a no-op ->
// CountOwned()==0 contract. A probe that owns a live goroutine (the "external resource")
// makes the orphan-goroutine half observable: goleak.VerifyNone asserts the probe's
// goroutine was reaped on Close. The probe is tagged `//go:build lifecycle` so this heavy
// double-close/reap drive stays out of the fast unit run.

// resourceProbe is a real testing.LifecycleProbe whose owned resource is a background
// goroutine plus a live-resource counter. Close stops the goroutine exactly once
// (idempotent: the second Close is a no-op) and decrements the counter, so CountOwned()
// reads 0 after teardown — the orphan budget is clean.
type resourceProbe struct {
	mu     sync.Mutex
	closed bool
	live   atomic.Int64
	stop   chan struct{}
	done   chan struct{}
	used   atomic.Bool
}

func newResourceProbe() *resourceProbe {
	p := &resourceProbe{stop: make(chan struct{}), done: make(chan struct{})}
	p.live.Store(1)
	go func() {
		defer close(p.done)
		<-p.stop // block until Close, modeling a held external resource
	}()
	return p
}

// Use exercises the live object once (the "use" leg). Returns nil while the resource is held.
func (p *resourceProbe) Use(_ context.Context) error {
	p.used.Store(true)
	return nil
}

// Close stops the goroutine and decrements the live counter, idempotently: the SECOND call
// is a no-op that returns nil (the double-close invariant AssertLifecycle asserts).
func (p *resourceProbe) Close(_ context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return nil // idempotent no-op
	}
	p.closed = true
	close(p.stop)
	<-p.done // wait for the goroutine to exit so CountOwned() is authoritative
	p.live.Store(0)
	return nil
}

// CountOwned reports the number of live resources; 0 after Close (no orphan).
func (p *resourceProbe) CountOwned(_ context.Context) (int, error) {
	return int(p.live.Load()), nil
}

// TestLifecycle_AssertLifecycleDrivesCleanProbe is the lifecycle conformance for the
// library's OWN AssertLifecycle driver over a well-behaved probe: it must report NO failure
// and leave zero orphans, and the probe's goroutine must be reaped (goleak.VerifyNone).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_AssertLifecycleDrivesCleanProbe(t *gotest.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := testingtest.NewReport(t) // a clean run must NOT fail t
	harness := testingtest.NewHarness(t)
	var probe *resourceProbe
	factory := func(_ context.Context, _ testingpkg.Harness) (testingpkg.LifecycleProbe, func(), error) {
		probe = newResourceProbe()
		return probe, func() {}, nil
	}
	testingpkg.AssertLifecycle(context.Background(), harness, report, factory)

	// After the driver ran, the probe must have been used and fully closed (no orphan).
	if probe == nil {
		t.Fatal("factory was never invoked")
	}
	if !probe.used.Load() {
		t.Fatal("AssertLifecycle did not invoke the use leg")
	}
	owned, err := probe.CountOwned(context.Background())
	if err != nil {
		t.Fatalf("CountOwned: %v", err)
	}
	if owned != 0 {
		t.Fatalf("probe still owns %d resource(s) after AssertLifecycle — orphan leak", owned)
	}
}

// The negative-controls for AssertLifecycle's report branches (use error, first/second Close
// error, orphan resource, CountOwned error, construct error) plus the shared recordingReport
// live in the ALWAYS-ON (untagged) assertlifecycle_test.go — so the driver's branches are
// covered in the fast unit/mutation run, not only behind the `lifecycle` build tag. This file
// owns only the GOROUTINE-owning probe (the orphan-goroutine half, asserted by goleak).
