// Package ratelimiter is the reference implementation used to validate the
// held-out verify suite. It is never shown to the agent.
package ratelimiter

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

type Clock interface {
	Now() time.Time
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

type Config struct {
	Capacity        int
	RefillPerSecond float64
}

type Dependencies struct {
	Clock Clock
}

type Limiter struct {
	mu       sync.Mutex
	clock    Clock
	capacity float64
	refill   float64
	tokens   float64
	last     time.Time
}

func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, errors.New("ratelimiter: Capacity must be > 0")
	}
	if configuration.RefillPerSecond < 0 {
		return nil, errors.New("ratelimiter: RefillPerSecond must be >= 0")
	}
	if dependencies.Clock == nil {
		dependencies.Clock = systemClock{}
	}
	return &Limiter{
		clock:    dependencies.Clock,
		capacity: float64(configuration.Capacity),
		refill:   configuration.RefillPerSecond,
		tokens:   float64(configuration.Capacity),
	}, nil
}

func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error) {
	if tokens <= 0 {
		return false, errors.New("ratelimiter: tokens must be > 0")
	}
	if err := ctx.Err(); err != nil {
		return false, fmt.Errorf("ratelimiter: %w", err)
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.clock.Now()
	if l.last.IsZero() {
		l.last = now
	}
	if elapsed := now.Sub(l.last).Seconds(); elapsed > 0 {
		l.tokens = min(l.capacity, l.tokens+elapsed*l.refill)
		l.last = now
	}
	if float64(tokens) <= l.tokens {
		l.tokens -= float64(tokens)
		return true, nil
	}
	return false, nil
}
