package agentsession

import (
	"crypto/rand"
	"encoding/hex"
	"time"

	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
)

// budgetAbortReason is the Abort text the library sends when the cumulative cost
// crosses the budget ceiling (the single budget authority). The adapter maps it to its
// native cancel; the terminal carries TurnBudgetExceeded.
const budgetAbortReason = "eden:budget-exceeded"

// defaultPermissionTimeout is the safe default for the chat chain's human-Resolve window
// (Spec.PermissionTimeout zero) and the advisor reasoning bound. It is long enough for a
// human to react in the chat, short enough that an unattended chat session does not hang
// indefinitely before the advisor/default-deny fallback fires.
const defaultPermissionTimeout = 5 * time.Minute

// recentDeltaWindow bounds the recent text/tool delta ring handed to the advisor in the
// AdviceContext (a small, redacted snippet — never the whole transcript, never a secret).
const recentDeltaWindow = 16

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

// permissionAnswer renders the normalized answer frame for a resolved permission request
// through the grammar's ONE HOME (internal/controlframe). The Rationale is the founder
// model's audit-logged reasoning; handing it to the codec here is how the library's
// produced Decision carries it to the adapter (which surfaces by/verdict on the wire), so
// the field is consumed, not dead.
func permissionAnswer(requestID string, decision Decision) string {
	return controlframe.EncodePermission(requestID, decision.Allow, decision.By, decision.Rationale)
}
