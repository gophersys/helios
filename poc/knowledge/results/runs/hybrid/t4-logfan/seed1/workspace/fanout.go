package logfan

import (
	"errors"
	"log/slog"
)

// New builds a logger that delivers every record to ALL given handlers.
// Returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errors.New("logfan.New: at least one handler required")
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}