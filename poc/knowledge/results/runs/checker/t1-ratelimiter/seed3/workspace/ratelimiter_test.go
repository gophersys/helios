package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

// fakeClock implements Clock with a controllable time.
type fakeClock struct {
	mu  sync.Mutex
	now time.Time
}

func (c *fakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

func (c *fakeClock) advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
}

func (c *fakeClock) set(t time.Time) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = t
}

func newFakeClock() *fakeClock {
	return &fakeClock{now: time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)}
}

func TestNew_InvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for Capacity=0")
	}

	_, err = New(Config{Capacity: -1, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for Capacity=-1")
	}
}

func TestNew_InvalidRefillRate(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for RefillPerSecond=-1")
	}
}

func TestNew_NegativeZeroRefillRateAllowed(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// With 0 refill, the bucket starts full and never refills.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed with full bucket")
	}
	// After draining, subsequent call must fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail after draining bucket")
	}
}

func TestNew_NilClockUsesSystemClock(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l.clock == nil {
		t.Fatal("expected clock to be set")
	}
	if _, ok := l.clock.(systemClock); !ok {
		t.Fatal("expected systemClock when nil is passed")
	}
}

func TestNew_StartsFull(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 5, RefillPerSecond: 1}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// First call should allow consuming all capacity.
	ok, err := l.Allow(context.Background(), 5)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed with full bucket")
	}
	// Second call must fail since bucket is drained.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail with empty bucket")
	}
}

func TestAllow_TokensRefillOverTime(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Drain the bucket.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed")
	}

	// Advance 1 second. We should have 5 tokens.
	fc.advance(time.Second)
	ok, err = l.Allow(context.Background(), 5)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed after 1s refill")
	}

	// Now bucket is empty again. Advance 200ms -> 1 token.
	fc.advance(200 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed after 200ms refill")
	}

	// Should have 0 left. Advance 100ms -> 0.5 tokens, not enough for 1.
	fc.advance(100 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail with 0.5 tokens available")
	}
}

func TestAllow_CapsAtCapacity(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 100}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Drain bucket.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed")
	}

	// Advance 1 hour. Refill would produce 360000 tokens but should cap at 10.
	fc.advance(time.Hour)
	ok, err = l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed after long refill, capped at capacity")
	}

	// After consuming 10, bucket is empty again. But next call with
	// no time elapsed should fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail with no time elapsed")
	}
}

func TestAllow_NegativeTokensError(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	_, err = l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for tokens=0")
	}

	_, err = l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for tokens=-1")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for cancelled context")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled error, got %v", err)
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
	defer cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for expired deadline")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected context.DeadlineExceeded error, got %v", err)
	}
}

func TestAllow_ConcurrentSafety(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 1000, RefillPerSecond: 1000}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Go(func() {
			_, _ = l.Allow(context.Background(), 1)
		})
	}
	wg.Wait()
	// The test passes if there's no data race (run with -race).
	// Partial consumption is fine; we just verify no crash.
}

func TestAllow_RefillAccumulatesFractional(t *testing.T) {
	fc := newFakeClock()
	// Refill 1 token/sec, capacity 10.
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1.0}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Drain fully.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed")
	}

	// Advance 500ms → 0.5 tokens accumulated. Not enough for 1 token.
	fc.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail with 0.5 tokens")
	}

	// Advance another 500ms → now 1.0 tokens. Should succeed.
	fc.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed after accumulating 1 token")
	}

	// No time elapsed, 0 tokens left. Should fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail with 0 tokens")
	}
}

func TestAllow_ClockNotTicking(t *testing.T) {
	// Same as zero refill — clock never advances means no refill.
	fc := newFakeClock()
	l, err := New(Config{Capacity: 3, RefillPerSecond: 5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	ok, err := l.Allow(context.Background(), 3)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed")
	}

	// Multiple calls with same time should all fail.
	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil || ok {
			t.Fatalf("iteration %d: expected false, nil but got ok=%v, err=%v", i, ok, err)
		}
	}
}

func TestAllow_RefillRateZeroDoesNotRefill(t *testing.T) {
	fc := newFakeClock()
	l, err := New(Config{Capacity: 5, RefillPerSecond: 0}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	ok, err := l.Allow(context.Background(), 5)
	if err != nil || !ok {
		t.Fatal("expected Allow to succeed")
	}

	// No refill even with time passing.
	fc.advance(1 * time.Hour)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil || ok {
		t.Fatal("expected Allow to fail with 0 refill rate")
	}
}