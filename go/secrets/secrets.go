// Package secrets is the port for resolving opaque references to short-lived secret
// values at point of use. Its discipline lives in the TYPE: a Secret is constructed
// un-printable — String/GoString/Format/MarshalText/MarshalJSON and slog.LogValue all
// redact — so values cannot reach logs, telemetry, or transcripts by construction (07 §2,
// 10 §4), not by a filter list. References are loggable and live in configuration; values
// never do.
package secrets

import (
	"context"
	"strings"
)

// schemeSeparator is the canonical scheme delimiter in a Reference's raw form.
const schemeSeparator = "://"

// Reference is the opaque, loggable handle to a secret. It lives in configuration and is
// safe to print, serialize, telemeter, and persist. It names a secret; it never carries the
// value. It is comparable (usable as a map key for routing and for dependency records).
// The zero value is the invalid reference, which Resolve rejects.
//
// The unexported field makes every Reference pass through ParseReference / Ref, so each is
// shape-validated and the struct stays comparable without an addressable field. Zero value:
// invalid (IsZero reports true). Safe for concurrent use (immutable value).
type Reference struct {
	// raw is the canonical form, e.g. "vault://eden/connectors/github#token" or a bare
	// stable name like "anthropic-api-key" (the implicit-scheme form).
	raw string
}

// ParseReference validates and constructs a Reference from its canonical string form. PURE:
// no I/O, no resolution — it checks shape only. A bare name with no "scheme://" is accepted
// and routed via Config.DefaultScheme at Resolve time. The scheme selects the adapter at the
// composition root; this package does not interpret it. Returns a wrapped error
// (errors.AsType[InvalidReferenceError]) for malformed input.
func ParseReference(s string) (Reference, error) {
	if !validReference(s) {
		return Reference{}, InvalidReferenceError{Ref: Reference{}}
	}
	return Reference{raw: s}, nil
}

// Ref is the ergonomic constructor for the common bare-name case (e.g.
// Ref("anthropic-api-key")), where the scheme is supplied by Config.DefaultScheme. It panics
// only on a name that cannot be a valid Reference under any scheme; for config-driven input
// prefer ParseReference. Pure; no I/O.
func Ref(name string) Reference {
	r, err := ParseReference(name)
	if err != nil {
		panic("secrets.Ref: " + err.Error())
	}
	return r
}

// validReference reports whether s can be a Reference under any scheme. The shape rule is
// minimal by design: a Reference is any non-empty string with no leading/trailing or interior
// whitespace (whitespace would be ambiguous in a log line or a config value). Scheme routing
// is the composition root's job, not a validation concern, so any non-whitespace token —
// bare name or "scheme://path" — is accepted.
func validReference(s string) bool {
	if s == "" {
		return false
	}
	if strings.TrimSpace(s) != s {
		return false
	}
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' || r == '\r' {
			return false
		}
	}
	return true
}

// String returns the canonical form. A Reference is loggable by design.
func (r Reference) String() string { return r.raw }

// Scheme returns the leading scheme (the substring before "://"), used at the composition
// root to route a Reference to an adapter. Empty when the Reference carries no explicit
// scheme (DefaultScheme applies) and for the zero value.
func (r Reference) Scheme() string {
	i := strings.Index(r.raw, schemeSeparator)
	if i < 0 {
		return ""
	}
	return r.raw[:i]
}

// IsZero reports whether r is the invalid zero Reference.
func (r Reference) IsZero() bool { return r.raw == "" }

// Provider resolves references to secrets. It is the ONLY port a consumer depends on;
// adapters (vault, env-for-development, keychain) implement it and are bound at the
// composition root. Accept this interface; return the concrete adapter (or *Mediator).
// Implementations MUST be safe for concurrent use by multiple goroutines.
type Provider interface {
	// Resolve mints/fetches the current value for ref and returns a fresh Secret the caller
	// owns and must Zeroize (defer sec.Zeroize() is the idiom). Resolve is the only blocking
	// method, so context is first. On failure it returns a wrapped error inspectable via
	// errors.AsType for InvalidReferenceError / NotFoundError / DeniedError / UnavailableError;
	// the error message carries the Reference, never the value. It never returns a non-nil
	// Secret together with a non-nil error.
	Resolve(ctx context.Context, ref Reference) (*Secret, error)
}
