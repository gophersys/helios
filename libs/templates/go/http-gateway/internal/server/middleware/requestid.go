package middleware

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"

	"github.com/gophersys/libs/go/observability"
)

// requestIDHeader is the canonical request-correlation header. An upstream proxy/ingress that
// already minted one wins (we propagate it); otherwise this middleware mints one so every request
// carries a stable id through the logs and the response.
const requestIDHeader = "X-Request-Id"

// requestIDBytes is the entropy width of a minted request id (16 bytes → 32 hex chars), ample to be
// collision-free across a fleet without pulling a uuid dependency for a correlation token.
const requestIDBytes = 16

// RequestID wraps next so every request carries a correlation id and an observability Scope (the
// OTel-correlated span). It propagates an inbound X-Request-Id when present (an ingress already
// stamped it) else mints one; echoes it on the response header; and
// opens a Scope around next so the span Event carries the method/path/request-id and the request's
// duration + outcome. The Scope's ctx flows into next, so every Event a handler emits inherits the
// trace/span correlation. It logs no secret — a request id and a path are operator-safe tokens.
func RequestID(provider observability.Provider) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			id := request.Header.Get(requestIDHeader)
			if id == "" {
				id = mintRequestID()
			}
			writer.Header().Set(requestIDHeader, id)
			ctx := request.Context()

			// No observability wired (a bare/test composition): still propagate the id, just no span.
			if provider == nil {
				next.ServeHTTP(writer, request.WithContext(ctx))
				return
			}

			ctx, end := provider.Scope(
				ctx, "http.request",
				observability.String("http.request.id", id),
				observability.String("http.method", request.Method),
				observability.String("http.target", request.URL.Path),
			)
			recorder := &statusRecorder{ResponseWriter: writer, status: http.StatusOK}
			next.ServeHTTP(recorder, request.WithContext(ctx))
			end(observability.Outcome{Err: recorder.serverError()})
		})
	}
}

// mintRequestID returns a fresh hex correlation id from crypto/rand. A rand read cannot fail on a
// healthy host; on the impossible error path it returns a fixed sentinel rather than panicking the
// request path — a correlation id is observability, never load-bearing.
func mintRequestID() string {
	buffer := make([]byte, requestIDBytes)
	if _, err := rand.Read(buffer); err != nil {
		return "unidentified-request"
	}
	return hex.EncodeToString(buffer)
}

// statusRecorder captures the response status so the request Scope's Outcome can distinguish a 5xx
// (a server fault worth marking the span failed) from a 4xx (a client fault — the span succeeded).
// It is a thin http.ResponseWriter wrapper, not a buffer: it never holds the body.
type statusRecorder struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
}

// WriteHeader records the status once and forwards it (a double WriteHeader keeps net/http's own
// "superfluous" guard, so we record only the first).
func (r *statusRecorder) WriteHeader(status int) {
	if !r.wroteHeader {
		r.status = status
		r.wroteHeader = true
	}
	r.ResponseWriter.WriteHeader(status)
}

// Write forwards the body; a handler that writes without an explicit WriteHeader keeps the default
// 200 the recorder was constructed with.
func (r *statusRecorder) Write(payload []byte) (int, error) {
	r.wroteHeader = true
	return r.ResponseWriter.Write(payload) //nolint:wrapcheck // pass-through of the underlying writer's error verbatim.
}

// serverError returns a sentinel error iff the response was a 5xx, so the Scope Outcome marks the
// span failed only on a server fault — a 4xx is the client's error, and the span still succeeded.
func (r *statusRecorder) serverError() error {
	if r.status >= http.StatusInternalServerError {
		return errServerStatus
	}
	return nil
}
