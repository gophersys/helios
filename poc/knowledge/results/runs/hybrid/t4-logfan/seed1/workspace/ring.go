package logfan

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

// ringState holds the ring buffer and its synchronisation.
// It is shared among all *Ring values derived from the same constructor call,
// so that WithAttrs/WithGroup return distinct handlers that write into the
// same underlying buffer.
type ringState struct {
	mu       sync.RWMutex
	buf      []slog.Record
	start    int
	count    int
	capacity int
}

// Ring is an in-memory ring-buffer slog.Handler that keeps the most recent
// records up to a fixed capacity.
type Ring struct {
	state *ringState
	attrs []slog.Attr
	group string
}

// NewRing creates a Ring handler with the given capacity.
// Returns an error when capacity <= 0.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errors.New("logfan.NewRing: capacity must be positive")
	}
	return &Ring{
		state: &ringState{
			buf:      make([]slog.Record, capacity),
			capacity: capacity,
		},
	}, nil
}

// Enabled returns true for all levels.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool { return true }

// Handle adds the record to the ring buffer, evicting the oldest record when
// the buffer is full. Handler-level attrs and groups are prepended to the
// record's own attrs before storage.
func (r *Ring) Handle(_ context.Context, rec slog.Record) error {
	// Collect all attrs: handler-level first, then the record's own attrs.
	allAttrs := make([]slog.Attr, 0, len(r.attrs))
	allAttrs = append(allAttrs, r.attrs...)
	rec.Attrs(func(a slog.Attr) bool {
		allAttrs = append(allAttrs, a)
		return true
	})

	// Build a record with the attrs, wrapped in a group if present.
	r2 := slog.NewRecord(rec.Time, rec.Level, rec.Message, rec.PC)
	if r.group != "" {
		anyAttrs := make([]any, len(allAttrs))
		for i, a := range allAttrs {
			anyAttrs[i] = a
		}
		r2.AddAttrs(slog.Group(r.group, anyAttrs...))
	} else {
		for _, a := range allAttrs {
			r2.AddAttrs(a)
		}
	}

	r.state.mu.Lock()
	defer r.state.mu.Unlock()

	pos := (r.state.start + r.state.count) % r.state.capacity
	r.state.buf[pos] = r2
	if r.state.count < r.state.capacity {
		r.state.count++
	} else {
		r.state.start = (r.state.start + 1) % r.state.capacity
	}
	return nil
}

// WithAttrs returns a new Ring handler that shares the same underlying buffer
// and prepends the given attrs to every subsequent record.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	newAttrs := make([]slog.Attr, 0, len(r.attrs)+len(attrs))
	newAttrs = append(newAttrs, r.attrs...)
	newAttrs = append(newAttrs, attrs...)
	return &Ring{
		state: r.state,
		attrs: newAttrs,
		group: r.group,
	}
}

// WithGroup returns a new Ring handler that shares the same underlying buffer
// and opens the given group for subsequent attrs.
func (r *Ring) WithGroup(name string) slog.Handler {
	newGroup := name
	if r.group != "" {
		newGroup = r.group + "." + name
	}
	return &Ring{
		state: r.state,
		attrs: r.attrs,
		group: newGroup,
	}
}

// Records returns the buffered records, oldest first.
// Each record is cloned so that mutating the returned slice does not affect
// the ring buffer. The call is safe for concurrent use.
func (r *Ring) Records() []slog.Record {
	r.state.mu.RLock()
	defer r.state.mu.RUnlock()

	res := make([]slog.Record, r.state.count)
	for i := 0; i < r.state.count; i++ {
		pos := (r.state.start + i) % r.state.capacity
		res[i] = r.state.buf[pos].Clone()
	}
	return res
}