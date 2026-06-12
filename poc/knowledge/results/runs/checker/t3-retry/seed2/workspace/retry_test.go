package retry

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"
)

// mockSleeper records sleep calls for verification.
type mockSleeper struct {
	durations []time.Duration
	err       error // error to return from Sleep, if any
}

func (s *mockSleeper) Sleep(_ context.Context, d time.Duration) error {
	s.durations = append(s.durations, d)
	return s.err
}

// errSleeper returns a fixed error on every call.
type errSleeper struct {
	err error
}

func (s *errSleeper) Sleep(_ context.Context, _ time.Duration) error {
	return s.err
}

var errSentinel = errors.New("boom")

// ---------- New validation ----------

func TestNew_InvalidMaxAttempts(t *testing.T) {
	_, err := New(Config{MaxAttempts: 0, BaseDelay: time.Second}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for MaxAttempts < 1")
	}
}

func TestNew_NegativeBaseDelay(t *testing.T) {
	_, err := New(Config{MaxAttempts: 1, BaseDelay: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for BaseDelay < 0")
	}
}

func TestNew_ValidConfig(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Retrier")
	}
}

// ---------- Default sleeper ----------

func TestNew_DefaultSleeper(t *testing.T) {
	r, err := New(Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	attempts := 0
	start := time.Now()
	err = r.Do(context.Background(), func(ctx context.Context) error {
		attempts++
		if attempts == 1 {
			return &TransientError{Err: errSentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected success, got: %v", err)
	}
	// The real sleeper should have introduced a non-trivial delay.
	if elapsed := time.Since(start); elapsed < time.Millisecond {
		t.Errorf("expected at least 1ms delay, got %v", elapsed)
	}
}

// ---------- Do ----------

func TestDo_ImmediateSuccess(t *testing.T) {
	r := newRetrier(t, Config{MaxAttempts: 3, BaseDelay: time.Second}, &mockSleeper{})
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got: %v", err)
	}
}

func TestDo_RetryThenSuccess(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 3, BaseDelay: 10*time.Millisecond}, mock)
	attempts := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempts++
		if attempts < 3 {
			return &TransientError{Err: errSentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected success, got: %v", err)
	}
	if attempts != 3 {
		t.Fatalf("expected 3 attempts, got %d", attempts)
	}
	if len(mock.durations) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(mock.durations))
	}
	// Backoff: BaseDelay, then 2*BaseDelay.
	if mock.durations[0] != 10*time.Millisecond {
		t.Errorf("expected first delay 10ms, got %v", mock.durations[0])
	}
	if mock.durations[1] != 20*time.Millisecond {
		t.Errorf("expected second delay 20ms, got %v", mock.durations[1])
	}
}

func TestDo_NonRetryableErrorReturnedImmediately(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 3, BaseDelay: time.Second}, mock)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return errSentinel
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error, got: %v", err)
	}
	if len(mock.durations) != 0 {
		t.Fatalf("expected no sleeps for non-retryable error, got %d", len(mock.durations))
	}
}

func TestDo_AllAttemptsFail_ReturnsLastError(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, mock)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error via errors.Is, got: %v", err)
	}
	// Must have retried twice (3 attempts total, 2 sleeps).
	if len(mock.durations) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(mock.durations))
	}
}

func TestDo_AllAttemptsFail_MaxAttempts1(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 1, BaseDelay: time.Second}, mock)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return errSentinel
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error via errors.Is, got: %v", err)
	}
	if len(mock.durations) != 0 {
		t.Fatalf("expected no sleeps for MaxAttempts=1, got %d", len(mock.durations))
	}
}

func TestDo_RetryAfterHonored(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 2, BaseDelay: time.Minute}, mock)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errSentinel, RetryAfter: 5 * time.Millisecond}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error, got: %v", err)
	}
	if len(mock.durations) != 1 {
		t.Fatalf("expected 1 sleep, got %d", len(mock.durations))
	}
	// RetryAfter should override BaseDelay.
	if mock.durations[0] != 5*time.Millisecond {
		t.Errorf("expected delay 5ms (RetryAfter), got %v", mock.durations[0])
	}
}

func TestDo_ZeroRetryAfterFallsBackToExponential(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 3, BaseDelay: 7 * time.Millisecond}, mock)
	// Return a TransientError with RetryAfter == 0.
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errSentinel, RetryAfter: 0}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error, got: %v", err)
	}
	if len(mock.durations) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(mock.durations))
	}
	if mock.durations[0] != 7*time.Millisecond {
		t.Errorf("expected first delay 7ms, got %v", mock.durations[0])
	}
	if mock.durations[1] != 14*time.Millisecond {
		t.Errorf("expected second delay 14ms, got %v", mock.durations[1])
	}
}

func TestDo_TransientWrappingSentinel_ErrorsIsWorks(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 1, BaseDelay: time.Second}, mock)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: fmt.Errorf("wrapped: %w", errSentinel)}
	})
	// MaxAttempts=1, single failure returns the error directly.
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error via errors.Is, got: %v", err)
	}
}

func TestDo_DeeplyWrappedTransientError(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, mock)
	inner := fmt.Errorf("inner %w", &TransientError{Err: errSentinel})
	attempts := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempts++
		return inner
	})
	// Should have retried because *TransientError is in the tree.
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error via errors.Is, got: %v", err)
	}
	if attempts != 2 {
		t.Fatalf("expected 2 attempts, got %d", attempts)
	}
}

func TestDo_SleeperError_ReturnsImmediately(t *testing.T) {
	sleepErr := errors.New("sleep failed")
	r, err := New(Config{MaxAttempts: 5, BaseDelay: time.Millisecond}, Dependencies{Sleeper: &errSleeper{err: sleepErr}})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	attempts := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		attempts++
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, sleepErr) {
		t.Fatalf("expected sleep error, got: %v", err)
	}
	// Should have stopped after first sleep attempt (operation runs once, sleeper fails).
	if attempts != 1 {
		t.Fatalf("expected 1 attempt (operation called once before sleeper fails), got %d", attempts)
	}
}

func TestDo_ContextCancelledBeforeStart(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err = r.Do(ctx, func(ctx context.Context) error {
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got: %v", err)
	}
}

func TestDo_ZeroBaseDelay(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 3, BaseDelay: 0}, mock)
	attempts := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempts++
		if attempts < 3 {
			return &TransientError{Err: errSentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected success, got: %v", err)
	}
	if attempts != 3 {
		t.Fatalf("expected 3 attempts, got %d", attempts)
	}
	if len(mock.durations) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(mock.durations))
	}
	// BaseDelay=0, so delays should be 0.
	for i, d := range mock.durations {
		if d != 0 {
			t.Errorf("expected delay 0 at index %d, got %v", i, d)
		}
	}
}

func TestDo_TransientErrorIsDetectedAtAnyDepth(t *testing.T) {
	mock := &mockSleeper{}
	r := newRetrier(t, Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, mock)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return fmt.Errorf("wrapper: %w", &TransientError{Err: errSentinel})
	})
	// Should have retried (attempt 2 is last attempt, error returned).
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel error via errors.Is, got: %v", err)
	}
	if len(mock.durations) != 1 {
		t.Fatalf("expected 1 sleep for retry, got %d", len(mock.durations))
	}
}

// ---------- helpers ----------

func newRetrier(t *testing.T, cfg Config, sleeper *mockSleeper) *Retrier {
	t.Helper()
	r, err := New(cfg, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return r
}
