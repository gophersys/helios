package agentsession

import (
	"crypto/rand"
	"encoding/hex"
	"time"
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

// rationaleSeparator delimits the OPTIONAL audit Rationale appended to the answer frame.
// It is the ASCII unit separator (0x1f), a byte that never appears in a request id, a
// verdict, or a By identity ("user:id" / "policy:name" / "advisor:name") — so a frame
// WITHOUT a rationale parses byte-identically to the pre-ratification frame (the change is
// additive: a parser that ignores the separator reads the unchanged id:verdict:by).
const rationaleSeparator = "\x1f"

// permissionAnswer renders the normalized answer frame for a resolved permission request:
// the request id, the allow/deny verdict, the deciding identity, and — when the decider
// supplied one — the audit Rationale after a 0x1f separator. It carries NO secret and is
// bounded. The Rationale is the founder model's audit-logged reasoning; appending it here
// is how the library's produced Decision carries it to the adapter (which strips the
// separator and surfaces by/verdict on the wire), so the field is consumed, not dead.
func permissionAnswer(requestID string, decision Decision) string {
	verdict := "deny"
	if decision.Allow {
		verdict = "allow"
	}
	frame := permissionAnswerPrefix + requestID + ":" + verdict + ":" + decision.By
	if decision.Rationale != "" {
		frame += rationaleSeparator + decision.Rationale
	}
	return frame
}
