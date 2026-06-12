package ratelimiter

import (
	"context"
	"errors"
	"sync"
	"time"
)

type Clock interface {
	Now() time.Time
}

type Config struct {
	Capacity        int
	RefillPerSecond float64
}

type Dependencies struct {
	Clock Clock
}

type Limiter struct {
	mu              sync.Mutex
	capacity        int
	refillPerSecond float64
	clock           Clock
	tokens          float64
	lastRefill      time.Time
}

func New(config Config, deps Dependencies) (*Limiter, error) {
	if config.Capacity <= 0 {
		return nil, errors.New("rate limiter: capacity must be positive")
	}
	if config.RefillPerSecond < 0 {
		return nil, errors.New("rate limiter: refill rate must not be negative")
	}
	clock := deps.Clock
	if clock == nil {
		clock = realClock{}
	}
	return &Limiter{
		capacity:        config.Capacity,
		refillPerSecond: config.RefillPerSecond,
		clock:           clock,
		tokens:          float64(config.Capacity),
		lastRefill:      clock.Now(),
	}, nil
}

type realClock struct{}

func (realClock) Now() time.Time { return time.Now() }

func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, errors.New("rate limiter: tokens must be positive")
	}

	// Check context cancellation before acquiring the lock.
	select {
	case <-ctx.Done():
		return false, ctx.Err()
	default:
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	now := l.clock.Now()
	elapsed := now.Sub(l.lastRefill).Seconds()
	l.lastRefill = now

	added := elapsed * l.refillPerSecond
	l.tokens += added
	if l.tokens > float64(l.capacity) {
		l.tokens = float64(l.capacity)
	}

	tokenF := float64(tokens)
	if l.tokens >= tokenF {
		l.tokens -= tokenF
		return true, nil
	}
	return false, nil
}