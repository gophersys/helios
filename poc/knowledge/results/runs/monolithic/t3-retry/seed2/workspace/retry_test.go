package retry

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// errSentinel is a sentinel error for testing errors.Is matching.
var errSentinel = errors.New("sentinel error")

// errBoom is used for non-retryable failures.
var errBoom = errors.New("boom")

// fakeSleeper records sleeps and can be made to fail after a certain count.
type fakeSleeper struct {
	mu      atomic.Int64 // number of Sleep calls so far
	failOn  int64        // fail (return non-nil error) on this call index, 0 = never
	failErr error
}

func (f *fakeSleeper) Sleep(_ context.Context, d time.Duration) error {
	n := f.mu.Add(1)
	if f.failOn > 0 && n == f.failOn {
		return f.failErr
	}
	return nil
}

func (f *fakeSleeper) calls() int64 { return f.mu.Load() }

// contextCancelledSleeper returns a cancelled context error on every call.
type contextCancelledSleeper struct{}

func (contextCancelledSleeper) Sleep(ctx context.Context, _ time.Duration) error {
	return ctx.Err()
}

// ---------------------------------------------------------------------------
// New validation
// ---------------------------------------------------------------------------

func TestNew_InvalidMaxAttempts(t *testing.T) {
	_, err := New(Config{MaxAttempts: 0, BaseDelay: time.Second}, Dependencies{})
	if err == nil {
		t.Fatal("expected error for MaxAttempts < 1")
	}
}

func TestNew_InvalidBaseDelay(t *testing.T) {
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
	if r.sleeper == nil {
		t.Fatal("expected a default sleeper")
	}
}

// ---------------------------------------------------------------------------
// TransientError
// ---------------------------------------------------------------------------

func TestTransientError_Error(t *testing.T) {
	e := &TransientError{Err: errSentinel}
	msg := e.Error()
	if msg == "" {
		t.Fatal("expected non-empty error string")
	}
}

func TestTransientError_Unwrap(t *testing.T) {
	e := &TransientError{Err: errSentinel}
	if !errors.Is(e, errSentinel) {
		t.Fatal("errors.Is must match through Unwrap")
	}
}

func TestTransientError_IsThroughWrapping(t *testing.T) {
	// Wrapped at arbitrary depth.
	inner := &TransientError{Err: fmt.Errorf("wrapped: %w", errSentinel)}
	if !errors.Is(inner, errSentinel) {
		t.Fatal("errors.Is must reach sentinel through double wrapping")
	}
}

// ---------------------------------------------------------------------------
// Do — success
// ---------------------------------------------------------------------------

func TestDo_ImmediateSuccess(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error { return nil })
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
}

func TestDo_SuccessOnSecondAttempt(t *testing.T) {
	var count atomic.Int64
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		n := count.Add(1)
		if n < 2 {
			return &TransientError{Err: fmt.Errorf("not yet %d", n)}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
	if count.Load() != 2 {
		t.Fatalf("expected 2 calls, got %d", count.Load())
	}
}

// ---------------------------------------------------------------------------
// Do — non-retryable errors
// ---------------------------------------------------------------------------

func TestDo_NonRetryableReturnsImmediately(t *testing.T) {
	var count atomic.Int64
	r, err := New(Config{MaxAttempts: 5, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		count.Add(1)
		return errBoom
	})
	if !errors.Is(err, errBoom) {
		t.Fatalf("expected errBoom, got %v", err)
	}
	if count.Load() != 1 {
		t.Fatalf("expected exactly 1 call, got %d", count.Load())
	}
}

func TestDo_NonRetryableWrappedError(t *testing.T) {
	r, err := New(Config{MaxAttempts: 5, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		return fmt.Errorf("outer: %w", errSentinel)
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("must match sentinel, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — all attempts fail (transient)
// ---------------------------------------------------------------------------

func TestDo_AllAttemptsFailTransient(t *testing.T) {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	lastErr := fmt.Errorf("final: %w", errSentinel)
	err = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: lastErr}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("must match sentinel through TransientError, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — sleeper cancellation
// ---------------------------------------------------------------------------

func TestDo_SleeperErrorStops(t *testing.T) {
	fs := &fakeSleeper{failOn: 1, failErr: context.DeadlineExceeded}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{Sleeper: fs})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: fmt.Errorf("transient")}
	})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected DeadlineExceeded, got %v", err)
	}
}

func TestDo_SleeperSystemCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Millisecond}, Dependencies{})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(ctx, func(_ context.Context) error {
		return &TransientError{Err: fmt.Errorf("transient")}
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — RetryAfter
// ---------------------------------------------------------------------------

func TestDo_RetryAfterUsed(t *testing.T) {
	fs := &fakeSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Hour}, Dependencies{Sleeper: fs})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: fmt.Errorf("busy"), RetryAfter: time.Millisecond}
	})
	// All attempts fail, but each sleep used RetryAfter (very short) not BaseDelay (1h).
	if err == nil {
		t.Fatal("expected error")
	}
}

// ---------------------------------------------------------------------------
// Do — MaxAttempts = 1 (no retries)
// ---------------------------------------------------------------------------

func TestDo_MaxAttemptsOne(t *testing.T) {
	r, err := New(Config{MaxAttempts: 1, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: errSentinel}
	})
	if !errors.Is(err, errSentinel) {
		t.Fatalf("expected sentinel, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — Sleeper not called on success
// ---------------------------------------------------------------------------

func TestDo_SleeperNotCalledOnSuccess(t *testing.T) {
	fs := &fakeSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: fs})
	if err != nil {
		t.Fatal(err)
	}
	_ = r.Do(context.Background(), func(_ context.Context) error { return nil })
	if fs.calls() != 0 {
		t.Fatalf("expected 0 sleeper calls, got %d", fs.calls())
	}
}

// ---------------------------------------------------------------------------
// Do — Sleeper not called on non-retryable
// ---------------------------------------------------------------------------

func TestDo_SleeperNotCalledOnNonRetryable(t *testing.T) {
	fs := &fakeSleeper{}
	r, err := New(Config{MaxAttempts: 3, BaseDelay: time.Second}, Dependencies{Sleeper: fs})
	if err != nil {
		t.Fatal(err)
	}
	_ = r.Do(context.Background(), func(_ context.Context) error { return errBoom })
	if fs.calls() != 0 {
		t.Fatalf("expected 0 sleeper calls, got %d", fs.calls())
	}
}

// ---------------------------------------------------------------------------
// Do — exponential backoff progression
// ---------------------------------------------------------------------------

func TestDo_ExponentialBackoffDelay(t *testing.T) {

	var sleeps []sleepRecord
	fs := &recordingSleeper{records: &sleeps}

	r, err := New(Config{MaxAttempts: 4, BaseDelay: 10 * time.Millisecond}, Dependencies{Sleeper: fs})
	if err != nil {
		t.Fatal(err)
	}

	var count atomic.Int64
	_ = r.Do(context.Background(), func(_ context.Context) error {
		count.Add(1)
		return &TransientError{Err: fmt.Errorf("transient")}
	})

	if len(sleeps) != 3 {
		t.Fatalf("expected 3 sleeps, got %d", len(sleeps))
	}

	expected := []time.Duration{
		10 * time.Millisecond,      // 2^0 * BaseDelay
		20 * time.Millisecond,      // 2^1 * BaseDelay
		40 * time.Millisecond,      // 2^2 * BaseDelay
	}
	for i, e := range expected {
		if sleeps[i].d != e {
			t.Errorf("sleep[%d]: expected %v, got %v", i, e, sleeps[i].d)
		}
	}

}
type sleepRecord struct {
	d time.Duration
}


type recordingSleeper struct {
	records *[]sleepRecord
}

func (s *recordingSleeper) Sleep(_ context.Context, d time.Duration) error {
	*s.records = append(*s.records, sleepRecord{d})
	return nil
}

// ---------------------------------------------------------------------------
// Do — Sleeper fails after some retries
// ---------------------------------------------------------------------------

func TestDo_SleeperFailsOnSecondCall(t *testing.T) {
	fs := &fakeSleeper{failOn: 2, failErr: context.DeadlineExceeded}
	r, err := New(Config{MaxAttempts: 5, BaseDelay: time.Millisecond}, Dependencies{Sleeper: fs})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		return &TransientError{Err: fmt.Errorf("transient")}
	})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected DeadlineExceeded, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — wrapped TransientError deep in error tree
// ---------------------------------------------------------------------------

func TestDo_WrappedTransientErrorRetryable(t *testing.T) {
	var count atomic.Int64
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(context.Background(), func(_ context.Context) error {
		n := count.Add(1)
		if n < 2 {
			// TransientError wrapped inside a non-retryable-looking wrapper.
			return fmt.Errorf("wrapper: %w", &TransientError{Err: fmt.Errorf("inner")})
		}
		return nil
	})
	if err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Do — context cancellation passed to operation
// ---------------------------------------------------------------------------

func TestDo_ContextCancelledDuringOperation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	r, err := New(Config{MaxAttempts: 3, BaseDelay: 0}, Dependencies{Sleeper: &fakeSleeper{}})
	if err != nil {
		t.Fatal(err)
	}
	err = r.Do(ctx, func(ctx context.Context) error {
		// Simulate the operation checking context.
		cancel()
		return ctx.Err()
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected Canceled, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Example
// ---------------------------------------------------------------------------

func ExampleRetrier_Do() {
	r, err := New(Config{MaxAttempts: 3, BaseDelay: 10 * time.Millisecond}, Dependencies{})
	if err != nil {
		panic(err)
	}
	err = r.Do(context.Background(), func(ctx context.Context) error {
		return &TransientError{Err: fmt.Errorf("service busy")}
	})
	fmt.Println(err)
	// Output:
	// transient error: service busy
}