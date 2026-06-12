package ratelimiter

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"
)

// mockClock implements Clock with a controllable time.
type mockClock struct {
	mu sync.Mutex
	t  time.Time
}

func newMockClock(t time.Time) *mockClock {
	return &mockClock{t: t}
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
}

func TestNew_ValidConfig(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatalf("New with valid config: unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("New returned nil limiter")
	}
}

func TestNew_NegativeCapacity(t *testing.T) {
	_, err := New(Config{Capacity: -1, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("New with negative capacity: expected error")
	}
}

func TestNew_ZeroCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0, RefillPerSecond: 1}, Dependencies{})
	if err == nil {
		t.Fatal("New with zero capacity: expected error")
	}
}

func TestNew_NegativeRefillRate(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -0.5}, Dependencies{})
	if err == nil {
		t.Fatal("New with negative refill: expected error")
	}
}

func TestNew_ZeroRefillRate(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("New with zero refill: unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("New returned nil limiter")
	}
}

func TestNew_NilClockDefaultsToSystemClock(t *testing.T) {
	l, err := New(Config{Capacity: 1, RefillPerSecond: 1}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatalf("New with nil clock: unexpected error: %v", err)
	}
	// The clock should be the system clock — call Allow with a live context.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on a full bucket: expected true")
	}
}

func TestAllow_ZeroTokens(t *testing.T) {
	l := mustNew(t, 10, 1)
	_, err := l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("Allow with zero tokens: expected error")
	}
}

func TestAllow_NegativeTokens(t *testing.T) {
	l := mustNew(t, 10, 1)
	_, err := l.Allow(context.Background(), -5)
	if err == nil {
		t.Fatal("Allow with negative tokens: expected error")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l := mustNew(t, 10, 1)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("Allow on cancelled context: expected false")
	}
	if err == nil {
		t.Fatal("Allow on cancelled context: expected error")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("Allow on cancelled context: error should wrap context.Canceled, got %v", err)
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	l := mustNew(t, 10, 1)
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
	defer cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("Allow on expired deadline: expected false")
	}
	if err == nil {
		t.Fatal("Allow on expired deadline: expected error")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Allow on expired deadline: error should wrap context.DeadlineExceeded, got %v", err)
	}
}

func TestAllow_ConsumesTokens(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 10, 1, Dependencies{Clock: mc})

	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// Consume all remaining 7 tokens in one call.
	ok, err = l.Allow(context.Background(), 7)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on bucket with remaining tokens: expected true")
	}
}

func TestAllow_ReturnsFalseWhenInsufficient(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 5, 1, Dependencies{Clock: mc})

	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// Try to consume more than remaining (2 tokens left).
	ok, err = l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow when insufficient tokens: expected false")
	}

	// The bucket should still have 2 tokens (unchanged).
	ok, err = l.Allow(context.Background(), 2)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow with exactly remaining tokens: expected true")
	}
}

func TestAllow_RefillsOverTime(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 10, 10, Dependencies{Clock: mc}) // 10 tokens/s

	// Drain the bucket.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// Advance by 500ms → should have refilled 5 tokens.
	mc.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow after 500ms at 10 t/s: expected true (5 tokens refilled)")
	}

	// Bucket is empty again. Advance 100ms → 1 token.
	mc.advance(100 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow after 100ms at 10 t/s: expected true (1 token refilled)")
	}
}

func TestAllow_FractionalAccumulation(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 10, 1, Dependencies{Clock: mc}) // 1 token/s

	// Drain all tokens.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// Advance 100ms → 0.1 fractional tokens. Cannot consume 1.
	mc.advance(100 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow after 100ms with 1 t/s: expected false (only 0.1 tokens)")
	}

	// Advance another 900ms → total 1s elapsed → 1 token accumulated.
	mc.advance(900 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow after 1s total with 1 t/s: expected true (1 token accumulated)")
	}
}

func TestAllow_CapsAtCapacity(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 5, 1, Dependencies{Clock: mc})

	// Drain bucket to 0.
	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// Advance 100s → would refill 100 tokens, but capped at capacity 5.
	mc.advance(100 * time.Second)
	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow after 100s idle: expected true (capped at capacity)")
	}

	// Bucket empty again; second Allow should fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow on empty bucket: expected false")
	}
}

func TestAllow_ConcurrentSafety(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 100, 1000, Dependencies{Clock: mc}) // refills faster than consumption for the test

	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			// Each goroutine: attempt to take 1 token a few times.
			for j := 0; j < 5; j++ {
				// Advance clock a tiny bit to give refill a chance.
				mc.advance(time.Microsecond)
				_, err := l.Allow(context.Background(), 1)
				// We don't check the result (raciness of mock clock means
				// tokens might be exhausted); we just verify no panics or
				// data races.
				_ = err
			}
		}()
	}
	wg.Wait()
}

func TestAllow_EmptyBucketReturnsFalse(t *testing.T) {
	mc := newMockClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l := mustNewDeps(t, 3, 0, Dependencies{Clock: mc}) // no refill

	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// No refill and no time passing — should fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow on empty bucket with no refill: expected false")
	}
}

func TestAllow_NegativeElapsed_Ignored(t *testing.T) {
	// If the clock jumps backward, elapsed is negative and should be treated as zero.
	start := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	mc := newMockClock(start)
	l := mustNewDeps(t, 5, 10, Dependencies{Clock: mc})

	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow on full bucket: expected true")
	}

	// Jump clock backward.
	mc.t = start.Add(-time.Second)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow: unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow after clock jump back: expected false (no refill on negative elapsed)")
	}
}

// --- helpers ---

// testT is satisfied by *testing.T and *testing.B.
type testT interface {
	Fatalf(format string, args ...any)
	Helper()
}

func mustNew(t testT, capacity int, refill float64) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: capacity, RefillPerSecond: refill}, Dependencies{})
	if err != nil {
		t.Fatalf("New(%d, %f): %v", capacity, refill, err)
	}
	return l
}

func mustNewDeps(t testT, capacity int, refill float64, deps Dependencies) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: capacity, RefillPerSecond: refill}, deps)
	if err != nil {
		t.Fatalf("New(%d, %f, %+v): %v", capacity, refill, deps, err)
	}
	return l
}

// BenchmarkAllow measures the throughput of Allow on a hot path.
func BenchmarkAllow(b *testing.B) {
	l := mustNew(b, 1_000_000, 1_000_000)
	ctx := context.Background()
	for b.Loop() {
		l.Allow(ctx, 1)
	}
}

var _ = fmt.Sprintf // avoid unused import if tests fail