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

func TestNew_InvalidConfig(t *testing.T) {
	tests := []struct {
		name   string
		config Config
	}{
		{"zero capacity", Config{Capacity: 0, RefillPerSecond: 1}},
		{"negative capacity", Config{Capacity: -1, RefillPerSecond: 1}},
		{"negative refill rate", Config{Capacity: 10, RefillPerSecond: -0.5}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(tt.config, Dependencies{Clock: &fakeClock{}})
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestNew_ValidConfig(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: &fakeClock{}})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil limiter")
	}
}

func TestNew_NilClockUsesSystemClock(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: nil})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// The bucket should start full, so Allow should succeed.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to return true for full bucket")
	}
}

func TestAllow_ZeroTokens(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: &fakeClock{}})
	if err != nil {
		t.Fatal(err)
	}
	_, err = l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for zero tokens")
	}
}

func TestAllow_NegativeTokens(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: &fakeClock{}})
	if err != nil {
		t.Fatal(err)
	}
	_, err = l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for negative tokens")
	}
}

func TestAllow_CancelledContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: &fakeClock{}})
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
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestAllow_DeadlineExceededContext(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: &fakeClock{}})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
	defer cancel()
	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("expected false for expired deadline")
	}
	if err == nil {
		t.Fatal("expected error for expired deadline")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected context.DeadlineExceeded, got %v", err)
	}
}

func TestAllow_StartsWithFullBucket(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed for full bucket")
	}
}

func TestAllow_ConsumesTokens(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	// Consume 3 tokens.
	ok, err := l.Allow(context.Background(), 3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed")
	}
	// Consume 7 tokens — should succeed (3+7=10).
	ok, err = l.Allow(context.Background(), 7)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed")
	}
	// Bucket is now empty; next call should fail.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected Allow to fail on empty bucket")
	}
}

func TestAllow_RefillsOverTime(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 10}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	// Drain the bucket.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed")
	}
	// Advance 500ms → should have refilled 5 tokens.
	fc.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed after refill")
	}
	// Bucket should be empty again.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected Allow to fail after consuming refilled tokens")
	}
}

func TestAllow_FractionalAccumulation(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	// 1 token per second.
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	// Drain the bucket.
	l.Allow(context.Background(), 10)
	// Advance 100ms → should have 0.1 tokens.
	fc.advance(100 * time.Millisecond)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected Allow to fail with only 0.1 tokens")
	}
	// Advance another 900ms → total 1.0 tokens.
	fc.advance(900 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed after 1s total")
	}
}

func TestAllow_RefillCappedAtCapacity(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	// Consume 1 token.
	l.Allow(context.Background(), 1)
	// Advance 1 hour — should be capped at capacity (10).
	fc.advance(time.Hour)
	// Should be able to take 10 tokens (capped, not 9 + refill).
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed after long refill (capped)")
	}
}

func TestAllow_ZeroRefillRate(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 5, RefillPerSecond: 0}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	// Drain the bucket.
	l.Allow(context.Background(), 5)
	// Advance any amount — no refill.
	fc.advance(time.Hour)
	ok, err := l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected Allow to fail with zero refill rate")
	}
}

func TestConcurrentAccess(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 1000, RefillPerSecond: 1000}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			// Each goroutine tries to take 1 token.
			ok, err := l.Allow(context.Background(), 1)
			if err != nil {
				t.Errorf("unexpected error: %v", err)
			}
			if !ok {
				t.Error("expected Allow to succeed in concurrent test")
			}
		}()
	}
	wg.Wait()
}

func TestConcurrentAccess_Exhaustion(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 10}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}

	var mu sync.Mutex
	successes := 0
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ok, err := l.Allow(context.Background(), 1)
			if err != nil {
				t.Errorf("unexpected error: %v", err)
			}
			if ok {
				mu.Lock()
				successes++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()

	// With 10 capacity and no time passing, at most 10 should succeed.
	if successes > 10 {
		t.Fatalf("expected at most 10 successes, got %d", successes)
	}
	if successes < 10 {
		t.Fatalf("expected exactly 10 successes with full bucket, got %d", successes)
	}
}

func TestAllow_DoesNotConsumeOnFailure(t *testing.T) {
	fc := &fakeClock{t: time.Now()}
	l, err := New(Config{Capacity: 5, RefillPerSecond: 5}, Dependencies{Clock: fc})
	if err != nil {
		t.Fatal(err)
	}
	// Try to take 10 tokens (more than capacity).
	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Fatal("expected Allow to fail for more tokens than capacity")
	}
	// Should still have 5 tokens available.
	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("expected Allow to succeed after failed attempt")
	}
}