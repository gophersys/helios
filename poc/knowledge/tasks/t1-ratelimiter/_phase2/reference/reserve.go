package ratelimiter

import (
	"context"
	"errors"
	"fmt"
	"time"
)

func (l *Limiter) Reserve(ctx context.Context, tokens int) (time.Duration, bool, error) {
	if tokens <= 0 {
		return 0, false, errors.New("ratelimiter: tokens must be > 0")
	}
	if err := ctx.Err(); err != nil {
		return 0, false, fmt.Errorf("ratelimiter: %w", err)
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	if float64(tokens) > l.capacity {
		return 0, false, nil
	}
	now := l.clock.Now()
	if l.last.IsZero() {
		l.last = now
	}
	if elapsed := now.Sub(l.last).Seconds(); elapsed > 0 {
		l.tokens = min(l.capacity, l.tokens+elapsed*l.refill)
		l.last = now
	}
	deficit := float64(tokens) - l.tokens
	if deficit <= 0 {
		return 0, true, nil
	}
	if l.refill <= 0 {
		return 0, false, nil
	}
	return time.Duration(deficit / l.refill * float64(time.Second)), true, nil
}
