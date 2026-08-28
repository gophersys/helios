// Usage tests — exercise the §5 call sites end-to-end so the surface composes the
// way the contract's worked examples claim. Authored FIRST (TDD discipline).
//
// We use dependencies.Clock as the port under test (S = dependencies.Clock): the
// FakeClock is the "fake" subject and a host-backed RealClock is the "adapter"
// subject, and ONE Suite proves both satisfy the same black-box cases. This is the
// fakes-drift closure (08 §2) reduced to the two universal ports testing owns.
package testingtest_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// clockSuite is the ONE exported-style Suite a pattern library would author: a set
// of black-box assertions over any dependencies.Clock. Run twice (fake + adapter),
// passing both is the substitutability proof.
func clockSuite() testingpkg.Suite[dependencies.Clock] {
	cases := []testingpkg.Case[dependencies.Clock]{
		{
			Name: "NowIsNonDecreasing",
			Run: func(c dependencies.Clock, h testingpkg.Harness, report testingpkg.Report) {
				prev := c.Now()
				for i := 0; i < 50; i++ {
					now := c.Now()
					if now.Before(prev) {
						report.Errorf("Now went backward: %v then %v", prev, now)
						return
					}
					prev = now
				}
			},
		},
		{
			Name: "AfterRespectsCancellation",
			Run: func(c dependencies.Clock, h testingpkg.Harness, report testingpkg.Report) {
				ctx, cancel := context.WithCancel(h.Context())
				ch := c.After(ctx, time.Hour)
				cancel()
				select {
				case v, ok := <-ch:
					if ok {
						report.Errorf("canceled After delivered %v", v)
					}
				case <-time.After(100 * time.Millisecond):
					// acceptable: never sent
				}
			},
		},
	}
	return testingpkg.Suite[dependencies.Clock]{
		Name:  "dependencies.Clock",
		Cases: testingtest.CaseSeq(cases...),
	}
}

// §5 call site 1: a pattern library closes the fakes-drift loop — the SAME Suite
// runs over BOTH the fake and the real adapter; passing both is the proof.
func TestClock_FakeAndAdapter_Conform(t *testing.T) {
	t.Parallel()
	epoch := time.Date(2026, 6, 12, 0, 0, 0, 0, time.UTC)
	r, err := testingpkg.New(testingpkg.Config{Seed: 1}, testingpkg.Deps{Epoch: epoch})
	if err != nil {
		t.Fatal(err)
	}

	suite := clockSuite()

	fake := func(ctx context.Context, h testingpkg.Harness) (dependencies.Clock, error) {
		return testingtest.NewFakeClock(epoch), nil
	}
	adapter := func(ctx context.Context, h testingpkg.Harness) (dependencies.Clock, error) {
		return dependencies.RealClock(), nil
	}

	testingtest.AssertResult(t, testingpkg.RunSuite(r, suite, fake))
	testingtest.AssertResult(t, testingpkg.RunSuite(r, suite, adapter))
}

// §5 in-library: driving virtual time in a consumer's own retry test — Advance
// fires the timer with no wall-clock sleep.
func TestRetry_FiresOnVirtualSchedule(t *testing.T) {
	t.Parallel()
	epoch := time.Unix(0, 0).UTC()
	r, err := testingpkg.New(testingpkg.Config{Seed: 7}, testingpkg.Deps{Epoch: epoch})
	if err != nil {
		t.Fatal(err)
	}
	fakes := r.Fakes()

	// A subject that schedules work 30s out via the injected Clock.
	ch := fakes.Clock.After(context.Background(), 30*time.Second)
	select {
	case <-ch:
		t.Fatal("timer fired before Advance")
	default:
	}
	// The §5 affordance: recover the concrete *FakeClock from the vended Clock port
	// to drive virtual time. Comma-ok form (not a bare assertion) so a wrong
	// underlying type fails the test rather than panicking (errcheck
	// check-type-assertions).
	fc, ok := fakes.Clock.(*testingtest.FakeClock)
	if !ok {
		t.Fatalf("Runner.Fakes().Clock should be a *testingtest.FakeClock; got %T", fakes.Clock)
	}
	fc.Advance(30 * time.Second)
	select {
	case <-ch:
		// fired on the virtual schedule
	case <-time.After(time.Second):
		t.Fatal("timer did not fire after Advance")
	}
}

// AssertResult bridges a real RunSuite Result back to go test in one line (the
// adapter the contract promises). A clean run must keep t green.
func TestAssertResult_RoundTrip(t *testing.T) {
	t.Parallel()
	r, err := testingpkg.New(testingpkg.Config{}, testingpkg.Deps{})
	if err != nil {
		t.Fatal(err)
	}
	suite := clockSuite()
	fake := func(ctx context.Context, h testingpkg.Harness) (dependencies.Clock, error) {
		return testingtest.NewFakeClock(time.Unix(0, 0).UTC()), nil
	}
	res := testingpkg.RunSuite(r, suite, fake)
	if res.Failed != 0 {
		t.Fatalf("fake clock should conform; %+v", res.Cases)
	}
	testingtest.AssertResult(t, res)
}
