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

// Config holds retry configuration.
type Config struct {
	MaxAttempts int           // total attempts, >= 1
	BaseDelay   time.Duration // first backoff delay, >= 0
}

// Dependencies holds external dependencies for the retrier.
type Dependencies struct {
	Sleeper Sleeper
}

type Retrier struct {
	config Config
	sleeper Sleeper
}

// New creates a Retrier, validating configuration. A nil Sleeper defaults
// to a real clock-based sleeper that respects context cancellation.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, errors.New("MaxAttempts must be >= 1")
	}
	if configuration.BaseDelay < 0 {
		return nil, errors.New("BaseDelay must be >= 0")
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

// Do calls operation up to MaxAttempts times, retrying on *TransientError.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error

	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// Check if the error is retryable via *TransientError in the error tree.
		transient, ok := errors.AsType[*TransientError](err)
		if !ok {
			// Non-retryable — return immediately.
			return err
		}

		// Last attempt? Return the error.
		if attempt == r.config.MaxAttempts-1 {
			return err
		}

		// Compute delay.
		var delay time.Duration
		if transient.RetryAfter > 0 {
			delay = transient.RetryAfter
		} else {
			delay = r.config.BaseDelay << uint(attempt) // exponential: BaseDelay * 2^attempt
		}

		// Sleep, respecting cancellation.
		if sleepErr := r.sleeper.Sleep(ctx, delay); sleepErr != nil {
			return sleepErr
		}
	}

	// All attempts exhausted; return last error.
	return lastErr
}

// defaultSleeper uses time.Sleep with context cancellation, matching
// the Sleep interface.
type defaultSleeper struct{}

func (defaultSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		return nil
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