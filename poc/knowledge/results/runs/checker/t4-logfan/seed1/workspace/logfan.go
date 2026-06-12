package logfan

import (
	"fmt"
	"log/slog"
)

// New builds a logger that delivers every record to ALL given handlers.
// It returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, fmt.Errorf("logfan: at least one handler is required")
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}