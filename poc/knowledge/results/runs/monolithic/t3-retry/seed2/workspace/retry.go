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
	return fmt.Sprintf("transient error: %v", e.Err)
}

func (e *TransientError) Unwrap() error {
	return e.Err
}

// Config configures retry behaviour.
type Config struct {
	MaxAttempts int
	BaseDelay   time.Duration
}

// Dependencies holds injected dependencies for the Retrier.
type Dependencies struct {
	Sleeper Sleeper
}

// Retrier executes an operation with retries and backoff.
type Retrier struct {
	config  Config
	sleeper Sleeper
}

// New creates a Retrier. Returns an error if configuration is invalid.
// A nil Sleeper defaults to a real clock-based sleeper.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, errors.New("retry: MaxAttempts must be >= 1")
	}
	if configuration.BaseDelay < 0 {
		return nil, errors.New("retry: BaseDelay must be >= 0")
	}
	sleeper := dependencies.Sleeper
	if sleeper == nil {
		sleeper = systemSleeper{}
	}
	return &Retrier{
		config:  configuration,
		sleeper: sleeper,
	}, nil
}

// Do calls operation up to MaxAttempts times.
//   - A nil return stops immediately.
//   - A non-retryable error (no *TransientError in the tree) stops immediately.
//   - A retryable error waits using backoff (or RetryAfter if > 0), then retries.
//   - If the Sleeper returns an error (e.g. context cancelled), Do stops.
//   - When all attempts fail, the last error is returned.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error
	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		lastErr = operation(ctx)
		if lastErr == nil {
			return nil
		}

		transient, ok := errors.AsType[*TransientError](lastErr)
		if !ok {
			return lastErr
		}

		// Last attempt — no sleep, return the transient error.
		if attempt == r.config.MaxAttempts-1 {
			return lastErr
		}

		delay := r.backoff(attempt, transient.RetryAfter)
		if err := r.sleeper.Sleep(ctx, delay); err != nil {
			return err
		}
	}
	// Unreachable for MaxAttempts >= 1; kept for completeness.
	return lastErr
}

// backoff computes the delay before the next retry.
func (r *Retrier) backoff(attempt int, retryAfter time.Duration) time.Duration {
	if retryAfter > 0 {
		return retryAfter
	}
	return r.config.BaseDelay * time.Duration(1<<attempt)
}

// systemSleeper is the default clock-based Sleeper.
type systemSleeper struct{}

func (systemSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if d == 0 {
		// Still check for cancellation.
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			return nil
		}
	}
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}