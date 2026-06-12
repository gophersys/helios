package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Clock provides the current time. Use it to inject a deterministic clock
// during testing.
type Clock interface {
	Now() time.Time
}

// Config configures the token-bucket rate limiter.
type Config struct {
	Capacity        int     // maximum tokens in the bucket
	RefillPerSecond float64 // tokens added per second
}

// Dependencies holds infrastructure that the limiter needs.
type Dependencies struct {
	Clock Clock
}

// Limiter is a token-bucket rate limiter safe for concurrent use.
type Limiter struct {
	mu         sync.Mutex
	capacity   int
	refillRate float64 // tokens per second
	tokens     float64
	lastCheck  time.Time
	clock      Clock
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// New creates a token-bucket rate limiter.
//
// The bucket starts full with Capacity tokens. If Dependencies.Clock is nil
// the system clock is used.
func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, errors.New("ratelimiter: capacity must be positive")
	}
	if configuration.RefillPerSecond < 0 {
		return nil, errors.New("ratelimiter: refill rate must not be negative")
	}

	clock := dependencies.Clock
	if clock == nil {
		clock = systemClock{}
	}

	return &Limiter{
		capacity:   configuration.Capacity,
		refillRate: configuration.RefillPerSecond,
		tokens:     float64(configuration.Capacity),
		lastCheck:  clock.Now(),
		clock:      clock,
	}, nil
}

// Allow attempts to consume tokens from the bucket.
//
// It refills the bucket based on elapsed time, then returns true if enough
// tokens were available. If the context is already cancelled it returns false
// and an error matching the context's error via errors.Is.
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
	elapsed := now.Sub(l.lastCheck)
	l.lastCheck = now

	l.tokens += elapsed.Seconds() * l.refillRate
	if l.tokens > float64(l.capacity) {
		l.tokens = float64(l.capacity)
	}

	if l.tokens >= float64(tokens) {
		l.tokens -= float64(tokens)
		return true, nil
	}

	return false, nil
}