package logfan

import (
	"errors"
	"log/slog"
)

// New builds a logger that delivers every record to ALL given handlers.
// It returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan: at least one handler is required")
	}
	var h slog.Handler
	if len(handlers) == 1 {
		h = handlers[0]
	} else {
		h = slog.NewMultiHandler(handlers...)
	}
	return slog.New(h), nil
}
