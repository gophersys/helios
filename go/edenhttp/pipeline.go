package edenhttp

import (
	"context"
	"encoding/json"
	"io"
	"net/http"

	"github.com/gophersys/libs/go/errors"
)

// maxRequestBody bounds a decoded JSON request body so a hostile/oversized payload cannot exhaust
// memory at the parse stage (1 MiB is ample for a control payload; the SSE stream is not a body).
const maxRequestBody = 1 << 20

// Stage names for the 6-stage pipeline, used only in wrapped error context so a failure says which
// stage produced it. The pipeline order is fixed (parse → validate → authorize → execute → respond
// → action); these are the canonical stage tokens.
const (
	stageParse     = "parse"
	stageValidate  = "validate"
	stageAuthorize = "authorize"
	stageExecute   = "execute"
)

// Handler is the 6-stage Eden HTTP handler pipeline (parse → validate → authorize → execute →
// respond → action), adopted from the IOTEA prior art and adapted to Eden + the frozen errors
// taxonomy. It is a typed, composable VALUE parameterized by the request input I and the response
// output O: each stage is one field, so a handler is declared by filling the stages it needs and
// the missing ones default to a permissive no-op. ServeHTTP runs the stages in order, short-
// circuiting to the uniform error Envelope on the first stage that returns a typed error (its Kind
// maps to the status).
//
// Stages (each may be nil → its default):
//
//	Parse     — decode the request into a typed I. Default: JSON-decode the request body (bounded).
//	Validate  — check the parsed I is well-formed. Default: no-op (accept any parsed input).
//	Authorize — the required Grant the caller must hold (the Identity is read from the context the
//	            Middleware stashed). Default: nil Grant → no grant required (still authenticated).
//	Execute   — the business step: produce the typed O (or a typed error). REQUIRED (a nil Execute
//	            is a misconfiguration the pipeline reports as KindInternal).
//	Respond   — the success status the Envelope is written with. Default: 200 OK.
//	Action    — an after-respond side effect (audit, fire-and-forget). Default: no-op. It runs
//	            AFTER the response is written, so its error is logged, never surfaced to the client.
//
// A Handler is constructed with the typed fields directly; ServeHTTP adapts it to net/http.
type Handler[I any, O any] struct {
	// Parse decodes the request into a typed input. Nil → DecodeJSONBody.
	Parse func(request *http.Request) (I, error)
	// Validate checks the parsed input. Nil → accept any input.
	Validate func(input I) error
	// Required is the Grant the caller must hold to proceed. Zero Grant → no grant required.
	Required Grant
	// Execute is the business step producing the response output. REQUIRED.
	Execute func(ctx context.Context, identity Identity, input I) (O, error)
	// SuccessStatus is the status a successful response is written with. 0 → 200 OK.
	SuccessStatus int
	// Action is an after-respond side effect; its error is logged, never surfaced. Nil → no-op.
	Action func(ctx context.Context, identity Identity, input I, output O) error
	// Logger, when non-nil, records a stage failure and an after-respond Action error.
	Logger Logger
}

// ServeHTTP runs the 6 stages in order and writes the uniform Envelope. It is the adapter from the
// typed pipeline to net/http, so a Handler mounts directly on a ServeMux. A stage error is written
// as the error Envelope (Kind→status); a successful run writes the data Envelope at SuccessStatus
// then runs Action.
func (h Handler[I, O]) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	ctx := request.Context()

	// authenticate: the Middleware stashed the verified Identity; its absence is a configuration
	// fault (the pipeline must be mounted behind Middleware) reported as unauthenticated.
	identity, ok := IdentityFrom(ctx)
	if !ok {
		h.fail(writer, errors.New(errors.KindUnauthenticated, "edenhttp: no verified identity on request (mount behind Middleware)"))
		return
	}

	// 1. PARSE.
	input, err := h.runParse(request)
	if err != nil {
		h.fail(writer, errors.Wrap(errors.KindOf(err), "edenhttp: "+stageParse, err))
		return
	}

	// 2. VALIDATE.
	if h.Validate != nil {
		if err := h.Validate(input); err != nil {
			h.fail(writer, errors.Wrap(orInvalid(err), "edenhttp: "+stageValidate, err))
			return
		}
	}

	// 3. AUTHORIZE — the Identity must hold a grant covering Required (zero Grant → no check).
	if h.Required != (Grant{}) {
		if err := identity.Authorize(h.Required); err != nil {
			h.fail(writer, errors.Wrap(errors.KindPermission, "edenhttp: "+stageAuthorize, err))
			return
		}
	}

	// 4. EXECUTE — the business step (required).
	if h.Execute == nil {
		h.fail(writer, errors.New(errors.KindInternal, "edenhttp: handler has no Execute stage"))
		return
	}
	output, err := h.Execute(ctx, identity, input)
	if err != nil {
		h.fail(writer, errors.Wrap(errors.KindOf(err), "edenhttp: "+stageExecute, err))
		return
	}

	// 5. RESPOND — the uniform success Envelope.
	status := h.SuccessStatus
	if status == 0 {
		status = http.StatusOK
	}
	WriteData(writer, status, output)

	// 6. ACTION — after-respond side effect; its error is logged, never surfaced to the client.
	if h.Action != nil {
		if err := h.Action(ctx, identity, input, output); err != nil {
			h.logError("edenhttp: after-respond action failed", "error", err.Error())
		}
	}
}

// runParse runs the Parse stage, defaulting to a bounded JSON body decode.
func (h Handler[I, O]) runParse(request *http.Request) (I, error) {
	if h.Parse != nil {
		return h.Parse(request)
	}
	var input I
	if err := DecodeJSONBody(request, &input); err != nil {
		return input, err
	}
	return input, nil
}

// fail logs a stage failure (5xx server-side only) and writes the uniform error Envelope.
func (h Handler[I, O]) fail(writer http.ResponseWriter, err error) {
	status := WriteError(writer, err)
	if status >= http.StatusInternalServerError {
		h.logError("edenhttp: request failed", "kind", errors.KindOf(err).String(), "error", err.Error())
	}
}

// logError emits a redaction-safe error line when a Logger is wired (no-op otherwise).
func (h Handler[I, O]) logError(message string, fields ...any) {
	if h.Logger != nil {
		h.Logger.Error(message, fields...)
	}
}

// DecodeJSONBody decodes the request body into out with a bounded reader and DisallowUnknownFields,
// so a malformed/oversized/unexpected-field body is a typed RequestError (KindInvalid → 400) rather
// than a silent partial decode. It is the default Parse stage and a standalone helper a custom Parse
// can reuse.
func DecodeJSONBody(request *http.Request, out any) error {
	if request.Body == nil {
		return errors.Wrap(errors.KindInvalid, "edenhttp: decode body", RequestError{Reason: "empty request body"})
	}
	decoder := json.NewDecoder(io.LimitReader(request.Body, maxRequestBody))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(out); err != nil {
		return errors.Wrap(errors.KindInvalid, "edenhttp: decode body", RequestError{Reason: "request body is not valid JSON for this endpoint"})
	}
	return nil
}

// orInvalid returns the error's Kind if it carries one, else KindInvalid — so a Validate stage that
// returns a bare error (no Kind) is treated as a 400 client fault, not a 500.
func orInvalid(err error) errors.Kind {
	if kind := errors.KindOf(err); kind != errors.KindUnknown {
		return kind
	}
	return errors.KindInvalid
}
