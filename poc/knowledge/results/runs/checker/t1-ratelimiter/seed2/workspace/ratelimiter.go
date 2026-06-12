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

// Config defines the bucket parameters.
type Config struct {
	Capacity        int
	RefillPerSecond float64
}

// Dependencies holds external dependencies for the limiter.
type Dependencies struct {
	Clock Clock
}

// Limiter is a token-bucket rate limiter, safe for concurrent use.
type Limiter struct {
	mu           sync.Mutex
	capacity     int
	refillPerSec float64
	tokens       float64
	lastRefill   time.Time
	clock        Clock
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// New creates a token-bucket Limiter.
func New(config Config, deps Dependencies) (*Limiter, error) {
	if config.Capacity <= 0 {
		return nil, errors.New("ratelimiter: capacity must be positive")
	}
	if config.RefillPerSecond < 0 {
		return nil, errors.New("ratelimiter: refill rate must be non-negative")
	}

	clock := deps.Clock
	if clock == nil {
		clock = systemClock{}
	}

	l := &Limiter{
		capacity:     config.Capacity,
		refillPerSec: config.RefillPerSecond,
		tokens:       float64(config.Capacity),
		lastRefill:   clock.Now(),
		clock:        clock,
	}
	return l, nil
}

// Allow checks whether enough tokens are available. If yes, it consumes them
// and returns true. Otherwise it returns false and does not consume tokens.
func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, errors.New("ratelimiter: tokens must be positive")
	}

	// Check if the context is already cancelled.
	if err := ctx.Err(); err != nil {
		return false, err
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	// Refill bucket based on elapsed time.
	now := l.clock.Now()
	elapsed := now.Sub(l.lastRefill)
	l.lastRefill = now

	if l.refillPerSec > 0 {
		added := elapsed.Seconds() * l.refillPerSec
		l.tokens += added
		if l.tokens > float64(l.capacity) {
			l.tokens = float64(l.capacity)
		}
	}

	// Try to consume tokens.
	if l.tokens >= float64(tokens) {
		l.tokens -= float64(tokens)
		return true, nil
	}

	return false, nil
}