package forge

import (
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// The error taxonomy below is a set of distinct types, each carrying the offending
// identity (the owner/name of the repository or the credential's loggable
// Reference) — NEVER the token value — inspectable via errors.AsType[...], never by
// string match (the errors contract, 12 §rule). The adapter returns each wrapped
// with the matching errors.Kind via errors.Wrap(... %w), so a caller branches on
// errors.KindOf across rewordings, and the cause chain stays reachable for
// diagnosis. Every message is operator-safe: it carries the repository slug or the
// Reference's canonical form, none ever carries a secret value.

// InvalidRequestError reports a malformed CreateRepoRequest (empty Owner/Name, a
// zero Credential Reference) caught at the port boundary before any I/O. It maps to
// errors.KindInvalid.
type InvalidRequestError struct {
	// Owner is the offending request's owner ("" when that is the missing field).
	Owner string
	// Name is the offending request's name ("" when that is the missing field).
	Name string
	// Reason names the specific validation that failed (operator-safe text).
	Reason string
}

func (e InvalidRequestError) Error() string {
	return "forge: invalid create-repository request for " + slug(e.Owner, e.Name) + ": " + e.Reason
}

// UnauthenticatedError reports that the forge rejected the credential, or that the
// credential could not be resolved through the secrets port. It carries the
// loggable Credential Reference (never the value) and maps to
// errors.KindUnauthenticated.
type UnauthenticatedError struct {
	// Owner is the repository owner the call targeted.
	Owner string
	// Name is the repository name the call targeted.
	Name string
	// Credential is the loggable reference whose resolution or use was rejected.
	Credential secrets.Reference
	// Cause is the optional underlying error (e.g. a secrets.DeniedError) preserved
	// in the chain for AsType/Is traversal. It NEVER carries a secret value.
	Cause error
}

func (e UnauthenticatedError) Error() string {
	message := "forge: authentication rejected for " + slug(e.Owner, e.Name) +
		" with credential " + quoteRef(e.Credential)
	if e.Cause != nil {
		return message + ": " + e.Cause.Error()
	}
	return message
}

// Unwrap exposes the underlying cause so a caller can inspect a wrapped
// secrets.DeniedError beneath the forge-typed boundary.
func (e UnauthenticatedError) Unwrap() error { return e.Cause }

// ConflictError reports a repository-state conflict the connector could not
// reconcile — a 422 whose validation code is NOT the idempotent "already exists"
// case (which succeeds via read-back), or a read-back that returned a repository
// the request did not describe. It maps to errors.KindConflict.
type ConflictError struct {
	// Owner is the repository owner the call targeted.
	Owner string
	// Name is the repository name the call targeted.
	Name string
	// Reason names the conflict the connector could not reconcile (operator-safe).
	Reason string
}

func (e ConflictError) Error() string {
	return "forge: conflict creating " + slug(e.Owner, e.Name) + ": " + e.Reason
}

// NotFoundError reports that a resource the connector expected (e.g. the
// read-back of an "already exists" repository) was absent. It maps to
// errors.KindNotFound.
type NotFoundError struct {
	// Owner is the repository owner the call targeted.
	Owner string
	// Name is the repository name the call targeted.
	Name string
}

func (e NotFoundError) Error() string {
	return "forge: repository not found: " + slug(e.Owner, e.Name)
}

// UnavailableError reports a transient transport or server-side fault (a network
// error, a 5xx, or a malformed/undecodable response) the caller MAY retry. It is
// the one retryable failure in the taxonomy and maps to errors.KindUnavailable.
type UnavailableError struct {
	// Owner is the repository owner the call targeted.
	Owner string
	// Name is the repository name the call targeted.
	Name string
	// Reason names the transient fault (operator-safe text; never a token).
	Reason string
	// Cause is the optional underlying error (a transport error, a 5xx-derived
	// secrets fault) preserved in the chain. It NEVER carries a secret value.
	Cause error
}

func (e UnavailableError) Error() string {
	message := "forge: forge unavailable for " + slug(e.Owner, e.Name) + ": " + e.Reason
	if e.Cause != nil {
		return message + ": " + e.Cause.Error()
	}
	return message
}

// Unwrap exposes the underlying transient cause for chain traversal.
func (e UnavailableError) Unwrap() error { return e.Cause }

// Classify maps a forge taxonomy error to its stable errors.Kind. It is the ONE
// place the type→Kind mapping lives (one concept, one home — 10 §9), so an adapter
// never re-derives it: an adapter wraps a taxonomy error via Wrap and the chain
// classifies. A foreign error (no taxonomy type in the chain) classifies as
// KindUnknown, which the edge maps to INTERNAL — never silently retryable.
func Classify(err error) errors.Kind {
	switch {
	case errors.IsType[InvalidRequestError](err):
		return errors.KindInvalid
	case errors.IsType[ForbiddenDeletionError](err):
		return errors.KindInvalid
	case errors.IsType[UnauthenticatedError](err):
		return errors.KindUnauthenticated
	case errors.IsType[ConflictError](err):
		return errors.KindConflict
	case errors.IsType[NotFoundError](err):
		return errors.KindNotFound
	case errors.IsType[UnavailableError](err):
		return errors.KindUnavailable
	default:
		return errors.KindUnknown
	}
}

// Wrap wraps a forge taxonomy error into the Eden errors model with its classified
// errors.Kind, preserving the cause chain under %w so a caller inspects by Kind
// (errors.KindOf) or by type (errors.AsType). It is the single classification seam
// every adapter funnels its failures through (one home for the type→Kind contract);
// a nil error stays nil so the happy path reads linearly.
func Wrap(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(Classify(err), err.Error(), err)
}

// slug renders the "owner/name" repository identity for an operator-safe message,
// degrading legibly when a field is missing rather than rendering a bare "/".
func slug(owner, name string) string {
	switch {
	case owner == "" && name == "":
		return "<unspecified>"
	case owner == "":
		return "<unspecified>/" + name
	case name == "":
		return owner + "/<unspecified>"
	default:
		return owner + "/" + name
	}
}

// quoteRef renders a Reference's canonical (loggable) form in quotes for a message.
// The zero reference renders as the explicit "<zero>" token so a missing credential
// is legible without ever fabricating a value (mirrors secrets.quoteRef).
func quoteRef(r secrets.Reference) string {
	if r.IsZero() {
		return `"<zero>"`
	}
	return `"` + r.String() + `"`
}
