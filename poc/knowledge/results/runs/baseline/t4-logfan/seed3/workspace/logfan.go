package logfan

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog handler that keeps the most recent
// capacity records. *Ring implements slog.Handler.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	records  []slog.Record
	start    int
	count    int
}

// NewRing creates a Ring handler with the given capacity. Returns an error
// if capacity <= 0.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errors.New("logfan: Ring capacity must be positive")
	}
	return &Ring{
		capacity: capacity,
		records:  make([]slog.Record, capacity),
	}, nil
}

// Enabled returns true — the ring is always enabled for all levels.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool {
	return true
}

// Handle stores a copy of the record in the ring buffer, evicting the oldest
// record when full.
func (r *Ring) Handle(_ context.Context, record slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec := cloneRecord(record)

	if r.count < r.capacity {
		idx := (r.start + r.count) % r.capacity
		r.records[idx] = rec
		r.count++
	} else {
		r.records[r.start] = rec
		r.start = (r.start + 1) % r.capacity
	}
	return nil
}

// WithAttrs returns a handler that adds the given attrs to every record
// before delegating to the ring.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &ringHandle{inner: r, attrs: attrs}
}

// WithGroup returns a handler that wraps every record's attrs under the
// given group name before delegating to the ring.
func (r *Ring) WithGroup(name string) slog.Handler {
	return &ringHandle{inner: r, group: name}
}

// Records returns the buffered records, oldest first. The returned slice is
// a copy; mutating it does not affect the ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.count == 0 {
		return nil
	}

	result := make([]slog.Record, r.count)
	for i := 0; i < r.count; i++ {
		result[i] = cloneRecord(r.records[(r.start+i)%r.capacity])
	}
	return result
}

// ringHandle wraps an inner slog.Handler with either pre-set attrs (from
// WithAttrs) or a group name (from WithGroup). Handle delegates to inner
// after applying its own transformation:
//
//   - attrs handler: add attrs to the record, then delegate to inner
//   - group handler: wrap the record's own attrs in a GroupValue under the
//     group key, then delegate to inner
//
// Chaining (e.g. WithGroup → WithAttrs → WithGroup) produces a linked list
// of ringHandle wrappers that apply transformations in the correct order.
type ringHandle struct {
	inner slog.Handler
	attrs []slog.Attr
	group string
}

func (h *ringHandle) Enabled(ctx context.Context, level slog.Level) bool {
	return h.inner.Enabled(ctx, level)
}

func (h *ringHandle) Handle(ctx context.Context, record slog.Record) error {
	if h.group != "" {
		// Group handler: wrap record's own attrs in the group.
		nr := slog.NewRecord(record.Time, record.Level, record.Message, record.PC)
		record.Attrs(func(a slog.Attr) bool {
			nr.AddAttrs(slog.Attr{Key: h.group, Value: slog.GroupValue(a)})
			return true
		})
		return h.inner.Handle(ctx, nr)
	}
	// Attrs handler: add attrs to the record.
	nr := slog.NewRecord(record.Time, record.Level, record.Message, record.PC)
	record.Attrs(func(a slog.Attr) bool {
		nr.AddAttrs(a)
		return true
	})
	for _, a := range h.attrs {
		nr.AddAttrs(a)
	}
	return h.inner.Handle(ctx, nr)
}

func (h *ringHandle) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &ringHandle{inner: h, attrs: attrs}
}

func (h *ringHandle) WithGroup(name string) slog.Handler {
	return &ringHandle{inner: h, group: name}
}

// multiHandler dispatches every record to ALL wrapped handlers.
type multiHandler struct {
	handlers []slog.Handler
}

func (h *multiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, hh := range h.handlers {
		if hh.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (h *multiHandler) Handle(ctx context.Context, record slog.Record) error {
	for _, hh := range h.handlers {
		if err := hh.Handle(ctx, record); err != nil {
			return err
		}
	}
	return nil
}

func (h *multiHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	out := make([]slog.Handler, len(h.handlers))
	for i, hh := range h.handlers {
		out[i] = hh.WithAttrs(attrs)
	}
	return &multiHandler{handlers: out}
}

func (h *multiHandler) WithGroup(name string) slog.Handler {
	out := make([]slog.Handler, len(h.handlers))
	for i, hh := range h.handlers {
		out[i] = hh.WithGroup(name)
	}
	return &multiHandler{handlers: out}
}

// New builds a logger that delivers every record to ALL given handlers.
// Returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler required")
	}
	return slog.New(&multiHandler{handlers: handlers}), nil
}

// cloneRecord creates an independent deep copy of a slog.Record.
func cloneRecord(r slog.Record) slog.Record {
	nr := slog.NewRecord(r.Time, r.Level, r.Message, r.PC)
	r.Attrs(func(a slog.Attr) bool {
		nr.AddAttrs(a)
		return true
	})
	return nr
}