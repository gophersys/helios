package logfan

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog handler that retains the most
// recent records up to its configured capacity.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	records  []slog.Record
	writeIdx int
	count    int
}

// NewRing creates a Ring handler with the given capacity.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errors.New("logfan: ring capacity must be positive")
	}
	return &Ring{
		capacity: capacity,
		records:  make([]slog.Record, capacity),
	}, nil
}

// Enabled reports whether the handler handles records at the given level.
// The ring handles all levels.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool {
	return true
}

// Handle stores a copy of the record in the ring buffer.
func (r *Ring) Handle(_ context.Context, record slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.records[r.writeIdx] = record.Clone()
	r.writeIdx = (r.writeIdx + 1) % r.capacity
	if r.count < r.capacity {
		r.count++
	}
	return nil
}

// WithAttrs returns a handler that includes the given attributes.
// The ring handler ignores stored attributes; they are already
// baked into records passed to Handle.
func (r *Ring) WithAttrs(_ []slog.Attr) slog.Handler {
	return r
}

// WithGroup returns a handler that handles records in the given group.
// The ring handler ignores groups; they are already baked into records
// passed to Handle.
func (r *Ring) WithGroup(_ string) slog.Handler {
	return r
}

// Records returns the buffered records, oldest first.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.count == 0 {
		return nil
	}

	result := make([]slog.Record, r.count)
	if r.count < r.capacity {
		// Not wrapped: stored at indices 0..r.count-1
		copy(result, r.records[:r.count])
	} else {
		// Wrapped: oldest at r.writeIdx, newest at (r.writeIdx-1) mod capacity.
		// Copy [writeIdx:capacity) then [0:writeIdx).
		n := r.capacity - r.writeIdx
		copy(result, r.records[r.writeIdx:])
		copy(result[n:], r.records[:r.writeIdx])
	}
	return result
}

// New builds a logger that delivers every record to ALL given handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler is required")
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}
