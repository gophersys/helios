package ratelimiter

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Clock provides the current time.
type Clock interface {
	Now() time.Time
}

// Config configures the rate limiter.
type Config struct {
	Capacity        int
	RefillPerSecond float64
}

// Dependencies holds injected dependencies.
type Dependencies struct {
	Clock Clock
}

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu              sync.Mutex
	clock           Clock
	capacity        float64
	refillPerSecond float64
	tokens          float64
	lastRefill      time.Time
}

// realClock uses time.Now.
type realClock struct{}

func (realClock) Now() time.Time { return time.Now() }

// New creates a new Limiter. The bucket starts full (Capacity tokens).
// Returns an error if Capacity <= 0 or RefillPerSecond < 0.
// If Dependencies.Clock is nil, the system clock is used.
func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, fmt.Errorf("ratelimiter: capacity must be positive, got %d", configuration.Capacity)
	}
	if configuration.RefillPerSecond < 0 {
		return nil, fmt.Errorf("ratelimiter: refill rate must be non-negative, got %f", configuration.RefillPerSecond)
	}

	clock := dependencies.Clock
	if clock == nil {
		clock = realClock{}
	}

	return &Limiter{
		clock:           clock,
		capacity:        float64(configuration.Capacity),
		refillPerSecond: configuration.RefillPerSecond,
		tokens:          float64(configuration.Capacity),
	}, nil
}

// Allow checks whether at least tokens are available in the bucket.
// It refills the bucket based on elapsed time before checking.
// Returns an error if tokens <= 0 or if ctx is already cancelled.
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, fmt.Errorf("ratelimiter: tokens must be positive, got %d", tokens)
	}

	select {
	case <-ctx.Done():
		return false, fmt.Errorf("ratelimiter: context cancelled: %w", ctx.Err())
	default:
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	now := l.clock.Now()
	if !l.lastRefill.IsZero() {
		elapsed := now.Sub(l.lastRefill).Seconds()
		l.tokens += elapsed * l.refillPerSecond
		if l.tokens > l.capacity {
			l.tokens = l.capacity
		}
	}
	l.lastRefill = now

	if float64(tokens) <= l.tokens {
		l.tokens -= float64(tokens)
		return true, nil
	}
	return false, nil
}