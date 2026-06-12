package retry

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"
)

// mockSleeper records delays for inspection and can be configured to fail.
type mockSleeper struct {
	mu      delayRecorder
	failOn  int // fail on the nth Sleep call (1-indexed), 0 = never fail
	callIdx atomic.Int64
}

type delayRecorder struct {
	delays []time.Duration
}

func (m *mockSleeper) Sleep(ctx context.Context, d time.Duration) error {
	idx := int(m.callIdx.Add(1) - 1)
	m.mu.delays = append(m.mu.delays, d)
	if m.failOn > 0 && idx+1 == m.failOn {
		return ctx.Err()
	}
	return nil
}

func (m *mockSleeper) Delays() []time.Duration {
	return m.mu.delays
}

// fixedSleeper is a Sleeper that never blocks and never fails.
type fixedSleeper struct{}

func (fixedSleeper) Sleep(_ context.Context, _ time.Duration) error { return nil }

func TestNew_InvalidMaxAttempts(t *testing.T) {
	_, err := New(Config{MaxAttempts: 0, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err == nil {
		t.Fatal("expected error for MaxAttempts < 1")
	}
}

func TestNew_InvalidBaseDelay(t *testing.T) {
	_, err := New(Config{MaxAttempts: 1, BaseDelay: -1}, Dependencies{Sleeper: fixedSleeper{}})
	if err == nil {
		t.Fatal("expected error for BaseDelay < 0")
	}
}

func TestNew_NilSleeperDefaults(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r.sleeper == nil {
		t.Fatal("sleeper should not be nil after defaulting")
	}
}

func TestDo_SuccessFirstAttempt(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	calls := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_NonTransientErrorStops(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := errors.New("permanent failure")
	calls := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return sentinel
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected sentinel error, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_TransientErrorRecovers(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	var calls atomic.Int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		if calls.Add(1) < 3 {
			return &TransientError{Err: fmt.Errorf("try again")}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls.Load() != 3 {
		t.Fatalf("expected 3 calls, got %d", calls.Load())
	}
}

func TestDo_ExhaustsAttempts(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := &TransientError{Err: fmt.Errorf("always transient")}
	calls := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return sentinel
	})
	// Last error must match via errors.Is.
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected last error via errors.Is, got %v", err)
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
}

func TestDo_TransientAtAnyDepth(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	var calls atomic.Int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		if calls.Add(1) < 3 {
			// TransientError wrapped in additional context.
			return fmt.Errorf("wrapped: %w", &TransientError{Err: fmt.Errorf("inner")})
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls.Load() != 3 {
		t.Fatalf("expected 3 calls, got %d", calls.Load())
	}
}

func TestDo_UsesRetryAfter(t *testing.T) {
	sleeper := &mockSleeper{failOn: 100} // never fail
	r, err := New(Config{MaxAttempts: 2, BaseDelay: 10 * time.Second}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	var calls atomic.Int32
	_ = r.Do(context.Background(), func(ctx context.Context) error {
		if calls.Add(1) == 1 {
			return &TransientError{Err: fmt.Errorf("retry"), RetryAfter: 5 * time.Millisecond}
		}
		return nil
	})
	delays := sleeper.Delays()
	if len(delays) != 1 {
		t.Fatalf("expected 1 sleep, got %v", delays)
	}
	// Should use RetryAfter (5ms), not exponential backoff (10s).
	if delays[0] != 5*time.Millisecond {
		t.Fatalf("expected 5ms delay for RetryAfter, got %v", delays[0])
	}
}

func TestDo_ExponentialBackoff(t *testing.T) {
	sleeper := &mockSleeper{failOn: 100} // never fail
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 100 * time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	_ = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: fmt.Errorf("retry")}
	})
	delays := sleeper.Delays()
	if len(delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d: %v", len(delays), delays)
	}
	if delays[0] != 100*time.Millisecond {
		t.Fatalf("expected first delay 100ms, got %v", delays[0])
	}
	if delays[1] != 200*time.Millisecond {
		t.Fatalf("expected second delay 200ms, got %v", delays[1])
	}
}

func TestDo_SleeperErrorStops(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sleeper := &mockSleeper{failOn: 1} // fail on first Sleep
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	var calls atomic.Int32
	err = r.Do(ctx, func(ctx context.Context) error {
		calls.Add(1)
		return &TransientError{Err: fmt.Errorf("retry")}
	})
	// Do returns the error from Sleeper.Sleep.
	if err == nil {
		t.Fatal("expected error from sleeper")
	}
}

func TestDo_ContextCancellationBeforeCall(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{Sleeper: systemSleeper{}})
	if err != nil {
		t.Fatal(err)
	}

	err = r.Do(ctx, func(ctx context.Context) error {
		return &TransientError{Err: fmt.Errorf("retry")}
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestTransientError_Error(t *testing.T) {
	e := &TransientError{Err: fmt.Errorf("something broke")}
	got := e.Error()
	want := "transient: something broke"
	if got != want {
		t.Fatalf("expected %q, got %q", want, got)
	}
}

func TestTransientError_Unwrap(t *testing.T) {
	inner := fmt.Errorf("inner")
	e := &TransientError{Err: inner}
	if !errors.Is(e, inner) {
		t.Fatal("errors.Is should unwrap through TransientError")
	}
}

func TestDo_NonTransientReturnsOriginal(t *testing.T) {
	sentinel := errors.New("hard fail")
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: fixedSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return fmt.Errorf("wrapped: %w", sentinel)
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected wrapped sentinel via errors.Is, got %v", err)
	}
}