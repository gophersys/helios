package retry

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"
)

// mockSleeper records delays and optionally fails all Sleep calls.
type mockSleeper struct {
	delays []time.Duration
	err    error
}

func (m *mockSleeper) Sleep(_ context.Context, d time.Duration) error {
	m.delays = append(m.delays, d)
	return m.err
}

// errFail is a sentinel for non-retryable failures.
var errFail = errors.New("fail")

// errTransient is a sentinel wrapped in TransientError.
func transientErr(wrapped error, retryAfter ...time.Duration) error {
	e := &TransientError{Err: wrapped}
	if len(retryAfter) > 0 {
		e.RetryAfter = retryAfter[0]
	}
	return e
}

func TestNewValidation(t *testing.T) {
	tests := []struct {
		name    string
		config  Config
		wantErr bool
	}{
		{"valid minimal", Config{MaxAttempts: 1, BaseDelay: 0}, false},
		{"valid normal", Config{MaxAttempts: 3, BaseDelay: time.Second}, false},
		{"zero attempts", Config{MaxAttempts: 0, BaseDelay: 0}, true},
		{"negative attempts", Config{MaxAttempts: -1, BaseDelay: 0}, true},
		{"negative delay", Config{MaxAttempts: 1, BaseDelay: -1}, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(tt.config, Dependencies{Sleeper: &mockSleeper{}})
			if (err != nil) != tt.wantErr {
				t.Fatalf("New() error = %v, wantErr = %v", err, tt.wantErr)
			}
		})
	}
}

func TestNewDefaultSleeper(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}
	if r.sleeper == nil {
		t.Fatal("expected non-nil default sleeper")
	}
}

func TestDoImmediateSuccess(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: &mockSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
}

func TestDoNonRetryable(t *testing.T) {
	mock := &mockSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return errFail
	})
	if !errors.Is(err, errFail) {
		t.Fatalf("expected errFail, got %v", err)
	}
	if len(mock.delays) > 0 {
		t.Fatal("expected no sleeps for non-retryable error")
	}
}

func TestDoRetryThenSuccess(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})

	attempt := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempt++
		if attempt < 3 {
			return transientErr(errFail)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if attempt != 3 {
		t.Fatalf("expected 3 attempts, got %d", attempt)
	}
}

func TestDoAllFail(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})

	someErr := errors.New("last failure")
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return transientErr(someErr)
	})
	if !errors.Is(err, someErr) {
		t.Fatalf("expected last error via errors.Is, got %v", err)
	}
}

func TestDoNonRetryableEndsImmediately(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 5, BaseDelay: time.Hour}, Dependencies{Sleeper: mock})

	attempt := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempt++
		return errFail
	})
	if !errors.Is(err, errFail) {
		t.Fatalf("expected errFail, got %v", err)
	}
	if attempt != 1 {
		t.Fatalf("expected only 1 attempt, got %d", attempt)
	}
}

func TestDoBackoffDelays(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 4, BaseDelay: 10 * time.Millisecond}, Dependencies{Sleeper: mock})

	_ = r.Do(context.Background(), func(ctx context.Context) error {
		return transientErr(errFail)
	})

	want := []time.Duration{
		10 * time.Millisecond,  // attempt 0 -> BaseDelay * 2^0
		20 * time.Millisecond,  // attempt 1 -> BaseDelay * 2^1
		40 * time.Millisecond,  // attempt 2 -> BaseDelay * 2^2
	}
	// Last (4th) attempt fails; no sleep after.
	if len(mock.delays) != len(want) {
		t.Fatalf("expected %d sleeps, got %d: %v", len(want), len(mock.delays), mock.delays)
	}
	for i, d := range mock.delays {
		if d != want[i] {
			t.Errorf("sleep %d: expected %v, got %v", i, want[i], d)
		}
	}
}

func TestDoRetryAfter(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: time.Minute}, Dependencies{Sleeper: mock})

	suggested := 5 * time.Millisecond
	_ = r.Do(context.Background(), func(ctx context.Context) error {
		return transientErr(errFail, suggested)
	})

	if len(mock.delays) == 0 {
		t.Fatal("expected at least one sleep")
	}
	for i, d := range mock.delays {
		if d != suggested {
			t.Errorf("sleep %d: expected %v (RetryAfter), got %v", i, suggested, d)
		}
	}
}

func TestDoSleeperError(t *testing.T) {
	sleepErr := errors.New("sleeper is sad")
	mock := &mockSleeper{err: sleepErr}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return transientErr(errFail)
	})
	if !errors.Is(err, sleepErr) {
		t.Fatalf("expected sleepErr via errors.Is, got %v", err)
	}
}

func TestDoContextCancelled(t *testing.T) {
	// Use the real sleeper with a cancelled context.
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{})

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	attempt := 0
	err := r.Do(ctx, func(ctx context.Context) error {
		attempt++
		return transientErr(errFail)
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
	if attempt != 1 {
		t.Fatalf("expected exactly 1 attempt before cancellation, got %d", attempt)
	}
}

func TestDoContextCancelledDuringSleep(t *testing.T) {
	// Sleeper that blocks forever; cancellation should unblock it.
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{})

	ctx, cancel := context.WithCancel(context.Background())
	// Cancel after a very short delay.
	go func() {
		time.Sleep(time.Millisecond)
		cancel()
	}()

	err := r.Do(ctx, func(ctx context.Context) error {
		return transientErr(errFail)
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestDoTransientErrorWrapped(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})

	wrapped := fmt.Errorf("outer: %w", transientErr(errFail))
	attempt := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		attempt++
		if attempt < 3 {
			return wrapped
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if attempt != 3 {
		t.Fatalf("expected 3 attempts, got %d", attempt)
	}

	// Verify the returned error on a failure path also matches.
	mock2 := &mockSleeper{}
	r2, _ := New(Config{MaxAttempts: 2, BaseDelay: 0}, Dependencies{Sleeper: mock2})
	err2 := r2.Do(context.Background(), func(ctx context.Context) error {
		return wrapped
	})
	if !errors.Is(err2, errFail) {
		t.Fatalf("expected errFail via errors.Is on wrapped transient, got %v", err2)
	}
}

func TestDoSingleAttempt(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{Sleeper: mock})

	err := r.Do(context.Background(), func(ctx context.Context) error {
		return transientErr(errFail)
	})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	// Should not have slept on single-attempt.
	if len(mock.delays) > 0 {
		t.Fatal("expected no sleep for single-attempt config")
	}
}

func TestDoReturnsOriginalErrorDirectly(t *testing.T) {
	// Verify that a non-retryable error returned from Do is the exact same
	// pointer (errors.Is works because they are the same value).
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})

	sentinel := errors.New("unique sentinel")
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return sentinel
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("expected errors.Is to match sentinel")
	}
}

func TestDoReturnsLastTransientError(t *testing.T) {
	mock := &mockSleeper{}
	r, _ := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: mock})

	last := errors.New("last attempt error")
	callCount := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		callCount++
		if callCount < 3 {
			return transientErr(errors.New("intermediate"))
		}
		return transientErr(last)
	})
	if !errors.Is(err, last) {
		t.Fatalf("expected last error via errors.Is, got %v", err)
	}
}
