package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// fakeClock implements Clock with a controllable Now().
type fakeClock struct {
	epoch atomic.Int64 // stores UnixNano as int64 for atomic access
}

func (f *fakeClock) Now() time.Time {
	return time.Unix(0, f.epoch.Load())
}

func (f *fakeClock) advance(d time.Duration) {
	f.epoch.Add(d.Nanoseconds())
}

func TestNew_InvalidConfig(t *testing.T) {
	tests := []struct {
		name string
		cfg  Config
	}{
		{"zero capacity", Config{Capacity: 0, RefillPerSecond: 1}},
		{"negative capacity", Config{Capacity: -1, RefillPerSecond: 1}},
		{"negative refill", Config{Capacity: 10, RefillPerSecond: -1}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(tt.cfg, Dependencies{Clock: &fakeClock{}})
			if err == nil {
				t.Fatal("expected error")
			}
		})
	}
}

func TestNew_ZeroRefill(t *testing.T) {
	l, err := New(Config{Capacity: 5, RefillPerSecond: 0}, Dependencies{Clock: &fakeClock{}})
	if err != nil {
		t.Fatal(err)
	}
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true with full bucket")
	}
}

func TestNew_NilClockUsesSystemClock(t *testing.T) {
	l, err := New(Config{Capacity: 1, RefillPerSecond: 1}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true on fresh bucket")
	}
}

func TestAllow_ZeroOrNegativeTokens(t *testing.T) {
	l := mustFull(t, Config{Capacity: 10, RefillPerSecond: 1})
	_, err := l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for zero tokens")
	}
	_, err = l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for negative tokens")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l := mustFull(t, Config{Capacity: 10, RefillPerSecond: 1})
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
		t.Fatalf("expected error to wrap context.Canceled, got: %v", err)
	}
}

func TestAllow_DeadlineExceeded(t *testing.T) {
	l := mustFull(t, Config{Capacity: 10, RefillPerSecond: 1})
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
	defer cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false on expired deadline")
	}
	if err == nil {
		t.Fatal("expected error on expired deadline")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected error to wrap context.DeadlineExceeded, got: %v", err)
	}
}

func TestAllow_ConsumesTokensInOrder(t *testing.T) {
	fc := &fakeClock{}
	fc.epoch.Store(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC).UnixNano())
	l := mustFull(t, Config{Capacity: 3, RefillPerSecond: 1}, fc)

	// Three tokens available -> all passes.
	for i := 0; i < 3; i++ {
		ok, err := l.Allow(context.Background(), 1)
		if err != nil {
			t.Fatalf("unexpected error at token %d: %v", i, err)
		}
		if !ok {
			t.Fatalf("expected true at token %d", i)
		}
	}

	// No tokens left.
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false when bucket is empty")
	}
}

func TestAllow_RefillsOverTime(t *testing.T) {
	fc := &fakeClock{}
	fc.epoch.Store(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC).UnixNano())
	l := mustFull(t, Config{Capacity: 3, RefillPerSecond: 1}, fc)

	// Drain bucket.
	for i := 0; i < 3; i++ {
		_, _ = l.Allow(context.Background(), 1)
	}

	// 1 second passes -> 1 token refilled.
	fc.advance(time.Second)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after refill")
	}

	// No tokens left again.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false after consuming refilled token")
	}
}

func TestAllow_CapsAtCapacity(t *testing.T) {
	fc := &fakeClock{}
	fc.epoch.Store(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC).UnixNano())
	l := mustFull(t, Config{Capacity: 5, RefillPerSecond: 10}, fc)

	// Drain.
	for i := 0; i < 5; i++ {
		_, _ = l.Allow(context.Background(), 1)
	}

	// 10 seconds pass -> refill 100 tokens, should cap at 5.
	fc.advance(10 * time.Second)
	ok, err := l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after cap refill")
	}

	// Should be empty again.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false after consuming full cap")
	}
}

func TestAllow_FractionalAccumulation(t *testing.T) {
	fc := &fakeClock{}
	fc.epoch.Store(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC).UnixNano())
	l := mustFull(t, Config{Capacity: 10, RefillPerSecond: 0.5}, fc)

	// Drain bucket.
	for i := 0; i < 10; i++ {
		_, _ = l.Allow(context.Background(), 1)
	}

	// 2 seconds -> 1 token.
	fc.advance(2 * time.Second)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after 2s at 0.5/s")
	}

	// 1 second -> 0.5 accumulated, not enough for 1 token.
	fc.advance(time.Second)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("expected false after 1s at 0.5/s")
	}

	// Another 1 second -> 1.0 total, enough.
	fc.advance(time.Second)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("expected true after 2 more seconds")
	}
}

func TestAllow_ConcurrentSafe(t *testing.T) {
	fc := &fakeClock{}
	fc.epoch.Store(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC).UnixNano())
	l := mustFull(t, Config{Capacity: 1000, RefillPerSecond: 100}, fc)

	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Go(func() {
			for j := 0; j < 50; j++ {
				_, _ = l.Allow(context.Background(), 1)
			}
		})
	}
	wg.Wait()
}

// mustFull creates a fully-filled Limiter or fails the test.
func mustFull(tb testing.TB, cfg Config, clock ...Clock) *Limiter {
	tb.Helper()
	var deps Dependencies
	if len(clock) > 0 {
		deps.Clock = clock[0]
	}
	l, err := New(cfg, deps)
	if err != nil {
		tb.Fatal(err)
	}
	return l
}