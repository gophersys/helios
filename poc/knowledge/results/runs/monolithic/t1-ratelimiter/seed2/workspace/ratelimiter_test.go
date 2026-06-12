package ratelimiter

import (
	"context"
	"sync"
	"testing"
	"time"
)

// mockClock is a deterministic clock for testing.
type mockClock struct {
	t    time.Time
	mu   sync.Mutex
	done chan struct{} // notifications for WaitForAdvance
}

func newMockClock(init time.Time) *mockClock {
	return &mockClock{t: init, done: make(chan struct{}, 1)}
}

func (m *mockClock) Now() time.Time {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.t
}

func (m *mockClock) advance(d time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.t = m.t.Add(d)
	select {
	case m.done <- struct{}{}:
	default:
	}
}

func TestNewValidation(t *testing.T) {
	tests := []struct {
		name   string
		config Config
	}{
		{"zero capacity", Config{Capacity: 0, RefillPerSecond: 10}},
		{"negative capacity", Config{Capacity: -1, RefillPerSecond: 10}},
		{"negative refill", Config{Capacity: 10, RefillPerSecond: -1}},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := New(tc.config, Dependencies{})
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestNewValid(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil limiter")
	}
}

func TestAllowInvalidTokens(t *testing.T) {
	l := mustNew(t, 10, 5)

	tests := []int{0, -1, -100}
	for _, tok := range tests {
		t.Run("", func(t *testing.T) {
			ok, err := l.Allow(context.Background(), tok)
			if ok {
				t.Error("expected false")
			}
			if err == nil {
				t.Error("expected error")
			}
		})
	}
}

func TestAllowCancelledContext(t *testing.T) {
	l := mustNew(t, 10, 5)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Error("expected false on cancelled context")
	}
	if err == nil {
		t.Fatal("expected error on cancelled context")
	}
	if !errorsIs(err, context.Canceled) {
		t.Errorf("expected error wrapping context.Canceled, got %v", err)
	}
}

func TestAllowFullBucket(t *testing.T) {
	l := mustNew(t, 5, 1)

	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Error("expected true for full bucket allowance")
	}
}

func TestAllowExceedsCapacity(t *testing.T) {
	l := mustNew(t, 3, 1)

	ok, err := l.Allow(context.Background(), 4)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Error("expected false for tokens exceeding bucket")
	}
}

func TestAllowConsumeThenExhaust(t *testing.T) {
	l := mustNew(t, 3, 1)

	ok, _ := l.Allow(context.Background(), 2)
	if !ok {
		t.Fatal("expected true for first allowance")
	}

	ok, _ = l.Allow(context.Background(), 2)
	if ok {
		t.Error("expected false for second allowance exceeding remaining")
	}
}

func TestRefillOverTime(t *testing.T) {
	clock := newMockClock(time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewWithClock(t, 10, 5, clock)

	// Use all 10 tokens.
	ok, _ := l.Allow(context.Background(), 10)
	if !ok {
		t.Fatal("expected true, bucket was full")
	}

	// Advance 1 second → should have 5 tokens (rate = 5/sec).
	clock.advance(time.Second)

	ok, _ = l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected true after 1 second refill")
	}
}

func TestRefillCappedAtCapacity(t *testing.T) {
	clock := newMockClock(time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewWithClock(t, 5, 10, clock)

	// Advance 1 second → would add 10 tokens but capped at 5.
	clock.advance(time.Second)

	// Should have 5 tokens, not more.
	ok, _ := l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected true (capped at capacity)")
	}

	// No more tokens left.
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected false, bucket empty after consuming 5")
	}
}

func TestFractionalAccumulation(t *testing.T) {
	clock := newMockClock(time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewWithClock(t, 100, 1, clock)

	// Use all 100 tokens.
	ok, _ := l.Allow(context.Background(), 100)
	if !ok {
		t.Fatal("expected true")
	}

	// Advance 500ms → fractional gain of 0.5 tokens.
	clock.advance(500 * time.Millisecond)

	// Should have 0.5 tokens — not enough for 1.
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected false, only 0.5 tokens available")
	}

	// Advance another 500ms → 1.0 tokens total.
	clock.advance(500 * time.Millisecond)

	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected true after 1 full second")
	}
}

func TestZeroRefillRate(t *testing.T) {
	l := mustNew(t, 5, 0)

	ok, _ := l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected true for initial full bucket")
	}

	// No refill happens.
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected false after exhausting with zero refill")
	}
}

func TestConcurrentSafety(t *testing.T) {
	l := mustNew(t, 1000, 1000)

	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Go(func() {
			// Simulate short bursts lasting under the race threshold.
			for j := 0; j < 10; j++ {
				l.Allow(context.Background(), 1) //nolint:errcheck
			}
		})
	}
	wg.Wait()
}

func TestUsesSystemClockWhenNil(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 1}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Basic smoke test — the system clock advances in real time so the call
	// should succeed without panicking.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected true on fresh bucket")
	}
}

func TestAllowRespectsDeadline(t *testing.T) {
	// Use a cancelled context (past deadline).
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Hour))
	cancel()

	l := mustNew(t, 10, 1)
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Error("expected false on expired deadline")
	}
	if err == nil {
		t.Fatal("expected error on expired deadline")
	}
	if !errorsIs(err, context.DeadlineExceeded) {
		t.Errorf("expected wrapping DeadlineExceeded, got %v", err)
	}
}

// --- helpers ---

func mustNew(t *testing.T, capacity int, rate float64) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: capacity, RefillPerSecond: rate}, Dependencies{})
	if err != nil {
		t.Fatalf("mustNew: %v", err)
	}
	return l
}

func mustNewWithClock(t *testing.T, capacity int, rate float64, clock Clock) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: capacity, RefillPerSecond: rate}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatalf("mustNewWithClock: %v", err)
	}
	return l
}

// errorsIs exists because we're on Go 1.26 and errors.Is is the canonical
// check, but in the test we need to verify wrapping — errors.Is(err, target)
// works on wrapped errors via %w.
func errorsIs(err, target error) bool {
	for e := err; e != nil; {
		if e == target {
			return true
		}
		if u, ok := e.(interface{ Unwrap() error }); ok {
			e = u.Unwrap()
			continue
		}
		break
	}
	return false
}