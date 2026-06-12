// Package retry is the reference implementation used to validate the
// held-out verify suite. It is never shown to the agent.
package retry

import (
	"context"
	"errors"
	"fmt"
	"time"
)

type Sleeper interface {
	Sleep(ctx context.Context, duration time.Duration) error
}

type systemSleeper struct{}

func (systemSleeper) Sleep(ctx context.Context, duration time.Duration) error {
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-timer.C:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

type TransientError struct {
	Err        error
	RetryAfter time.Duration
}

func (e *TransientError) Error() string { return fmt.Sprintf("transient: %v", e.Err) }
func (e *TransientError) Unwrap() error { return e.Err }

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

func New(configuration Config, dependencies Dependencies) (*Retrier, error) {
	if configuration.MaxAttempts < 1 {
		return nil, errors.New("retry: MaxAttempts must be >= 1")
	}
	if configuration.BaseDelay < 0 {
		return nil, errors.New("retry: BaseDelay must be >= 0")
	}
	if dependencies.Sleeper == nil {
		dependencies.Sleeper = systemSleeper{}
	}
	return &Retrier{
		maxAttempts: configuration.MaxAttempts,
		baseDelay:   configuration.BaseDelay,
		sleeper:     dependencies.Sleeper,
	}, nil
}

func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error {
	delay := r.baseDelay
	var lastErr error
	for attempt := 1; attempt <= r.maxAttempts; attempt++ {
		lastErr = operation(ctx)
		if lastErr == nil {
			return nil
		}
		transient, ok := errors.AsType[*TransientError](lastErr)
		if !ok {
			return fmt.Errorf("retry: attempt %d failed permanently: %w", attempt, lastErr)
		}
		if attempt == r.maxAttempts {
			break
		}
		wait := delay
		if transient.RetryAfter > 0 {
			wait = transient.RetryAfter
		}
		if err := r.sleeper.Sleep(ctx, wait); err != nil {
			return fmt.Errorf("retry: aborted while waiting to retry: %w", err)
		}
		delay *= 2
	}
	return fmt.Errorf("retry: all %d attempts failed: %w", r.maxAttempts, lastErr)
}
