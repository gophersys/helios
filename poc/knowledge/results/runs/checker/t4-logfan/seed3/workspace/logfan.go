package logfan

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer [slog.Handler] that keeps the most recent
// capacity records.
type Ring struct {
	mu         sync.RWMutex
	records    []slog.Record
	head       int
	count      int
	capacity   int
	preAttrs   []slog.Attr
	openGroups []string
}

// NewRing creates an in-memory ring-buffer slog handler keeping the most
// recent capacity records.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errors.New("logfan: capacity must be positive")
	}
	return &Ring{
		records:  make([]slog.Record, capacity),
		capacity: capacity,
	}, nil
}

// Records returns the buffered records, oldest first. The returned slice is a
// deep copy — mutating it does not affect the ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	n := r.count
	if n == 0 {
		return nil
	}

	out := make([]slog.Record, n)
	if n < r.capacity {
		for i := 0; i < n; i++ {
			out[i] = r.records[i].Clone()
		}
	} else {
		for i := 0; i < n; i++ {
			out[i] = r.records[(r.head+i)%r.capacity].Clone()
		}
	}
	return out
}

// Enabled implements slog.Handler. The ring accepts all levels.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool {
	return true
}

// Handle implements slog.Handler.
func (r *Ring) Handle(_ context.Context, rec slog.Record) error {
	rec = rec.Clone()
	if len(r.preAttrs) > 0 {
		rec.AddAttrs(r.preAttrs...)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	if r.count < r.capacity {
		r.records[(r.head+r.count)%r.capacity] = rec
		r.count++
	} else {
		r.records[r.head] = rec
		r.head = (r.head + 1) % r.capacity
	}
	return nil
}

// WithAttrs implements slog.Handler.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	h2 := &Ring{
		records:    make([]slog.Record, r.capacity),
		capacity:   r.capacity,
		preAttrs:   make([]slog.Attr, len(r.preAttrs), len(r.preAttrs)+len(attrs)),
		openGroups: append([]string{}, r.openGroups...),
	}
	copy(h2.preAttrs, r.preAttrs)
	h2.preAttrs = append(h2.preAttrs, prefixAttrs(r.openGroups, attrs)...)
	return h2
}

// WithGroup implements slog.Handler.
func (r *Ring) WithGroup(name string) slog.Handler {
	h2 := &Ring{
		records:    make([]slog.Record, r.capacity),
		capacity:   r.capacity,
		preAttrs:   append([]slog.Attr{}, r.preAttrs...),
		openGroups: append(append([]string{}, r.openGroups...), name),
	}
	return h2
}

// prefixAttrs wraps attrs in nested slog.Group calls according to the open
// group stack, innermost first.
func prefixAttrs(groups []string, attrs []slog.Attr) []slog.Attr {
	if len(groups) == 0 {
		return attrs
	}
	wrapped := attrs
	for i := len(groups) - 1; i >= 0; i-- {
		args := make([]any, len(wrapped))
		for j, a := range wrapped {
			args[j] = a
		}
		wrapped = []slog.Attr{slog.Group(groups[i], args...)}
	}
	return wrapped
}

// New builds a logger that delivers every record to ALL given handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler required")
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}