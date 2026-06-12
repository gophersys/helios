package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

type mockClock struct {
	mu  sync.Mutex
	now time.Time
}

func (m *mockClock) Now() time.Time {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.now
}

func (m *mockClock) advance(d time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.now = m.now.Add(d)
}

func TestNewValid(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: &mockClock{now: time.Now()}})
	if err != nil {
		t.Fatalf("New returned unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("New returned nil Limiter")
	}
}

func TestNewNilClock(t *testing.T) {
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{})
	if err != nil {
		t.Fatalf("New with nil clock returned unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("New with nil clock returned nil Limiter")
	}
}

func TestNewInvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0, RefillPerSecond: 5}, Dependencies{Clock: &mockClock{}})
	if err == nil {
		t.Fatal("New with Capacity=0 should return error")
	}

	_, err = New(Config{Capacity: -1, RefillPerSecond: 5}, Dependencies{Clock: &mockClock{}})
	if err == nil {
		t.Fatal("New with negative Capacity should return error")
	}
}

func TestNewInvalidRefillRate(t *testing.T) {
	_, err := New(Config{Capacity: 10, RefillPerSecond: -0.5}, Dependencies{Clock: &mockClock{}})
	if err == nil {
		t.Fatal("New with negative RefillPerSecond should return error")
	}
}

func TestAllowInvalidTokens(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	_, err = l.Allow(context.Background(), 0)
	if err == nil {
		t.Fatal("Allow with tokens=0 should return error")
	}

	_, err = l.Allow(context.Background(), -1)
	if err == nil {
		t.Fatal("Allow with negative tokens should return error")
	}
}

func TestAllowCancelledContext(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("Allow on cancelled context should return false")
	}
	if err == nil {
		t.Fatal("Allow on cancelled context should return error")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatal("returned error should wrap context.Canceled")
	}
}

func TestAllowStartsFull(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	ok, err := l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow should succeed with full bucket")
	}
}

func TestAllowNotEnoughTokens(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 5, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	ok, err := l.Allow(context.Background(), 5)
	if err != nil || !ok {
		t.Fatal("Allow should succeed with exactly full bucket")
	}

	// Second call should fail — bucket is empty and no time has passed.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow should return false when bucket is empty")
	}
}

func TestAllowRefill(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 5}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Consume all 10 tokens.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("first Allow should succeed")
	}

	// Advance 1 second: 5 tokens should have accumulated.
	mc.advance(time.Second)
	ok, err = l.Allow(context.Background(), 5)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow should succeed after refill")
	}
}

func TestAllowCapsAtCapacity(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 100}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Consume all 10.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("first Allow should succeed")
	}

	// Advance 10 seconds: 1000 tokens would accumulate, but capped at 10.
	mc.advance(10 * time.Second)
	ok, err = l.Allow(context.Background(), 10)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow should succeed with full bucket after cap")
	}

	// Should be empty again.
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow should return false after consuming capped refill")
	}
}

func TestAllowFractionalAccumulation(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 10, RefillPerSecond: 1}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	// Consume all 10.
	ok, err := l.Allow(context.Background(), 10)
	if err != nil || !ok {
		t.Fatal("first Allow should succeed")
	}

	// Advance 0.5 seconds: 0.5 tokens accumulated, not enough for 1.
	mc.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if ok {
		t.Fatal("Allow should return false with fractional tokens < 1")
	}

	// Advance another 0.5 seconds: 1.0 total, now enough.
	mc.advance(500 * time.Millisecond)
	ok, err = l.Allow(context.Background(), 1)
	if err != nil {
		t.Fatalf("Allow returned unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("Allow should succeed after accumulating 1 full token across two refills")
	}
}

func TestAllowConcurrent(t *testing.T) {
	mc := &mockClock{now: time.Now()}
	l, err := New(Config{Capacity: 100, RefillPerSecond: 1000}, Dependencies{Clock: mc})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	for range 10 {
		wg.Go(func() {
			for range 5 {
				l.Allow(context.Background(), 1)
			}
		})
	}
	wg.Wait()
}