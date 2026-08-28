//go:build lifecycle

package dependencies_test

import (
	"context"
	"runtime"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// dependencies owns no closeable OS handle (it is a pure port library), so the full-object
// lifecycle conformance (ADR-0020 dimension (c)) is expressed on the one piece of the library
// that DOES have a construct→use→teardown lifecycle with an external-ish resource: the ctx-bridge
// GOROUTINE that Clock.After spawns to honor cancellation. "Construct" = register an After timer;
// "use" = it is pending; "teardown" = cancel the ctx; the invariant under test is that the
// bridge goroutine is REAPED (the leaf analog of "CountOwned()==0, no orphan") and that a SECOND
// cancel is a harmless no-op (the double-close-is-idempotent analog). goleak.VerifyNone owns the
// orphan-goroutine half.

// TestLifecycle_RealClockAfterReapsBridgeOnCancel asserts the REAL clock's After bridge goroutine
// terminates when its ctx is canceled, leaving no orphan (dimension (c) reap, on the real adapter).
func TestLifecycle_RealClockAfterReapsBridgeOnCancel(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of the lifecycle assertion

	c := dependencies.RealClock()
	ctx, cancel := context.WithCancel(context.Background())

	// Construct + use: register a far-future deadline that cannot fire on its own in the window.
	ch := c.After(ctx, time.Hour)

	// Teardown: cancel. The bridge goroutine must observe ctx.Done and exit; the channel stays
	// un-sent (the cancellation contract, §2 Clock).
	cancel()
	// A SECOND cancel is an idempotent no-op (the double-close analog).
	cancel()

	select {
	case v, ok := <-ch:
		if ok {
			t.Fatalf("canceled After delivered %v; the channel must be un-sent", v)
		}
	case <-time.After(time.Second):
		// Acceptable: never sent. goleak below proves the bridge goroutine was reaped.
	}
	waitForGoroutineQuiescence()
}

// TestLifecycle_FakeClockAfterReapsBridgeOnCancel asserts the same reap invariant on the FAKE
// adapter — the construct→use→double-cancel→reap conformance holds identically for fake and real
// (the two-binding lifecycle, ADR-0020 dimension (c)).
func TestLifecycle_FakeClockAfterReapsBridgeOnCancel(t *testing.T) {
	defer goleak.VerifyNone(t)

	c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
	ctx, cancel := context.WithCancel(context.Background())

	ch := c.After(ctx, time.Hour)
	cancel()
	cancel() // idempotent second teardown

	// Even crossing the deadline after cancel must not deliver a tick (cancel wins).
	c.Advance(2 * time.Hour)
	select {
	case v, ok := <-ch:
		if ok {
			t.Fatalf("canceled fake After delivered %v; must be un-sent", v)
		}
	case <-time.After(time.Second):
	}
	waitForGoroutineQuiescence()
}

// TestLifecycle_FakeClockAfterReapsBridgeOnFire asserts the bridge goroutine ALSO terminates on
// the happy path: when Advance fires the timer, the bridge forwards the tick and then exits — no
// goroutine is left parked on a channel after the resource has been consumed.
func TestLifecycle_FakeClockAfterReapsBridgeOnFire(t *testing.T) {
	defer goleak.VerifyNone(t)

	c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	ch := c.After(ctx, 10*time.Second)
	c.Advance(10 * time.Second) // cross the deadline → the timer fires
	select {
	case <-ch:
		// fired and forwarded; the bridge goroutine must now exit.
	case <-time.After(time.Second):
		t.Fatal("After did not fire after Advance crossed the deadline")
	}
	waitForGoroutineQuiescence()
}

// TestLifecycle_ResolveIsCopyOnWrite is the value-type half of the lifecycle invariant: Resolve
// NEVER mutates the Set it was handed and re-resolving is idempotent (the leaf analog of "Close
// is a no-op, the receiver is untouched"). A regression that resolved in place would be the
// value-type equivalent of an orphaned/mutated resource.
func TestLifecycle_ResolveIsCopyOnWrite(t *testing.T) {
	defer goleak.VerifyNone(t)

	base := dependencies.Set{}
	first := dependencies.Resolve(base)
	if base.Clock != nil || base.Random != nil || base.Sink != nil {
		t.Fatal("Resolve mutated its by-value argument (not copy-on-write)")
	}
	second := dependencies.Resolve(first)
	if first != second {
		t.Fatalf("re-resolve not idempotent: %+v != %+v", first, second)
	}
}

// waitForGoroutineQuiescence yields a few times so a just-canceled bridge goroutine has scheduled
// its exit before goleak.VerifyNone samples the goroutine set. goleak retries internally, so this
// only tightens the window; it never masks a true leak (a parked goroutine never exits).
func waitForGoroutineQuiescence() {
	for range 10 {
		runtime.Gosched()
	}
}
