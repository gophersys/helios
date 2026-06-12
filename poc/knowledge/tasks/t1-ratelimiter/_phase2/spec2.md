# Task extension: Reserve

The module in this directory already implements the `ratelimiter` package per
`spec.md`. Extend it — keep every existing exported symbol and behavior
intact.

## New contract (must exist with exactly this signature)

```go
// Reserve reports whether `tokens` could be granted and how long the caller
// would have to wait for that, WITHOUT consuming anything.
func (l *Limiter) Reserve(ctx context.Context, tokens int) (wait time.Duration, ok bool, err error)
```

## Semantics

- `tokens <= 0` is an error. A cancelled `ctx` returns an error matching the
  context's error via `errors.Is`.
- If `tokens > Capacity`, the request can never be granted: return
  `(0, false, nil)`.
- Otherwise, after applying the usual elapsed-time refill:
  - if enough tokens are already available: `(0, true, nil)`;
  - else, if `RefillPerSecond > 0`: the duration until the deficit refills,
    and `true`;
  - else (no refill): `(0, false, nil)`.
- `Reserve` must NOT consume tokens — a subsequent `Allow` sees the same
  bucket state.

## Deliverables

- The extension plus tests for it. Everything that passed before must still
  pass.
