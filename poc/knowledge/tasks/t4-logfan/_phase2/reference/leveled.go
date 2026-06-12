package logfan

import (
	"context"
	"errors"
	"log/slog"
)

// leveledHandler filters once, in front of the fan-out. It holds a single
// next handler — filtering is real logic, not a hand-rolled multi-handler
// (the documented exception to go/slog-multihandler).
type leveledHandler struct {
	minimum slog.Level
	next    slog.Handler
}

func (h *leveledHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return level >= h.minimum && h.next.Enabled(ctx, level)
}

func (h *leveledHandler) Handle(ctx context.Context, record slog.Record) error {
	if record.Level < h.minimum {
		return nil
	}
	return h.next.Handle(ctx, record)
}

func (h *leveledHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &leveledHandler{minimum: h.minimum, next: h.next.WithAttrs(attrs)}
}

func (h *leveledHandler) WithGroup(name string) slog.Handler {
	return &leveledHandler{minimum: h.minimum, next: h.next.WithGroup(name)}
}

func NewLeveled(minimum slog.Level, handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler is required")
	}
	return slog.New(&leveledHandler{minimum: minimum, next: slog.NewMultiHandler(handlers...)}), nil
}
