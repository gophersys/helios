package logfan

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog.Handler keeping the most recent
// capacity records safe for concurrent use.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	buf      []slog.Record
	next     int // next write position
	count    int // total calls to Handle since creation
}

// NewRing creates an in-memory ring-buffer slog handler keeping the most
// recent capacity records.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, fmt.Errorf("logfan.NewRing: capacity must be positive, got %d", capacity)
	}
	return &Ring{
		capacity: capacity,
		buf:      make([]slog.Record, capacity),
	}, nil
}

// Enabled implements slog.Handler. Always returns true (accepts all levels).
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool { return true }

// Handle implements slog.Handler by storing a clone of the record in the
// ring buffer, evicting the oldest record when full.
func (r *Ring) Handle(_ context.Context, rec slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.buf[r.next] = rec.Clone()
	r.next = (r.next + 1) % r.capacity
	r.count++
	return nil
}

// WithAttrs returns a slog.Handler that attaches fixed attributes to every
// record before storing it in this ring.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &ringAttacher{r, attrs, ""}
}

// WithGroup returns a slog.Handler that records the group name for every
// record stored in this ring.
func (r *Ring) WithGroup(name string) slog.Handler {
	return &ringAttacher{r, nil, name}
}

// Records returns the buffered records, oldest first. The caller receives
// a fresh copy; mutating the returned slice does not affect the ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	n := r.capacity
	if r.count < r.capacity {
		n = r.count
	}
	result := make([]slog.Record, n)
	if n == 0 {
		return result
	}
	start := 0
	if r.count >= r.capacity {
		start = r.next
	}
	for i := 0; i < n; i++ {
		idx := (start + i) % r.capacity
		result[i] = r.buf[idx].Clone()
	}
	return result
}

// ringAttacher wraps a *Ring and attaches fixed attrs / a group name to
// every record before storing. Returned by Ring.WithAttrs and
// Ring.WithGroup to satisfy the slog.Handler contract.
type ringAttacher struct {
	ring  *Ring
	attrs []slog.Attr
	group string
}

func (a *ringAttacher) Enabled(_ context.Context, _ slog.Level) bool { return true }

func (a *ringAttacher) Handle(_ context.Context, rec slog.Record) error {
	rec = rec.Clone()
	if a.group != "" {
		flat := flattenAttrs(a.attrs)
		rec.AddAttrs(slog.Group(a.group, flat...))
	} else if len(a.attrs) > 0 {
		rec.AddAttrs(a.attrs...)
	}
	return a.ring.Handle(nil, rec)
}

func (a *ringAttacher) WithAttrs(attrs []slog.Attr) slog.Handler {
	merged := make([]slog.Attr, 0, len(a.attrs)+len(attrs))
	merged = append(merged, a.attrs...)
	merged = append(merged, attrs...)
	return &ringAttacher{a.ring, merged, a.group}
}

func (a *ringAttacher) WithGroup(name string) slog.Handler {
	return &ringAttacher{a.ring, a.attrs, name}
}

// New builds a logger that delivers every record to ALL given handlers.
// Returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, fmt.Errorf("logfan.New: at least one handler required")
	}
	if len(handlers) == 1 {
		return slog.New(handlers[0]), nil
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}

// flattenAttrs converts []slog.Attr to []any in key, value pairs
// for use with slog.Group.
func flattenAttrs(attrs []slog.Attr) []any {
	out := make([]any, 0, len(attrs)*2)
	for _, a := range attrs {
		out = append(out, a.Key, a.Value.Any())
	}
	return out
}
