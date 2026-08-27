package agentsessiontest

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
)

// This file holds the deterministic Event builders a test uses to pin an exact script,
// plus the internal frame parser the fake conn uses to interpret the library's
// normalized permission-answer control frame.

// fixedEmitTime is the deterministic Time stamped on built events so the fake is
// reproducible; the library re-stamps a zero Time via the injected Clock, so leaving it
// zero is also fine. Builders set it explicitly so a script's Time is stable.
var fixedEmitTime = time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)

// ReadyEvent builds the Ready handshake transition (the fake emits it automatically at
// Spawn; exposed for tests that script their own lead-in).
func ReadyEvent() agentsession.Event { return readyEvent() }

func readyEvent() agentsession.Event {
	return agentsession.Event{
		Kind:  agentsession.EventSessionState,
		Time:  fixedEmitTime,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}
}

// MessageStart builds an assistant message-start event.
func MessageStart(role string) agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventMessageStart,
		Time:    fixedEmitTime,
		Message: &agentsession.MessagePayload{Role: role},
	}
}

// TextDelta builds a streamed assistant text fragment.
func TextDelta(delta string) agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventTextDelta,
		Time:    fixedEmitTime,
		Message: &agentsession.MessagePayload{Role: "assistant", Delta: delta},
	}
}

// ThinkingProgress builds a pre-message reasoning HEARTBEAT carrying the running estimated
// thinking-token count (no content yet) — the signal a UI shows as a live "thinking…" status
// while the model reasons before emitting any assistant text.
func ThinkingProgress(tokens int) agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventThinkingProgress,
		Time:    fixedEmitTime,
		Message: &agentsession.MessagePayload{Role: "assistant", Tokens: tokens},
	}
}

// ThinkingDelta builds a reasoning/thinking fragment.
func ThinkingDelta(delta string) agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventThinkingDelta,
		Time:    fixedEmitTime,
		Message: &agentsession.MessagePayload{Role: "assistant", Delta: delta},
	}
}

// MessageEnd builds the assistant message-completed event.
func MessageEnd() agentsession.Event {
	return agentsession.Event{Kind: agentsession.EventMessageEnd, Time: fixedEmitTime}
}

// ToolStart builds a tool-invocation-start event. grantID may be left empty so the
// library's grant-linkage stamps it from the Spec.Grants.
func ToolStart(callID, name, argsSummary string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventToolStart,
		Time: fixedEmitTime,
		Tool: &agentsession.ToolPayload{CallID: callID, Name: name, ArgsSummary: argsSummary},
	}
}

// ToolUpdate builds a tool partial-result event (OMP partial streaming).
func ToolUpdate(callID, partialDigest string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventToolUpdate,
		Time: fixedEmitTime,
		Tool: &agentsession.ToolPayload{CallID: callID, PartialDigest: partialDigest},
	}
}

// ToolEnd builds a tool-invocation-end event.
func ToolEnd(callID string, outcome agentsession.ToolOutcome, resultDigest string, duration time.Duration) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventToolEnd,
		Time: fixedEmitTime,
		Tool: &agentsession.ToolPayload{
			CallID: callID, Outcome: outcome, ResultDigest: resultDigest, Duration: duration,
		},
	}
}

// PermissionRequest builds an out-of-grant permission-request event.
func PermissionRequest(requestID, tool, reason string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventPermissionRequest,
		Time: fixedEmitTime,
		Permission: &agentsession.PermissionPayload{
			RequestID: requestID, Tool: tool, Reason: reason, Decision: agentsession.GrantPending,
		},
	}
}

// PermissionResolved builds a permission-resolved record (the fake emits it as the
// scripted reaction to a permission answer).
func PermissionResolved(requestID string, decision agentsession.GrantDecision, by string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventPermissionResolved,
		Time: fixedEmitTime,
		Permission: &agentsession.PermissionPayload{
			RequestID: requestID, Decision: decision, By: by,
		},
	}
}

// Usage builds a token-usage tick. cumulative=true marks session-to-date totals.
//
//nolint:gocritic // UsageMeter/TokenLedger are the contract's copyable value records (§2); the builder takes them by value.
func Usage(meter agentsession.UsageMeter) agentsession.Event {
	clone := meter
	return agentsession.Event{Kind: agentsession.EventUsage, Time: fixedEmitTime, Usage: &clone}
}

// Result builds a clean terminal Result carrying the authoritative ledger.
//
//nolint:gocritic // UsageMeter/TokenLedger are the contract's copyable value records (§2); the builder takes them by value.
func Result(ledger agentsession.TokenLedger, resultText, stopReason string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventResult,
		Time: fixedEmitTime,
		Terminal: &agentsession.TerminalPayload{
			Outcome: agentsession.TurnCompleted, Ledger: ledger,
			ResultText: resultText, StopReason: stopReason,
		},
	}
}

// Extension builds a forward-compat EventExtension carrying raw harness bytes (the
// rate_limit_event lesson — never dropped, never fatal).
func Extension(raw []byte) agentsession.Event {
	return agentsession.Event{Kind: agentsession.EventExtension, Time: fixedEmitTime, Extension: raw}
}

// resultEvent is the fake's default clean terminal when a script omits one.
func resultEvent() agentsession.Event {
	return Result(agentsession.TokenLedger{
		UsageMeter: agentsession.UsageMeter{Harness: "fake", CostMicros: 0, Cumulative: true},
		Turns:      1,
	}, "done", "end_turn")
}

// abortedEvent is the fake's terminal for an Abort/Close (carries the By reason text).
func abortedEvent(by string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventAborted,
		Time: fixedEmitTime,
		Terminal: &agentsession.TerminalPayload{
			Outcome: agentsession.TurnAborted,
			Ledger:  agentsession.TokenLedger{UsageMeter: agentsession.UsageMeter{Harness: "fake", Cumulative: true}},
			By:      by,
		},
	}
}

// parsePermissionAnswer interprets the library's normalized answer frame through the
// grammar's ONE HOME (agentsession/internal/controlframe). It returns the request id,
// whether it was allowed, and ok=false for any non-answer frame.
func parsePermissionAnswer(text string) (requestID string, allowed, ok bool) {
	requestID, allowed, _, _, ok = controlframe.DecodePermission(text)
	return requestID, allowed, ok
}
