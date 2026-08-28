package edenhttp

import (
	"context"
	"time"
)

// Clock is the minimal injected time port (mirrors agentsession.Clock / agentruntime.Clock). It
// is the spine's ONLY wall-clock source, so New stays pure and a test stamps deterministic SSE
// heartbeat instants and token-expiry checks under a fake clock. Exactly 1 method (≤5, 10 §9).
type Clock interface{ Now() time.Time }

// TokenVerifier is the consumer-defined identity port the spine's middleware drives: it turns a
// raw bearer token into a verified Identity (subject + grants) or a typed error. It is the SHAPE
// OF THE NEED — one method, well under the 10 §9 ceiling — not a mirror of a JWT library: the
// in-lib HMACVerifier realizes it for the dev-JWT path, and a consumer may bind its own
// production verifier (a real IdP) behind the SAME port without touching the middleware.
//
// Verify MUST be pure given its inputs (it reads no env, no clock of its own — the spine passes
// the Clock instant as now) so the middleware is deterministic and the verifier is trivially
// fakeable. A malformed/expired/under-signed token is a typed *errors.Error (KindUnauthenticated);
// a verifier never panics on attacker-controlled input.
type TokenVerifier interface {
	// Verify parses and authenticates the raw bearer token (the value after "Bearer "), using now
	// as the reference instant for any expiry check, and returns the caller's Identity. A token
	// that does not authenticate returns a non-nil error of Kind KindUnauthenticated.
	Verify(token string, now time.Time) (Identity, error)
}

// Logger is the narrow, redaction-safe structured-log seam the spine emits on (a consumer-defined
// port — the shape of the need, not a mirror of slog). The composition root adapts an
// observability.Provider / *slog.Logger onto it. A message or field is NEVER a secret: the spine
// never handles a resolved credential, and a token value never reaches a log line. Optional on
// Deps (a nil Logger is a silent no-op). Exactly 2 methods (≤5, 10 §9).
type Logger interface {
	// Info records one operator-facing line. Fields are alternating key/value pairs (the slog
	// convention the composition root adapts).
	Info(message string, fields ...any)

	// Error records one operator-facing error line. A field is never a secret value.
	Error(message string, fields ...any)
}

// identityContextKey is the unexported context key the middleware stashes the verified Identity
// under (revive context-keys-type: a dedicated unexported type, never a bare string). One home for
// the key so IdentityFrom is the only reader.
type identityContextKey struct{}

// withIdentity returns a child context carrying the verified Identity, set by the middleware after
// a successful Verify so a downstream pipeline's authorize stage reads it via IdentityFrom.
func withIdentity(ctx context.Context, identity Identity) context.Context {
	return context.WithValue(ctx, identityContextKey{}, identity)
}

// IdentityFrom returns the verified Identity the spine's Middleware stashed on the request context,
// and whether one is present. A handler mounted behind the Middleware always finds one; a handler
// reached without it (a misconfiguration) gets ok=false and MUST treat the request as unauthenticated.
func IdentityFrom(ctx context.Context) (Identity, bool) {
	identity, ok := ctx.Value(identityContextKey{}).(Identity)
	return identity, ok
}
