package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

// fakeClock implements Clock using a controllable time.
type fakeClock struct {
	mu   sync.Mutex
	now  time.Time
}

func newFakeClock(t time.Time) *fakeClock {
	return &fakeClock{now: t}
}

func (f *fakeClock) Now() time.Time {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.now
}

func (f *fakeClock) advance(d time.Duration) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.now = f.now.Add(d)
}

func (f *fakeClock) set(t time.Time) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.now = t
}

// ─── New ───────────────────────────────────────────────────────────────────

func TestNew_InvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for Capacity == 0")
	}
	_, err = New(Config{Capacity: -1, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for Capacity < 0")
	}
}

func TestNew_InvalidRefillRate(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for negative RefillPerSecond")
	}
}

func TestNew_NilClockDefaultsToSystem(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatal(err)
	}
	// If clock were nil we'd panic; just verify Allow works.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected Allow to return true on a full bucket")
	}
}

// ─── Allow: parameter validation ──────────────────────────────────────────

func TestAllow_ZeroTokens(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newFakeClock(time.Now())})
	if err != nil {
		t.Fatal(err)
	}
	_, err = l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for tokens == 0")
	}
}

func TestAllow_NegativeTokens(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newFakeClock(time.Now())})
	if err != nil {
		t.Fatal(err)
	}
	_, err = l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for tokens < 0")
	}
}

// ─── Allow: context cancellation ──────────────────────────────────────────

func TestAllow_CancelledContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newFakeClock(time.Now())})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false with cancelled context")
	}
	if err == nil || !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newFakeClock(time.Now())})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Hour))
	defer cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false with expired context")
	}
	if err == nil || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected context.DeadlineExceeded, got %v", err)
	}
}

func TestAllow_ContextNotCancelled(t *testing.T) {
	// Verify that a live context does not interfere.
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newFakeClock(time.Now())})
	if err != nil {
		t.Fatal(err)
	}
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true with live context and full bucket")
	}
}

// ─── Token consumption ────────────────────────────────────────────────────

func TestAllow_Consumption(t *testing.T) {
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Starts full.
	for i := 0; i < 10; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}

	// 11th call should fail — bucket is empty.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false on empty bucket")
	}
}

func TestAllow_PartialConsumptionDenied(t *testing.T) {
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 5, RefillPerSecond: 1}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Consume 3 tokens.
	for i := 0; i < 3; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}

	// Requesting 3 tokens when only 2 remain should be denied.
	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false when insufficient tokens")
	}

	// The bucket should still have 2 tokens — a subsequent request for 2 should succeed.
	ok, err = l.Allow(context.Background(), 2)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true when requesting exactly remaining tokens")
	}
}

// ─── Refill ───────────────────────────────────────────────────────────────

func TestAllow_RefillOverTime(t *testing.T) {
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	// 10 tokens/second, capacity 10.
	l, err := New(Config{Capacity: 10, RefillPerSecond: 10}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Drain the bucket.
	for i := 0; i < 10; i++ {
		l.Allow(context.Background(), 1)
	}

	// Advance 500ms → should have refilled 5 tokens.
	clock.advance(500 * time.Millisecond)

	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true after refill", i)
		}
	}

	// 6th call should fail (only 5 tokens refilled).
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false after consuming refilled tokens")
	}
}

func TestAllow_RefillCappedAtCapacity(t *testing.T) {
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 5, RefillPerSecond: 100}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Consume 3, leaving 2.
	for i := 0; i < 3; i++ {
		l.Allow(context.Background(), 1)
	}

	// Advance 1 hour — should refill well past capacity but cap at 5.
	clock.advance(time.Hour)

	// Should be able to take 5 (full capacity), not just 2.
	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true after long refill", i)
		}
	}

	// 6th should fail.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false after consuming capped refill")
	}
}

func TestAllow_ZeroRefillRate(t *testing.T) {
	// Zero refill rate means tokens never replenish.
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 3, RefillPerSecond: 0}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Drain.
	for i := 0; i < 3; i++ {
		l.Allow(context.Background(), 1)
	}

	// Advance arbitrarily — no refill at rate 0.
	clock.advance(time.Hour)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false with zero refill rate")
	}
}

// ─── Fractional accumulation ──────────────────────────────────────────────

func TestAllow_FractionalRefill(t *testing.T) {
	// 0.1 tokens/second → 100ms = 0.01 tokens. We need to show that
	// fractional accumulations actually accumulate across calls until
	// they cross an integer threshold.
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 10, RefillPerSecond: 0.1}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Drain to empty.
	for i := 0; i < 10; i++ {
		l.Allow(context.Background(), 1)
	}

	// Advance 5 seconds → 0.5 tokens accumulated.
	clock.advance(5 * time.Second)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false with only 0.5 tokens")
	}

	// Advance another 5 seconds → another 0.5 → 1.0 token.
	clock.advance(5 * time.Second)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after accumulating 1.0 token")
	}
}

func TestAllow_MultipleCallsRefillCorrectly(t *testing.T) {
	// Verify that two calls to Allow with time advancing between them
	// correctly accumulate refill each time.
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 10, RefillPerSecond: 2}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Drain to empty.
	for i := 0; i < 10; i++ {
		l.Allow(context.Background(), 1)
	}

	// Advance 0.5s → 1 token. Consume it — should succeed.
	clock.advance(500 * time.Millisecond)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after 0.5s at 2tokens/s")
	}

	// Should now be back to 0. Advance another 0.5s → 1 token again.
	clock.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after second 0.5s interval")
	}
}

// ─── Concurrency safety ───────────────────────────────────────────────────

func TestAllow_ConcurrentSafety(t *testing.T) {
	// Run Allow concurrently to detect races.
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 1000, RefillPerSecond: 1000}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Go(func() {
			// Each goroutine makes 50 calls with tiny time advances.
			for j := 0; j < 50; j++ {
				clock.advance(time.Millisecond)
				l.Allow(context.Background(), 1)
			}
		})
	}
	wg.Wait()
}

// ─── Race detection with `-race` ──────────────────────────────────────────

func TestAllow_RaceDetection(t *testing.T) {
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 100, RefillPerSecond: 100}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	const goroutines = 10
	const iterations = 100
	var wg sync.WaitGroup
	for i := 0; i < goroutines; i++ {
		wg.Go(func() {
			for j := 0; j < iterations; j++ {
				clock.advance(time.Microsecond)
				l.Allow(context.Background(), 1)
			}
		})
	}
	wg.Wait()
}

func TestNew_Parallel(t *testing.T) {
	// Create limiters in parallel to ensure New is safe too.
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Go(func() {
			l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newFakeClock(time.Now())})
			if err != nil {
				t.Error(err)
				return
			}
			l.Allow(context.Background(), 1)
		})
	}
	wg.Wait()
}

// ─── Bucket starts full ───────────────────────────────────────────────────

func TestBucketStartsFull(t *testing.T) {
	for capacity := 1; capacity <= 10; capacity++ {
		clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
		l, err := New(Config{Capacity: capacity, RefillPerSecond: 0}, Dependencies{Clock: clock})
		if err != nil {
			t.Fatal(err)
		}
		for i := 0; i < capacity; i++ {
			ok, err := l.Allow(context.Background(), 1)
			if err != nil {
				t.Fatal(err)
			}
			if !ok {
				t.Fatalf("capacity %d iteration %d: expected true", capacity, i)
			}
		}
	}
}

// ─── Allow with large token counts ────────────────────────────────────────

func TestAllow_BulkConsumption(t *testing.T) {
	clock := newFakeClock(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 100, RefillPerSecond: 10}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatal(err)
	}

	// Consume 50 at once.
	ok, err := l.Allow(context.Background(), 50)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true for bulk consume within capacity")
	}

	// Try 60 — should fail (only 50 left).
	ok, err = l.Allow(context.Background(), 60)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false for bulk consume exceeding remaining")
	}

	// Advance 6 seconds → 60 tokens refilled, capped at 100 but only 50 remain → 100
	// Actually: bucket had 50 left, add 60 = 110 capped at 100.
	clock.advance(6 * time.Second)
	ok, err = l.Allow(context.Background(), 100)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after refill for full capacity")
	}
}
