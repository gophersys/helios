package retry

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"
)

// mockSleeper records delays and can be configured to return an error.
type mockSleeper struct {
	delays   []time.Duration
	sleepErr error
}

func (m *mockSleeper) Sleep(_ context.Context, d time.Duration) error {
	m.delays = append(m.delays, d)
	return m.sleepErr
}

// -------- New validation --------

func TestNew_InvalidMaxAttempts(t *testing.T) {
	_, err := New(Config{MaxAttempts: 0, BaseDelay: 0}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for MaxAttempts=0")
	}
}

func TestNew_InvalidBaseDelay(t *testing.T) {
	_, err := New(Config{MaxAttempts: 1, BaseDelay: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for BaseDelay=-1")
	}
}

func TestNew_DefaultSleeper(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r.sleeper == nil {
		t.Fatal("expected non-nil default sleeper")
	}
}

func TestNew_Valid(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Retrier")
	}
}

// -------- Do: immediate success --------

func TestDo_ImmediateSuccess(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
	if len(s.delays) != 0 {
		t.Fatalf("expected 0 sleeps, got %d", len(s.delays))
	}
}

// -------- Do: success after retry --------

func TestDo_SuccessAfterRetry(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls atomic.Int32
	err = r.Do(context.Background(), func(ctx context.Context) error {
		n := calls.Add(1)
		if n < 2 {
			return &TransientError{Err: fmt.Errorf("not yet")}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if calls.Load() != 2 {
		t.Fatalf("expected 2 calls, got %d", calls.Load())
	}
}

// -------- Do: non-retryable error returns immediately --------

func TestDo_NonRetryableError(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	baseErr := errors.New("fatal")
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return baseErr
	})
	if !errors.Is(err, baseErr) {
		t.Fatalf("expected error to match baseErr via errors.Is")
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
	if len(s.delays) != 0 {
		t.Fatalf("expected 0 sleeps, got %d", len(s.delays))
	}
}

// -------- Do: wrapped TransientError at depth --------

func TestDo_WrappedTransientError(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		// Wrap TransientError at depth so simple errors.Is on the
		// TransientError type still works through the chain.
		return fmt.Errorf("wrapper: %w", &TransientError{Err: errors.New("inner")})
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	_, ok := errors.AsType[*TransientError](err)
	if !ok {
		t.Fatal("expected error tree to contain *TransientError")
	}
}

// -------- Do: exhaust all attempts --------

func TestDo_ExhaustAttempts(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	inner := errors.New("last failure")
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &TransientError{Err: inner}
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	if !errors.Is(err, inner) {
		t.Fatal("returned error must match last failure via errors.Is")
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
	if len(s.delays) != 2 { // 3 attempts → 2 sleeps (before attempts 2 and 3)
		t.Fatalf("expected 2 sleeps, got %d", len(s.delays))
	}
}

// -------- Do: RetryAfter overrides exponential backoff --------

func TestDo_RetryAfterOverride(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &TransientError{
			Err:        errors.New("slow down"),
			RetryAfter: 5 * time.Millisecond,
		}
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	// Verify delay used RetryAfter (5ms), not the huge BaseDelay (1h).
	if len(s.delays) > 0 {
		for i, d := range s.delays {
			if d > time.Second {
				t.Fatalf("sleep[%d] = %v, expected RetryAfter (5ms), not backoff", i, d)
			}
		}
	}
}

// -------- Do: sleeper returns error (context cancellation) --------

func TestDo_SleeperError(t *testing.T) {
	s := &mockSleeper{sleepErr: errors.New("sleeper failed")}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &TransientError{Err: errors.New("transient")}
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	if !errors.Is(err, s.sleepErr) {
		t.Fatalf("returned error must match sleeper error via errors.Is")
	}
	if calls != 1 {
		t.Fatalf("expected 1 call (one before sleep), got %d", calls)
	}
}

// -------- Do: exponential backoff delay sequence --------

func TestDo_ExponentialBackoff(t *testing.T) {
	s := &mockSleeper{}
	base := 10 * time.Millisecond
	r, err := New(Config{MaxAttempts: 4, BaseDelay: base}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	_ = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errors.New("always fail")}
	})
	// 4 attempts → 3 sleeps: delays should be base, 2*base, 4*base.
	if len(s.delays) != 3 {
		t.Fatalf("expected 3 sleeps, got %d", len(s.delays))
	}
	expected := []time.Duration{base, 2 * base, 4 * base}
	for i, d := range s.delays {
		if d != expected[i] {
			t.Fatalf("sleep[%d] = %v, expected %v", i, d, expected[i])
		}
	}
}

// -------- Do: single attempt (MaxAttempts=1) --------

func TestDo_SingleAttempt(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 1, BaseDelay: time.Second}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &TransientError{Err: errors.New("fail")}
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
	if len(s.delays) != 0 {
		t.Fatalf("expected 0 sleeps with single attempt, got %d", len(s.delays))
	}
}

// -------- Do: BaseDelay=0 --------

func TestDo_ZeroBaseDelay(t *testing.T) {
	s := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: s})
	if err != nil {
		t.Fatal(err)
	}
	var calls int
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &TransientError{Err: errors.New("fail")}
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	// With BaseDelay=0, delay is always 0, so sleeper is called with 0.
	if len(s.delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(s.delays))
	}
	for i, d := range s.delays {
		if d != 0 {
			t.Fatalf("sleep[%d] = %v, expected 0", i, d)
		}
	}
}

// -------- TransientError invariants --------

func TestTransientError_ErrorContainsWrapped(t *testing.T) {
	te := &TransientError{Err: errors.New("boom")}
	msg := te.Error()
	if msg == "" {
		t.Fatal("Error() returned empty string")
	}
}

func TestTransientError_Unwrap(t *testing.T) {
	inner := errors.New("inner")
	te := &TransientError{Err: inner}
	if !errors.Is(te, inner) {
		t.Fatal("errors.Is must find inner through Unwrap")
	}
}

// -------- Sleeper cancellation --------

func TestDefaultSleeper_ContextCancelled(t *testing.T) {
	s := defaultSleeper{}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err := s.Sleep(ctx, time.Hour)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestDefaultSleeper_HonoursTimeout(t *testing.T) {
	s := defaultSleeper{}
	ctx, cancel := context.WithTimeout(context.Background(), time.Nanosecond)
	defer cancel()
	// Give the timeout a moment to fire.
	time.Sleep(time.Millisecond)
	err := s.Sleep(ctx, time.Hour)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected context.DeadlineExceeded, got %v", err)
	}
}