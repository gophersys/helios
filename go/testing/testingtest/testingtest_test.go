// Tests for package testingtest — the universal fakes (FakeClock, FakeRandomSource)
// and the *testing.T adapters (NewReport, NewHarness, AssertResult). Authored FIRST
// from the frozen contract (docs/architecture/contracts/testing.md §3), then
// implemented until green (TDD discipline, ADR-0016).
package testingtest_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// ── FakeClock ─────────────────────────────────────────────────────────────────.

// FakeClock implements dependencies.Clock exactly (compile-time, mirrors the
// contract's `var _` assertion).
func TestFakeClock_ImplementsClock(t *testing.T) {
	t.Parallel()
	var _ dependencies.Clock = (*testingtest.FakeClock)(nil)
	var _ testingpkg.Clock = (*testingtest.FakeClock)(nil)
}

// Zero start (time.Time{}) → the Unix epoch (contract §3).
func TestFakeClock_ZeroStartIsUnixEpoch(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Time{})
	if got := c.Now(); !got.Equal(time.Unix(0, 0).UTC()) {
		t.Fatalf("zero-start FakeClock should be Unix epoch; got %v", got)
	}
}

// Now reflects the start instant and never self-advances (virtual time).
func TestFakeClock_NowNeverSelfAdvances(t *testing.T) {
	t.Parallel()
	start := time.Date(2026, 6, 12, 12, 0, 0, 0, time.UTC)
	c := testingtest.NewFakeClock(start)
	first := c.Now()
	time.Sleep(5 * time.Millisecond) // wall time passes…
	second := c.Now()
	if !first.Equal(start) || !second.Equal(start) {
		t.Fatalf("virtual clock advanced on its own: %v then %v (start %v)", first, second, start)
	}
}

// Advance moves virtual time by exactly d.
func TestFakeClock_AdvanceMovesNow(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	c.Advance(90 * time.Second)
	if got := c.Now(); !got.Equal(time.Unix(90, 0).UTC()) {
		t.Fatalf("after Advance(90s) Now should be +90s; got %v", got)
	}
}

// After does NOT fire until Advance crosses its deadline (contract §3, rationale 5).
func TestFakeClock_AfterFiresOnlyOnAdvance(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	ch := c.After(context.Background(), 30*time.Second)
	select {
	case <-ch:
		t.Fatal("After fired before any Advance; virtual time must not self-advance")
	default:
	}
	c.Advance(29 * time.Second)
	select {
	case <-ch:
		t.Fatal("After fired before its deadline was crossed")
	default:
	}
	c.Advance(1 * time.Second) // now total 30s — crosses the deadline
	select {
	case fired := <-ch:
		if !fired.Equal(time.Unix(30, 0).UTC()) {
			t.Fatalf("After delivered the wrong instant: %v", fired)
		}
	case <-time.After(time.Second):
		t.Fatal("After did not fire after Advance crossed its deadline")
	}
}

// A non-positive duration is already-due: After delivers immediately at the
// deadline instant without any Advance (a real timer fires "at or after").
func TestFakeClock_AfterNonPositiveFiresImmediately(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Unix(100, 0).UTC())
	for _, d := range []time.Duration{0, -time.Second} {
		ch := c.After(context.Background(), d)
		select {
		case fired := <-ch:
			if !fired.Equal(time.Unix(100, 0).UTC().Add(d)) {
				t.Fatalf("After(%v) delivered %v; want the deadline instant", d, fired)
			}
		case <-time.After(time.Second):
			t.Fatalf("After(%v) did not fire immediately", d)
		}
	}
}

// Advance releases all crossed After channels in deadline order before returning
// (contract §3 concurrency note).
func TestFakeClock_AdvanceReleasesInDeadlineOrder(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	ch10 := c.After(context.Background(), 10*time.Second)
	ch20 := c.After(context.Background(), 20*time.Second)
	ch30 := c.After(context.Background(), 30*time.Second)
	c.Advance(25 * time.Second) // crosses 10 and 20, not 30; returns after releasing
	// 10 and 20 must be ready immediately (released before Advance returned).
	for i, ch := range []<-chan time.Time{ch10, ch20} {
		select {
		case <-ch:
		default:
			t.Fatalf("channel %d not released after Advance crossed its deadline", i)
		}
	}
	select {
	case <-ch30:
		t.Fatal("ch30 fired though Advance did not reach 30s")
	default:
	}
}

// After honors ctx cancellation: a canceled ctx means the channel is never sent
// on (mirrors dependencies.Clock.After contract).
func TestFakeClock_AfterRespectsCancellation(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	ctx, cancel := context.WithCancel(context.Background())
	ch := c.After(ctx, 10*time.Second)
	cancel()
	c.Advance(20 * time.Second) // crosses the deadline, but ctx is canceled
	select {
	case v, ok := <-ch:
		if ok {
			t.Fatalf("canceled After delivered %v; must not send", v)
		}
	case <-time.After(200 * time.Millisecond):
		// Acceptable: never sent.
	}
}

// FakeClock is goroutine-safe: concurrent Now/Advance must not race (run with -race).
func TestFakeClock_ConcurrentSafe(t *testing.T) {
	t.Parallel()
	c := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				_ = c.Now()
				c.Advance(time.Millisecond)
			}
		}()
	}
	wg.Wait()
}

// ── FakeRandomSource ──────────────────────────────────────────────────────────.

func TestFakeRandomSource_ImplementsRandomSource(t *testing.T) {
	t.Parallel()
	var _ dependencies.RandomSource = (*testingtest.FakeRandomSource)(nil)
	var _ testingpkg.RandomSource = (*testingtest.FakeRandomSource)(nil)
}

// Read fills p completely (io.ReadFull-shaped, mirrors dependencies contract).
func TestFakeRandomSource_FullRead(t *testing.T) {
	t.Parallel()
	r := testingtest.NewFakeRandomSource(1)
	for _, size := range []int{1, 7, 32, 257, 4096} {
		p := make([]byte, size)
		n, err := r.Read(p)
		if err != nil {
			t.Fatalf("Read(%d): %v", size, err)
		}
		if n != size {
			t.Fatalf("Read(%d) short: n=%d", size, n)
		}
	}
}

// Identical seed + identical call sequence ⇒ identical bytes (frozen invariant, OQ6).
func TestFakeRandomSource_DeterministicFromSeed(t *testing.T) {
	t.Parallel()
	read := func() []byte {
		r := testingtest.NewFakeRandomSource(7)
		out := make([]byte, 0, 128)
		for i := 0; i < 4; i++ {
			p := make([]byte, 32)
			if _, err := r.Read(p); err != nil {
				t.Fatalf("Read: %v", err)
			}
			out = append(out, p...)
		}
		return out
	}
	a, b := read(), read()
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("same seed/sequence diverged at byte %d", i)
		}
	}
}

func TestFakeRandomSource_DifferentSeedsDiffer(t *testing.T) {
	t.Parallel()
	read := func(seed uint64) []byte {
		r := testingtest.NewFakeRandomSource(seed)
		p := make([]byte, 64)
		if _, err := r.Read(p); err != nil {
			t.Fatalf("Read: %v", err)
		}
		return p
	}
	a := read(1)
	b := read(2)
	same := true
	for i := range a {
		if a[i] != b[i] {
			same = false
			break
		}
	}
	if same {
		t.Fatal("different seeds produced identical streams")
	}
}

// Read is serialized / goroutine-safe (run with -race).
func TestFakeRandomSource_ConcurrentSafe(t *testing.T) {
	t.Parallel()
	r := testingtest.NewFakeRandomSource(3)
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			p := make([]byte, 16)
			for j := 0; j < 200; j++ {
				if _, err := r.Read(p); err != nil {
					t.Errorf("Read: %v", err)
					return
				}
			}
		}()
	}
	wg.Wait()
}

// ── *testing.T adapters ───────────────────────────────────────────────────────.

// NewReport adapts *testing.T to testing.Report. On a passing case, no failure is
// recorded on a child T. We verify it satisfies the interface and that Skipf does
// not fail the parent (skips don't fail).
func TestNewReport_SatisfiesReport(t *testing.T) {
	t.Parallel()
	// NewReport's return type is testingpkg.Report by signature; binding it proves
	// the adapter constructs without panic. The interface satisfaction is in the
	// signature, so an explicit typed var would be a redundant QF1011 declaration.
	_ = testingtest.NewReport(t)
}

// NewReport.Skipf maps to t.Skipf — the subtest is skipped, not failed, and the
// body after Skipf is unreachable (t.Skipf calls runtime.Goexit). t.Run returning
// true (not-failed) and the unreachable Fatal not firing is the observable.
//
//nolint:tparallel // the subtest's result (ok) is inspected synchronously right after t.Run, so it MUST run serially; a parallel subtest would not have finished when ok is read.
func TestNewReport_SkipfSkips(t *testing.T) {
	t.Parallel()
	ok := t.Run("inner", func(st *testing.T) {
		rep := testingtest.NewReport(st)
		rep.Skipf("skip %d", 1)
		st.Fatal("unreachable: Skipf must halt the test body")
	})
	if !ok {
		t.Fatal("Skipf should skip (not fail) the wrapped *testing.T")
	}
}

// The fail/panic routing of AssertResult (failing/panicking cases must fail t) is
// verified against the pure resultReport decision core in the internal test file
// (assertresult_internal_test.go): a real failing subtest unavoidably fails its
// parent, so the decision is unit-tested directly rather than through a live T.

// NewHarness builds a standalone testing.Harness; capabilities default to present.
func TestNewHarness_Defaults(t *testing.T) {
	t.Parallel()
	h := testingtest.NewHarness(t)
	if h.Clock() == nil {
		t.Fatal("NewHarness Clock is nil")
	}
	if h.RandomSource() == nil {
		t.Fatal("NewHarness RandomSource is nil")
	}
	if h.Context() == nil {
		t.Fatal("NewHarness Context is nil")
	}
	if !h.Has("anything") {
		t.Fatal("capabilities should default to present")
	}
}

// WithEpoch anchors the harness clock; WithSeed seeds its RandomSource.
func TestNewHarness_WithEpochAndSeed(t *testing.T) {
	t.Parallel()
	epoch := time.Date(2021, 5, 5, 0, 0, 0, 0, time.UTC)
	h := testingtest.NewHarness(t, testingtest.WithEpoch(epoch), testingtest.WithSeed(11))
	if got := h.Clock().Now(); !got.Equal(epoch) {
		t.Fatalf("WithEpoch not honored: want %v got %v", epoch, got)
	}
	// Same seed via the option must match a directly-seeded FakeRandomSource.
	want := make([]byte, 32)
	if _, err := testingtest.NewFakeRandomSource(11).Read(want); err != nil {
		t.Fatalf("seed reference read: %v", err)
	}
	got := make([]byte, 32)
	if _, err := h.RandomSource().Read(got); err != nil {
		t.Fatalf("harness random read: %v", err)
	}
	for i := range want {
		if want[i] != got[i] {
			t.Fatalf("WithSeed(11) stream diverged from NewFakeRandomSource(11) at %d", i)
		}
	}
}

// WithoutCapability removes a capability so Has reports false for it (the gate seam).
func TestNewHarness_WithoutCapability(t *testing.T) {
	t.Parallel()
	h := testingtest.NewHarness(t, testingtest.WithoutCapability("docker"))
	if h.Has("docker") {
		t.Fatal("WithoutCapability(docker) should make Has(docker) == false")
	}
	if !h.Has("other") {
		t.Fatal("only the named capability should be removed")
	}
}

// Harness.Cleanup registered via NewHarness runs through t.Cleanup (LIFO). We can
// only assert it is callable here; LIFO order is proven in the suite path.
func TestNewHarness_CleanupCallable(t *testing.T) {
	t.Parallel()
	h := testingtest.NewHarness(t)
	h.Cleanup(func() {}) // must not panic
}

// AssertResult: a Result with only passes/skips must NOT fail t (skips don't fail).
//
//nolint:tparallel // the subtest's result (ok) is inspected synchronously right after t.Run, so it MUST run serially; a parallel subtest would not have finished when ok is read.
func TestAssertResult_PassAndSkipDoNotFail(t *testing.T) {
	t.Parallel()
	res := testingpkg.Result{
		Suite:   "x",
		Passed:  2,
		Skipped: 1,
		Cases: []testingpkg.CaseResult{
			{Name: "a", Outcome: testingpkg.Pass},
			{Name: "b", Outcome: testingpkg.Pass},
			{Name: "c", Outcome: testingpkg.Skip},
		},
	}
	// Run in a subtest and confirm it did not fail.
	ok := t.Run("inner", func(st *testing.T) {
		testingtest.AssertResult(st, res)
	})
	if !ok {
		t.Fatal("AssertResult failed t on a pass+skip-only Result")
	}
}
