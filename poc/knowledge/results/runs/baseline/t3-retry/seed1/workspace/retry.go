package retry

import (
	"context"
	"errors"
	"time"
)

// Sleeper waits for a duration, honoring cancellation.
type Sleeper interface {
	Sleep(ctx context.Context, duration time.Duration) error
}

// TransientError marks a failure as retryable.
type TransientError struct {
	Err        error
	RetryAfter time.Duration // optional server-suggested delay
}

func (e *TransientError) Error() string {
	if e.Err == nil {
		return ""
	}
	return e.Err.Error()
}

func (e *TransientError) Unwrap() error {
	return e.Err
}

// Config configures backoff and attempt limits.
type Config struct {
	MaxAttempts int           // total attempts, >= 1
	BaseDelay   time.Duration // first backoff delay, >= 0
}

// Dependencies wires external services.
type Dependencies struct {
	Sleeper Sleeper
}

// Retrier executes an operation with retry and backoff.
type Retrier struct {
	config  Config
	sleeper Sleeper
}

// realSleeper is the default clock-based Sleeper.
type realSleeper struct{}

func (realSleeper) Sleep(ctx context.Context, d time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(d):
		return nil
	}
}

// New validates configuration and returns a Retrier.
func New(config Config, deps Dependencies) (*Retrier, error) {
	if config.MaxAttempts < 1 {
		return nil, errors.New("retry: MaxAttempts must be >= 1")
	}
	if config.BaseDelay < 0 {
		return nil, errors.New("retry: BaseDelay must be >= 0")
	}
	sleeper := deps.Sleeper
	if sleeper == nil {
		sleeper = realSleeper{}
	}
	return &Retrier{config: config, sleeper: sleeper}, nil
}

// Do calls operation up to MaxAttempts times, retrying only on
// *TransientError failures with exponential backoff.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error

	for attempt := 1; attempt <= r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}
		lastErr = err

		// Last attempt — no sleep, return last failure.
		if attempt == r.config.MaxAttempts {
			return lastErr
		}

		// Only retryable when a *TransientError is in the error tree.
		var transient *TransientError
		if !errors.As(err, &transient) {
			return err
		}

		delay := r.backoff(attempt, transient.RetryAfter)
		if sleepErr := r.sleeper.Sleep(ctx, delay); sleepErr != nil {
			return sleepErr
		}
	}

	return lastErr
}

// backoff returns the sleep delay before the next retry.
// Uses RetryAfter when > 0, otherwise exponential backoff from BaseDelay.
func (r *Retrier) backoff(attempt int, retryAfter time.Duration) time.Duration {
	if retryAfter > 0 {
		return retryAfter
	}
	// attempt 1 -> 2^0 = 1
	// attempt 2 -> 2^1 = 2
	// attempt 3 -> 2^2 = 4
	return r.config.BaseDelay * time.Duration(1<<uint(attempt-1))
}
