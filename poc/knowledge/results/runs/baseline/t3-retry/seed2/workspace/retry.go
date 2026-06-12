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
	return e.Err.Error()
}

func (e *TransientError) Unwrap() error {
	return e.Err
}

// Config controls the retry behaviour.
type Config struct {
	MaxAttempts int           // total attempts, >= 1
	BaseDelay   time.Duration // first backoff delay, >= 0
}

// Dependencies holds external services the Retrier needs.
type Dependencies struct {
	Sleeper Sleeper
}

// realSleeper is the default clock-based sleeper.
type realSleeper struct{}

func (realSleeper) Sleep(ctx context.Context, d time.Duration) error {
	timer := time.NewTimer(d)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

// Retrier executes an operation with retries and backoff.
type Retrier struct {
	config Config
	sleeper Sleeper
}

// New creates a Retrier after validating the configuration.
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

// Do calls operation up to MaxAttempts times, retrying only on *TransientError.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error

	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// Is this a retryable error?
		var transient *TransientError
		if !errors.As(err, &transient) {
			return err
		}

		// No more attempts — return the last error.
		if attempt == r.config.MaxAttempts-1 {
			break
		}

		// Determine the delay before the next attempt.
		delay := r.config.BaseDelay
		if transient.RetryAfter > 0 {
			delay = transient.RetryAfter
		} else {
			// Exponential: BaseDelay, 2*BaseDelay, 4*BaseDelay, …
			for i := 0; i < attempt; i++ {
				delay *= 2
			}
		}

		if sleepErr := r.sleeper.Sleep(ctx, delay); sleepErr != nil {
			return sleepErr
		}
	}

	return lastErr
}