package secrets

// The error taxonomy below is a set of distinct types, each carrying the offending Reference
// (never the value), inspectable via errors.AsType[...] — never by string match. Adapters
// return these wrapped with %w so callers branch on kind across rewordings. Every message
// carries the Reference's canonical (loggable) form; none ever carries a secret value.

// InvalidReferenceError reports that a Reference is malformed or the zero value.
type InvalidReferenceError struct{ Ref Reference }

// NotFoundError reports that a well-formed Reference names no existing secret.
type NotFoundError struct{ Ref Reference }

// DeniedError reports that the caller lacks the scope required to resolve a Reference.
type DeniedError struct{ Ref Reference }

// UnavailableError reports that the backing store was unreachable; it is the one retryable
// failure in the taxonomy.
type UnavailableError struct{ Ref Reference }

// ZeroizedError reports a Use call on a Secret whose bytes were already wiped by Zeroize.
type ZeroizedError struct{}

func (e InvalidReferenceError) Error() string {
	return "secrets: invalid reference " + quoteRef(e.Ref)
}

func (e NotFoundError) Error() string {
	return "secrets: secret not found for reference " + quoteRef(e.Ref)
}

func (e DeniedError) Error() string {
	return "secrets: access denied for reference " + quoteRef(e.Ref)
}

func (e UnavailableError) Error() string {
	return "secrets: backing store unavailable for reference " + quoteRef(e.Ref)
}

func (e ZeroizedError) Error() string {
	return "secrets: secret already zeroized"
}

// quoteRef renders a Reference's canonical form in quotes for an error message. The zero
// reference renders as the explicit "<zero>" token so a malformed/missing reference is legible
// without ever fabricating a value.
func quoteRef(r Reference) string {
	if r.IsZero() {
		return `"<zero>"`
	}
	return `"` + r.String() + `"`
}
