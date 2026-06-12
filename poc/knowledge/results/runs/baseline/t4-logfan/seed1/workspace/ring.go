package logfan

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog.Handler that keeps the most
// recent records up to its configured capacity.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	buf      []slog.Record
	start    int
	count    int
}

// NewRing creates a *Ring with the given capacity.
// Returns an error if capacity <= 0.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errors.New("logfan: ring capacity must be positive")
	}
	return &Ring{
		capacity: capacity,
		buf:      make([]slog.Record, capacity),
	}, nil
}

// Enabled reports whether the handler handles records at the given level.
// Ring accepts all levels.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool {
	return true
}

// Handle stores the slog.Record in the ring buffer.
func (r *Ring) Handle(_ context.Context, rec slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	idx := (r.start + r.count) % r.capacity
	r.buf[idx] = rec.Clone()
	if r.count == r.capacity {
		r.start = (r.start + 1) % r.capacity
	} else {
		r.count++
	}
	return nil
}

// WithAttrs returns a Handler whose attributes consist of attrs followed
// by the attributes of any record handled.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &wrapper{ring: r, attrs: attrs}
}

// WithGroup returns a Handler that starts a group with the given name.
func (r *Ring) WithGroup(name string) slog.Handler {
	return &wrapper{ring: r, group: name}
}

// Records returns the buffered records, oldest first.
// The returned slice is a copy — mutating it does not affect the ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	out := make([]slog.Record, r.count)
	for i := 0; i < r.count; i++ {
		idx := (r.start + i) % r.capacity
		out[i] = r.buf[idx].Clone()
	}
	return out
}

// wrapper is a slog.Handler that applies attrs/grouping before delegating
// to the parent (either the Ring or another wrapper), building a chain.
type wrapper struct {
	parent slog.Handler // the next handler in the chain (Ring or another wrapper)
	ring   *Ring        // final Ring sink (only set when this wrapper attaches directly to Ring)
	attrs  []slog.Attr
	group  string
}

// resolveParent returns the parent handler for this wrapper.
// If ring is set, this wrapper attaches directly to Ring; otherwise
// parent must be set.
func (w *wrapper) resolveParent() slog.Handler {
	if w.ring != nil {
		return w.ring
	}
	return w.parent
}

func (w *wrapper) Enabled(ctx context.Context, level slog.Level) bool {
	return w.resolveParent().Enabled(ctx, level)
}

func (w *wrapper) Handle(ctx context.Context, rec slog.Record) error {
	parent := w.resolveParent()

	if w.group != "" {
		// Collect existing record attrs.
		var recAttrs []slog.Attr
		rec.Attrs(func(a slog.Attr) bool {
			recAttrs = append(recAttrs, a)
			return true
		})

		newRec := slog.NewRecord(rec.Time, rec.Level, rec.Message, rec.PC)
		// Wrap everything inside the group.
		groupArgs := make([]any, 0, len(w.attrs)+len(recAttrs))
		for _, a := range w.attrs {
			groupArgs = append(groupArgs, a)
		}
		for _, a := range recAttrs {
			groupArgs = append(groupArgs, a)
		}
		newRec.AddAttrs(slog.Group(w.group, groupArgs...))
		return parent.Handle(ctx, newRec)
	}

	// No group: just prepend attrs.
	if len(w.attrs) > 0 {
		rec.AddAttrs(w.attrs...)
	}
	return parent.Handle(ctx, rec)
}

func (w *wrapper) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &wrapper{parent: w, attrs: attrs}
}

func (w *wrapper) WithGroup(name string) slog.Handler {
	return &wrapper{parent: w, group: name}
}
