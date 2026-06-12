# Task: token-bucket rate limiter

Implement package `ratelimiter` (in this module, package files at the module
root) — a token-bucket rate limiter.

## Contract (exported API — must exist with exactly these signatures)

```go
package ratelimiter

type Clock interface {
    Now() time.Time
}

type Config struct {
    Capacity        int     // maximum tokens in the bucket
    RefillPerSecond float64 // tokens added per second
}

type Dependencies struct {
    Clock Clock
}

func New(configuration Config, dependencies Dependencies) (*Limiter, error)

func (l *Limiter) Allow(ctx context.Context, tokens int) (bool, error)
```

## Semantics

- `New` returns an error if `Capacity <= 0` or `RefillPerSecond < 0`.
- If `Dependencies.Clock` is nil, the limiter uses the system clock.
- The bucket starts full (`Capacity` tokens).
- `Allow(ctx, tokens)`:
  - returns an error if `tokens <= 0`;
  - if `ctx` is already cancelled, returns `false` and an error that matches
    the context's error via `errors.Is`;
  - refills the bucket based on time elapsed since the previous call
    (`RefillPerSecond` tokens per second, fractional accumulation, capped at
    `Capacity`), then consumes `tokens` and returns `true` if enough tokens
    are available, otherwise consumes nothing and returns `false`.
- The limiter must be safe for concurrent use.

## Deliverables

- The implementation.
- Your own tests for the behavior you consider important.
- No third-party dependencies.
