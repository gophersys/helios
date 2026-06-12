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

// defaultSleeper uses time.After to sleep, respecting context cancellation.
type defaultSleeper struct{}

func (defaultSleeper) Sleep(ctx context.Context, d time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(d):
		return nil
	}
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

// Config controls retry behaviour.
type Config struct {
	MaxAttempts int
	BaseDelay   time.Duration
}

// Dependencies holds injected services.
type Dependencies struct {
	Sleeper Sleeper
}

// Retrier executes an operation with retry.
type Retrier struct {
	config  Config
	sleeper Sleeper
}

// New creates a Retrier, validating configuration. A nil Sleeper defaults to a
// real clock-based sleeper.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, fmt.Errorf("retry: MaxAttempts must be >= 1, got %d", configuration.MaxAttempts)
	}
	if configuration.BaseDelay < 0 {
		return nil, fmt.Errorf("retry: BaseDelay must be >= 0, got %v", configuration.BaseDelay)
	}
	sleeper := dependencies.Sleeper
	if sleeper == nil {
		sleeper = defaultSleeper{}
	}
	return &Retrier{
		config:  configuration,
		sleeper: sleeper,
	}, nil
}

// Do calls operation up to MaxAttempts times, retrying only when a
// *TransientError is found in the error tree.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error
	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}
		lastErr = err

		// Is this error retryable?
		tErr, ok := errors.AsType[*TransientError](err)
		if !ok {
			return err
		}

		// Last attempt — retry would be pointless.
		if attempt == r.config.MaxAttempts-1 {
			return err
		}

		// Compute delay: prefer RetryAfter from the error, fall back to
		// exponential backoff (BaseDelay, 2*BaseDelay, 4*BaseDelay, …).
		delay := r.config.BaseDelay << attempt
		if tErr.RetryAfter > 0 {
			delay = tErr.RetryAfter
		}
		if err := r.sleeper.Sleep(ctx, delay); err != nil {
			return err
		}
	}
	return lastErr
}