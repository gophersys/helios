package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

// fakeClock implements Clock with controllable time for deterministic tests.
type fakeClock struct {
	t time.Time
}

func (f *fakeClock) Now() time.Time { return f.t }

func (f *fakeClock) advance(d time.Duration) { f.t = f.t.Add(d) }

func TestNew_InvalidConfig(t *testing.T) {
	tests := []struct {
		name string
		cfg  Config
	}{
		{"zero capacity", Config{Capacity: 0, RefillPerSecond: 10}},
		{"negative capacity", Config{Capacity: -1, RefillPerSecond: 10}},
		{"negative refill rate", Config{Capacity: 1, RefillPerSecond: -1}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			l, err := New(tt.cfg, Dependencies{Clock: &fakeClock{}})
			if err == nil {
				t.Fatal("expected error, got nil")
			}
			if l != nil {
				t.Fatal("expected nil limiter on error")
			}
		})
	}
}

func TestNew_DefaultClock(t *testing.T) {
	// A nil clock should not cause a panic or error; the returned limiter
	// must use the system clock.
	l, err := New(Config{Capacity: 1, RefillPerSecond: 1}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil limiter")
	}
}

func TestAllow_NonPositiveTokens(t *testing.T) {
	l := newLimiter(t, 5, 1, &fakeClock{})

	tests := []struct {
		name   string
		tokens int
	}{
		{"zero", 0},
		{"negative", -1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ok, err := l.Allow(context.Background(), tt.tokens)
			if err == nil {
				t.Fatal("expected error")
			}
			if ok {
				t.Fatal("expected false")
			}
		})
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l := newLimiter(t, 5, 1, &fakeClock{})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for cancelled context")
	}
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected error to match context.Canceled, got %v", err)
	}
}

func TestAllow_StartsFull(t *testing.T) {
	l := newLimiter(t, 5, 1, &fakeClock{})

	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow (bucket starts full)")
	}

	// Next call with zero time elapsed should deny — bucket is empty.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected deny (bucket empty after full consumption)")
	}
}

func TestAllow_DenyWhenEmpty(t *testing.T) {
	l := newLimiter(t, 1, 0, &fakeClock{})

	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow (single token available)")
	}

	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected deny (bucket empty)")
	}
}

func TestAllow_RefillOverTime(t *testing.T) {
	fc := &fakeClock{t: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)}
	l := newLimiter(t, 10, 5, fc)

	// Drain the bucket.
	l.Allow(context.Background(), 10)

	// Advance 2 seconds → 10 tokens refilled (5/sec * 2s), but capped at
	// capacity (10).
	fc.advance(2 * time.Second)

	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow after refill")
	}
}

func TestAllow_RefillCapsAtCapacity(t *testing.T) {
	fc := &fakeClock{t: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)}
	l := newLimiter(t, 5, 10, fc)

	// Advance 10 seconds — would accumulate 100 tokens, but capped at 5.
	fc.advance(10 * time.Second)

	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow up to capacity")
	}

	// No tokens left.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected deny beyond capacity")
	}
}

func TestAllow_FractionalAccumulation(t *testing.T) {
	fc := &fakeClock{t: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)}
	// 0.5 tokens per second.
	l := newLimiter(t, 10, 0.5, fc)

	// Drain the bucket so we start from zero.
	l.Allow(context.Background(), 10)

	// Advance 1 second → 0.5 tokens available.
	fc.advance(1 * time.Second)

	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected deny (only 0.5 tokens after 1s at 0.5 rate)")
	}

	// Advance another 1 second → total 1.0 token.
	fc.advance(1 * time.Second)

	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow (1 token accumulated over 2s at 0.5 rate)")
	}
}

func TestAllow_ZeroRefillRate(t *testing.T) {
	fc := &fakeClock{t: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)}
	l := newLimiter(t, 3, 0, fc)

	l.Allow(context.Background(), 3)

	// Advance forever — no refill.
	fc.advance(1 * time.Hour)

	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected deny (zero refill rate)")
	}
}

func TestAllow_ConcurrentSafety(t *testing.T) {
	l := newLimiter(t, 1000, 0, nil)
	ctx := context.Background()
	var wg sync.WaitGroup

	// Attempt 1000 concurrent calls, each consuming 1 token.
	errs := make(chan error, 1000)
	oks := make(chan bool, 1000)

	for range 1000 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ok, err := l.Allow(ctx, 1)
			errs <- err
			oks <- ok
		}()
	}
	wg.Wait()
	close(errs)
	close(oks)

	var allowed, denied int
	for ok := range oks {
		if ok {
			allowed++
		} else {
			denied++
		}
	}
	for err := range errs {
		if err != nil {
			t.Fatalf("unexpected error during concurrent access: %v", err)
		}
	}

	if allowed != 1000 {
		t.Fatalf("expected exactly 1000 allowed (bucket capacity), got %d allowed, %d denied", allowed, denied)
	}
}

func newLimiter(t *testing.T, capacity int, refill float64, clock Clock) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: capacity, RefillPerSecond: refill}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatalf("New(%d, %f): %v", capacity, refill, err)
	}
	return l
}