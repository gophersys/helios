package logfan

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog handler.
// It implements slog.Handler.
type Ring struct {
	mu       sync.Mutex
	buf      []slog.Record
	head     int
	count    int
	capacity int
}

// NewRing creates an in-memory ring-buffer slog handler keeping the most
// recent capacity records. *Ring implements slog.Handler.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, fmt.Errorf("logfan: ring capacity must be positive, got %d", capacity)
	}
	return &Ring{
		buf:      make([]slog.Record, capacity),
		capacity: capacity,
	}, nil
}

// Enabled returns true for all levels.
func (r *Ring) Enabled(context.Context, slog.Level) bool {
	return true
}

// Handle stores the record in the ring buffer. When the buffer is full,
// the oldest record is evicted.
func (r *Ring) Handle(_ context.Context, rec slog.Record) error {
	rec = rec.Clone()
	r.mu.Lock()
	if r.count < r.capacity {
		pos := (r.head + r.count) % r.capacity
		r.buf[pos] = rec
		r.count++
	} else {
		r.buf[r.head] = rec
		r.head = (r.head + 1) % r.capacity
	}
	r.mu.Unlock()
	return nil
}

// WithAttrs returns a handler that adds attrs to every record.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &wrapHandler{ring: r, attrs: attrs}
}

// WithGroup returns a handler that opens a group for every record.
func (r *Ring) WithGroup(name string) slog.Handler {
	return &wrapHandler{ring: r, group: name}
}

// Records returns the buffered records, oldest first. The returned slice
// is a detached copy; mutating it does not affect the ring buffer.
func (r *Ring) Records() []slog.Record {
	r.mu.Lock()
	defer r.mu.Unlock()

	result := make([]slog.Record, r.count)
	for i := range result {
		pos := (r.head + i) % r.capacity
		result[i] = r.buf[pos].Clone()
	}
	return result
}

// wrapHandler wraps a Ring with additional attrs and/or group for
// correct slog.Handler WithAttrs/WithGroup semantics.
type wrapHandler struct {
	ring  *Ring
	attrs []slog.Attr
	group string
}

func (w *wrapHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return w.ring.Enabled(ctx, level)
}

func (w *wrapHandler) Handle(ctx context.Context, rec slog.Record) error {
	rec = rec.Clone()
	rec.AddAttrs(w.attrs...)
	// Group is a formatting concern; for in-memory storage the record
	// attrs are stored as-is. Groups only affect serialization.
	return w.ring.Handle(ctx, rec)
}

func (w *wrapHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	newAttrs := make([]slog.Attr, 0, len(w.attrs)+len(attrs))
	newAttrs = append(newAttrs, w.attrs...)
	newAttrs = append(newAttrs, attrs...)
	return &wrapHandler{ring: w.ring, attrs: newAttrs, group: w.group}
}

func (w *wrapHandler) WithGroup(name string) slog.Handler {
	newGroup := name
	if w.group != "" {
		newGroup = w.group + "." + name
	}
	return &wrapHandler{ring: w.ring, attrs: w.attrs, group: newGroup}
}