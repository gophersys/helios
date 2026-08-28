package testing

import (
	"context"
)

// LifecycleProbe is the port a subject-under-test exposes so the lifecycle-conformance
// driver can verify the construct→use→double-close→teardown contract WITHOUT importing
// the subject's concrete type. It is the generalisation of the workspaceprovider
// CountOwned/reap pattern (ADR-0020 dimension (c)): a handle that owns external resources
// implements this port so AssertLifecycle can prove idempotent Close and zero orphans on
// any binding (fake or real substrate).
//
// Consumer-defined and ≤5 methods (10 §9): the probe is the shape of what the lifecycle
// assertion needs, not a mirror of the implementation.
type LifecycleProbe interface {
	// Use exercises the subject once after construction (the "use" leg). A nil error means
	// the live object behaves; the driver calls it before the first Close.
	Use(ctx context.Context) error
	// Close releases the subject's resources. It MUST be idempotent: the SECOND call is a
	// no-op that returns nil (the "double-close is a no-op" invariant). The driver calls it
	// twice and asserts the second is clean.
	Close(ctx context.Context) error
	// CountOwned returns the number of external resources the subject still owns. After
	// teardown the driver asserts this is zero — no orphan container/cluster/handle.
	CountOwned(ctx context.Context) (int, error)
}

// LifecycleFactory builds a fresh LifecycleProbe for one AssertLifecycle run, the single seam
// a pattern library implements per binding (fake + each real substrate). Called once per run
// for isolation; the returned teardown is invoked LIFO after the assertions, even on failure.
type LifecycleFactory func(ctx context.Context, h Harness) (probe LifecycleProbe, teardown func(), err error)

// AssertLifecycle drives the full object lifecycle over a freshly built subject and reports
// any violation to the Report sink (this package never imports stdlib testing — assertion is
// delegated to Report so suites run inside shipped binaries, 10 §6.1). It asserts, in order:
//
//  1. construct succeeds (factory returns a probe + teardown);
//  2. use succeeds on the live object;
//  3. the FIRST Close succeeds;
//  4. the SECOND Close is an idempotent no-op (returns nil) — the double-close invariant;
//  5. after teardown, CountOwned() == 0 — no orphan resources.
//
// The goleak/orphan-goroutine half of dimension (c) is asserted by the caller's package-level
// goleak.VerifyTestMain / defer goleak.VerifyNone(t); this driver owns the resource half.
func AssertLifecycle(ctx context.Context, h Harness, report Report, factory LifecycleFactory) {
	probe, teardown, err := factory(ctx, h)
	if err != nil {
		report.Fatalf("AssertLifecycle: construct failed: %v", err)
		return
	}
	if teardown != nil {
		h.Cleanup(teardown)
	}

	if err := probe.Use(ctx); err != nil {
		report.Errorf("AssertLifecycle: use on the live object failed: %v", err)
	}

	if err := probe.Close(ctx); err != nil {
		report.Errorf("AssertLifecycle: first Close returned an error: %v", err)
	}

	// The cardinal lifecycle invariant: a second Close is a no-op, never an error or a panic.
	if err := probe.Close(ctx); err != nil {
		report.Errorf("AssertLifecycle: second Close was NOT idempotent (returned %v) — double-close must be a no-op", err)
	}

	owned, err := probe.CountOwned(ctx)
	if err != nil {
		report.Errorf("AssertLifecycle: CountOwned after Close failed: %v", err)
		return
	}
	if owned != 0 {
		report.Errorf("AssertLifecycle: %d resource(s) still owned after teardown — orphan leak (want 0)", owned)
	}
}
