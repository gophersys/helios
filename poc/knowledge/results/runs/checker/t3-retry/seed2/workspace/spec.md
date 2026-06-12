# Task: retrying executor with typed transient errors

Implement package `retry` (in this module, package files at the module root).

## Contract (exported API — must exist with exactly these signatures)

```go
package retry

// Sleeper waits for a duration, honoring cancellation.
type Sleeper interface {
    Sleep(ctx context.Context, duration time.Duration) error
}

// TransientError marks a failure as retryable.
type TransientError struct {
    Err        error
    RetryAfter time.Duration // optional server-suggested delay
}

func (e *TransientError) Error() string
func (e *TransientError) Unwrap() error

type Config struct {
    MaxAttempts int           // total attempts, >= 1
    BaseDelay   time.Duration // first backoff delay, >= 0
}

type Dependencies struct {
    Sleeper Sleeper
}

func New(configuration Config, dependencies Dependencies) (*Retrier, error)

func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error
```

## Semantics

- `New` returns an error if `MaxAttempts < 1` or `BaseDelay < 0`. A nil
  `Sleeper` defaults to a real clock-based sleeper.
- `Do` calls `operation` up to `MaxAttempts` times:
  - success (nil error) returns nil immediately;
  - a failure is **retryable only when a `*TransientError` is present in the
    error tree** (it may be wrapped at any depth);
  - a non-retryable failure is returned immediately; the returned error must
    still match the original via `errors.Is`;
  - before each retry, wait via the Sleeper: use the transient error's
    `RetryAfter` when it is > 0, otherwise exponential backoff
    (`BaseDelay`, then `2*BaseDelay`, then `4*BaseDelay`, ...);
  - if the Sleeper returns an error (e.g. the context was cancelled), `Do`
    stops and returns an error matching it via `errors.Is`;
  - when all attempts fail, the returned error must match the last failure
    via `errors.Is`.

## Deliverables

- The implementation.
- Your own tests for the behavior you consider important.
- No third-party dependencies.
