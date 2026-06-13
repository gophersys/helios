package secrets

// The error taxonomy. Each is a distinct type carrying the offending Reference (never the
// value), inspectable via errors.AsType[...] — never by string match. Adapters return these
// wrapped with %w so callers branch on kind across rewordings. The message carries the
// Reference's canonical (loggable) form; it never carries a secret value.
type (
	InvalidReferenceError struct{ Ref Reference } // ref malformed or zero
	NotFoundError         struct{ Ref Reference } // ref well-formed, no such secret
	DeniedError           struct{ Ref Reference } // caller lacks scope for ref
	UnavailableError      struct{ Ref Reference } // backing store unreachable (retryable)
	ZeroizedError         struct{}                // Use after Zeroize
)

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
