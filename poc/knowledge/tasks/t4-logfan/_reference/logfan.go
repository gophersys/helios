// Package logfan is the reference implementation used to validate the
// held-out verify suite. It is never shown to the agent.
package logfan

import (
	"context"
	"errors"
	"log/slog"
	"sync"
)

type Ring struct {
	mu       sync.Mutex
	capacity int
	records  []slog.Record
}

func NewRing(capacity int) (*Ring, error) {
	if capacity <= 0 {
		return nil, errors.New("logfan: ring capacity must be > 0")
	}
	return &Ring{capacity: capacity}, nil
}

func (r *Ring) Enabled(context.Context, slog.Level) bool { return true }

func (r *Ring) Handle(ctx context.Context, record slog.Record) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.records = append(r.records, record.Clone())
	if len(r.records) > r.capacity {
		r.records = append([]slog.Record(nil), r.records[len(r.records)-r.capacity:]...)
	}
	return nil
}

// WithAttrs and WithGroup return the same ring: the buffer is shared and the
// reference intentionally records the bare records (attrs live on the Record).
func (r *Ring) WithAttrs(attrs []slog.Attr) slog.Handler { return r }
func (r *Ring) WithGroup(name string) slog.Handler       { return r }

func (r *Ring) Records() []slog.Record {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]slog.Record, len(r.records))
	copy(out, r.records)
	return out
}

func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler is required")
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}
