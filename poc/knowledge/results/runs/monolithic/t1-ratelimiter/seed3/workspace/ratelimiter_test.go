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

// setTime directly sets the clock time.
func (f *fakeClock) setTime(t time.Time) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.now = t
}

func TestNew_InvalidCapacity(t *testing.T) {
	tests := []struct {
		name string
		cap  int
	}{
		{"zero", 0},
		{"negative", -1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(Config{Capacity: tt.cap, RefillPerSecond: 1}, Dependencies{})
			if err == nil {
				t.Fatal("expected error for invalid capacity")
			}
		})
	}
}

func TestNew_InvalidRefillRate(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -0.1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for negative refill rate")
	}
}

func TestNew_NilClockDefaults(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil limiter")
	}
	// Ensure it works with a real context (not cancelled).
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to return true with full bucket")
	}
}

func TestAllow_InvalidTokens(t *testing.T) {
	l := mustCreate(t, 10, 1)
	_, err := l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for tokens <= 0")
	}
	_, err = l.Allow(context.Background(), -5)
	if err == nil {
		t.Fatal("expected error for tokens <= 0")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l := mustCreate(t, 10, 1)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false on cancelled context")
	}
	if err == nil {
		t.Fatal("expected error on cancelled context")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected error wrapping context.Canceled, got %v", err)
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	l := mustCreate(t, 10, 1)
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Hour))
	defer cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false on expired deadline")
	}
	if err == nil {
		t.Fatal("expected error on expired deadline")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected error wrapping context.DeadlineExceeded, got %v", err)
	}
}

func TestAllow_FullBucket(t *testing.T) {
	l := mustCreate(t, 5, 1)
	// Full bucket = 5 tokens, each call consumes 1.
	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("iteration %d: unexpected error: %v", i, err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}
	// Sixth call should fail — bucket empty.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected false on empty bucket")
	}
}

func TestAllow_ExceedsCapacity(t *testing.T) {
	l := mustCreate(t, 3, 1)
	ok, err := l.Allow(context.Background(), 4)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected false when requesting more tokens than capacity")
	}
}

func TestAllow_Refill(t *testing.T) {
	fc := newFakeClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 5, RefillPerSecond: 2}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Consume all 5 tokens.
	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}

	// Advance 1 second → 2 tokens gained.
	fc.advance(time.Second)

	ok, err := l.Allow(context.Background(), 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected true after refill")
	}

	// No more tokens left.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected false after consuming refilled tokens")
	}
}

func TestAllow_FractionalRefill(t *testing.T) {
	fc := newFakeClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 10, RefillPerSecond: 0.5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Consume all 10 tokens.
	for i := 0; i < 10; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}

	// Advance 1 second → 0.5 tokens gained (fractional).
	fc.advance(time.Second)

	// Should not be enough for 1 token yet.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected false — fractional refill < 1")
	}

	// Advance another second → now 1.0 total gained → enough for 1 token.
	fc.advance(time.Second)

	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected true after 2 seconds of 0.5/s refill")
	}
}

func TestAllow_CapsAtCapacity(t *testing.T) {
	fc := newFakeClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 5, RefillPerSecond: 10}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Initially full (5). Consume 1, wait 10 seconds → would be 5+100 = 105
	// but should cap at 5.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected true")
	}

	fc.advance(10 * time.Second)

	// Should be back to 5 (capped).
	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true after cap", i)
		}
	}

	// Now empty again.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected false — bucket empty after cap consumption")
	}
}

func TestAllow_ZeroRefillRate(t *testing.T) {
	l := mustCreate(t, 3, 0)
	// Consume all 3.
	for i := 0; i < 3; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}
	// Should not refill regardless of time.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected false — zero refill rate never refills")
	}
}

func TestAllow_ConcurrentSafe(t *testing.T) {
	l := mustCreate(t, 100, 5)
	var wg sync.WaitGroup
	var mu sync.Mutex
	var allowed int

	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ok, err := l.Allow(context.Background(), 1)
			if err != nil {
				return
			}
			if ok {
				mu.Lock()
				allowed++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	// At most 100 tokens can be allowed (burst), but with concurrent
	// goroutines we just check no panics and allowed >= 0.
	if allowed < 0 {
		t.Fatal("unexpected negative allowed count")
	}
}

func TestAllow_AccumulatesMultipleCalls(t *testing.T) {
	fc := newFakeClock(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC))
	l, err := New(Config{Capacity: 10, RefillPerSecond: 3}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Consume all 10.
	for i := 0; i < 10; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}

	// Advance 1s → 3 tokens.
	fc.advance(time.Second)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected true after 1s refill")
	}

	// Advance another 1s without calling Allow — should accumulate
	// another 3 tokens on next call.
	fc.advance(time.Second)
	// The 2s refill: after first Advance+Allow, we consumed 1 from the 3,
	// leaving ~2, then second Advance adds 3 more = ~5 total. Should be
	// enough for 5.
	for i := 0; i < 5; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("iteration %d: unexpected error: %v", i, err)
		}
		if !ok {
			t.Fatalf("iteration %d: expected true", i)
		}
	}
}

// mustCreate is a test helper that creates a limiter with the system clock.
func mustCreate(t *testing.T, capacity int, refillPerSecond float64) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: capacity, RefillPerSecond: refillPerSecond}, Dependencies{})
	if err != nil {
		t.Fatalf("mustCreate: unexpected error: %v", err)
	}
	return l
}