package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Clock provides the current time.
type Clock interface {
	Now() time.Time
}

// Config holds the token-bucket parameters.
type Config struct {
	Capacity        int     // maximum tokens in the bucket
	RefillPerSecond float64 // tokens added per second
}

// Dependencies holds external dependencies for the limiter.
type Dependencies struct {
	Clock Clock
}

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu       sync.Mutex
	clock    Clock
	capacity float64
	rate     float64 // tokens per nanosecond

	tokens   float64
	lastTime time.Time
}

// New creates a new Limiter. It returns an error if Capacity <= 0 or
// RefillPerSecond < 0. If Dependencies.Clock is nil, the system clock is used.
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
		clock:    clock,
		capacity: float64(configuration.Capacity),
		rate:     configuration.RefillPerSecond / float64(time.Second.Nanoseconds()),
		tokens:   float64(configuration.Capacity),
		lastTime: clock.Now(),
	}, nil
}

// Allow attempts to consume tokens from the bucket. It returns true if the
// tokens were consumed. If ctx is already cancelled it returns false and an
// error that matches the context's error via errors.Is. It returns an error
// if tokens <= 0.
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
	elapsed := now.Sub(l.lastTime)
	l.lastTime = now

	// Refill: add tokens based on elapsed time, capped at capacity.
	l.tokens += elapsed.Nanoseconds() * l.rate
	if l.tokens > l.capacity {
		l.tokens = l.capacity
	}

	ftokens := float64(tokens)
	if l.tokens >= ftokens {
		l.tokens -= ftokens
		return true, nil
	}
	return false, nil
}

// systemClock implements Clock using the real system clock.
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }