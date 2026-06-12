package ratelimiter

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Clock abstracts time for deterministic testing.
type Clock interface {
	Now() time.Time
}

// Config holds the token-bucket parameters.
type Config struct {
	Capacity        int     // maximum tokens in the bucket
	RefillPerSecond float64 // tokens added per second
}

// Dependencies holds injected services.
type Dependencies struct {
	Clock Clock
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu              sync.Mutex
	tokens          float64
	lastCheck       time.Time
	capacity        float64
	refillPerSecond float64
	clock           Clock
}

// New creates a rate limiter. Returns an error if Capacity <= 0 or
// RefillPerSecond < 0. If Dependencies.Clock is nil the system clock is used.
// The bucket starts full.
func New(config Config, deps Dependencies) (*Limiter, error) {
	if config.Capacity <= 0 {
		return nil, fmt.Errorf("ratelimiter: capacity must be positive, got %d", config.Capacity)
	}
	if config.RefillPerSecond < 0 {
		return nil, fmt.Errorf("ratelimiter: refill per second must be non-negative, got %f", config.RefillPerSecond)
	}

	clock := deps.Clock
	if clock == nil {
		clock = systemClock{}
	}

	now := clock.Now()
	return &Limiter{
		tokens:          float64(config.Capacity),
		lastCheck:       now,
		capacity:        float64(config.Capacity),
		refillPerSecond: config.RefillPerSecond,
		clock:           clock,
	}, nil
}

// Allow attempts to consume tokens from the bucket. It refills the bucket
// based on elapsed time first.
//
//   - If tokens <= 0 it returns an error.
//   - If ctx is already cancelled it returns false and an error that matches
//     ctx.Err() via errors.Is.
//   - Otherwise it refills, then returns true if enough tokens were available
//     or false if not (nothing is consumed in the false case).
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, fmt.Errorf("ratelimiter: tokens must be positive, got %d", tokens)
	}

	if err := ctx.Err(); err != nil {
		return false, fmt.Errorf("ratelimiter: %w", err)
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	now := l.clock.Now()
	elapsed := now.Sub(l.lastCheck)
	l.lastCheck = now

	// Refill proportionally to elapsed time.
	if l.refillPerSecond > 0 {
		l.tokens += elapsed.Seconds() * l.refillPerSecond
		if l.tokens > l.capacity {
			l.tokens = l.capacity
		}
	}

	ftokens := float64(tokens)
	if l.tokens >= ftokens {
		l.tokens -= ftokens
		return true, nil
	}
	return false, nil
}
