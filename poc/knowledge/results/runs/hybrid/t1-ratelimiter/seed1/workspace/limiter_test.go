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
	t time.Time
}

func (f *fakeClock) Now() time.Time { return f.t }

func (f *fakeClock) advance(d time.Duration) { f.t = f.t.Add(d) }

func TestNew_InvalidCapacity(t *testing.T) {
	tests := []struct {
		name string
		cap  int
	}{
		{"zero capacity", 0},
		{"negative capacity", -1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(Config{Capacity: tt.cap, RefillPerSecond: 1}, Dependencies{Clock: &fakeClock{t: time.Now()}})
			if err == nil {
				t.Fatal("expected an error for invalid capacity")
			}
		})
	}
}

func TestNew_NegativeRefillRate(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -1}, Dependencies{Clock: &fakeClock{t: time.Now()}})
	if err == nil {
		t.Fatal("expected an error for negative refill rate")
	}
}

func TestNew_ZeroRefillRateIsValid(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 0}, Dependencies{Clock: &fakeClock{t: time.Now()}})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow to succeed with zero refill rate when bucket has tokens")
	}
}

func TestNew_NilClockDefaultsToSystemClock(t *testing.T) {
	l, err := New(Config{Capacity: 1, RefillPerSecond: 1}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected allow to succeed with default clock")
	}
}

func TestAllow_NegativeTokens(t *testing.T) {
	l := mustCreate(t, &fakeClock{t: time.Now()}, 10, 1)
	_, err := l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for negative tokens")
	}
}

func TestAllow_ZeroTokens(t *testing.T) {
	l := mustCreate(t, &fakeClock{t: time.Now()}, 10, 1)
	_, err := l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for zero tokens")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l := mustCreate(t, &fakeClock{t: time.Now()}, 10, 1)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for cancelled context")
	}
	if err == nil {
		t.Fatal("expected an error for cancelled context")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected error to match context.Canceled, got %v", err)
	}
}

func TestAllow_StartsFull(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l := mustCreate(t, fc, 10, 1)
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected bucket to start full")
	}
}

func TestAllow_RefillsOverTime(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	// Capacity 10, refill 10 tokens/second.
	l := mustCreate(t, fc, 10, 10)
	// Use all tokens.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("expected first burst to succeed")
	}

	// Next call without refill should fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected depletion after consuming all tokens")
	}

	// Advance 500ms → 5 tokens should be available (10 * 0.5).
	fc.advance(500 * time.Millisecond)

	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected 5 tokens after 500ms at 10 tokens/sec")
	}
}

func TestAllow_RefillDoesNotExceedCapacity(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l := mustCreate(t, fc, 10, 5)
	// Use 5 tokens, leaving 5.
	ok, _ := l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected initial allow to succeed")
	}
	// Advance 10 seconds → would refill 50 tokens, but capped at 10.
	fc.advance(10 * time.Second)
	// Should now have capacity (10) tokens available.
	ok, _ = l.Allow(context.Background(), 10)
	if !ok {
		t.Fatal("expected 10 tokens after long refill (capped at capacity)")
	}
}

func TestAllow_RejectsWhenInsufficientTokens(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l := mustCreate(t, fc, 5, 1)
	ok, _ := l.Allow(context.Background(), 5)
	if !ok {
		t.Fatal("expected initial burst to succeed")
	}
	// Advance 100ms → 0.1 tokens available, not enough for 1.
	fc.advance(100 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected reject when insufficient tokens")
	}
	// Tokens should NOT have been consumed.
	fc.advance(900 * time.Millisecond) // total 1s → 1 token refilled
	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected allow after enough refill time")
	}
	// After consuming 1, there should be ~0 tokens left (fractional could be ~0.0 - epsilon).
	// Advance 1s to get 1 more token.
	fc.advance(1 * time.Second)
	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected allow after another refill")
	}
}

func TestAllow_FractionalAccumulation(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	// Capacity 100, refill 1 token/second.
	l := mustCreate(t, fc, 100, 1)
	// Use all tokens.
	ok, _ := l.Allow(context.Background(), 100)
	if !ok {
		t.Fatal("expected initial burst to succeed")
	}
	// Advance 500ms → 0.5 tokens accumulated; not enough for 1.
	fc.advance(500 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected fractional tokens < 1 to prevent consumption")
	}
	// Advance another 500ms → total 1s → 1.0 tokens.
	fc.advance(500 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected 1 token after 1 second")
	}
	// Advance 100ms → 0.1 tokens.
	fc.advance(100 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if ok {
		t.Fatal("expected 0.1 tokens to not be enough for 1")
	}
	// Advance 900ms → total 1s → 1.0 tokens again.
	fc.advance(900 * time.Millisecond)
	ok, _ = l.Allow(context.Background(), 1)
	if !ok {
		t.Fatal("expected 1 token after another second")
	}
}

func TestAllow_ConcurrentSafety(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l := mustCreate(t, fc, 1000, 100)
	var wg sync.WaitGroup
	ctx := context.Background()

	for range 20 {
		wg.Go(func() {
			for range 50 {
				l.Allow(ctx, 1)
			}
		})
	}
	wg.Wait()

	// Advance enough to confirm the limiter isn't stuck.
	fc.advance(10 * time.Second)
	ok, err := l.Allow(ctx, 1000)
	if err != nil {
		t.Fatalf("unexpected error after concurrent access: %v", err)
	}
	if !ok {
		t.Fatal("expected allow after refill following concurrent access")
	}
}

func mustCreate(t *testing.T, clock Clock, cap int, rate float64) *Limiter {
	t.Helper()
	l, err := New(Config{Capacity: cap, RefillPerSecond: rate}, Dependencies{Clock: clock})
	if err != nil {
		t.Fatalf("mustCreate: %v", err)
	}
	return l
}