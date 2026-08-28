//go:build integration

package dependencies_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// Host-leveraging integration (ADR-0020 dimension (d)): dependencies is a stdlib-only leaf, so its
// REAL substrate is the host itself — the operating-system wall clock and the kernel CSPRNG
// (crypto/rand). The fast unit lane drives the fakes and avoids real waiting; THIS lane proves the
// same contract holds against the live host: the system clock actually advances in real time, the
// real After timer fires on the real timeline, and the kernel entropy source produces
// high-quality (non-degenerate) bytes. The shared conformance suite is the contract; here it runs
// over the real, host-backed Set so "fake ≡ real" is proven against the real substrate.

// TestIntegration_RealPortSuiteOverHost runs the single shared port-substitutability suite over
// the REAL host-backed adapters — the same suite the fakes pass — proving the real substrate
// honors every port property (§4 conformance, real binding).
func TestIntegration_RealPortSuiteOverHost(t *testing.T) {
	dependenciestest.RunPortSuite(t, func() dependencies.Set {
		return dependencies.Resolve(dependencies.Set{})
	})
}

// TestIntegration_RealClockAdvancesInRealTime asserts the system clock measures real elapsed wall
// time: a real sleep between two Now() reads shows up as a real, monotonic delta. This is the
// behavior the fake deliberately suppresses (frozen until Advance), so it can only be proven on
// the real substrate.
func TestIntegration_RealClockAdvancesInRealTime(t *testing.T) {
	c := dependencies.RealClock()
	a := c.Now()
	time.Sleep(20 * time.Millisecond)
	b := c.Now()
	delta := b.Sub(a)
	if delta < 10*time.Millisecond {
		t.Fatalf("real clock did not advance with wall time: delta=%v (want >= ~20ms)", delta)
	}
	if delta > time.Second {
		t.Fatalf("real clock delta implausibly large: %v", delta)
	}
}

// TestIntegration_RealClockAfterFiresOnRealTimeline asserts the real After timer fires on the real
// OS timeline (no fake Advance), and that a real ctx cancellation reaps it cleanly — the live
// behavior of the cancellation contract on the host.
func TestIntegration_RealClockAfterFiresOnRealTimeline(t *testing.T) {
	c := dependencies.RealClock()

	fired := c.After(context.Background(), 15*time.Millisecond)
	select {
	case <-fired:
	case <-time.After(2 * time.Second):
		t.Fatal("real After did not fire on the real timeline within 2s")
	}

	ctx, cancel := context.WithCancel(context.Background())
	canceled := c.After(ctx, time.Hour)
	cancel()
	select {
	case v, ok := <-canceled:
		if ok {
			t.Fatalf("canceled real After delivered %v; must be un-sent", v)
		}
	case <-time.After(200 * time.Millisecond):
		// Acceptable: never sent.
	}
}

// TestIntegration_RealRandomIsNonDegenerate asserts the kernel CSPRNG produces high-quality bytes
// on the real host: a large read is not all-zero, not constant, and spans most byte values. A fake
// seeded stream could be made to look like this, but here it is the LIVE crypto/rand source — the
// real-substrate entropy guarantee the contract rests on (§2 RandomSource "cryptographically
// suitable").
func TestIntegration_RealRandomIsNonDegenerate(t *testing.T) {
	r := dependencies.RealRandom(nil)
	const n = 4096
	p := make([]byte, n)
	if _, err := r.Read(p); err != nil {
		t.Fatalf("real entropy Read error: %v", err)
	}
	var seen [256]bool
	distinct := 0
	for _, x := range p {
		if !seen[x] {
			seen[x] = true
			distinct++
		}
	}
	// Over 4096 cryptographically-random bytes, essentially all 256 values appear; require a
	// generous floor so the test is robust but still catches a degenerate (constant/zero) source.
	if distinct < 200 {
		t.Fatalf("real entropy looks degenerate: only %d/256 distinct byte values in %d bytes", distinct, n)
	}
}
