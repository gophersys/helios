package logfan

import (
	"log/slog"
)

var errNoHandlers = &noHandlersError{}

type noHandlersError struct{}

func (e *noHandlersError) Error() string { return "logfan: at least one handler required" }

// New builds a logger that delivers every record to ALL given handlers.
// Returns an error when called with no handlers.
func New(handlers ...slog.Handler) (*slog.Logger, error) {
	if len(handlers) == 0 {
		return nil, errNoHandlers
	}
	return slog.New(slog.NewMultiHandler(handlers...)), nil
}