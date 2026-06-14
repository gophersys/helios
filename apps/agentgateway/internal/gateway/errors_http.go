package gateway

import (
	"encoding/json"
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// ConfigError is the typed New-time configuration fault (a missing dependency or an
// invalid Config field). It is wrapped on the errors seam (errors.KindInvalid) so a
// caller branches via errors.AsType, never on the message string. It carries NO secret.
type ConfigError struct {
	Field   string
	Message string
}

// Error renders an operator-safe message; never a secret value.
func (e ConfigError) Error() string {
	return "gateway: invalid configuration: " + e.Field + ": " + e.Message
}

// RequestError is the typed client-fault for a malformed HTTP request (bad JSON, missing
// path field, unparseable from-seq). errors.KindInvalid → 400. It carries NO secret.
type RequestError struct {
	Reason string
}

// Error renders the operator-safe reason.
func (e RequestError) Error() string { return "gateway: bad request: " + e.Reason }

// errorBody is the redaction-safe JSON error envelope sent to the client. It carries the
// stable Kind token (the contract the UI branches on) and the operator-safe message — the
// errors library guarantees neither embeds a secret (12 §"Redaction-safe"). It NEVER
// includes the wrapped cause chain verbatim or any field that could carry a credential.
type errorBody struct {
	Kind    string `json:"kind"`
	Message string `json:"message"`
}

// statusForKind maps an Eden errors.Kind onto an HTTP status. The Kind is the wire
// contract (errors §); the boundary switches on it, never on a substring. KindUnknown and
// any unmapped kind collapse to 500 (we never leak an internal cause to the client body).
func statusForKind(kind errors.Kind) int {
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
		// 499 (client closed request) is the de-facto code; std lib has no constant.
		return 499
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

// writeError classifies err by its Eden Kind, maps it to an HTTP status, and writes the
// redaction-safe JSON envelope. The client receives the stable Kind token and the
// operator-safe message ONLY — never the cause chain, never a credential. A 5xx logs the
// operator-safe message server-side (the redaction guarantee holds: the errors library
// never carries a secret in its message).
func (g *Gateway) writeError(w http.ResponseWriter, err error) {
	kind := errors.KindOf(err)
	status := statusForKind(kind)

	message := safeMessage(err, status)
	if status >= http.StatusInternalServerError {
		g.logError("gateway: request failed", "kind", kind.String(), "message", err.Error())
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	// The envelope is two known-safe strings; an encode fault here is unrecoverable (the
	// header is already sent) and is intentionally ignored.
	_ = json.NewEncoder(w).Encode(errorBody{Kind: kind.String(), Message: message}) //nolint:errcheck,errchkjson // header already committed; the body is two redaction-safe strings.
}

// writeData writes a success edenhttp.Envelope ({data, errors:[], kind:""}) wrapping data with the
// given status. It is the envelope path for the product-config surface (POST /product/propose),
// reusing the canonical edenhttp envelope so the wizard branches on the ONE Eden response shape
// (one concept, one home). The body NEVER carries a credential — ProductConfig has no secret field.
func (g *Gateway) writeData(w http.ResponseWriter, status int, data any) {
	edenhttp.WriteData(w, status, data)
}

// writeEnvelopeError classifies err by its Eden Kind and writes the uniform edenhttp error Envelope
// ({data:null, errors:[message], kind}). It is the envelope-shaped error path for the product-config
// surface; the client receives the stable Kind token and the operator-safe message only (a 5xx
// returns a fixed generic message). A 5xx is logged server-side (the errors library is secret-free).
func (g *Gateway) writeEnvelopeError(w http.ResponseWriter, err error) {
	kind := errors.KindOf(err)
	if statusForKind(kind) >= http.StatusInternalServerError {
		g.logError("gateway: request failed", "kind", kind.String(), "message", err.Error())
	}
	edenhttp.WriteError(w, err)
}

// safeMessage returns the operator-safe client message. For a 5xx it returns a fixed,
// generic string so an internal cause never reaches the browser; for a 4xx it returns the
// errors library's operator-safe message (guaranteed secret-free by construction).
func safeMessage(err error, status int) string {
	if status >= http.StatusInternalServerError {
		return "internal error"
	}
	if err == nil {
		return ""
	}
	return err.Error()
}
