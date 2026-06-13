package observabilitytest

import (
	"strconv"
	"strings"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// itoa renders a uint64 without importing fmt — keeps span/trace ID minting
// allocation-light and the fake stdlib-only.
func itoa(n uint64) string { return strconv.FormatUint(n, 10) }

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

// decodeLedger reconstructs a typed Ledger from a "cost.ledger" Event's Fields —
// the inverse of LedgerEvent — so a budget test round-trips token/cost data.
func decodeLedger(e observability.Event) observability.Ledger {
	var l observability.Ledger
	for _, f := range e.Fields {
		tv := f.Value.TelemetryValue()
		switch f.Key {
		case "run.id":
			l.RunID, _ = tv.(string)
		case "phase.id":
			l.PhaseID, _ = tv.(string)
		case "model":
			l.Model, _ = tv.(string)
		case "harness":
			l.Harness, _ = tv.(string)
		case "tokens.in":
			l.TokensIn, _ = tv.(int64)
		case "tokens.out":
			l.TokensOut, _ = tv.(int64)
		case "cache.hits":
			l.CacheHits, _ = tv.(int64)
		case "cost.micros":
			l.CostMicros, _ = tv.(int64)
		case "retries":
			if n, ok := tv.(int64); ok {
				l.Retries = int32(n)
			}
		case "wall.time":
			l.WallTime, _ = tv.(time.Duration)
		}
	}
	return l
}
