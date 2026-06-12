package ratelimiter

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

// Clock abstracts time so the limiter is deterministic in tests.
type Clock interface {
	Now() time.Time
}

// Config controls bucket capacity and refill rate.
type Config struct {
	Capacity        int     // maximum tokens in the bucket
	RefillPerSecond float64 // tokens added per second
}

// Dependencies holds optional injected dependencies.
type Dependencies struct {
	Clock Clock
}

// Limiter implements a concurrency-safe token-bucket rate limiter.
type Limiter struct {
	mu         sync.Mutex
	clock      Clock
	capacity   int
	tokens     float64
	lastRefill time.Time
	rate       float64 // RefillPerSecond
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// New creates a Limiter. An error is returned when Capacity <= 0 or
// RefillPerSecond < 0. If dependencies.Clock is nil the system clock is used.
func New(configuration Config, dependencies Dependencies) (*Limiter, error) {
	if configuration.Capacity <= 0 {
		return nil, errors.New("ratelimiter: Capacity must be positive")
	}
	if configuration.RefillPerSecond < 0 {
		return nil, errors.New("ratelimiter: RefillPerSecond must not be negative")
	}

	clock := dependencies.Clock
	if clock == nil {
		clock = systemClock{}
	}

	return &Limiter{
		clock:      clock,
		capacity:   configuration.Capacity,
		tokens:     float64(configuration.Capacity),
		lastRefill: clock.Now(),
		rate:       configuration.RefillPerSecond,
	}, nil
}

// Allow checks whether at least tokens are available, consuming them on
// success. tokens must be positive.
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

	// Refill based on elapsed time since last refill.
	now := l.clock.Now()
	if !l.lastRefill.IsZero() {
		elapsed := now.Sub(l.lastRefill).Seconds()
		l.tokens += elapsed * l.rate
		if l.tokens > float64(l.capacity) {
			l.tokens = float64(l.capacity)
		}
	}
	l.lastRefill = now

	// Attempt to consume tokens.
	if l.tokens >= float64(tokens) {
		l.tokens -= float64(tokens)
		return true, nil
	}
	return false, nil
}
