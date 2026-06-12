# Task extension: leveled fan-out

The module in this directory already implements the `logfan` package per
`spec.md`. Extend it — keep every existing exported symbol and behavior
intact.

## New contract (must exist with exactly this signature)

```go
// NewLeveled is New with a minimum level: records below `minimum` are
// delivered to NO handler; records at or above it are delivered to ALL.
func NewLeveled(minimum slog.Level, handlers ...slog.Handler) (*slog.Logger, error)
```

## Semantics

- No handlers is an error (same as `New`).
- The returned logger's handler must report `Enabled(ctx, level) == false`
  for levels below `minimum`.
- Filtering happens once, for all handlers — per-handler behavior is
  otherwise identical to `New`.

## Deliverables

- The extension plus tests for it. Everything that passed before must still
  pass.
