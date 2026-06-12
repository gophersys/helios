package ratelimiter

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"
)

// Clock provides the current time.
type Clock interface {
	Now() time.Time
}

// Config configures the token bucket.
type Config struct {
	Capacity        int
	RefillPerSecond float64
}

// Dependencies holds the limiter's external dependencies.
type Dependencies struct {
	Clock Clock
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu sync.Mutex

	clock    Clock
	capacity int
	refill   float64 // tokens per second

	tokens     float64
	lastRefill time.Time
}

// New creates a new token-bucket Limiter. The bucket starts full.
func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, fmt.Errorf("ratelimiter: capacity must be positive, got %d", configuration.Capacity)
	}
	if configuration.RefillPerSecond < 0 {
		return nil, fmt.Errorf("ratelimiter: refill rate must be non-negative, got %f", configuration.RefillPerSecond)
	}
	clock := dependencies.Clock
	if clock == nil {
		clock = systemClock{}
	}
	now := clock.Now()
	return &Limiter{
		clock:      clock,
		capacity:   configuration.Capacity,
		refill:     configuration.RefillPerSecond,
		tokens:     float64(configuration.Capacity),
		lastRefill: now,
	}, nil
}

// Allow checks whether tokens can be consumed from the bucket.
//
// It refills the bucket based on time elapsed since the previous call, then
// consumes tokens and returns true if enough are available. Otherwise it
// consumes nothing and returns false.
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, fmt.Errorf("ratelimiter: tokens must be positive, got %d", tokens)
	}
	if err := ctx.Err(); err != nil {
		return false, fmt.Errorf("ratelimiter: %w", err)
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	// Refill based on elapsed time.
	now := l.clock.Now()
	elapsed := now.Sub(l.lastRefill)
	if elapsed > 0 {
		refillTokens := elapsed.Seconds() * l.refill
		l.tokens = math.Min(l.tokens+refillTokens, float64(l.capacity))
		l.lastRefill = now
	}

	tokensF := float64(tokens)
	if l.tokens >= tokensF {
		l.tokens -= tokensF
		return true, nil
	}
	return false, nil
}

// Ensure systemClock implements Clock.
var _ Clock = systemClock{}