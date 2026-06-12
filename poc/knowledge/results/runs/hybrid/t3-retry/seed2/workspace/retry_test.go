package retry

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// FakeSleeper — records Sleep calls and can simulate cancellation.
// ---------------------------------------------------------------------------

type fakeSleeper struct {
	mu     sync.Mutex
	calls  []time.Duration
	failOn int // 1-based: which Sleep call should fail
	failWith error
	callN   int
}

func (f *fakeSleeper) Sleep(_ context.Context, d time.Duration) error {
	f.mu.Lock()
	f.calls = append(f.calls, d)
	f.callN++
	fn := f.callN
	f.mu.Unlock()

	if fn == f.failOn {
		return f.failWith
	}
	return nil
}

func (f *fakeSleeper) Calls() []time.Duration {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]time.Duration, len(f.calls))
	copy(out, f.calls)
	return out
}

// errSentinel is a sentinel error used in non-retryable tests.
var errSentinel = errors.New("boom")

// wrapSentinel creates a TransientError wrapping errSentinel.
func wrapSentinel(after time.Duration) *TransientError {
	return &TransientError{Err: errSentinel, RetryAfter: after}
}

// ---------------------------------------------------------------------------
// New validation
// ---------------------------------------------------------------------------

func TestNew_RejectsInvalidConfig(t *testing.T) {
	tests := []struct {
		name string
		cfg  Config
	}{
		{"MaxAttempts < 1", Config{MaxAttempts: 0, BaseDelay: time.Second}},
		{"BaseDelay < 0", Config{MaxAttempts: 1, BaseDelay: -1}},
		{"both invalid", Config{MaxAttempts: 0, BaseDelay: -1}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(tt.cfg, Dependencies{})
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestNew_AcceptsValidConfig(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Retrier")
	}
}

func TestNew_DefaultsNilSleeper(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{Sleeper: nil})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Retrier")
	}
	// We can't directly assert the type, but Do should work fine.
	err = r.Do(context.Background(), func(ctx context.Context) error { return nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — success paths
// ---------------------------------------------------------------------------

func TestDo_ImmediateSuccess(t *testing.T) {
	sleeper := &fakeSleeper{}
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Second}, sleeper)

	var calls atomic.Int64
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls.Add(1)
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls.Load() != 1 {
		t.Fatalf("expected 1 call, got %d", calls.Load())
	}
}

func TestDo_RetryThenSuccess(t *testing.T) {
	sleeper := &fakeSleeper{}
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, sleeper)

	var calls atomic.Int64
	err := r.Do(context.Background(), func(ctx context.Context) error {
		n := calls.Add(1)
		if n < 3 {
			return wrapSentinel(0)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls.Load() != 3 {
		t.Fatalf("expected 3 calls, got %d", calls.Load())
	}

	durations := sleeper.Calls()
	if len(durations) != 2 {
		t.Fatalf("expected 2 Sleep calls, got %d", len(durations))
	}
	// Exponential backoff: first 10ms, then 20ms.
	if durations[0] != 10*time.Millisecond {
		t.Fatalf("expected first sleep 10ms, got %v", durations[0])
	}
	if durations[1] != 20*time.Millisecond {
		t.Fatalf("expected second sleep 20ms, got %v", durations[1])
	}
}

// ---------------------------------------------------------------------------
// Do — retryable error exhaustion
// ---------------------------------------------------------------------------

func TestDo_ExhaustedRetries(t *testing.T) {
	sleeper := &fakeSleeper{}
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, sleeper)

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return wrapSentinel(0)
	})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected error to match errSentinel via errors.Is, got %v", err)
	}
	// Should have called Sleep twice (attempts 1 and 2), not on final attempt
	if got := len(sleeper.Calls()); got != 2 {
		t.Fatalf("expected 2 Sleep calls, got %d", got)
	}
}

// ---------------------------------------------------------------------------
// Do — non-retryable error
// ---------------------------------------------------------------------------

func TestDo_NonRetryableError(t *testing.T) {
	sleeper := &fakeSleeper{}
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Second}, sleeper)

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return errSentinel
	})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected errors.Is(errSentinel), got %v", err)
	}
	// Should not sleep at all
	if got := len(sleeper.Calls()); got != 0 {
		t.Fatalf("expected 0 Sleep calls, got %d", got)
	}
}

// ---------------------------------------------------------------------------
// Do — RetryAfter from transient error
// ---------------------------------------------------------------------------

func TestDo_UsesRetryAfter(t *testing.T) {
	sleeper := &fakeSleeper{}
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, sleeper)

	var calls atomic.Int64
	err := r.Do(context.Background(), func(ctx context.Context) error {
		n := calls.Add(1)
		if n < 3 {
			return wrapSentinel(100 * time.Millisecond)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}

	durations := sleeper.Calls()
	if len(durations) != 2 {
		t.Fatalf("expected 2 Sleep calls, got %d", len(durations))
	}
	// Both should use RetryAfter since it's > 0
	for i, d := range durations {
		if d != 100*time.Millisecond {
			t.Fatalf("expected sleep %d to be 100ms, got %v", i, d)
		}
	}
}

// ---------------------------------------------------------------------------
// Do — Sleeper error / context cancellation
// ---------------------------------------------------------------------------

func TestDo_SleeperErrorStopsRetry(t *testing.T) {
	sleeperErr := fmt.Errorf("sleeper failed")
	sleeper := &fakeSleeper{failOn: 1, failWith: sleeperErr}
	r := mustNew(t, Config{MaxAttempts: 5, BaseDelay: time.Millisecond}, sleeper)

	var calls atomic.Int64
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls.Add(1)
		return wrapSentinel(0)
	})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, sleeperErr) {
		t.Fatalf("expected errors.Is(sleeperErr), got %v", err)
	}
	// operation should have been called once (first attempt fails, sleep fails, stop)
	if calls.Load() != 1 {
		t.Fatalf("expected 1 call, got %d", calls.Load())
	}
}

func TestDo_ContextCancelledDuringOperation(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Second}, &fakeSleeper{})

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled

	err := r.Do(ctx, func(ctx context.Context) error {
		return ctx.Err()
	})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestDo_ContextCancelledDuringSleep(t *testing.T) {
	// Use a real sleeper so Sleep actually blocks on ctx.Done()
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Hour}, nil) // nil -> real clockSleeper

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errCh := make(chan error, 1)
	go func() {
		errCh <- r.Do(ctx, func(ctx context.Context) error {
			return wrapSentinel(0)
		})
	}()

	// Give the goroutine time to enter the first Sleep
	time.Sleep(10 * time.Millisecond)
	cancel()

	select {
	case err := <-errCh:
		if err == nil {
			t.Fatal("expected error, got nil")
		}
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("expected context.Canceled, got %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for Do to return")
	}
}

// ---------------------------------------------------------------------------
// Do — wrapped transient error (deep in error tree)
// ---------------------------------------------------------------------------

func TestDo_WrappedTransientError(t *testing.T) {
	sleeper := &fakeSleeper{}
	r := mustNew(t, Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, sleeper)

	// Create a transient error that is wrapped in an extra layer
	wrapped := fmt.Errorf("wrapper: %w", wrapSentinel(0))

	var calls atomic.Int64
	err := r.Do(context.Background(), func(ctx context.Context) error {
		n := calls.Add(1)
		if n == 1 {
			return wrapped
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls.Load() != 2 {
		t.Fatalf("expected 2 calls, got %d", calls.Load())
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func mustNew(t *testing.T, cfg Config, s *fakeSleeper) *Retrier {
	t.Helper()
	var deps Dependencies
	if s != nil {
		deps.Sleeper = s
	}
	r, err := New(cfg, deps)
	if err != nil {
		t.Fatalf("New(%+v) failed: %v", cfg, err)
	}
	return r
}