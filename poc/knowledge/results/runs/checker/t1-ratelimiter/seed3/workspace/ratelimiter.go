package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Clock abstracts time for testability.
type Clock interface {
	Now() time.Time
}

// Config configures the token-bucket rate limiter.
type Config struct {
	Capacity        int
	RefillPerSecond float64
}

// Dependencies holds external dependencies for the limiter.
type Dependencies struct {
	Clock Clock
}

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu              sync.Mutex
	capacity        int
	refillPerSecond float64
	clock           Clock
	tokens          float64
	lastRefill      time.Time
}

// New creates a new Limiter.
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

	now := clock.Now()
	return &Limiter{
		capacity:        configuration.Capacity,
		refillPerSecond: configuration.RefillPerSecond,
		clock:           clock,
		tokens:          float64(configuration.Capacity),
		lastRefill:      now,
	}, nil
}

// Allow attempts to consume tokens from the bucket.
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
	elapsed := now.Sub(l.lastRefill).Seconds()
	if elapsed > 0 {
		refill := elapsed * l.refillPerSecond
		l.tokens += refill
		if l.tokens > float64(l.capacity) {
			l.tokens = float64(l.capacity)
		}
		l.lastRefill = now
	}

	if l.tokens >= float64(tokens) {
		l.tokens -= float64(tokens)
		return true, nil
	}
	return false, nil
}

// systemClock implements Clock using the real wall clock.
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }