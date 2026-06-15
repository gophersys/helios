package observabilitytest

import (
	"strings"

	"github.com/gophersys/libs/go/observability"
)

// leakError reports a Field whose telemetry projection rendered the secret canary.
type leakError struct {
	Field  string
	Canary string
}

func (e *leakError) Error() string {
	return "observabilitytest: field " + e.Field + " leaked canary " + e.Canary
}

// containsCanary reports whether v's telemetry projection renders canary as a
// substring. It inspects the redacted projection only — never any raw material —
// because TelemetryValue is the only door onto the stream.
func containsCanary(v observability.Valuer, canary string) bool {
	if v == nil {
		return false
	}
	tv := v.TelemetryValue()
	switch s := tv.(type) {
	case string:
		return strings.Contains(s, canary)
	case []byte:
		return strings.Contains(string(s), canary)
	default:
		return false
	}
}
