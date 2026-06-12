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
	return fmt.Sprintf("transient error: %v", e.Err)
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
	config  Config
	sleeper Sleeper
}

// realSleeper is a clock-based sleeper that respects context cancellation.
type realSleeper struct{}

func (realSleeper) Sleep(ctx context.Context, d time.Duration) error {
	if d == 0 {
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

func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	var lastErr error

	for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}
		lastErr = err

		// Only retry if a *TransientError is in the error tree.
		var transient *TransientError
		if !errors.As(err, &transient) {
			return err
		}

		// Last attempt — no sleep, return the error.
		if attempt >= r.config.MaxAttempts-1 {
			return err
		}

		// Determine delay: server-suggested when > 0, otherwise exponential backoff.
		delay := transient.RetryAfter
		if delay <= 0 {
			delay = r.config.BaseDelay << uint(attempt) // BaseDelay * 2^attempt
		}

		if sleepErr := r.sleeper.Sleep(ctx, delay); sleepErr != nil {
			return sleepErr
		}
	}

	return lastErr
}