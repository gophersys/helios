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
	RetryAfter time.Duration
}

func (e *TransientError) Error() string {
	return "transient: " + e.Err.Error()
}

func (e *TransientError) Unwrap() error {
	return e.Err
}

// Config controls the retry loop.
type Config struct {
	MaxAttempts int
	BaseDelay   time.Duration
}

// Dependencies holds injected services.
type Dependencies struct {
	Sleeper Sleeper
}

// Retrier executes operations with retry and backoff.
type Retrier struct {
	config  Config
	sleeper Sleeper
}

// New validates configuration and returns a Retrier.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, errors.New("MaxAttempts must be >= 1")
	}
	if configuration.BaseDelay < 0 {
		return nil, errors.New("BaseDelay must be >= 0")
	}
	s := dependencies.Sleeper
	if s == nil {
		s = &clockSleeper{}
	}
	return &Retrier{
		config:  configuration,
		sleeper: s,
	}, nil
}

// Do calls operation up to MaxAttempts times with backoff.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error
	delay := r.config.BaseDelay

	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// Non-retryable errors are returned immediately.
		transient, ok := errors.AsType[*TransientError](err)
		if !ok {
			return err
		}

		// If this was the last attempt, don't sleep — return the error.
		if attempt == r.config.MaxAttempts-1 {
			break
		}

		sleepDuration := transient.RetryAfter
		if sleepDuration <= 0 {
			sleepDuration = delay
		}

		if sleepDuration > 0 {
			if sleeperErr := r.sleeper.Sleep(ctx, sleepDuration); sleeperErr != nil {
				return sleeperErr
			}
		}

		delay *= 2
	}

	return lastErr
}

// clockSleeper is the default real-time Sleeper.
type clockSleeper struct{}

func (c *clockSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		return nil
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