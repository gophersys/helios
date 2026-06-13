package claudeadapter

import (
	"math"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// maxDigestBytes bounds a tool arg/result digest. The full payload rides the redacted
// transcript (07 §2); the event carries only a bounded summary so a leak surface is
// minimized and the stream stays light.
const maxDigestBytes = 256

// digester produces a bounded, redacted summary of a raw tool arg/result payload. The
// adapter owns redacting non-secret-typed sensitive payloads (command output, file
// contents) before an Event is emitted (Q9): credentials are kept off the stream by the
// secrets.Secret type, but file/command bytes get bounded here.
type digester func(raw []byte) string

// defaultDigester truncates a raw payload to maxDigestBytes and marks truncation. It
// never returns the full payload (the bounded-digest guarantee).
func defaultDigester(raw []byte) string {
	if len(raw) == 0 {
		return ""
	}
	if len(raw) <= maxDigestBytes {
		return string(raw)
	}
	return string(raw[:maxDigestBytes]) + "…(truncated)"
}

// usdToMicros converts a reported USD cost to integer micro-units with no float drift
// across millions of calls (aligned with observability.Ledger.CostMicros). It rounds to
// the nearest micro-unit. A non-finite or negative cost maps to the -1 "unreported"
// sentinel.
func usdToMicros(usd float64) int64 {
	if math.IsNaN(usd) || math.IsInf(usd, 0) || usd < 0 {
		return -1
	}
	return int64(math.Round(usd * 1_000_000))
}

// millisToDuration converts a reported millisecond wall time to a time.Duration.
func millisToDuration(millis int64) time.Duration {
	return time.Duration(millis) * time.Millisecond
}

// reasonFromSubtype maps a result-line failure subtype to the branchable ErrorReason the
// engine acts on (retry on rate-limit, abort on auth).
func reasonFromSubtype(subtype string) agentsession.ErrorReason {
	switch subtype {
	case "error_max_turns":
		return agentsession.ReasonMaxTurns
	case "error_during_execution":
		return agentsession.ReasonHarnessError
	case "error_rate_limit":
		return agentsession.ReasonRateLimit
	case "error_budget", "error_max_budget":
		return agentsession.ReasonBudget
	default:
		return agentsession.ReasonHarnessError
	}
}

// subtypeDetail returns a redacted, operator-safe detail string for a failure subtype
// (never a credential — the subtype is a fixed enum the CLI emits).
func subtypeDetail(subtype string) string {
	if subtype == "" {
		return "harness reported an error result"
	}
	return "harness result subtype: " + subtype
}
