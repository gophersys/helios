package platformconnectoradapter

import (
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// mapLoadError maps a sealed-row load fault onto the secrets taxonomy so callers branch on AsType[…]
// across rewordings (secrets.md §6.6). It inspects the fault's Kind (the errors contract — typed
// inspection, never a string match): a caller-not-authorized fault (the loader enforced a
// tenancy/authorization denial) → DeniedError; a not-found → NotFoundError; everything else (a dial
// failure, a query timeout, a store outage) → UnavailableError (the one retryable signal). The
// Reference is carried; the value never is (a sealed-row load never surfaces a plaintext).
func mapLoadError(ref secrets.Reference, err error) error {
	if err == nil {
		return nil
	}
	switch errors.KindOf(err) {
	case errors.KindNotFound:
		return secrets.NotFoundError{Ref: ref}
	case errors.KindPermission, errors.KindUnauthenticated:
		return secrets.DeniedError{Ref: ref}
	case errors.KindInvalid:
		// A malformed connector id the loader rejected is a bad reference, not an outage.
		return secrets.InvalidReferenceError{Ref: ref}
	default:
		// A dial failure / timeout / store outage / unclassified fault is an availability problem — the
		// retryable signal. The connectors backing store being unreachable is transient by nature.
		return secrets.UnavailableError{Ref: ref}
	}
}

// mapUnsealError maps an envelope.Unseal fault onto the secrets taxonomy. envelope authenticates the
// record: a tampered ciphertext / wrong KEK / malformed Sealed is KindInvalid (GCM authentication
// failure), which is a bad-reference-for-this-KEK verdict → InvalidReferenceError. A KEK-resolution
// fault carries the underlying secrets Kind (the KEK reference is resolved through the same secrets
// port), so a denied/unavailable KEK maps to DeniedError/UnavailableError — the isolation seam the KEK
// itself is behind. The Reference carried is the CONNECTOR reference; the loggable KEK reference rides
// inside the wrapped envelope error, never the value.
func mapUnsealError(ref secrets.Reference, err error) error {
	if err == nil {
		return nil
	}
	switch errors.KindOf(err) {
	case errors.KindInvalid:
		// Authenticated-decryption failure (tampered/wrong-KEK) or a malformed record — not a value this
		// KEK opens, so the reference does not resolve to a usable secret here.
		return secrets.InvalidReferenceError{Ref: ref}
	case errors.KindNotFound:
		// The KEK reference itself resolves to no secret (a mis-seeded platform Vault) — surface it as
		// the connector being unresolvable rather than pretend it succeeded.
		return secrets.NotFoundError{Ref: ref}
	case errors.KindPermission, errors.KindUnauthenticated:
		return secrets.DeniedError{Ref: ref}
	default:
		// A KEK backing-store outage (Vault unreachable) is transient — the one retryable signal.
		return secrets.UnavailableError{Ref: ref}
	}
}
