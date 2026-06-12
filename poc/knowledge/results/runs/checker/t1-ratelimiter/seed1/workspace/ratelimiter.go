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

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// Config holds the static parameters of the token bucket.
type Config struct {
	Capacity        int     // maximum tokens in the bucket
	RefillPerSecond float64 // tokens added per second
}

// Dependencies holds the external dependencies of the limiter.
type Dependencies struct {
	Clock Clock
}

// Limiter is a concurrency-safe token-bucket rate limiter.
type Limiter struct {
	mu       sync.Mutex
	capacity float64
	rate     float64 // refill per nanosecond = RefillPerSecond / 1e9
	clock    Clock

	tokens      float64
	lastRefill  time.Time
}

// New creates a new Limiter. Returns an error if Capacity <= 0 or RefillPerSecond < 0.
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
		capacity:   float64(configuration.Capacity),
		rate:       configuration.RefillPerSecond / 1e9,
		clock:      clock,
		tokens:     float64(configuration.Capacity),
		lastRefill: now,
	}, nil
}

// Allow tries to consume tokens from the bucket.
// It refills the bucket based on elapsed time, then consumes tokens if enough
// are available.
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, errors.New("ratelimiter: tokens must be positive")
	}

	// Check context cancellation before taking the lock.
	select {
	case <-ctx.Done():
		return false, ctx.Err()
	default:
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	// Refill based on elapsed time.
	now := l.clock.Now()
	elapsed := now.Sub(l.lastRefill).Nanoseconds()
	if elapsed > 0 {
		added := float64(elapsed) * l.rate
		l.tokens += added
		if l.tokens > l.capacity {
			l.tokens = l.capacity
		}
		l.lastRefill = now
	}

	if l.tokens >= float64(tokens) {
		l.tokens -= float64(tokens)
		return true, nil
	}
	return false, nil
}