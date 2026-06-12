package retry

import (
	"context"
	"errors"
	"fmt"
	"time"
)

// Sleeper waits for a duration, honoring cancellation.
type Sleeper interface {
	Sleep(ctx context.Context, duration time.Duration) error
}

// TransientError marks a failure as retryable.
type TransientError struct {
	Err        error
	RetryAfter time.Duration
}

func (e *TransientError) Error() string {
	return fmt.Sprintf("transient: %v", e.Err)
}

func (e *TransientError) Unwrap() error {
	return e.Err
}

type Config struct {
	MaxAttempts int
	BaseDelay   time.Duration
}

type Dependencies struct {
	Sleeper Sleeper
}

// systemSleeper is the default real-clock Sleeper.
type systemSleeper struct{}

func (systemSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			return nil
		}
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// Retrier retries an operation on transient failures.
type Retrier struct {
	maxAttempts int
	baseDelay   time.Duration
	sleeper     Sleeper
}

// New creates a Retrier. Returns an error if configuration is invalid.
// A nil Sleeper defaults to a real clock-based sleeper.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, fmt.Errorf("retry: MaxAttempts must be >= 1, got %d", configuration.MaxAttempts)
	}
	if configuration.BaseDelay < 0 {
		return nil, fmt.Errorf("retry: BaseDelay must be >= 0, got %v", configuration.BaseDelay)
	}

	sleeper := dependencies.Sleeper
	if sleeper == nil {
		sleeper = systemSleeper{}
	}

	return &Retrier{
		maxAttempts: configuration.MaxAttempts,
		baseDelay:   configuration.BaseDelay,
		sleeper:     sleeper,
	}, nil
}

// Do calls operation up to MaxAttempts times, retrying only on *TransientError.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error

	for attempt := 0; attempt < r.maxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// If this is the last attempt, return the error directly.
		if attempt == r.maxAttempts-1 {
			return err
		}

		// Non-transient errors are not retried.
		transient, ok := errors.AsType[*TransientError](err)
		if !ok {
			return err
		}

		// Compute delay.
		delay := r.baseDelay << uint(attempt) // baseDelay * 2^attempt
		if transient.RetryAfter > 0 {
			delay = transient.RetryAfter
		}

		// Wait before retry.
		if sleepErr := r.sleeper.Sleep(ctx, delay); sleepErr != nil {
			return sleepErr
		}
	}

	// Unreachable because the loop always returns when attempts are exhausted.
	return lastErr
}