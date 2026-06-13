package agentsession

import (
	"crypto/rand"
	"encoding/hex"
)

// budgetAbortReason is the Abort text the library sends when the cumulative cost
// crosses the budget ceiling (the single budget authority). The adapter maps it to its
// native cancel; the terminal carries TurnBudgetExceeded.
const budgetAbortReason = "eden:budget-exceeded"

// permissionAnswerPrefix tags the normalized control frame that answers a permission
// request, so the adapter's Send can map it to the harness's native permission-answer.
const permissionAnswerPrefix = "eden:permission:"

// sessionID derives a stable, unique session id from the spec + route plus a random
// suffix, so two sessions over the same workspace never collide on the transcript key.
// It is NOT a secret and carries no credential material.
//
//nolint:gocritic // contract §2: Spec is the frozen, copyable session input (the configuration pattern); the port takes it by value.
func sessionID(spec Spec, route Route) string {
	suffix := randomSuffix()
	base := route.Harness
	if spec.Routing.Role != "" {
		base += "-" + spec.Routing.Role
	}
	if spec.Routing.Phase != "" {
		base += "-" + spec.Routing.Phase
	}
	return "session-" + base + "-" + suffix
}

// randomSuffix returns 8 random hex chars for session-id uniqueness. A crypto/rand
// failure (effectively impossible) falls back to a fixed token rather than panicking;
// collisions are still avoided in practice by the harness+role+phase prefix.
func randomSuffix() string {
	buf := make([]byte, 4)
	if _, err := rand.Read(buf); err != nil {
		return "00000000"
	}
	return hex.EncodeToString(buf)
}

// permissionAnswer renders the normalized answer frame for a resolved permission
// request: the request id, the allow/deny verdict, and the deciding identity. It
// carries NO secret and is bounded.
func permissionAnswer(requestID string, decision Decision) string {
	verdict := "deny"
	if decision.Allow {
		verdict = "allow"
	}
	return permissionAnswerPrefix + requestID + ":" + verdict + ":" + decision.By
}
