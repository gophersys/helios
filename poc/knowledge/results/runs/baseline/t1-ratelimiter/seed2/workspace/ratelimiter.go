package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Clock abstracts time so tests can control it.
type Clock interface {
	Now() time.Time
}

// Config holds the rate-limiter parameters.
type Config struct {
	Capacity        int     // maximum tokens in the bucket
	RefillPerSecond float64 // tokens added per second
}

// Dependencies groups external dependencies.
type Dependencies struct {
	Clock Clock
}

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu         sync.Mutex
	config     Config
	clock      Clock
	tokens     float64
	lastRefill time.Time
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// New creates a Limiter. It returns an error if Capacity <= 0 or
// RefillPerSecond < 0. When Dependencies.Clock is nil the system clock is used.
func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, errors.New("ratelimiter: capacity must be positive")
	}
	if configuration.RefillPerSecond < 0 {
		return nil, errors.New("ratelimiter: refill rate must be non-negative")
	}

	clock := dependencies.Clock
	if clock == nil {
		clock = systemClock{}
	}

	now := clock.Now()

	return &Limiter{
		config:     configuration,
		clock:      clock,
		tokens:     float64(configuration.Capacity),
		lastRefill: now,
	}, nil
}

// Allow attempts to consume tokens from the bucket. It returns true if
// enough tokens were available.
//
// tokens must be positive, otherwise an error is returned.
// If ctx is already cancelled Allow returns false and an error matching the
// context's error.
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, errors.New("ratelimiter: tokens must be positive")
	}

	select {
	case <-ctx.Done():
		return false, ctx.Err()
	default:
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	now := l.clock.Now()
	elapsed := now.Sub(l.lastRefill)
	l.lastRefill = now

	// Refill the bucket based on elapsed time, fractional accumulation, capped.
	l.tokens += elapsed.Seconds() * l.config.RefillPerSecond
	if cap := float64(l.config.Capacity); l.tokens > cap {
		l.tokens = cap
	}

	need := float64(tokens)
	if l.tokens >= need {
		l.tokens -= need
		return true, nil
	}

	return false, nil
}