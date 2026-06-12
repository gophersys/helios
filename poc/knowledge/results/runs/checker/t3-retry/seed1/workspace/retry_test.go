package retry

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"
)

// mockSleeper is a test Sleeper with an optional custom sleep function.
type mockSleeper struct {
	fn func(ctx context.Context, d time.Duration) error
}

func (m *mockSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if m.fn != nil {
		return m.fn(ctx, d)
	}
	return nil
}

var errSentinel = errors.New("sentinel error")
var errPermanent = errors.New("permanent error")

// --- New constructor tests ---

func TestNew_ValidConfig(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}
	if r == nil {
		t.Fatal("New returned nil Retrier")
	}
}

func TestNew_MaxAttemptsBelowOne(t *testing.T) {
	_, err := New(Config{MaxAttempts: 0, BaseDelay: 0}, Dependencies{})
	if err == nil {
		t.Fatal("New with MaxAttempts=0 should return error")
	}
}

func TestNew_BaseDelayNegative(t *testing.T) {
	_, err := New(Config{MaxAttempts: 1, BaseDelay: -1}, Dependencies{})
	if err == nil {
		t.Fatal("New with BaseDelay=-1 should return error")
	}
}

func TestNew_NilSleeperDefaults(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}
	if _, ok := r.sleeper.(*clockSleeper); !ok {
		t.Fatal("nil Sleeper should default to *clockSleeper")
	}
}

// --- Do behavior tests ---

func TestDo_SuccessFirstAttempt(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return nil
	})
	if err != nil {
		t.Fatalf("Do returned error: %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_SuccessAfterRetries(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		n := atomic.AddInt32(&calls, 1)
		if n < 3 {
			return &TransientError{Err: fmt.Errorf("attempt %d failed", n)}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("Do returned error: %v", err)
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
}

func TestDo_NonRetryableErrorReturnedImmediately(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return errPermanent
	})
	if !errors.Is(err, errPermanent) {
		t.Fatalf("Do returned %v, expected it to match errPermanent via errors.Is", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_PlainErrorNotRetried(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	plainErr := errors.New("plain error")
	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return plainErr
	})
	if !errors.Is(err, plainErr) {
		t.Fatalf("Do returned %v, expected it to match plainErr via errors.Is", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_AllAttemptsExhausted(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("Do returned %v, expected it to match errSentinel via errors.Is", err)
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
}

func TestDo_MaxAttemptsOne(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("Do returned %v, expected to match errSentinel", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_ContextCancelled(t *testing.T) {
	r, err := New(Config{MaxAttempts: 5, BaseDelay: time.Hour}, Dependencies{Sleeper: &clockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	var calls int32
	err = r.Do(ctx, func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("Do returned %v, expected context.Canceled", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call (first attempt, sleeper returns ctx err), got %d", calls)
	}
}

func TestDo_SleeperReturnsError(t *testing.T) {
	sleeperErr := errors.New("sleeper failure")
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{
		Sleeper: &mockSleeper{fn: func(ctx context.Context, d time.Duration) error {
			return sleeperErr
		}},
	})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, sleeperErr) {
		t.Fatalf("Do returned %v, expected to match sleeperErr via errors.Is", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call (sleeper error after first retry), got %d", calls)
	}
}

func TestDo_RetryAfterOverride(t *testing.T) {
	var slept time.Duration
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Minute}, Dependencies{
		Sleeper: &mockSleeper{fn: func(ctx context.Context, d time.Duration) error {
			slept = d
			return nil
		}},
	})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		n := atomic.AddInt32(&calls, 1)
		if n < 2 {
			return &TransientError{
				Err:        errSentinel,
				RetryAfter: 5 * time.Second,
			}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("Do returned error: %v", err)
	}
	if calls != 2 {
		t.Fatalf("expected 2 calls, got %d", calls)
	}
	if slept != 5*time.Second {
		t.Fatalf("expected sleep of 5s (RetryAfter), got %v", slept)
	}
}

func TestDo_ExponentialBackoff(t *testing.T) {
	var sleeps []time.Duration
	r, err := New(Config{MaxAttempts: 4, BaseDelay: 10*time.Millisecond}, Dependencies{
		Sleeper: &mockSleeper{fn: func(ctx context.Context, d time.Duration) error {
			sleeps = append(sleeps, d)
			return nil
		}},
	})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("Do returned %v, expected errSentinel", err)
	}
	if calls != 4 {
		t.Fatalf("expected 4 calls, got %d", calls)
	}

	expected := []time.Duration{10 * time.Millisecond, 20 * time.Millisecond, 40 * time.Millisecond}
	if len(sleeps) != len(expected) {
		t.Fatalf("expected %d sleeps, got %d: %v", len(expected), len(sleeps), sleeps)
	}
	for i, s := range sleeps {
		if s != expected[i] {
			t.Fatalf("sleep[%d] = %v, expected %v", i, s, expected[i])
		}
	}
}

func TestDo_TransientErrorWrappedAtDepth(t *testing.T) {
	r, err := New(Config{MaxAttempts: 2, BaseDelay: time.Millisecond}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		if calls == 1 {
			// TransientError wrapped with fmt.Errorf at arbitrary depth.
			return fmt.Errorf("outer: %w", &TransientError{Err: errSentinel})
		}
		return nil
	})
	if err != nil {
		t.Fatalf("Do returned error: %v", err)
	}
	if calls != 2 {
		t.Fatalf("expected 2 calls, got %d", calls)
	}
}

func TestDo_BaseDelayZero(t *testing.T) {
	// With BaseDelay=0 the retry happens immediately (sleep of 0).
	var slept time.Duration
	r, err := New(Config{MaxAttempts: 2, BaseDelay: 0}, Dependencies{
		Sleeper: &mockSleeper{fn: func(ctx context.Context, d time.Duration) error {
			slept = d
			return nil
		}},
	})
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}

	var calls int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		atomic.AddInt32(&calls, 1)
		if calls == 1 {
			return &TransientError{Err: errSentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("Do returned error: %v", err)
	}
	if calls != 2 {
		t.Fatalf("expected 2 calls, got %d", calls)
	}
	if slept != 0 {
		t.Fatalf("expected sleep of 0 with BaseDelay=0, got %v", slept)
	}
}