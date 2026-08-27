package middleware

import "github.com/gophersys/libs/go/errors"

// errServerStatus is the sentinel the request Scope's Outcome carries when a response was a 5xx — a
// declared, typed value (never an ad-hoc New at the call site, per the errors contract) so the span
// is marked failed on a server fault without inventing a throwaway error inline. It is internal to
// the middleware seam; it never reaches the client (the response was already written).
var errServerStatus = errors.New(errors.KindInternal, "middleware: request completed with a 5xx status")
