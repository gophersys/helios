package logfan

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
)

// Ring is an in-memory ring-buffer slog handler keeping the most recent
// capacity records.
type Ring struct {
	mu       sync.RWMutex
	capacity int
	buf      []slog.Record
	start    int
	count    int
	preAttrs []slog.Attr // prefix attrs from WithAttrs; applied during Handle
}

// NewRing creates a Ring handler that retains at most capacity records.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, fmt.Errorf("logfan.NewRing: capacity must be positive, got %d", capacity)
	}
	return &Ring{
		capacity: capacity,
		buf:      make([]slog.Record, capacity),
	}, nil
}

// Enabled implements slog.Handler. Always returns true.
func (r *Ring) Enabled(_ context.Context, _ slog.Level) bool { return true }

// Handle implements slog.Handler.
func (r *Ring) Handle(_ context.Context, record slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec := record.Clone()
	for _, a := range r.preAttrs {
		rec.AddAttrs(a)
	}

	idx := (r.start + r.count) % r.capacity
	r.buf[idx] = rec
	if r.count < r.capacity {
		r.count++
	} else {
		r.start = (r.start + 1) % r.capacity
	}
	return nil
}

func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	r.mu.RLock()
	defer r.mu.RUnlock()

	merged := make([]slog.Attr, len(r.preAttrs)+len(attrs))
	copy(merged, r.preAttrs)
	copy(merged[len(r.preAttrs):], attrs)
	return &Ring{capacity: r.capacity, buf: make([]slog.Record, r.capacity), preAttrs: merged}
}

// WithGroup implements slog.Handler.
func (r *Ring) WithGroup(name string) slog.Handler {
	r.mu.RLock()
	defer r.mu.RUnlock()

	pre := make([]slog.Attr, len(r.preAttrs))
	copy(pre, r.preAttrs)
	return &Ring{capacity: r.capacity, buf: make([]slog.Record, r.capacity), preAttrs: pre}
}

// Records returns the buffered records, oldest first. The returned slice is a
// deep copy; mutating it does not affect the Ring.
func (r *Ring) Records() []slog.Record {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.count == 0 {
		return nil
	}
	out := make([]slog.Record, r.count)
	for i := 0; i < r.count; i++ {
		idx := (r.start + i) % r.capacity
		out[i] = r.buf[idx].Clone()
	}
	return out
}

// multiHandler fans every record out to all registered handlers.
type multiHandler struct {
	handlers []slog.Handler
}

// New builds a logger that delivers every record to ALL given handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, fmt.Errorf("logfan.New: at least one handler is required")
	}
	return slog.New(&multiHandler{handlers: handlers}), nil
}

func (m *multiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, h := range m.handlers {
		if h.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (m *multiHandler) Handle(ctx context.Context, record slog.Record) error {
	for _, h := range m.handlers {
		if err := h.Handle(ctx, record); err != nil {
			return err
		}
	}
	return nil
}

func (m *multiHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	hs := make([]slog.Handler, len(m.handlers))
	for i, h := range m.handlers {
		hs[i] = h.WithAttrs(attrs)
	}
	return &multiHandler{handlers: hs}
}

func (m *multiHandler) WithGroup(name string) slog.Handler {
	hs := make([]slog.Handler, len(m.handlers))
	for i, h := range m.handlers {
		hs[i] = h.WithGroup(name)
	}
	return &multiHandler{handlers: hs}
}