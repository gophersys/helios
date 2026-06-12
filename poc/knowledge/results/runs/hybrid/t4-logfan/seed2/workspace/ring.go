package logfan

import (
	"context"
	"log/slog"
	"sync"
)

// ringState holds the mutable ring buffer state, shared across all clones
// created by WithAttrs/WithGroup. Its own mutex protects concurrent access.
type ringState struct {
	mu       sync.Mutex
	capacity int
	buf      []slog.Record
	pos      int // next write index
	count    int // number of records stored (capped at capacity)
}

// Ring is an in-memory ring-buffer slog handler that keeps the most recent
// capacity records. It implements slog.Handler and is safe for concurrent use.
type Ring struct {
	state    *ringState
	level    slog.Leveler
	preAttrs []slog.Attr
	prefixes []string
}

// NewRing creates a Ring with the given capacity.
// Returns an error if capacity <= 0.
func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errInvalidCapacity
	}
	return &Ring{
		state: &ringState{
			capacity: capacity,
			buf:      make([]slog.Record, capacity),
		},
		level: slog.LevelDebug,
	}, nil
}

var errInvalidCapacity = &capacityError{}

type capacityError struct{}

func (e *capacityError) Error() string { return "logfan: capacity must be positive" }

// Enabled reports whether the handler handles records at the given level.
func (r *Ring) Enabled(_ context.Context, level slog.Level) bool {
	return level >= r.level.Level()
}

// Handle stores a copy of the record in the ring buffer, evicting the oldest
// record when the buffer is full. Pre-defined attrs and groups (set via
// WithAttrs/WithGroup) are added to the record before storage.
func (r *Ring) Handle(_ context.Context, record slog.Record) error {
	rec := record.Clone()

	// Apply pre-defined attrs, nested in groups if any.
	if len(r.prefixes) > 0 {
		attrs := make([]slog.Attr, len(r.preAttrs))
		copy(attrs, r.preAttrs)
		for i := len(r.prefixes) - 1; i >= 0; i-- {
			anyAttrs := make([]any, len(attrs))
			for j, a := range attrs {
				anyAttrs[j] = a
			}
			attrs = []slog.Attr{slog.Group(r.prefixes[i], anyAttrs...)}
		}
		rec.AddAttrs(attrs...)
	} else {
		rec.AddAttrs(r.preAttrs...)
	}

	s := r.state
	s.mu.Lock()
	s.buf[s.pos] = rec
	s.pos = (s.pos + 1) % s.capacity
	if s.count < s.capacity {
		s.count++
	}
	s.mu.Unlock()
	return nil
}

// WithAttrs returns a new Ring that adds the given attrs to each record.
// The underlying ring buffer is shared.
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler {
	r2 := &Ring{
		state: r.state,
		level: r.level,
	}
	r2.preAttrs = append(r2.preAttrs, r.preAttrs...)
	r2.preAttrs = append(r2.preAttrs, attrs...)
	r2.prefixes = append(r2.prefixes, r.prefixes...)
	return r2
}

// WithGroup returns a new Ring that groups subsequent attrs under the given name.
func (r *Ring) WithGroup(name string) slog.Handler {
	r2 := &Ring{
		state:    r.state,
		level:    r.level,
		preAttrs: r.preAttrs,
	}
	r2.prefixes = append(r2.prefixes, r.prefixes...)
	r2.prefixes = append(r2.prefixes, name)
	return r2
}

// Records returns the buffered records, oldest first, as a copy.
// Mutating the returned slice does not affect the ring.
func (r *Ring) Records() []slog.Record {
	s := r.state
	s.mu.Lock()
	defer s.mu.Unlock()

	result := make([]slog.Record, s.count)
	if s.count == 0 {
		return result
	}

	if s.count < s.capacity {
		for i := 0; i < s.count; i++ {
			result[i] = s.buf[i].Clone()
		}
	} else {
		// Buffer is full; records wrap around starting at r.state.pos.
		for i := 0; i < s.capacity; i++ {
			idx := (s.pos + i) % s.capacity
			result[i] = s.buf[idx].Clone()
		}
	}
	return result
}