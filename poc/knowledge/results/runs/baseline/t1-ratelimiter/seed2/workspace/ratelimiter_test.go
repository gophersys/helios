package ratelimiter

import (
	"context"
	"sync"
	"testing"
	"time"
)

// mockClock implements Clock for deterministic testing.
type mockClock struct {
	t time.Time
}

func newMockClock() *mockClock {
	return &mockClock{t: time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)}
}

func (m *mockClock) Now() time.Time { return m.t }

func (m *mockClock) advance(d time.Duration) { m.t = m.t.Add(d) }

// ---------------------------------------------------------------------------
// New validation
// ---------------------------------------------------------------------------

func TestNew_RejectsNonPositiveCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for Capacity == 0")
	}
	_, err = New(Config{Capacity: -1, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for Capacity < 0")
	}
}

func TestNew_RejectsNegativeRefillPerSecond(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -0.5}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for RefillPerSecond < 0")
	}
}

func TestNew_AcceptsZeroRefillPerSecond(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed for full bucket")
	}
}

func TestNew_AcceptsValidConfig(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 2.5}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil Limiter")
	}
}

// ---------------------------------------------------------------------------
// Default clock (nil Clock → system clock)
// ---------------------------------------------------------------------------

func TestNew_UsesSystemClockWhenClockIsNil(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 10}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Make a quick call — must not hang or panic.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed with fresh bucket")
	}
}

// ---------------------------------------------------------------------------
// Allow input validation
// ---------------------------------------------------------------------------

func TestAllow_RejectsNonPositiveTokens(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}
	_, err = l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for tokens == 0")
	}
	_, err = l.Allow(context.Background(), -3)
	if err == nil {
		t.Fatal("expected error for tokens < 0")
	}
}

// ---------------------------------------------------------------------------
// Cancelled context
// ---------------------------------------------------------------------------

func TestAllow_CancelledContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for cancelled context")
	}
	if err == nil {
		t.Fatal("expected error for cancelled context")
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Hour))
	defer cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for deadline-exceeded context")
	}
	if err == nil {
		t.Fatal("expected error for deadline-exceeded context")
	}
}

// ---------------------------------------------------------------------------
// Basic allow / deny
// ---------------------------------------------------------------------------

func TestAllow_ConsumesTokens(t *testing.T) {
	l, err := New(Config{Capacity: 3, RefillPerSecond: 1}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}

	// bucket starts with 3 tokens
	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed for 3 tokens on full bucket")
	}

	// bucket now empty
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected Allow to fail on empty bucket")
	}
}

func TestAllow_PartialConsumption(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}

	// consume 3 — leaves 7
	ok, _ := l.Allow(context.Background(), 3)
	if !ok {
		t.Fatal("expected Allow to succeed for 3 out of 10")
	}

	// consume 7 — leaves 0
	ok, _ = l.Allow(context.Background(), 7)
	if !ok {
		t.Fatal("expected Allow to succeed for remaining 7")
	}

	// bucket empty
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected Allow to fail on empty bucket")
	}
}

// ---------------------------------------------------------------------------
// Refill over time (deterministic clock)
// ---------------------------------------------------------------------------

func TestAllow_RefillOverTime(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain bucket
	ok, _ := l.Allow(context.Background(), 10)
	if !ok {
		t.Fatal("expected Allow to succeed for full bucket")
	}

	// Advance 1 second → 5 tokens refilled
	mc.advance(time.Second)
	ok, _ = l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected Allow to succeed after 1s refill of 5 tokens")
	}

	// bucket should be empty again
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected Allow to fail after consuming refilled tokens")
	}
}

func TestAllow_RefillCapsAtCapacity(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Consume 3 out of 10 → 7 left
	ok, _ := l.Allow(context.Background(), 3)
	if !ok {
		t.Fatal("expected Allow to succeed")
	}

	// Advance 10 seconds → would add 50 tokens, but capped at 10
	mc.advance(10 * time.Second)
	ok, _ = l.Allow(context.Background(), 10)
	if !ok {
		t.Fatal("expected Allow for 10 tokens after long pause (capped at capacity)")
	}

	// bucket should be empty now
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected Allow to fail after consuming capped capacity")
	}
}

func TestAllow_ZeroRefillRate(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 0}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}

	// consume all
	ok, _ := l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected Allow to succeed for full bucket")
	}

	// no refill — should fail
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected Allow to fail when refill rate is 0")
	}
}

// ---------------------------------------------------------------------------
// Fractional accumulation
// ---------------------------------------------------------------------------

func TestAllow_FractionalRefill(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 10}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain to 0
	ok, _ := l.Allow(context.Background(), 10)
	if !ok {
		t.Fatal("expected Allow for full bucket")
	}

	// Advance 100ms → should add 1 token (10 tokens/s * 0.1s = 1)
	mc.advance(100 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected Allow after 100ms at 10 tokens/s")
	}

	// bucket empty
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected Allow to fail after consuming fractional refill")
	}

	// Advance 50ms → should add 0.5 tokens — not enough for 1
	mc.advance(50 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected Allow to fail with only 0.5 tokens accumulated")
	}

	// Advance another 50ms → should have 1.0 total now
	mc.advance(50 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected Allow after accumulating 1.0 tokens over two intervals")
	}
}

// ---------------------------------------------------------------------------
// Concurrent safety
// ---------------------------------------------------------------------------

func TestAllow_ConcurrentSafety(t *testing.T) {
	l, err := New(Config{Capacity: 100, RefillPerSecond: 100}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			// Each goroutine does multiple Allow calls without a shared
			// deterministic clock advance — this stresses the mutex.
			for j := 0; j < 50; j++ {
				l.Allow(context.Background(), 1) //nolint:errcheck
			}
		}()
	}
	wg.Wait()
}

// ---------------------------------------------------------------------------
// Bucket starts full
// ---------------------------------------------------------------------------

func TestNew_BucketStartsFull(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 7, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Must be able to consume exactly Capacity tokens immediately.
	ok, err := l.Allow(context.Background(), 7)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected bucket to start with full Capacity")
	}
}

// ---------------------------------------------------------------------------
// Allow does not leak tokens on deny
// ---------------------------------------------------------------------------

func TestAllow_DoesNotLeakTokensOnDeny(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 5, RefillPerSecond: 5}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain bucket
	ok, _ := l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected Allow for full bucket")
	}

	// Try to consume more than available — should return false and keep tokens
	ok, _ = l.Allow(context.Background(), 3)
	if ok {
		t.Fatal("expected Allow to fail, not enough tokens")
	}

	// Advance 1s → 5 tokens refilled, but since we didn't consume on the deny,
	// the 5 tokens should still be there from the refill.
	mc.advance(time.Second)
	ok, _ = l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected Allow to succeed after refill; tokens should not leak on deny")
	}
}
