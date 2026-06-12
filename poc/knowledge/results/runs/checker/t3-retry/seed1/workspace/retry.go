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
	RetryAfter time.Duration // optional server-suggested delay
}

func (e *TransientError) Error() string {
	return e.Err.Error()
}

func (e *TransientError) Unwrap() error {
	return e.Err
}

// Config holds configuration for the retrier.
type Config struct {
	MaxAttempts int           // total attempts, >= 1
	BaseDelay   time.Duration // first backoff delay, >= 0
}

// Dependencies holds the injected dependencies for the retrier.
type Dependencies struct {
	Sleeper Sleeper
}

// Retrier executes operations with retry logic.
type Retrier struct {
	config  Config
	sleeper Sleeper
}

// New creates a Retrier. Returns an error if MaxAttempts < 1 or BaseDelay < 0.
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
		sleeper = &clockSleeper{}
	}
	return &Retrier{
		config:  configuration,
		sleeper: sleeper,
	}, nil
}

// clockSleeper is the default real-time Sleeper.
type clockSleeper struct{}

func (s *clockSleeper) Sleep(ctx context.Context, d time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(d):
		return nil
	}
}

// Do calls operation up to MaxAttempts times.
//   - Success (nil error) returns nil immediately.
//   - A failure is retryable only when a *TransientError is present in the error tree.
//   - A non-retryable failure is returned immediately.
//   - Before each retry, wait using the Sleeper: use RetryAfter when > 0, else exponential backoff.
//   - If the Sleeper returns an error, Do stops and returns an error matching it via errors.Is.
//   - When all attempts fail, the returned error matches the last failure via errors.Is.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	delay := r.config.BaseDelay

	for attempt := range r.config.MaxAttempts {
		err := operation(ctx)
		if err == nil {
			return nil
		}

		// Check if retryable using errors.AsType (Go 1.26).
		transient, ok := errors.AsType[*TransientError](err)
		if !ok {
			return err
		}

		// Last attempt? Don't sleep, return the error.
		if attempt == r.config.MaxAttempts-1 {
			return err
		}

		// Determine delay for this retry.
		sleepDuration := delay
		if transient.RetryAfter > 0 {
			sleepDuration = transient.RetryAfter
		}

		// Sleep, honoring context cancellation.
		if sleeperErr := r.sleeper.Sleep(ctx, sleepDuration); sleeperErr != nil {
			return sleeperErr
		}

		// Exponential backoff for next retry.
		delay *= 2
	}

	return nil // unreachable for valid config (MaxAttempts >= 1)
}
