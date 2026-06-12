# Task: fan-out structured logging

Implement package `logfan` (in this module, package files at the module
root) using the standard library's `log/slog`.

## Contract (exported API — must exist with exactly these signatures)

```go
package logfan

// NewRing creates an in-memory ring-buffer slog handler keeping the most
// recent `capacity` records. *Ring must implement slog.Handler.
func NewRing(capacity int) (*Ring, error)

// Records returns the buffered records, oldest first.
func (r *Ring) Records() []slog.Record

// New builds a logger that delivers every record to ALL given handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error)
```

## Semantics

- `NewRing` returns an error if `capacity <= 0`. When the buffer is full,
  the oldest record is evicted. `Records` returns a copy (mutating the
  returned slice must not affect the ring). The ring must be safe for
  concurrent use.
- `New` returns an error when called with no handlers. The returned logger
  sends every record to every handler.

## Deliverables

- The implementation.
- Your own tests for the behavior you consider important.
- No third-party dependencies.
