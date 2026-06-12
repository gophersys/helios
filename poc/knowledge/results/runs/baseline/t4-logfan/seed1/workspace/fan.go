package logfan

import (
	"context"
	"errors"
	"log/slog"
)

// fanHandler delivers every record to all of its handlers.
type fanHandler struct {
	handlers []slog.Handler
}

// New builds a logger that delivers every record to ALL given handlers.
// Returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler required")
	}
	return slog.New(&fanHandler{handlers: handlers}), nil
}

func (h *fanHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, handler := range h.handlers {
		if handler.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (h *fanHandler) Handle(ctx context.Context, rec slog.Record) error {
	for _, handler := range h.handlers {
		// Clone so each handler gets its own copy — a handler may call
		// AddAttrs on the record (as our ring wrappers do).
		if err := handler.Handle(ctx, rec.Clone()); err != nil {
			return err
		}
	}
	return nil
}

func (h *fanHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	next := make([]slog.Handler, len(h.handlers))
	for i, handler := range h.handlers {
		next[i] = handler.WithAttrs(attrs)
	}
	return &fanHandler{handlers: next}
}

func (h *fanHandler) WithGroup(name string) slog.Handler {
	next := make([]slog.Handler, len(h.handlers))
	for i, handler := range h.handlers {
		next[i] = handler.WithGroup(name)
	}
	return &fanHandler{handlers: next}
}
