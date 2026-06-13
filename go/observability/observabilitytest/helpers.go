package observabilitytest

import (
	"strings"
	"time"

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

// asString / asInt64 / asDuration project a telemetry value to a concrete type,
// returning the zero value on a type mismatch. They keep decodeLedger's per-field
// dispatch a single assignment each (no nested type-assert branch), so the decoder
// stays flat and the comma-ok bool is never silently discarded.
func asString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func asInt64(v any) int64 {
	if n, ok := v.(int64); ok {
		return n
	}
	return 0
}

func asDuration(v any) time.Duration {
	if d, ok := v.(time.Duration); ok {
		return d
	}
	return 0
}

// decodeLedger reconstructs a typed Ledger from a "cost.ledger" Event's Fields —
// the inverse of LedgerEvent — so a budget test round-trips token/cost data. A
// field whose projection has an unexpected type contributes its zero value.
func decodeLedger(e observability.Event) observability.Ledger {
	var l observability.Ledger
	for _, f := range e.Fields {
		if f.Value == nil {
			// A Field with a nil Valuer (e.g. a raw Field{Value: nil} literal that
			// bypassed the Any constructor) carries no telemetry value; skip it
			// rather than nil-deref, mirroring containsCanary's nil guard so the two
			// inspection paths agree.
			continue
		}
		tv := f.Value.TelemetryValue()
		switch f.Key {
		case "run.id":
			l.RunID = asString(tv)
		case "phase.id":
			l.PhaseID = asString(tv)
		case "model":
			l.Model = asString(tv)
		case "harness":
			l.Harness = asString(tv)
		case "tokens.in":
			l.TokensIn = asInt64(tv)
		case "tokens.out":
			l.TokensOut = asInt64(tv)
		case "cache.hits":
			l.CacheHits = asInt64(tv)
		case "cost.micros":
			l.CostMicros = asInt64(tv)
		case "retries":
			l.Retries = int32(asInt64(tv))
		case "wall.time":
			l.WallTime = asDuration(tv)
		}
	}
	return l
}
