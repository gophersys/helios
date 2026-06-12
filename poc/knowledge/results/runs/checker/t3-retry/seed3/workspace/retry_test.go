package retry

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"
)
// mockSleeper records sleep calls; always returns nil.
type mockSleeper struct {
	delays []time.Duration
}

func (m *mockSleeper) Sleep(_ context.Context, d time.Duration) error {
	m.delays = append(m.delays, d)
	return nil
}

// controllableSleeper waits on a channel so tests control timing.
type controllableSleeper struct {
	ch   chan struct{}
	err  error // error to return after unblock
}

func (c *controllableSleeper) Sleep(ctx context.Context, _ time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-c.ch:
		return c.err
	}
}

func TestNew_ValidatesMaxAttempts(t *testing.T) {
	_, err := New(Config{MaxAttempts: 0, BaseDelay: 0}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for MaxAttempts < 1")
	}
}

func TestNew_ValidatesBaseDelay(t *testing.T) {
	_, err := New(Config{MaxAttempts: 1, BaseDelay: -1}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for BaseDelay < 0")
	}
}

func TestNew_NilSleeperDefaults(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// The retrier should work with the default sleeper; success path.
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
}

func TestDo_SuccessOnFirstAttempt(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
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
	if len(sleeper.delays) != 0 {
		t.Fatalf("expected no sleeps, got %d", len(sleeper.delays))
	}
}

func TestDo_NonRetryableErrorReturnedImmediately(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
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
		t.Fatalf("expected sentinel error via errors.Is, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestDo_TransientErrorTriggersRetry(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := errors.New("transient")
	calls := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		if calls < 3 {
			return &TransientError{Err: sentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil on third attempt success, got %v", err)
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
}

func TestDo_ExhaustedRetriesReturnLastError(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := errors.New("always transient")
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: sentinel}
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected last error via errors.Is, got %v", err)
	}
	if len(sleeper.delays) != 2 {
		t.Fatalf("expected 2 sleeps (attempts 1 and 2), got %d", len(sleeper.delays))
	}
}

func TestDo_ExponentialBackoff(t *testing.T) {
	sleeper := &mockSleeper{}
	baseDelay := 10 * time.Millisecond
	r, err := New(Config{MaxAttempts: 4, BaseDelay: baseDelay}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errors.New("retry")}
	})
	if err == nil {
		t.Fatal("expected error")
	}
	// BaseDelay, 2*BaseDelay, 4*BaseDelay = 3 sleeps for 4 attempts
	if len(sleeper.delays) != 3 {
		t.Fatalf("expected 3 delays, got %d", len(sleeper.delays))
	}
	expected := []time.Duration{baseDelay, 2 * baseDelay, 4 * baseDelay}
	for i, d := range sleeper.delays {
		if d != expected[i] {
			t.Fatalf("delay %d: expected %v, got %v", i, expected[i], d)
		}
	}
}

func TestDo_RetryAfterOverridesBackoff(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 1 * time.Hour}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	customDelay := 5 * time.Millisecond
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errors.New("retry"), RetryAfter: customDelay}
	})
	if err == nil {
		t.Fatal("expected error")
	}
	if len(sleeper.delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(sleeper.delays))
	}
	for i, d := range sleeper.delays {
		if d != customDelay {
			t.Fatalf("delay %d: expected %v, got %v", i, customDelay, d)
		}
	}
}

func TestDo_SleeperErrorStopsRetry(t *testing.T) {
	cs := &controllableSleeper{ch: make(chan struct{}), err: errors.New("sleeper fail")}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: cs})
	if err != nil {
		t.Fatal(err)
	}
	calls := 0
	errCh := make(chan error, 1)
	go func() {
		errCh <- r.Do(context.Background(), func(ctx context.Context) error {
			calls++
			return &TransientError{Err: fmt.Errorf("attempt %d", calls)}
		})
	}()
	cs.ch <- struct{}{} // unblock first sleep with error
	got := <-errCh
	if got == nil || got.Error() != "sleeper fail" {
		t.Fatalf("expected 'sleeper fail', got %v", got)
	}
	if calls != 1 {
		t.Fatalf("expected 1 call (sleeper returns error on first retry sleep), got %d", calls)
	}
}

func TestDo_ContextCancelledDuringSleep(t *testing.T) {
	cs := &controllableSleeper{ch: make(chan struct{})}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: cs})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	errCh := make(chan error, 1)
	go func() {
		errCh <- r.Do(ctx, func(ctx context.Context) error {
			return &TransientError{Err: errors.New("retry")}
		})
	}()
	cancel()
	got := <-errCh
	if !errors.Is(got, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", got)
	}
}

func TestDo_TransientErrorWrappedInTree(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := errors.New("inner")
	calls := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		if calls < 3 {
			return fmt.Errorf("wrapping: %w", &TransientError{Err: sentinel})
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if calls != 3 {
		t.Fatalf("expected 3 calls, got %d", calls)
	}
}

func TestDo_ZeroBaseDelay(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	calls := 0
	err = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		if calls < 3 {
			return &TransientError{Err: errors.New("retry")}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	// With BaseDelay=0 and no RetryAfter, delay is 0 each time.
	if len(sleeper.delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(sleeper.delays))
	}
	for i, d := range sleeper.delays {
		if d != 0 {
			t.Fatalf("delay %d expected 0, got %v", i, d)
		}
	}
}

func TestDo_TransientErrorRetryAfterZero_UsesBackoff(t *testing.T) {
	sleeper := &mockSleeper{}
	baseDelay := 10 * time.Millisecond
	r, err := New(Config{MaxAttempts: 3, BaseDelay: baseDelay}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: errors.New("retry"), RetryAfter: 0}
	})
	if err == nil {
		t.Fatal("expected error")
	}
	// RetryAfter=0 should fall back to exponential backoff.
	expected := []time.Duration{baseDelay, 2 * baseDelay}
	if len(sleeper.delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(sleeper.delays))
	}
	for i, d := range sleeper.delays {
		if d != expected[i] {
			t.Fatalf("delay %d: expected %v, got %v", i, expected[i], d)
		}
	}
}

// TestDo_DefaultSleeperRespectsCancellation verifies that the default sleeper
// (time-based) stops when the context is cancelled.
func TestDo_DefaultSleeperRespectsCancellation(t *testing.T) {
	r, err := New(Config{MaxAttempts: 5, BaseDelay: time.Hour}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	errCh := make(chan error, 1)
	go func() {
		errCh <- r.Do(ctx, func(ctx context.Context) error {
			return &TransientError{Err: errors.New("retry"), RetryAfter: time.Hour}
		})
	}()
	// Give a moment for the first sleep to start, then cancel.
	time.Sleep(10 * time.Millisecond)
	cancel()
	got := <-errCh
	if !errors.Is(got, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", got)
	}
}

func TestDo_NonRetryableErrorsIs(t *testing.T) {
	sleeper := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := errors.New("fail")
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return fmt.Errorf("wrapped: %w", sentinel)
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected non-retryable error to match via errors.Is, got %v", err)
	}
}

// BenchmarkDo_Success measures the hot path.
func BenchmarkDo_Success(b *testing.B) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		b.Fatal(err)
	}
	ctx := context.Background()
	b.ResetTimer()
	for b.Loop() {
		_ = r.Do(ctx, func(ctx context.Context) error {
			return nil
		})
	}
}

// raceTestSleeper helps detect races under -race.
type raceTestSleeper struct{}

func (raceTestSleeper) Sleep(ctx context.Context, _ time.Duration) error {
	return ctx.Err()
}

func TestDo_NoDataRace(t *testing.T) {
	r, err := New(Config{MaxAttempts: 5, BaseDelay: 0}, Dependencies{Sleeper: raceTestSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	sentinel := errors.New("x")
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: sentinel}
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected sentinel, got %v", err)
	}
}