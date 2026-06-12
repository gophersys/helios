package retry

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"
)

// mockSleeper records delays and optionally returns an error.
type mockSleeper struct {
	delays []time.Duration
	err    error
}

func (m *mockSleeper) Sleep(_ context.Context, d time.Duration) error {
	m.delays = append(m.delays, d)
	return m.err
}

func TestNew_InvalidMaxAttempts(t *testing.T) {
	r, err := New(Config{MaxAttempts: 0, BaseDelay: time.Second}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for MaxAttempts=0")
	}
	if r != nil {
		t.Fatal("expected nil Retrier on error")
	}
}

func TestNew_InvalidBaseDelay(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for BaseDelay=-1")
	}
	if r != nil {
		t.Fatal("expected nil Retrier on error")
	}
}

func TestNew_NilSleeperDefaults(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}
	if r == nil {
		t.Fatal("expected non-nil Retrier")
	}
}

func TestDo_SuccessFirstAttempt(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
	if len(sleeper.delays) != 0 {
		t.Fatalf("expected no delays on success, got %v", sleeper.delays)
	}
}

func TestDo_NonRetryableError(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	sentinelErr := errors.New("fatal")
	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		return sentinelErr
	})
	if !errors.Is(err, sentinelErr) {
		t.Fatalf("expected error matching sentinel, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected exactly 1 call, got %d", calls)
	}
}

func TestDo_RetryableThenSuccess(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	attempt := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		attempt++
		if attempt < 3 {
			return &TransientError{Err: fmt.Errorf("attempt %d failed", attempt)}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil on success after retry, got %v", err)
	}
	if attempt != 3 {
		t.Fatalf("expected 3 attempts, got %d", attempt)
	}
	if len(sleeper.delays) != 2 {
		t.Fatalf("expected 2 sleep delays, got %d", len(sleeper.delays))
	}
}

func TestDo_AllRetriesFail(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	lastErr := errors.New("final failure")
	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		return &TransientError{Err: lastErr}
	})
	if !errors.Is(err, lastErr) {
		t.Fatalf("expected error matching lastErr, got %v", err)
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
}

func TestDo_RetryAfterHonored(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	retryAfter := 50 * time.Millisecond
	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		if calls < 3 {
			return &TransientError{Err: fmt.Errorf("attempt %d", calls), RetryAfter: retryAfter}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected success, got %v", err)
	}
	for i, d := range sleeper.delays {
		if d != retryAfter {
			t.Fatalf("delay %d: expected %v, got %v", i, retryAfter, d)
		}
	}
}

func TestDo_ExponentialBackoff(t *testing.T) {
	sleeper := &mockSleeper{}
	base := 10 * time.Millisecond
	r, err := New(Config{MaxAttempts: 4, BaseDelay: base}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	_ = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: errors.New("retry")}
	})

	expected := []time.Duration{base, 2 * base, 4 * base}
	if len(sleeper.delays) != len(expected) {
		t.Fatalf("expected %d delays, got %d: %v", len(expected), len(sleeper.delays), sleeper.delays)
	}
	for i, d := range sleeper.delays {
		if d != expected[i] {
			t.Fatalf("delay %d: expected %v, got %v", i, expected[i], d)
		}
	}
}

func TestDo_SleeperError(t *testing.T) {
	sleeper := &mockSleeper{err: errors.New("sleep failed")}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		return &TransientError{Err: fmt.Errorf("attempt %d", calls)}
	})
	if !errors.Is(err, sleeper.err) {
		t.Fatalf("expected sleeper error, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected only 1 call before sleeper error, got %d", calls)
	}
}

func TestDo_ContextCancelled(t *testing.T) {
	// Use a real sleeper but cancel the context.
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // pre-cancelled

	err = r.Do(ctx, func(_ context.Context) error {
		return &TransientError{Err: errors.New("retry")}
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestDo_WrappedTransientError(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	innerErr := errors.New("inner")
	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		// Wrap the TransientError so it's not at the top level.
		return fmt.Errorf("wrapper: %w", &TransientError{Err: innerErr})
	})
	// All attempts fail; returned error must match the last failure via errors.Is.
	// The last failure is the wrapped error. errors.Is(err, innerErr) should work
	// because the wrapper wraps TransientError, and TransientError.Unwrap returns innerErr.
	if !errors.Is(err, innerErr) {
		t.Fatalf("expected error wrapping innerErr, got %v", err)
	}
	if calls != 2 {
		t.Fatalf("expected 2 calls, got %d", calls)
	}
}

func TestTransientError_Error(t *testing.T) {
	e := &TransientError{Err: errors.New("something broke")}
	msg := e.Error()
	if msg != "transient: something broke" {
		t.Fatalf("unexpected error message: %q", msg)
	}
}

func TestTransientError_Unwrap(t *testing.T) {
	inner := errors.New("inner")
	e := &TransientError{Err: inner}
	if !errors.Is(e, inner) {
		t.Fatal("TransientError should unwrap to its inner error")
	}
}

func TestDo_MaxAttemptsOne(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 1, BaseDelay: time.Second}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	// Retryable but MaxAttempts=1 means no retry.
	lastErr := errors.New("fail")
	err = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: lastErr}
	})
	if !errors.Is(err, lastErr) {
		t.Fatalf("expected matching lastErr, got %v", err)
	}
	if len(sleeper.delays) != 0 {
		t.Fatalf("expected no delays for 1 attempt")
	}
}

func TestDo_BaseDelayZero(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		if calls < 3 {
			return &TransientError{Err: fmt.Errorf("attempt %d", calls)}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected success, got %v", err)
	}
	// All delays should be 0.
	for i, d := range sleeper.delays {
		if d != 0 {
			t.Fatalf("delay %d: expected 0, got %v", i, d)
		}
	}
}

func TestDo_NonRetryableMatchesOriginal(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	sentinel := fmt.Errorf("original: %w", errors.New("cause"))
	err = r.Do(context.Background(), func(_ context.Context) error {
		return sentinel
	})
	// errors.Is on sentinel itself.
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected error to match sentinel, got %v", err)
	}
}

func TestDo_LastErrorMatchesWhenAllFail(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}

	inner := errors.New("underlying cause")
	calls := 0
	err = r.Do(context.Background(), func(_ context.Context) error {
		calls++
		return fmt.Errorf("attempt %d: %w", calls, &TransientError{Err: inner})
	})
	// The last failure wraps TransientError which wraps inner.
	// errors.Is should find inner through the chain.
	if !errors.Is(err, inner) {
		t.Fatalf("expected error matching inner, got %v", err)
	}
}