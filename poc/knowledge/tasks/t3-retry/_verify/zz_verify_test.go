package retry_test

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"

	retry "example.helios/retry"
)

type recordingSleeper struct {
	slept []time.Duration
	fail  error
}

func (s *recordingSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if s.fail != nil {
		return s.fail
	}
	s.slept = append(s.slept, d)
	return nil
}

func newRetrier(t *testing.T, attempts int, base time.Duration, sleeper retry.Sleeper) *retry.Retrier {
	t.Helper()
	r, err := retry.New(retry.Config{MaxAttempts: attempts, BaseDelay: base}, retry.Dependencies{Sleeper: sleeper})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return r
}

func TestVerifySucceedsAfterTransientFailures(t *testing.T) {
	sleeper := &recordingSleeper{}
	r := newRetrier(t, 5, 10*time.Millisecond, sleeper)

	calls := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		if calls < 3 {
			return &retry.TransientError{Err: errors.New("flaky")}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("Do: %v", err)
	}
	if calls != 3 {
		t.Fatalf("calls = %d; want 3", calls)
	}
	want := []time.Duration{10 * time.Millisecond, 20 * time.Millisecond}
	if len(sleeper.slept) != len(want) || sleeper.slept[0] != want[0] || sleeper.slept[1] != want[1] {
		t.Fatalf("slept = %v; want %v (exponential backoff)", sleeper.slept, want)
	}
}

func TestVerifyWrappedTransientIsDetected(t *testing.T) {
	sleeper := &recordingSleeper{}
	r := newRetrier(t, 3, time.Millisecond, sleeper)

	calls := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		if calls == 1 {
			// transient buried one level deep in the tree
			return fmt.Errorf("calling upstream: %w", &retry.TransientError{Err: errors.New("503")})
		}
		return nil
	})
	if err != nil || calls != 2 {
		t.Fatalf("Do = %v after %d calls; want nil after 2 (wrapped transient must retry)", err, calls)
	}
}

func TestVerifyRetryAfterOverridesBackoff(t *testing.T) {
	sleeper := &recordingSleeper{}
	r := newRetrier(t, 3, time.Millisecond, sleeper)

	calls := 0
	_ = r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		if calls == 1 {
			return &retry.TransientError{Err: errors.New("busy"), RetryAfter: 50 * time.Millisecond}
		}
		return nil
	})
	if len(sleeper.slept) != 1 || sleeper.slept[0] != 50*time.Millisecond {
		t.Fatalf("slept = %v; want [50ms] (RetryAfter overrides backoff)", sleeper.slept)
	}
}

func TestVerifyNonTransientFailsImmediately(t *testing.T) {
	sleeper := &recordingSleeper{}
	r := newRetrier(t, 5, time.Millisecond, sleeper)

	sentinel := errors.New("permanent")
	calls := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return sentinel
	})
	if calls != 1 {
		t.Fatalf("calls = %d; want 1 (non-transient must not retry)", calls)
	}
	if !errors.Is(err, sentinel) {
		t.Fatalf("err = %v; want errors.Is(err, sentinel)", err)
	}
	if len(sleeper.slept) != 0 {
		t.Fatalf("slept = %v; want none", sleeper.slept)
	}
}

func TestVerifyExhaustionReturnsLastError(t *testing.T) {
	sleeper := &recordingSleeper{}
	r := newRetrier(t, 3, time.Millisecond, sleeper)

	sentinel := errors.New("still down")
	calls := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &retry.TransientError{Err: sentinel}
	})
	if calls != 3 {
		t.Fatalf("calls = %d; want 3 (MaxAttempts)", calls)
	}
	if !errors.Is(err, sentinel) {
		t.Fatalf("err = %v; want errors.Is(err, sentinel)", err)
	}
}

func TestVerifySleeperCancellationStopsRetrying(t *testing.T) {
	sleeper := &recordingSleeper{fail: context.Canceled}
	r := newRetrier(t, 5, time.Millisecond, sleeper)

	calls := 0
	err := r.Do(context.Background(), func(ctx context.Context) error {
		calls++
		return &retry.TransientError{Err: errors.New("flaky")}
	})
	if calls != 1 {
		t.Fatalf("calls = %d; want 1 (sleep failed)", calls)
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("err = %v; want errors.Is(err, context.Canceled)", err)
	}
}

func TestVerifyValidationAndDefaults(t *testing.T) {
	if _, err := retry.New(retry.Config{MaxAttempts: 0}, retry.Dependencies{}); err == nil {
		t.Fatal("MaxAttempts 0: want error")
	}
	if _, err := retry.New(retry.Config{MaxAttempts: 1, BaseDelay: -time.Second}, retry.Dependencies{}); err == nil {
		t.Fatal("negative BaseDelay: want error")
	}
	// nil sleeper defaults to a real one; a success-first operation never sleeps
	r, err := retry.New(retry.Config{MaxAttempts: 2, BaseDelay: time.Hour}, retry.Dependencies{})
	if err != nil {
		t.Fatalf("New with nil sleeper: %v", err)
	}
	if err := r.Do(context.Background(), func(ctx context.Context) error { return nil }); err != nil {
		t.Fatalf("Do: %v", err)
	}
}
