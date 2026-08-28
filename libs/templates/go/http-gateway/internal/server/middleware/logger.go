// Package middleware holds the gateway's cross-cutting HTTP seams that are NOT the edenhttp spine's
// own (the spine owns authentication). Today it carries the adapter that bridges the
// observability.Provider onto the narrow edenhttp.Logger port — the composition owns the adaptation,
// so edenhttp never depends on observability. A generated app adds request-id / panic-recovery /
// CORS middleware here, each a small http.Handler wrapper.
package middleware

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// ObservabilityLogger adapts an observability.Provider onto the 2-method edenhttp.Logger port (Info
// / Error). The spine logs operator-facing lines through it; a field is NEVER a secret (the spine
// never handles a resolved credential, and the observability Field constructors keep secret-bearing
// values redacted by construction). It is a value, safe to copy and share.
type ObservabilityLogger struct {
	// Provider is the structured-Event stream the lines are emitted on. A nil Provider is a no-op.
	Provider observability.Provider
}

// compile-time assertion: ObservabilityLogger satisfies the edenhttp.Logger port.
var _ edenhttp.Logger = ObservabilityLogger{}

// Info records one operator-facing info line as a SeverityInfo Event.
func (l ObservabilityLogger) Info(message string, fields ...any) {
	if l.Provider == nil {
		return
	}
	l.Provider.Log(context.Background(), observability.SeverityInfo, message, toFields(fields)...)
}

// Error records one operator-facing error line as a SeverityError Event.
func (l ObservabilityLogger) Error(message string, fields ...any) {
	if l.Provider == nil {
		return
	}
	l.Provider.Log(context.Background(), observability.SeverityError, message, toFields(fields)...)
}

// toFields adapts the slog-style alternating key/value varargs the edenhttp.Logger port uses into
// the observability Field constructors (the only redaction-safe door onto the stream). A non-string
// key or a dangling final key is dropped rather than panicking — a log adaptation never crashes the
// request path.
func toFields(kv []any) []observability.Field {
	out := make([]observability.Field, 0, len(kv)/2)
	for i := 0; i+1 < len(kv); i += 2 {
		key, ok := kv[i].(string)
		if !ok {
			continue
		}
		out = append(out, observability.String(key, stringify(kv[i+1])))
	}
	return out
}

// stringify renders a log field value to a telemetry-safe string. The edenhttp spine only ever
// passes string-shaped diagnostic fields (it never handles a credential), so a plain fmt is safe and
// no secret can reach this path by construction.
func stringify(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}
