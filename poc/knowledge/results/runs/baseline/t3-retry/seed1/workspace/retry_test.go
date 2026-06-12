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

// spySleeper records calls and can be programmed to fail.
type spySleeper struct {
	mu     sync.Mutex
	calls  []time.Duration
	failOn int // 1-indexed; if set, the Nth call returns an error
	failErr error
}

func (s *spySleeper) Sleep(_ context.Context, d time.Duration) error {
	s.mu.Lock()
	s.calls = append(s.calls, d)
	fail := len(s.calls) == s.failOn
	err := s.failErr
	s.mu.Unlock()
	if fail {
		return err
	}
	return nil
}

func (s *spySleeper) Delays() []time.Duration {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]time.Duration, len(s.calls))
	copy(out, s.calls)
	return out
}

// errSentinel is a non-transient error for testing.
var errSentinel = errors.New("boom")

func TestNewValidation(t *testing.T) {
	tests := []struct {
		name string
		cfg  Config
	}{
		{"zero attempts", Config{MaxAttempts: 0, BaseDelay: 0}},
		{"negative attempts", Config{MaxAttempts: -1, BaseDelay: 0}},
		{"negative base delay", Config{MaxAttempts: 1, BaseDelay: -1}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(tt.cfg, Dependencies{})
			if err == nil {
				t.Fatal("expected error")
			}
		})
	}
}

func TestNewNilSleeperDefault(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{Sleeper: nil})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if r.sleeper == nil {
		t.Fatal("expected non-nil sleeper")
	}
}

func TestDoSuccessFirstAttempt(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond})
	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 call, got %d", count)
	}
}

func TestDoNonRetryableErrorReturnsImmediately(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond})
	s := &spySleeper{}
	r.sleeper = s

	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		return errSentinel
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected errSentinel, got %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 call, got %d", count)
	}
	if len(s.calls) != 0 {
		t.Fatalf("expected no sleep, got %d", len(s.calls))
	}
}

func TestDoWrappedNonRetryable(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond})
	err := r.Do(context.Background(), func(ctx context.Context) error {
		return fmt.Errorf("wrapped: %w", errSentinel)
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected error to match errSentinel via errors.Is, got %v", err)
	}
}

func TestDoWrappedTransientErrorStillRetryable(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond})
	s := &spySleeper{}
	r.sleeper = s

	var count atomic.Int32
	err := r.Do(context.Background(), func(ctx context.Context) error {
		n := count.Add(1)
		if n < 3 {
			return fmt.Errorf("outer: %w", &TransientError{Err: errSentinel})
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if count.Load() != 3 {
		t.Fatalf("expected 3 calls, got %d", count.Load())
	}
}

func TestDoTransientWithRetryAfter(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Hour}) // large base; RetryAfter should override
	s := &spySleeper{}
	r.sleeper = s

	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		if count < 2 {
			return &TransientError{Err: errSentinel, RetryAfter: 5 * time.Millisecond}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	delays := s.Delays()
	if len(delays) != 1 {
		t.Fatalf("expected 1 sleep, got %d", len(delays))
	}
	if delays[0] != 5*time.Millisecond {
		t.Fatalf("expected 5ms delay, got %v", delays[0])
	}
}

func TestDoExponentialBackoff(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 5, BaseDelay: 10 * time.Millisecond})
	s := &spySleeper{}
	r.sleeper = s

	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		if count < 5 {
			return &TransientError{Err: errSentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	expected := []time.Duration{
		10 * time.Millisecond,       // 2^0 * 10ms
		20 * time.Millisecond,       // 2^1 * 10ms
		40 * time.Millisecond,       // 2^2 * 10ms
		80 * time.Millisecond,       // 2^3 * 10ms
	}
	delays := s.Delays()
	if len(delays) != len(expected) {
		t.Fatalf("expected %d delays, got %d: %v", len(expected), len(delays), delays)
	}
	for i := range expected {
		if delays[i] != expected[i] {
			t.Errorf("delay %d: expected %v, got %v", i, expected[i], delays[i])
		}
	}
}

func TestDoContextCancelledDuringSleep(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Hour}) // long enough to trigger cancellation
	ctx, cancel := context.WithCancel(context.Background())

	var count int
	errCh := make(chan error, 1)
	go func() {
		errCh <- r.Do(ctx, func(ctx context.Context) error {
			count++
			return &TransientError{Err: errSentinel}
		})
	}()
	// Wait for the sleep to start, then cancel.
	time.Sleep(10 * time.Millisecond)
	cancel()

	select {
	case err := <-errCh:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("expected context.Canceled, got %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for Do to return")
	}
}

func TestDoAllAttemptsFail(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: time.Millisecond})

	var count int
	finalErr := fmt.Errorf("final: %w", &TransientError{Err: errSentinel})
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		if count < 3 {
			return &TransientError{Err: errSentinel}
		}
		return finalErr
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected last error to match errSentinel via errors.Is, got %v", err)
	}
	if count != 3 {
		t.Fatalf("expected 3 calls, got %d", count)
	}
}

func TestDoZeroBaseDelay(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: 0})
	s := &spySleeper{}
	r.sleeper = s

	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		if count < 3 {
			return &TransientError{Err: errSentinel}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	// With BaseDelay=0, exponential backoff is still 0*2^N = 0.
	delays := s.Delays()
	if len(delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(delays))
	}
	for i, d := range delays {
		if d != 0 {
			t.Errorf("delay %d: expected 0, got %v", i, d)
		}
	}
}

func TestDoSleeperErrorStops(t *testing.T) {
	sleepErr := errors.New("sleep failed")
	r := mustNew(t, Config{MaxAttempts: 5, BaseDelay: time.Millisecond})
	s := &spySleeper{failOn: 1, failErr: sleepErr}
	r.sleeper = s

	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, sleepErr) {
		t.Fatalf("expected sleepErr, got %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 operation call, got %d", count)
	}
}

func TestDoRetryAfterZeroFallsBackToExponential(t *testing.T) {
	r := mustNew(t, Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond})
	s := &spySleeper{}
	r.sleeper = s

	var count int
	err := r.Do(context.Background(), func(ctx context.Context) error {
		count++
		if count < 3 {
			return &TransientError{Err: errSentinel, RetryAfter: 0}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	delays := s.Delays()
	if len(delays) != 2 {
		t.Fatalf("expected 2 sleeps, got %d", len(delays))
	}
	if delays[0] != 10*time.Millisecond {
		t.Errorf("delay 0: expected 10ms, got %v", delays[0])
	}
	if delays[1] != 20*time.Millisecond {
		t.Errorf("delay 1: expected 20ms, got %v", delays[1])
	}
}

// mustNew creates a Retrier, failing the test on error.
func mustNew(t testing.TB, cfg Config) *Retrier {
	t.Helper()
	r, err := New(cfg, Dependencies{})
	if err != nil {
		t.Fatalf("New(%+v): %v", cfg, err)
	}
	return r
}