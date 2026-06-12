package logfan

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog handler that keeps the most recent
// capacity records. Ring must implement slog.Handler.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	buf      []slog.Record
	start    int
	count    int
}

// NewRing creates a Ring handler with the given capacity.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, fmt.Errorf("logfan: ring capacity must be positive, got %d", capacity)
	}
	return &Ring{
		capacity: capacity,
		buf:      make([]slog.Record, capacity),
	}, nil
}

// Enabled reports whether the handler handles records at the given level.
// The ring handler handles all levels.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool {
	return true
}

// Handle handles the slog record by storing it in the ring buffer.
func (r *Ring) Handle(_ context.Context, record slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Deep-copy the record so external mutations don't affect stored data.
	rec := slog.NewRecord(record.Time, record.Level, record.Message, record.PC)
	record.Attrs(func(a slog.Attr) bool {
		rec.AddAttrs(a)
		return true
	})

	idx := (r.start + r.count) % r.capacity
	if r.count == r.capacity {
		// Buffer full: overwrite oldest slot, then advance start.
		r.buf[r.start] = rec
		r.start = (r.start + 1) % r.capacity
	} else {
		r.buf[idx] = rec
		r.count++
	}
	return nil
}

// WithAttrs returns a slog.Handler that adds the given attrs to every record
// it handles, delegating storage to the Ring.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &ringHandler{ring: r, outer: attrs}
}

// WithGroup returns a slog.Handler that opens the named group, delegating
// storage to the Ring.
func (r *Ring) WithGroup(name string) slog.Handler {
	return &ringHandler{ring: r, groups: []groupEntry{{name: name}}}
}

// Records returns a copy of the buffered records, oldest first.
// Mutating the returned slice does not affect the ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]slog.Record, r.count)
	for i := 0; i < r.count; i++ {
		idx := (r.start + i) % r.capacity
		result[i] = copyRecord(r.buf[idx])
	}
	return result
}

func copyRecord(rec slog.Record) slog.Record {
	c := slog.NewRecord(rec.Time, rec.Level, rec.Message, rec.PC)
	rec.Attrs(func(a slog.Attr) bool {
		c.AddAttrs(a)
		return true
	})
	return c
}

// groupEntry tracks a group opened via WithGroup and any attrs added while
// inside that group.
type groupEntry struct {
	name  string
	inner []slog.Attr
}

// ringHandler wraps a Ring with additional attrs and/or groups. It implements
// slog.Handler by composing attrs and group nesting and then delegating
// storage to the underlying Ring.
type ringHandler struct {
	ring   *Ring
	outer  []slog.Attr   // attrs added before any group opened
	groups []groupEntry  // group nesting, outermost first
}

func (h *ringHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.ring.Enabled(ctx, level)
}

func (h *ringHandler) Handle(ctx context.Context, record slog.Record) error {
	// Add top-level (outer) attrs.
	for _, a := range h.outer {
		record.AddAttrs(a)
	}
	var current []slog.Attr
	for i := len(h.groups) - 1; i >= 0; i-- {
		g := h.groups[i]
		current = append(g.inner, current...)
		args := make([]any, len(current))
		for i, a := range current {
			args[i] = a
		}
		current = []slog.Attr{slog.Group(g.name, args...)}
	}
	for _, a := range current {
		record.AddAttrs(a)
	}
	return h.ring.Handle(ctx, record)
}

func (h *ringHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	if len(h.groups) == 0 {
		// No open groups; append to outer.
		outer := make([]slog.Attr, len(h.outer)+len(attrs))
		copy(outer, h.outer)
		copy(outer[len(h.outer):], attrs)
		return &ringHandler{ring: h.ring, outer: outer}
	}
	// Append to the innermost group.
	groups := copyGroups(h.groups)
	last := &groups[len(groups)-1]
	last.inner = append(last.inner, attrs...)
	return &ringHandler{ring: h.ring, outer: h.outer, groups: groups}
}

func (h *ringHandler) WithGroup(name string) slog.Handler {
	groups := make([]groupEntry, len(h.groups)+1)
	copy(groups, h.groups)
	groups[len(groups)-1] = groupEntry{name: name}
	return &ringHandler{ring: h.ring, outer: h.outer, groups: groups}
}

func copyGroups(src []groupEntry) []groupEntry {
	dst := make([]groupEntry, len(src))
	for i := range src {
		dst[i] = src[i]
		if src[i].inner != nil {
			dst[i].inner = make([]slog.Attr, len(src[i].inner))
			copy(dst[i].inner, src[i].inner)
		}
	}
	return dst
}