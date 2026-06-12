package logfan

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog handler that keeps the most recent
// capacity records.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	buf      []slog.Record
	start    int // index of oldest record
	count    int // number of records currently stored
}

// NewRing creates a ring-buffer slog handler.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, fmt.Errorf("logfan: capacity must be positive, got %d", capacity)
	}
	return &Ring{
		capacity: capacity,
		buf:      make([]slog.Record, capacity),
	}, nil
}

// Enabled reports whether the handler handles records at the given level.
func (r *Ring) Enabled(context.Context, slog.Level) bool { return true }

// Handle handles the Record. All levels are accepted.
func (r *Ring) Handle(_ context.Context, rec slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	rec = rec.Clone()
	if r.count < r.capacity {
		r.buf[(r.start+r.count)%r.capacity] = rec
		r.count++
	} else {
		r.buf[r.start] = rec
		r.start = (r.start + 1) % r.capacity
	}
	return nil
}

// WithAttrs returns a new handler whose records include the given attributes
// in addition to the receiver's own attributes.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &ringSubHandler{r: r, preAttrs: attrs}
}

// WithGroup returns a new handler whose records are grouped under the given
// name.
func (r *Ring) WithGroup(name string) slog.Handler {
	return &ringSubHandler{r: r, groups: []string{name}}
}

// Records returns the buffered records, oldest first. The returned slice is a
// copy; mutating it does not affect the ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]slog.Record, r.count)
	for i := 0; i < r.count; i++ {
		out[i] = r.buf[(r.start+i)%r.capacity]
	}
	return out
}

// ringSubHandler wraps a Ring with pre-attrs and open groups, producing a
// slog.Handler that chains to the Ring when a record is handled.
type ringSubHandler struct {
	r        *Ring
	preAttrs []slog.Attr
	groups   []string
}

func (h *ringSubHandler) Enabled(context.Context, slog.Level) bool { return true }

func (h *ringSubHandler) Handle(ctx context.Context, rec slog.Record) error {
	resolved := resolveAttrs(h.groups, h.preAttrs)
	if len(resolved) > 0 {
		rec.AddAttrs(resolved...)
	}
	return h.r.Handle(ctx, rec)
}

func (h *ringSubHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	// Merge new attrs into the current group context.
	newPreAttrs := h.preAttrs
	if len(h.groups) > 0 {
		wrapped := attrs
		for i := len(h.groups) - 1; i >= 0; i-- {
			wrapped = []slog.Attr{slog.Group(h.groups[i], attrsToAny(wrapped)...)}
		}
		newPreAttrs = append(newPreAttrs, wrapped...)
		return &ringSubHandler{r: h.r, preAttrs: newPreAttrs}
	}
	newPreAttrs = append(append([]slog.Attr{}, h.preAttrs...), attrs...)
	return &ringSubHandler{r: h.r, preAttrs: newPreAttrs}
}

func (h *ringSubHandler) WithGroup(name string) slog.Handler {
	return &ringSubHandler{
		r:        h.r,
		preAttrs: h.preAttrs,
		groups:   append(append([]string{}, h.groups...), name),
	}
}

// resolveAttrs wraps pre-attrs with the open group names so that the result
// reflects slog's group nesting rules.
func resolveAttrs(groups []string, attrs []slog.Attr) []slog.Attr {
	if len(groups) == 0 {
		return attrs
	}
	// Walk groups from innermost outward so that the outermost group
	// appears first in the result.
	result := attrs
	for i := len(groups) - 1; i >= 0; i-- {
		result = []slog.Attr{slog.Group(groups[i], attrsToAny(result)...)}
	}
	return result
}

// attrsToAny converts a []slog.Attr to []any for use with slog.Group.
func attrsToAny(attrs []slog.Attr) []any {
	out := make([]any, len(attrs))
	for i, a := range attrs {
		out[i] = a
	}
	return out
}
