package ompadapter

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

// defaultDigester truncates a raw payload to maxDigestBytes and marks truncation. It never
// returns the full payload (the bounded-digest guarantee).
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
// across millions of calls (aligned with observability.Ledger.CostMicros). It rounds to the
// nearest micro-unit. A non-finite or negative cost maps to the -1 "unreported" sentinel.
// omp reports cost as a USD float on every usage block (e.g. cost.total = 0.000346136).
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

// reasonFromErrorStatus maps an omp assistant-message HTTP errorStatus to the branchable
// ErrorReason the engine acts on (retry on rate-limit, abort on auth). omp surfaces the
// upstream provider HTTP status verbatim on a stopReason:"error" message (the spike captured
// 402 for insufficient credit and 404 for an unavailable model).
func reasonFromErrorStatus(status int) agentsession.ErrorReason {
	switch status {
	case 401, 403:
		return agentsession.ReasonAuth
	case 402:
		return agentsession.ReasonBudget
	case 429:
		return agentsession.ReasonRateLimit
	default:
		return agentsession.ReasonHarnessError
	}
}

// statusDetail renders a redacted, operator-safe detail string for a failure status. It
// emits ONLY the numeric status (a fixed enum the provider returns), never the provider's
// errorMessage text — that message can echo a request body and is not guaranteed
// secret-free, so it is kept off the Event.
func statusDetail(status int) string {
	if status == 0 {
		return "harness reported an error result"
	}
	return "harness upstream error status: " + itoa(status)
}

// itoa renders a non-negative HTTP status as its base-10 string without a strconv import in
// the hot path. Statuses are small; the loop is bounded.
func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	negative := n < 0
	if negative {
		n = -n
	}
	var buf [12]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if negative {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}
