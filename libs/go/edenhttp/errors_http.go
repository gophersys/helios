package edenhttp

import (
	"net/http"

	"github.com/gophersys/libs/go/errors"
)

// statusClientClosedRequest is the de-facto 499 "client closed request" code (nginx-origin); the
// std lib has no constant for it. A canceled request maps here so a client disconnect is not
// miscounted as a 5xx server fault.
const statusClientClosedRequest = 499

// ConfigError is the typed New-time configuration fault (a missing dependency or an invalid Config
// field). It is wrapped on the errors seam (errors.KindInvalid) so a caller branches via
// errors.AsType, never on the message string. It carries NO secret value.
type ConfigError struct {
	// Field names the offending dependency or configuration field.
	Field string
	// Message is the operator-safe explanation (never a credential).
	Message string
}

// Error renders an operator-safe message; never a secret value.
func (e ConfigError) Error() string {
	return "edenhttp: invalid configuration: " + e.Field + ": " + e.Message
}

// RequestError is the typed client-fault for a malformed HTTP request (bad JSON, a missing path
// field, an unparseable cursor). It is wrapped on the errors seam (typically errors.KindInvalid →
// 400) so the boundary branches by Kind. It carries NO secret value.
type RequestError struct {
	// Reason is the operator-safe explanation of what was malformed (never a credential).
	Reason string
}

// Error renders the operator-safe reason.
func (e RequestError) Error() string { return "edenhttp: bad request: " + e.Reason }

// StatusForKind maps an Eden errors.Kind onto an HTTP status. The Kind is the wire contract (the
// errors library §); the boundary switches on it, never on a substring. KindUnknown/KindInternal
// and any unmapped kind collapse to 500 so an internal cause never leaks to the client body. This
// is the ONE home for the Kind→status mapping every Eden HTTP service shares (one concept, one home).
func StatusForKind(kind errors.Kind) int {
	switch kind {
	case errors.KindInvalid:
		return http.StatusBadRequest
	case errors.KindNotFound:
		return http.StatusNotFound
	case errors.KindConflict:
		return http.StatusConflict
	case errors.KindExhausted:
		return http.StatusTooManyRequests
	case errors.KindUnavailable:
		return http.StatusServiceUnavailable
	case errors.KindDeadline:
		return http.StatusGatewayTimeout
	case errors.KindCanceled:
		return statusClientClosedRequest
	case errors.KindUnauthenticated:
		return http.StatusUnauthorized
	case errors.KindPermission:
		return http.StatusForbidden
	case errors.KindUnknown, errors.KindInternal:
		return http.StatusInternalServerError
	default:
		return http.StatusInternalServerError
	}
}

// safeMessage returns the operator-safe client message for err at the given status. For a 5xx it
// returns a fixed generic string so an internal cause never reaches the browser; for a 4xx it
// returns the errors library's message, which the errors contract guarantees secret-free (12
// §"Redaction-safe").
func safeMessage(err error, status int) string {
	if status >= http.StatusInternalServerError {
		return "internal error"
	}
	if err == nil {
		return ""
	}
	return err.Error()
}
