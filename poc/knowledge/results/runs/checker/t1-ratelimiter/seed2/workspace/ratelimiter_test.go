package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

// mockClock implements Clock with a controllable time.
type mockClock struct {
	mu  sync.Mutex
	now time.Time
}

func newMockClock() *mockClock {
	return &mockClock{now: time.Now()}
}

func (m *mockClock) Now() time.Time {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.now
}

func (m *mockClock) Advance(d time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.now = m.now.Add(d)
}

func TestNew_ValidConfig(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil limiter")
	}
}

func TestNew_CapacityMustBePositive(t *testing.T) {
	_, err := New(Config{Capacity: 0, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for zero capacity")
	}

	_, err = New(Config{Capacity: -1, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for negative capacity")
	}
}

func TestNew_RefillRateMustBeNonNegative(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for negative refill rate")
	}
}

func TestNew_ZeroRefillRateAllowed(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil limiter")
	}
}

func TestAllow_TokensMustBePositive(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}

	_, err = l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for tokens == 0")
	}

	_, err = l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for negative tokens")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Error("expected false for cancelled context")
	}
	if err == nil {
		t.Fatal("expected error for cancelled context")
	}
	if !errors.Is(err, context.Canceled) {
		t.Errorf("expected error to match context.Canceled, got %v", err)
	}
}

func TestAllow_ConsumeTokens(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true with sufficient tokens")
	}

	// Should have 7 tokens left.
	ok, err = l.Allow(context.Background(), 7)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true with enough remaining tokens")
	}

	// Bucket now empty; no refill has elapsed.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Error("expected false when bucket is empty")
	}
}

func TestAllow_RefillOverTime(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 10}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain the bucket.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected to drain bucket")
	}

	// Advance 500ms → should add 5 tokens.
	mc.Advance(500 * time.Millisecond)

	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true after refill")
	}

	// Bucket should be empty again.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Error("expected false when insufficient tokens after partial refill")
	}
}

func TestAllow_FractionalAccumulation(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain the bucket.
	l.Allow(context.Background(), 10)

	// Advance 100ms → 0.1 tokens accumulated.
	mc.Advance(100 * time.Millisecond)

	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Error("expected false with only 0.1 tokens accumulated")
	}

	// Advance another 900ms → total 1.0 tokens.
	mc.Advance(900 * time.Millisecond)

	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true after 1.0 tokens accumulated")
	}
}

func TestAllow_CappedAtCapacity(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 10, RefillPerSecond: 100}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Consume 5 tokens, leaving 5.
	l.Allow(context.Background(), 5)

	// Advance a long time — more than enough to refill to full.
	mc.Advance(10 * time.Second)

	// Should have 10 tokens (capped), not more.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true after refill cap at Capacity")
	}

	// Now empty.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Error("expected false — bucket should be empty")
	}
}

func TestAllow_NoRefillWhenZeroRate(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 5, RefillPerSecond: 0}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain.
	l.Allow(context.Background(), 5)

	// Advance arbitrary time — rate is 0, so no refill.
	mc.Advance(1 * time.Hour)

	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Error("expected false when RefillPerSecond is 0")
	}
}

func TestAllow_BucketStartsFull(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 1}, Dependencies{Clock: newMockClock()})
	if err != nil {
		t.Fatal(err)
	}

	// Immediate consumption of full capacity.
	ok, err := l.Allow(context.Background(), 5)
	if err != nil || !ok {
		t.Fatal("expected bucket to start full")
	}
}

func TestAllow_ConcurrentAccess(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 100, RefillPerSecond: 100}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	allowed := make(chan bool, 200)

	for i := 0; i < 200; i++ {
		wg.Go(func() {
			ok, err := l.Allow(context.Background(), 1)
			if err != nil {
				t.Errorf("Allow returned error: %v", err)
			}
			allowed <- ok
		})
	}
	wg.Wait()
	close(allowed)

	// Without any time advance, no refill beyond initial 100 tokens.
	totalAllowed := 0
	for ok := range allowed {
		if ok {
			totalAllowed++
		}
	}

	if totalAllowed > 100 {
		t.Errorf("expected at most 100 allowed (initial capacity), got %d", totalAllowed)
	}
}

func TestNilClockUsesSystemClock(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 1}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatal(err)
	}

	ok, err := l.Allow(context.Background(), 5)
	if err != nil || !ok {
		t.Fatal("expected to consume initial tokens with system clock")
	}
}

func TestAllow_NoSideEffectOnDeny(t *testing.T) {
	mc := newMockClock()
	l, err := New(Config{Capacity: 5, RefillPerSecond: 10}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Drain.
	l.Allow(context.Background(), 5)

	// Try to take 1 — denied.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected denial")
	}

	// Advance enough to refill 1 token.
	mc.Advance(100 * time.Millisecond)

	// Should now get it.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true — denied call should not have consumed tokens")
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-1*time.Hour))
	defer cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Error("expected false for deadline exceeded context")
	}
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Errorf("expected error to match context.DeadlineExceeded, got %v", err)
	}
}