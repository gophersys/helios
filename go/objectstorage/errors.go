package objectstorage

import "github.com/gophersys/libs/go/errors"

// The error taxonomy below is a set of distinct types, each carrying the offending ObjectRef
// (never a payload, never a credential), inspectable via errors.AsType[...] — never by string
// match. Each type also carries a stable errors.Kind so a wrapping caller's errors.KindOf(err)
// classifies correctly (the store wraps a Backend error with %w preserving the chain). The
// adapter returns these wrapped; callers branch on KIND across rewordings. Every message carries
// the ObjectRef's loggable form; none ever carries a payload or a credential value.

// InvalidError reports a malformed request: a zero/blank ObjectRef, a traversing key, a negative
// Put size, a nil body, or an out-of-range presign expiry. Reason names the offending field for
// the operator (it is a fixed token like "key"/"size"/"expiry", never a value).
type InvalidError struct {
	Ref    ObjectRef
	Reason string
}

// NotFoundError reports that a well-formed ObjectRef (or bucket) names no existing object.
type NotFoundError struct{ Ref ObjectRef }

// DeniedError reports that the caller lacks permission for the operation on the ObjectRef (an S3
// 403). It carries the loggable ref, never the credential that was rejected.
type DeniedError struct{ Ref ObjectRef }

// UnavailableError reports that the backing object store was unreachable (connection refused,
// 5xx, timeout); it is the one retryable failure in the taxonomy.
type UnavailableError struct{ Ref ObjectRef }

// Kind returns the stable classification of an InvalidError (KindInvalid), so a wrapping caller's
// errors.KindOf sees it through the chain.
func (e InvalidError) Kind() errors.Kind { return errors.KindInvalid }

// Kind returns the stable classification of a NotFoundError (KindNotFound).
func (e NotFoundError) Kind() errors.Kind { return errors.KindNotFound }

// Kind returns the stable classification of a DeniedError (KindPermission).
func (e DeniedError) Kind() errors.Kind { return errors.KindPermission }

// Kind returns the stable classification of an UnavailableError (KindUnavailable).
func (e UnavailableError) Kind() errors.Kind { return errors.KindUnavailable }

func (e InvalidError) Error() string {
	reason := e.Reason
	if reason == "" {
		reason = "request"
	}
	return "objectstorage: invalid " + reason + " for object " + quoteRef(e.Ref)
}

func (e NotFoundError) Error() string {
	return "objectstorage: object not found " + quoteRef(e.Ref)
}

func (e DeniedError) Error() string {
	return "objectstorage: access denied for object " + quoteRef(e.Ref)
}

func (e UnavailableError) Error() string {
	return "objectstorage: object store unavailable for object " + quoteRef(e.Ref)
}

// quoteRef renders an ObjectRef's canonical form in quotes for an error message. The zero ref
// renders as the explicit "<zero>" token so a malformed/missing reference is legible without ever
// fabricating a value.
func quoteRef(r ObjectRef) string {
	if r.IsZero() {
		return `"<zero>"`
	}
	return `"` + r.String() + `"`
}

// kindOfTaxonomy reports the errors.Kind a taxonomy error carries, or KindUnknown. It lets the
// store classify a Backend error whose concrete type is one of the taxonomy types even though it
// is not an *errors.Error: the store wraps with this Kind so errors.KindOf is correct end-to-end.
func kindOfTaxonomy(err error) errors.Kind {
	switch {
	case isType[InvalidError](err):
		return errors.KindInvalid
	case isType[NotFoundError](err):
		return errors.KindNotFound
	case isType[DeniedError](err):
		return errors.KindPermission
	case isType[UnavailableError](err):
		return errors.KindUnavailable
	default:
		return errors.KindUnknown
	}
}

// isType reports whether err's chain carries a value of type E via errors.AsType[E]. The taxonomy
// is inspected by TYPE, never by string (the errors contract).
func isType[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}
