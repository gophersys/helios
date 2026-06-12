package ratelimiter_test

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	ratelimiter "example.helios/ratelimiter"
)

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

func newLimiter(t *testing.T, capacity int, refill float64, clock ratelimiter.Clock) *ratelimiter.Limiter {
	t.Helper()
	l, err := ratelimiter.New(
		ratelimiter.Config{Capacity: capacity, RefillPerSecond: refill},
		ratelimiter.Dependencies{Clock: clock},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return l
}

func TestVerifyBucketStartsFullAndExhausts(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	ctx := context.Background()

	for i := 0; i < 2; i++ {
		ok, err := l.Allow(ctx, 1)
		if err != nil || !ok {
			t.Fatalf("Allow #%d = %v, %v; want true, nil", i+1, ok, err)
		}
	}
	ok, err := l.Allow(ctx, 1)
	if err != nil || ok {
		t.Fatalf("Allow on empty bucket = %v, %v; want false, nil", ok, err)
	}
}

func TestVerifyRefill(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	ctx := context.Background()

	for i := 0; i < 2; i++ {
		if ok, _ := l.Allow(ctx, 1); !ok {
			t.Fatalf("drain #%d failed", i+1)
		}
	}
	clock.advance(1 * time.Second) // refills exactly 1 token
	if ok, err := l.Allow(ctx, 1); err != nil || !ok {
		t.Fatalf("Allow after 1s refill = %v, %v; want true, nil", ok, err)
	}
	if ok, _ := l.Allow(ctx, 1); ok {
		t.Fatal("Allow after consuming the refilled token; want false")
	}
}

func TestVerifyRefillCapsAtCapacity(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	ctx := context.Background()

	clock.advance(time.Hour) // would refill 3600 tokens; cap is 2
	for i := 0; i < 2; i++ {
		if ok, _ := l.Allow(ctx, 1); !ok {
			t.Fatalf("Allow #%d after long idle; want true", i+1)
		}
	}
	if ok, _ := l.Allow(ctx, 1); ok {
		t.Fatal("Allow #3 after long idle; want false (capacity cap)")
	}
}

func TestVerifyCancelledContext(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	ok, err := l.Allow(ctx, 1)
	if ok {
		t.Fatal("Allow with cancelled ctx returned true")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("Allow with cancelled ctx: err = %v; want errors.Is(err, context.Canceled)", err)
	}
}

func TestVerifyValidation(t *testing.T) {
	if _, err := ratelimiter.New(ratelimiter.Config{Capacity: 0, RefillPerSecond: 1}, ratelimiter.Dependencies{}); err == nil {
		t.Fatal("New with Capacity 0: want error")
	}
	if _, err := ratelimiter.New(ratelimiter.Config{Capacity: 1, RefillPerSecond: -1}, ratelimiter.Dependencies{}); err == nil {
		t.Fatal("New with negative refill: want error")
	}
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 1, 1, clock)
	if _, err := l.Allow(context.Background(), 0); err == nil {
		t.Fatal("Allow with tokens=0: want error")
	}
}

func TestVerifyNilClockDefaultsToSystem(t *testing.T) {
	l, err := ratelimiter.New(
		ratelimiter.Config{Capacity: 1, RefillPerSecond: 1},
		ratelimiter.Dependencies{},
	)
	if err != nil {
		t.Fatalf("New with nil clock: %v", err)
	}
	if ok, err := l.Allow(context.Background(), 1); err != nil || !ok {
		t.Fatalf("Allow with system clock = %v, %v; want true, nil", ok, err)
	}
}

func TestVerifyConcurrentUse(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 100, 0, clock)
	ctx := context.Background()

	var wg sync.WaitGroup
	granted := make([]bool, 200)
	for i := 0; i < 200; i++ {
		wg.Go(func() {
			ok, err := l.Allow(ctx, 1)
			if err != nil {
				t.Errorf("Allow: %v", err)
			}
			granted[i] = ok
		})
	}
	wg.Wait()

	count := 0
	for _, ok := range granted {
		if ok {
			count++
		}
	}
	if count != 100 {
		t.Fatalf("granted %d of 200 with capacity 100 and no refill; want exactly 100", count)
	}
}
