package dependenciestest_test

import (
	"bytes"
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// ---- Fakes satisfy the production ports (§3).

func TestFakesSatisfyPorts(t *testing.T) {
	t.Parallel()
	var _ dependencies.Clock = dependenciestest.NewClock(time.Unix(0, 0).UTC())
	var _ dependencies.RandomSource = dependenciestest.NewRandom([32]byte{})
	var _ dependencies.Sink = &dependenciestest.RecordingSink{}
}

// ---- Clock fake (§3).

// Now is frozen until Advance is called; it starts at the chosen epoch.
func TestFakeClockFrozenUntilAdvance(t *testing.T) {
	t.Parallel()
	start := time.Date(2026, 6, 12, 0, 0, 0, 0, time.UTC)
	c := dependenciestest.NewClock(start)
	if !c.Now().Equal(start) {
		t.Fatalf("NewClock.Now() = %v, want epoch %v", c.Now(), start)
	}
	// Frozen: repeated Now without Advance returns the same instant.
	if !c.Now().Equal(c.Now()) {
		t.Fatal("fake Clock.Now must be frozen between Advance calls")
	}
	c.Advance(90 * time.Minute)
	want := start.Add(90 * time.Minute)
	if !c.Now().Equal(want) {
		t.Fatalf("after Advance, Now() = %v, want %v", c.Now(), want)
	}
}

// Now is non-decreasing across Advance calls (monotonic property, §4).
func TestFakeClockNonDecreasing(t *testing.T) {
	t.Parallel()
	c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
	prev := c.Now()
	for range 5 {
		c.Advance(time.Second)
		now := c.Now()
		if now.Before(prev) {
			t.Fatalf("Now went backward: %v then %v", prev, now)
		}
		prev = now
	}
}

// After fires when Advance crosses the deadline (§3, §4).
func TestFakeClockAfterFiresOnAdvance(t *testing.T) {
	t.Parallel()
	c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
	ch := c.After(context.Background(), 10*time.Second)
	select {
	case <-ch:
		t.Fatal("After fired before its deadline was crossed")
	default:
	}
	c.Advance(9 * time.Second)
	select {
	case <-ch:
		t.Fatal("After fired before the full duration elapsed")
	default:
	}
	c.Advance(1 * time.Second) // now at the deadline
	select {
	case <-ch:
		// fired
	case <-time.After(time.Second):
		t.Fatal("After did not fire after Advance crossed the deadline")
	}
}

// Advance releases EVERY crossed After channel in deadline order before returning,
// even when the timers were registered out of insertion order (§3 "fire ... in deadline
// order"; dependenciestest.go:24 "After channels fire when Advance crosses their
// deadline"). This mirrors the sibling testingtest.TestFakeClock_AdvanceReleasesInDeadlineOrder
// so the dependenciestest twin proves the same multi-timer guarantee.
func TestFakeClockAdvanceReleasesInDeadlineOrder(t *testing.T) {
	t.Parallel()
	start := time.Unix(0, 0).UTC()
	c := dependenciestest.NewClock(start)
	// Register OUT of insertion order relative to their deadlines (30, 10, 20) so a
	// straight insertion-order walk could not accidentally produce deadline order.
	ch30 := c.After(context.Background(), 30*time.Second)
	ch10 := c.After(context.Background(), 10*time.Second)
	ch20 := c.After(context.Background(), 20*time.Second)

	c.Advance(25 * time.Second) // crosses 10 and 20, not 30; returns after releasing both.

	// Both crossed channels must be ready immediately (released before Advance returned),
	// and each must carry ITS OWN deadline — the value that makes "deadline order"
	// observable on a per-timer basis, not c.now.
	for _, tc := range []struct {
		name string
		ch   <-chan time.Time
		d    time.Duration
	}{
		{"ch10", ch10, 10 * time.Second},
		{"ch20", ch20, 20 * time.Second},
	} {
		select {
		case got := <-tc.ch:
			if want := start.Add(tc.d); !got.Equal(want) {
				t.Fatalf("%s delivered %v, want its deadline %v", tc.name, got, want)
			}
		default:
			t.Fatalf("%s not released after Advance crossed its deadline", tc.name)
		}
	}

	// The uncrossed timer must NOT have fired.
	select {
	case v := <-ch30:
		t.Fatalf("ch30 fired with %v though Advance did not reach 30s", v)
	default:
	}
}

// After honors ctx cancellation: a canceled ctx leaves the channel un-sent (§4).
func TestFakeClockAfterRespectsCancellation(t *testing.T) {
	t.Parallel()
	c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
	ctx, cancel := context.WithCancel(context.Background())
	ch := c.After(ctx, 10*time.Second)
	cancel()
	// Even after crossing the deadline, a canceled timer must not deliver a tick.
	c.Advance(20 * time.Second)
	select {
	case v, ok := <-ch:
		if ok {
			t.Fatalf("canceled After delivered %v; must be un-sent", v)
		}
	case <-time.After(200 * time.Millisecond):
		// Acceptable: never sent.
	}
}

// ---- Random fake (§3).

// Random is deterministic and seedable: same seed -> same byte stream.
func TestFakeRandomDeterministic(t *testing.T) {
	t.Parallel()
	seed := [32]byte{1, 2, 3}
	a := dependenciestest.NewRandom(seed)
	b := dependenciestest.NewRandom(seed)
	pa := make([]byte, 64)
	pb := make([]byte, 64)
	if _, err := a.Read(pa); err != nil {
		t.Fatal(err)
	}
	if _, err := b.Read(pb); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(pa, pb) {
		t.Fatal("same seed must produce the same byte stream")
	}
}

func TestFakeRandomDifferentSeeds(t *testing.T) {
	t.Parallel()
	a := dependenciestest.NewRandom([32]byte{1})
	b := dependenciestest.NewRandom([32]byte{2})
	pa := make([]byte, 64)
	pb := make([]byte, 64)
	if _, err := a.Read(pa); err != nil {
		t.Fatal(err)
	}
	if _, err := b.Read(pb); err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(pa, pb) {
		t.Fatal("different seeds should (overwhelmingly) produce different streams")
	}
}

// Random fills the buffer completely (full-read property, §4).
func TestFakeRandomFullRead(t *testing.T) {
	t.Parallel()
	r := dependenciestest.NewRandom([32]byte{})
	p := make([]byte, 100)
	n, err := r.Read(p)
	if err != nil {
		t.Fatalf("Read error: %v", err)
	}
	if n != len(p) {
		t.Fatalf("short read: got %d want %d", n, len(p))
	}
}

// ---- RecordingSink fake (§3).

func TestRecordingSinkCaptures(t *testing.T) {
	t.Parallel()
	var s dependenciestest.RecordingSink
	if err := s.Emit(context.Background(), "a"); err != nil {
		t.Fatal(err)
	}
	if err := s.Emit(context.Background(), 42); err != nil {
		t.Fatal(err)
	}
	recs := s.Records()
	if len(recs) != 2 {
		t.Fatalf("Records() len = %d, want 2", len(recs))
	}
	if recs[0] != "a" || recs[1] != 42 {
		t.Fatalf("Records() = %v, want [a 42]", recs)
	}
}

// Records returns a snapshot copy: mutating it does not affect the sink.
func TestRecordingSinkRecordsIsSnapshot(t *testing.T) {
	t.Parallel()
	var s dependenciestest.RecordingSink
	if err := s.Emit(context.Background(), "x"); err != nil {
		t.Fatal(err)
	}
	recs := s.Records()
	recs[0] = "mutated"
	if got := s.Records(); got[0] != "x" {
		t.Fatalf("Records() must return a snapshot copy; sink mutated to %v", got[0])
	}
}

// Records on an empty sink returns an empty (or nil) slice, never panics.
func TestRecordingSinkEmpty(t *testing.T) {
	t.Parallel()
	var s dependenciestest.RecordingSink
	if got := s.Records(); len(got) != 0 {
		t.Fatalf("empty sink Records() len = %d, want 0", len(got))
	}
}

// ---- Fakes() one-call helper (§3).

func TestFakesHelper(t *testing.T) {
	t.Parallel()
	t.Run("Populated", testFakesPopulated)
	t.Run("SameObjects", testFakesSameObjects)
	t.Run("PinnedAndDrivable", testFakesPinnedAndDrivable)
	t.Run("SinkCapturesViaSet", testFakesSinkCapturesViaSet)
}

// testFakesPopulated checks Fakes() returns a complete, valid Set plus non-nil handles.
func testFakesPopulated(t *testing.T) {
	t.Parallel()
	set, clock, random, sink := dependenciestest.Fakes()
	if set.Clock == nil || set.Random == nil || set.Sink == nil {
		t.Fatalf("Fakes() must return a fully-populated Set, got %+v", set)
	}
	if err := dependencies.Validate(set); err != nil {
		t.Fatalf("Fakes() Set must validate, got: %v", err)
	}
	if clock == nil || random == nil || sink == nil {
		t.Fatal("Fakes() must return non-nil handles to each fake")
	}
}

// testFakesSameObjects checks the returned handles are the SAME objects wired into the
// Set, so a test can drive them (pinned to a fixed instant and seed).
func testFakesSameObjects(t *testing.T) {
	t.Parallel()
	set, clock, random, sink := dependenciestest.Fakes()
	if set.Clock != dependencies.Clock(clock) {
		t.Error("Set.Clock is not the returned clock handle")
	}
	if set.Random != dependencies.RandomSource(random) {
		t.Error("Set.Random is not the returned random handle")
	}
	if set.Sink != dependencies.Sink(sink) {
		t.Error("Set.Sink is not the returned sink handle")
	}
}

// testFakesPinnedAndDrivable checks the fake clock starts at the Unix epoch and that
// driving the handle is observable through the Set (same object).
func testFakesPinnedAndDrivable(t *testing.T) {
	t.Parallel()
	set, clock, _, _ := dependenciestest.Fakes()
	if !clock.Now().Equal(time.Unix(0, 0).UTC()) {
		t.Fatalf("Fakes() clock not pinned to Unix epoch, got %v", clock.Now())
	}
	clock.Advance(time.Hour)
	if !set.Clock.Now().Equal(time.Unix(0, 0).UTC().Add(time.Hour)) {
		t.Fatal("advancing the returned clock handle is not visible via Set.Clock")
	}
}

// testFakesSinkCapturesViaSet checks emitting through Set.Sink is captured by the handle.
func testFakesSinkCapturesViaSet(t *testing.T) {
	t.Parallel()
	set, _, _, sink := dependenciestest.Fakes()
	if err := set.Sink.Emit(context.Background(), "via-set"); err != nil {
		t.Fatalf("emit via Set failed: %v", err)
	}
	if recs := sink.Records(); len(recs) != 1 || recs[0] != "via-set" {
		t.Fatalf("sink handle did not capture emit via Set, got %v", recs)
	}
}

// Fakes() is deterministic: two calls produce the same pinned instant and seed.
func TestFakesDeterministic(t *testing.T) {
	t.Parallel()
	_, c1, r1, _ := dependenciestest.Fakes()
	_, c2, r2, _ := dependenciestest.Fakes()
	if !c1.Now().Equal(c2.Now()) {
		t.Fatal("Fakes() clocks must start at the same pinned instant")
	}
	p1 := make([]byte, 32)
	p2 := make([]byte, 32)
	if _, err := r1.Read(p1); err != nil {
		t.Fatalf("r1.Read: %v", err)
	}
	if _, err := r2.Read(p2); err != nil {
		t.Fatalf("r2.Read: %v", err)
	}
	if !bytes.Equal(p1, p2) {
		t.Fatal("Fakes() randoms must start from the same pinned seed")
	}
}

// ---- Concurrency safety of fakes (§3 "safe for concurrent use", §4).

func TestFakesConcurrent(t *testing.T) {
	t.Parallel()
	c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
	r := dependenciestest.NewRandom([32]byte{})
	var s dependenciestest.RecordingSink

	var wg sync.WaitGroup
	for range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = c.Now()
			c.Advance(time.Millisecond)
			p := make([]byte, 8)
			if _, err := r.Read(p); err != nil {
				return // determinism asserted in TestFakeRandomFullRead
			}
			if err := s.Emit(context.Background(), "rec"); err != nil {
				return // capture asserted below via the final count
			}
			_ = s.Records()
		}()
	}
	wg.Wait()

	if got := len(s.Records()); got != 32 {
		t.Fatalf("concurrent Emit lost records: got %d want 32", got)
	}
}
