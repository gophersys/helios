package configuration

// ParseError wraps an I/O failure surfaced by Parse/Merge (the err channel),
// so callers branch on structure, not strings. It is inspectable via
// errors.AsType[*ParseError] and wraps the underlying Source error with %w.
// (Config-is-wrong is NOT a ParseError — it is Diagnostics; see rationale 4.)
type ParseError struct {
	Source string // the input name that failed to read
	Err    error  // the wrapped Source.Read error
}

func (e *ParseError) Error() string {
	if e.Err == nil {
		return e.Source + ": read failed"
	}
	return e.Source + ": " + e.Err.Error()
}

func (e *ParseError) Unwrap() error { return e.Err }
