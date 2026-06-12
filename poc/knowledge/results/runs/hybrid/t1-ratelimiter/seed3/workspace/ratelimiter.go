package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Clock abstracts the system clock for testing.
type Clock interface {
	Now() time.Time
}

// Config holds the token-bucket parameters.
type Config struct {
	Capacity        int
	RefillPerSecond float64
}

// Dependencies groups injected dependencies.
type Dependencies struct {
	Clock Clock
}

// Limiter implements a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu              sync.Mutex
	capacity        int
	tokens          float64
	refillPerSecond float64
	lastRefill      time.Time
	clock           Clock
}

// New creates a Limiter. It returns an error when Capacity <= 0 or
// RefillPerSecond < 0. When Dependencies.Clock is nil the system clock is used.
func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, errors.New("ratelimiter: Capacity must be positive")
	}
	if configuration.RefillPerSecond < 0 {
		return nil, errors.New("ratelimiter: RefillPerSecond must be non-negative")
	}

	clock := dependencies.Clock
	if clock == nil {
		clock = systemClock{}
	}

	return &Limiter{
		capacity:        configuration.Capacity,
		tokens:          float64(configuration.Capacity),
		refillPerSecond: configuration.RefillPerSecond,
		lastRefill:      clock.Now(),
		clock:           clock,
	}, nil
}

// systemClock implements Clock using the real system clock.
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// Allow checks whether tokens can be consumed. It refills the bucket based on
// elapsed time, then consumes tokens if enough are available.
//
// Returns an error when tokens <= 0. Returns false and an error wrapping the
// context's error when ctx is already cancelled.
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, errors.New("ratelimiter: tokens must be positive")
	}

	// Check cancellation *before* acquiring the lock so we can return early.
	if err := ctx.Err(); err != nil {
		return false, err
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	// Double-check cancellation after acquiring the lock.
	if err := ctx.Err(); err != nil {
		return false, err
	}

	now := l.clock.Now()
	elapsed := now.Sub(l.lastRefill).Seconds()
	l.lastRefill = now

	// Refill: fractional accumulation, capped at capacity.
	l.tokens += elapsed * l.refillPerSecond
	if l.tokens > float64(l.capacity) {
		l.tokens = float64(l.capacity)
	}

	needed := float64(tokens)
	if l.tokens < needed {
		return false, nil
	}

	l.tokens -= needed
	return true, nil
}
