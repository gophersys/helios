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

type Config struct {
	MaxAttempts int           // total attempts, >= 1
	BaseDelay   time.Duration // first backoff delay, >= 0
}

type Dependencies struct {
	Sleeper Sleeper
}

type Retrier struct {
	config Config
	deps   Dependencies
}

// realSleeper is the default clock-based sleeper.
type realSleeper struct{}

func (s *realSleeper) Sleep(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// New creates a Retrier, validating the configuration.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, errors.New("retry: MaxAttempts must be >= 1")
	}
	if configuration.BaseDelay < 0 {
		return nil, errors.New("retry: BaseDelay must be >= 0")
	}
	if dependencies.Sleeper == nil {
		dependencies.Sleeper = &realSleeper{}
	}
	return &Retrier{
		config: configuration,
		deps:   dependencies,
	}, nil
}

// Do calls operation up to MaxAttempts times, retrying on transient errors.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error
	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}
		lastErr = err

		// On the last attempt, return the error directly.
		if attempt == r.config.MaxAttempts-1 {
			return lastErr
		}

		// Only retry if the error tree contains a *TransientError.
		transient, ok := errors.AsType[*TransientError](err)
		if ok {
			delay := transient.RetryAfter
			if delay <= 0 {
				delay = r.config.BaseDelay << attempt // exponential: BaseDelay, 2x, 4x, ...
			}
			if sleepErr := r.deps.Sleeper.Sleep(ctx, delay); sleepErr != nil {
				return sleepErr
			}
		} else {
			// Non-retryable failure — return immediately.
			return err
		}
	}
	return lastErr
}
