package envelope

import (
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// invalidConfig builds the typed error a malformed Config or Deps yields at New. It carries the
// KindInvalid classification the errors contract mandates for a wiring mistake; the message names
// the missing field, never a value (there is no value at New — only the loggable KEK Reference).
func invalidConfig(message string) *errors.Error {
	return errors.New(errors.KindInvalid, "envelope: "+message)
}

// wrapKEK wraps a KEK-resolution failure, translating the secrets port's typed error taxonomy to
// the errors.Kind a caller branches on (a NotFound KEK reads differently from an Unavailable Vault).
// The secrets errors are distinct types that carry no errors.Kind of their own, so kindOfSecrets is
// the ONE place envelope maps them (never a string match — typed inspection, the errors contract).
// The loggable KEK Reference rides the field set; the KEK value never does (it was never resolved on
// this path).
func wrapKEK(reference secrets.Reference, cause error) *errors.Error {
	return errors.Wrap(kindOfSecrets(cause), "envelope: resolve KEK", cause).
		WithField("kek-reference", reference.String())
}

// kindOfSecrets maps the secrets port's typed error taxonomy to the errors.Kind axis. The secrets
// errors are distinct value types (secrets.NotFoundError, ...), not *errors.Error, so errors.KindOf
// would flatten them all to KindUnknown; this typed switch preserves the classification the caller
// needs. An unrecognized cause keeps the errors.KindOf verdict (which is KindUnknown for a bare
// error) so a new secrets error type is visibly unclassified, not silently miscoded.
func kindOfSecrets(cause error) errors.Kind {
	switch {
	case errors.IsType[secrets.NotFoundError](cause):
		return errors.KindNotFound
	case errors.IsType[secrets.DeniedError](cause):
		return errors.KindPermission
	case errors.IsType[secrets.UnavailableError](cause):
		return errors.KindUnavailable
	case errors.IsType[secrets.InvalidReferenceError](cause):
		return errors.KindInvalid
	default:
		return errors.KindOf(cause)
	}
}

// invalidSealed builds the typed error an unusable Sealed record yields at Unseal — a zero record,
// a short/malformed nonce or wrapped-DEK, or a GCM authentication failure (a tampered ciphertext or
// the wrong KEK). All are KindInvalid: the record is not something this KEK can open. The message
// names WHAT was wrong (the field), never any byte content — the blobs are opaque and never a secret
// value in the clear, so no redaction concern, but there is nothing useful to surface anyway.
func invalidSealed(message string) *errors.Error {
	return errors.New(errors.KindInvalid, "envelope: "+message)
}
