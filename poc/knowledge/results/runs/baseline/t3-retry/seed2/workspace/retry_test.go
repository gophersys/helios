package retry

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"
)

// mockSleeper records delay values and can be programmed to return an error.
type mockSleeper struct {
	delays []time.Duration
	// If non-nil, returned on every Sleep call after this many successes.
	failAfter int
	calls     int
	err       error
}

func (m *mockSleeper) Sleep(_ context.Context, d time.Duration) error {
	m.delays = append(m.delays, d)
	m.calls++
	if m.err != nil && m.calls > m.failAfter {
		return m.err
	}
	return nil
}

func TestNew_RejectsInvalidConfig(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		config Config
	}{
		{"MaxAttempts < 1", Config{MaxAttempts: 0, BaseDelay: time.Second}},
		{"MaxAttempts == 0", Config{MaxAttempts: 0, BaseDelay: 0}},
		{"MaxAttempts negative", Config{MaxAttempts: -1, BaseDelay: time.Second}},
		{"BaseDelay < 0", Config{MaxAttempts: 1, BaseDelay: -time.Nanosecond}},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			_, err := New(tc.config, Dependencies{})
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestNew_AcceptsValidConfig(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		config Config
	}{
		{"minimal", Config{MaxAttempts: 1, BaseDelay: 0}},
		{"normal", Config{MaxAttempts: 3, BaseDelay: time.Second}},
		{"zero delay", Config{MaxAttempts: 5, BaseDelay: 0}},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			r, err := New(tc.config, Dependencies{Sleeper: &mockSleeper{}})
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if r == nil {
				t.Fatal("expected non-nil Retrier")
			}
		})
	}
}

func TestNew_NilSleeperDefaultsToReal(t *testing.T) {
	t.Parallel()

	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Retrier")
	}

	// A nil Sleeper must not cause nil-pointer panics.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err = r.Do(ctx, func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDo_ImmediateSuccess(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	err = r.Do(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if len(sleeper.delays) != 0 {
		t.Fatalf("expected no sleeps, got %v", sleeper.delays)
	}
}

func TestDo_NonRetryableError(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: sleeper})

	sentinel := errors.New("fatal")
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return sentinel
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected error matching sentinel via errors.Is, got %v", err)
	}
	if len(sleeper.delays) != 0 {
		t.Fatalf("expected no sleeps for non-retryable, got %v", sleeper.delays)
	}
}

func TestDo_RetryableSuccessOnSecondAttempt(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, Dependencies{Sleeper: sleeper})

	attempt := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempt++
		if attempt == 1 {
			return &TransientError{Err: errors.New("transient")}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if attempt != 2 {
		t.Fatalf("expected 2 attempts, got %d", attempt)
	}
	if len(sleeper.delays) != 1 {
		t.Fatalf("expected 1 sleep, got %d", len(sleeper.delays))
	}
	if sleeper.delays[0] != 10*time.Millisecond {
		t.Fatalf("expected delay 10ms, got %v", sleeper.delays[0])
	}
}

func TestDo_RetryableExhaustion(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, Dependencies{Sleeper: sleeper})

	sentinel := errors.New("still failing")
	err := r.Do(context.Background(), func(ctx context.Context) error {

		return &TransientError{Err: sentinel}
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected error matching sentinel via errors.Is, got %v", err)
	}
	// Should have slept twice (after attempt 1 and attempt 2).
	if len(sleeper.delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d: %v", len(sleeper.delays), sleeper.delays)
	}
}

func TestDo_ExponentialBackoff(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	baseDelay := 10 * time.Millisecond
	r, _ := New(Config{MaxAttempts: 4, BaseDelay: baseDelay}, Dependencies{Sleeper: sleeper})

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errors.New("transient")}
	})
	if err == nil {
		t.Fatal("expected error")
	}

	// Attempts: 1→sleep(10ms), 2→sleep(20ms), 3→sleep(40ms), 4→fail (no sleep)
	expected := []time.Duration{
		10 * time.Millisecond,
		20 * time.Millisecond,
		40 * time.Millisecond,
	}
	if len(sleeper.delays) != len(expected) {
		t.Fatalf("expected %d delays, got %d: %v", len(expected), len(sleeper.delays), sleeper.delays)
	}
	for i, d := range sleeper.delays {
		if d != expected[i] {
			t.Fatalf("delay[%d] = %v, want %v", i, d, expected[i])
		}
	}
}

func TestDo_RetryAfterOverridesBackoff(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 10 * time.Minute}, Dependencies{Sleeper: sleeper})

	suggested := 5 * time.Second
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{
			Err:        errors.New("rate limited"),
			RetryAfter: suggested,
		}
	})
	if err == nil {
		t.Fatal("expected error")
	}

	if len(sleeper.delays) == 0 {
		t.Fatal("expected at least one sleep")
	}
	// Every sleep should use RetryAfter, not exponential backoff.
	for i, d := range sleeper.delays {
		if d != suggested {
			t.Fatalf("delay[%d] = %v, want RetryAfter %v", i, d, suggested)
		}
	}
}

func TestDo_RetryAfterZeroUsesBackoff(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	baseDelay := 10 * time.Millisecond
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: baseDelay}, Dependencies{Sleeper: sleeper})

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{
			Err:        errors.New("transient"),
			RetryAfter: 0, // explicitly zero — should use backoff
		}
	})
	if err == nil {
		t.Fatal("expected error")
	}

	if len(sleeper.delays) < 1 {
		t.Fatal("expected at least one sleep")
	}
	if sleeper.delays[0] != baseDelay {
		t.Fatalf("first delay = %v, want BaseDelay %v", sleeper.delays[0], baseDelay)
	}
}

func TestDo_SleeperErrorStops(t *testing.T) {
	t.Parallel()

	sleeperErr := errors.New("sleeper failed")
	sleeper := &mockSleeper{err: sleeperErr, failAfter: 0}
	r, _ := New(Config{MaxAttempts: 5, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})

	calls := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &TransientError{Err: fmt.Errorf("attempt %d failed", calls)}
	})
	if !errors.Is(err, sleeperErr) {
		t.Fatalf("expected sleeper error via errors.Is, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected only 1 call before sleeper error, got %d", calls)
	}
}

func TestDo_ContextCancellationDuringSleeper(t *testing.T) {
	t.Parallel()

	// Use a real sleeper so Sleep actually blocks and respects context cancellation.
	r, _ := New(Config{MaxAttempts: 5, BaseDelay: time.Hour}, Dependencies{})

	ctx, cancel := context.WithCancel(context.Background())

	// Schedule cancellation after a short delay.
	done := make(chan struct{})
	go func() {
		time.Sleep(5 * time.Millisecond)
		cancel()
		close(done)
	}()

	calls := 0
	err := r.Do(ctx, func(ctx context.Context) error {
		calls++
		return &TransientError{Err: errors.New("transient")}
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled via errors.Is, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected only 1 call, got %d", calls)
	}
	<-done
}

func TestDo_SingleAttemptNoSleep(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 1, BaseDelay: time.Hour}, Dependencies{Sleeper: sleeper})

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errors.New("transient")}
	})
	if err == nil {
		t.Fatal("expected error")
	}
	if len(sleeper.delays) != 0 {
		t.Fatalf("expected no sleeps with MaxAttempts=1, got %d", len(sleeper.delays))
	}
}

func TestDo_TransientErrorWrappedAtDepth(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})

	inner := errors.New("inner failure")
	err := r.Do(context.Background(), func(ctx context.Context) error {
		// Wrap a TransientError inside another error.
		return fmt.Errorf("wrapped: %w",
			&TransientError{Err: inner})
	})
	// Should succeed on retry since it's retryable... wait no, the operation always fails.
	// But it should be retried because the error tree contains *TransientError.
	if err == nil {
		t.Fatal("expected error")
	}
	// The returned error should match inner via errors.Is.
	if !errors.Is(err, inner) {
		t.Fatalf("expected error matching inner via errors.Is, got %v", err)
	}
	// Should have attempted 2 times (wrapped TransientError is retryable).
	if len(sleeper.delays) != 1 {
		t.Fatalf("expected 1 sleep with MaxAttempts=2, got %d", len(sleeper.delays))
	}
}

func TestDo_ReturnsLastErrorMatchesIs(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})

	sentinel := errors.New("last failure")
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: sentinel}
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected error matching sentinel via errors.Is, got %v", err)
	}
}

func TestDo_NonRetryableReturnsOriginalMatchesIs(t *testing.T) {
	t.Parallel()

	sleeper := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})

	sentinel := errors.New("fatal")
	wrapped := fmt.Errorf("wrapped: %w", sentinel)
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return wrapped
	})
	// Must match original via errors.Is.
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected error matching sentinel via errors.Is, got %v", err)
	}
	// Must be the exact same error value returned (or at least match via Is).
	if !errors.Is(err, wrapped) {
		t.Fatalf("expected error matching wrapped via errors.Is, got %v", err)
	}
}