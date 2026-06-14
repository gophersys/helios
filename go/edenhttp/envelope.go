package edenhttp

import (
	"encoding/json"
	"net/http"

	"github.com/gophersys/libs/go/errors"
)

// Envelope is the uniform Eden HTTP response body (adapted from IOTEA's IoteaApiResponse): every
// route returns {data, errors}, so the browser branches on ONE shape across the whole surface. On
// success Data carries the typed payload and Errors is empty; on failure Data is null and Errors
// is a list of operator-safe strings (never a credential, never a cause chain). Kind is the stable
// errors.Kind token (the contract the UI maps to a status/behavior) — present on a failure, empty
// on success.
//
// This is the ONE home for the Eden response shape (one concept, one home, 10 §9); a handler never
// hand-rolls a competing JSON shape.
type Envelope struct {
	// Data is the success payload (any JSON-marshalable value); null on a failure.
	Data any `json:"data"`
	// Errors is the list of operator-safe error messages; empty on success.
	Errors []string `json:"errors"`
	// Kind is the stable errors.Kind token on a failure (e.g. "not-found"); empty on success.
	Kind string `json:"kind,omitempty"`
}

// NewDataEnvelope builds a success Envelope carrying data and no errors.
func NewDataEnvelope(data any) Envelope {
	return Envelope{Data: data, Errors: []string{}}
}

// NewErrorEnvelope builds a failure Envelope: null data, the stable Kind token, and the
// operator-safe messages. It is the single point error text is shaped, so a credential cannot
// reach the body by construction (the errors library guarantees its message is secret-free).
func NewErrorEnvelope(kind errors.Kind, messages ...string) Envelope {
	if messages == nil {
		messages = []string{}
	}
	return Envelope{Data: nil, Errors: messages, Kind: kind.String()}
}

// WriteJSON writes body as a JSON Envelope-or-value with the given status and the Eden content
// type. A pre-write marshal fault (the header is not yet committed) is surfaced as a 500 error
// envelope; once the header is committed a write fault is an unrecoverable dropped connection,
// nothing to act on. The body NEVER carries a credential — every payload is a redaction-safe
// projection the consumer supplies.
func WriteJSON(writer http.ResponseWriter, status int, body any) {
	encoded, err := json.Marshal(body)
	if err != nil {
		// Encoding a known DTO should not fail; treat it as an internal fault and emit the
		// redaction-safe envelope (the header is not yet sent at this point).
		WriteError(writer, errors.Wrap(errors.KindInternal, "edenhttp: encode response", err))
		return
	}
	writer.Header().Set("Content-Type", "application/json; charset=utf-8")
	writer.WriteHeader(status)
	//nolint:errcheck // the header is committed; a write fault here is a dropped client connection, nothing to act on.
	_, _ = writer.Write(encoded)
}

// WriteData writes a success Envelope wrapping data with the given status (the common 200/201 path).
func WriteData(writer http.ResponseWriter, status int, data any) {
	WriteJSON(writer, status, NewDataEnvelope(data))
}

// WriteError classifies err by its Eden Kind, maps it to an HTTP status (StatusForKind), and writes
// the uniform error Envelope. The client receives the stable Kind token and the operator-safe
// message ONLY — never the cause chain, never a credential. A 5xx returns a fixed generic message
// (the internal cause stays server-side). It returns the status written so a caller can log/telemeter.
func WriteError(writer http.ResponseWriter, err error) int {
	kind := errors.KindOf(err)
	status := StatusForKind(kind)
	envelope := NewErrorEnvelope(kind, safeMessage(err, status))

	writer.Header().Set("Content-Type", "application/json; charset=utf-8")
	writer.WriteHeader(status)
	//nolint:errcheck,errchkjson // header already committed; the body is a known redaction-safe Envelope.
	_ = json.NewEncoder(writer).Encode(envelope)
	return status
}
