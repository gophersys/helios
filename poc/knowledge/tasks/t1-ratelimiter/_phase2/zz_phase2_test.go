package ratelimiter_test

import (
	"context"
	"errors"
	"testing"
	"time"
)

func approximately(t *testing.T, got, want time.Duration) {
	t.Helper()
	delta := got - want
	if delta < 0 {
		delta = -delta
	}
	if delta > 10*time.Millisecond {
		t.Fatalf("duration = %v; want ~%v", got, want)
	}
}

func TestVerifyP2ReserveOnDrainedBucket(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	ctx := context.Background()
	for i := 0; i < 2; i++ {
		if ok, _ := l.Allow(ctx, 1); !ok {
			t.Fatalf("drain #%d failed", i+1)
		}
	}
	wait, ok, err := l.Reserve(ctx, 1)
	if err != nil || !ok {
		t.Fatalf("Reserve(1) = %v, %v, %v; want ~1s, true, nil", wait, ok, err)
	}
	approximately(t, wait, time.Second)

	wait, ok, err = l.Reserve(ctx, 2)
	if err != nil || !ok {
		t.Fatalf("Reserve(2) = %v, %v, %v; want ~2s, true, nil", wait, ok, err)
	}
	approximately(t, wait, 2*time.Second)
}

func TestVerifyP2ReserveImmediatelyAvailable(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	wait, ok, err := l.Reserve(context.Background(), 1)
	if err != nil || !ok || wait != 0 {
		t.Fatalf("Reserve on full bucket = %v, %v, %v; want 0, true, nil", wait, ok, err)
	}
}

func TestVerifyP2ReserveNeverGrantable(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	_, ok, err := l.Reserve(context.Background(), 3)
	if err != nil || ok {
		t.Fatalf("Reserve(3) with capacity 2 = ok=%v err=%v; want false, nil", ok, err)
	}
	// no refill, drained bucket: not grantable
	l2 := newLimiter(t, 1, 0, clock)
	if granted, _ := l2.Allow(context.Background(), 1); !granted {
		t.Fatal("drain failed")
	}
	_, ok, err = l2.Reserve(context.Background(), 1)
	if err != nil || ok {
		t.Fatalf("Reserve with zero refill on empty bucket = ok=%v err=%v; want false, nil", ok, err)
	}
}

func TestVerifyP2ReserveDoesNotConsume(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	ctx := context.Background()
	for i := 0; i < 2; i++ {
		l.Allow(ctx, 1)
	}
	if _, ok, _ := l.Reserve(ctx, 1); !ok {
		t.Fatal("Reserve(1) should be grantable after 1s")
	}
	clock.advance(time.Second)
	if granted, err := l.Allow(ctx, 1); err != nil || !granted {
		t.Fatalf("Allow after Reserve+advance = %v, %v; Reserve must not consume", granted, err)
	}
	// and the full bucket case: Reserve then Allow both succeed
	l3 := newLimiter(t, 1, 1, clock)
	if _, ok, _ := l3.Reserve(ctx, 1); !ok {
		t.Fatal("Reserve on full bucket failed")
	}
	if granted, _ := l3.Allow(ctx, 1); !granted {
		t.Fatal("Allow after Reserve on full bucket failed; Reserve consumed tokens")
	}
}

func TestVerifyP2ReserveValidationAndContext(t *testing.T) {
	clock := &fakeClock{now: time.Unix(1000, 0)}
	l := newLimiter(t, 2, 1, clock)
	if _, _, err := l.Reserve(context.Background(), 0); err == nil {
		t.Fatal("Reserve(0): want error")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, ok, err := l.Reserve(ctx, 1)
	if ok || !errors.Is(err, context.Canceled) {
		t.Fatalf("Reserve with cancelled ctx = ok=%v err=%v; want false, context.Canceled in tree", ok, err)
	}
}
