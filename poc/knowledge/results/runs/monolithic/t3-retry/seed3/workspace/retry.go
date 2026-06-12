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

type Retrier struct {
	maxAttempts int
	baseDelay   time.Duration
	sleeper     Sleeper
}

// New creates a Retrier. A nil Sleeper defaults to a real clock-based sleeper.
func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, errors.New("retry: MaxAttempts must be >= 1")
	}
	if configuration.BaseDelay < 0 {
		return nil, errors.New("retry: BaseDelay must be >= 0")
	}
	if dependencies.Sleeper == nil {
		dependencies.Sleeper = systemClockSleeper{}
	}
	return &Retrier{
		maxAttempts: configuration.MaxAttempts,
		baseDelay:   configuration.BaseDelay,
		sleeper:     dependencies.Sleeper,
	}, nil
}

// Do calls operation up to MaxAttempts times.
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error

	for attempt := 0; attempt < r.maxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// Check if this is a retryable error.
		transient, ok := errors.AsType[*TransientError](err)
		if !ok {
			// Non-retryable: return immediately.
			return err
		}

		// Last attempt: don't sleep, just let it fall through to return lastErr.
		if attempt == r.maxAttempts-1 {
			break
		}

		// Compute delay.
		delay := r.baseDelay << uint(attempt) // exponential: base, 2*base, 4*base, ...
		if transient.RetryAfter > 0 {
			delay = transient.RetryAfter
		}

		if err := r.sleeper.Sleep(ctx, delay); err != nil {
			return err
		}
	}

	return lastErr
}

// systemClockSleeper is a real clock-based sleeper.
type systemClockSleeper struct{}

func (systemClockSleeper) Sleep(ctx context.Context, d time.Duration) error {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}