package gateway

import "github.com/gophersys/libs/go/agentsession"

// This file holds the stable lower-kebab wire tokens for the agentsession enums that do
// not expose a String() method (ToolOutcome, GrantDecision, TurnOutcome, ErrorReason).
// The tokens mirror the library's naming convention so the UI branches on one stable
// vocabulary across every event field. The mapping lives here at the seam (one home).

// toolOutcomeToken renders a ToolOutcome as a stable token. The zero value (OK) renders
// "ok"; only an end event populates a meaningful outcome.
func toolOutcomeToken(outcome agentsession.ToolOutcome) string {
	switch outcome {
	case agentsession.ToolOutcomeOK:
		return "ok"
	case agentsession.ToolOutcomeError:
		return "error"
	case agentsession.ToolOutcomeDenied:
		return "denied"
	default:
		return "ok"
	}
}

// grantDecisionToken renders a GrantDecision as a stable token.
func grantDecisionToken(decision agentsession.GrantDecision) string {
	switch decision {
	case agentsession.GrantPending:
		return "pending"
	case agentsession.GrantAllowed:
		return "allowed"
	case agentsession.GrantDenied:
		return "denied"
	default:
		return "pending"
	}
}

// turnOutcomeToken renders a TurnOutcome as a stable token.
func turnOutcomeToken(outcome agentsession.TurnOutcome) string {
	switch outcome {
	case agentsession.TurnCompleted:
		return "completed"
	case agentsession.TurnAborted:
		return "aborted"
	case agentsession.TurnFailed:
		return "failed"
	case agentsession.TurnMaxTurns:
		return "max-turns"
	case agentsession.TurnBudgetExceeded:
		return "budget-exceeded"
	default:
		return "completed"
	}
}

// errorReasonToken renders an ErrorReason as a stable token (empty for the unknown
// zero value so a non-failed terminal omits the field).
func errorReasonToken(reason agentsession.ErrorReason) string {
	switch reason {
	case agentsession.ReasonUnknown:
		return ""
	case agentsession.ReasonAuth:
		return "auth"
	case agentsession.ReasonRateLimit:
		return "rate-limit"
	case agentsession.ReasonBudget:
		return "budget"
	case agentsession.ReasonMaxTurns:
		return "max-turns"
	case agentsession.ReasonTransport:
		return "transport"
	case agentsession.ReasonHarnessError:
		return "harness-error"
	default:
		return ""
	}
}
