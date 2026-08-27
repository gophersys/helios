package edenhttp_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
	"github.com/gophersys/libs/go/errors"
)

// ── New (the pure spine) ──────────────────────────────────────────────────────.

func TestNew_RequiresVerifier(t *testing.T) {
	t.Parallel()
	_, err := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Clock: edenhttptest.FixedClock{}})
	requireKind(t, err, errors.KindInvalid)
}

func TestNew_RequiresClock(t *testing.T) {
	t.Parallel()
	_, err := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Verifier: edenhttptest.NewVerifier()})
	requireKind(t, err, errors.KindInvalid)
}

func TestNew_DefaultsHeartbeatInterval(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	if got := spine.HeartbeatInterval(); got != edenhttp.DefaultHeartbeatInterval {
		t.Fatalf("HeartbeatInterval = %v, want default %v", got, edenhttp.DefaultHeartbeatInterval)
	}
	if spine.Clock() == nil {
		t.Fatal("Clock() returned nil")
	}
}

// ── Middleware (behind auth even locally) ─────────────────────────────────────.

// TestMiddleware_AdmitsValidToken proves a well-signed token with the audit subject reaches the
// downstream handler with the Identity stashed on the context.
func TestMiddleware_AdmitsValidToken(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	var seen edenhttp.Identity
	var reached bool
	handler := spine.MiddlewareFunc(func(_ http.ResponseWriter, r *http.Request) {
		seen, _ = edenhttp.IdentityFrom(r.Context())
		reached = true
	})

	recorder := serve(handler, authedRequest(edenhttptest.MintToken("sessions:control")))
	if !reached {
		t.Fatalf("middleware did not call next; status=%d body=%s", recorder.Code, recorder.Body.String())
	}
	if seen.Subject != edenhttptest.Subject {
		t.Errorf("identity subject = %q, want %q", seen.Subject, edenhttptest.Subject)
	}
	if !seen.HasGrant(edenhttp.NewGrant("sessions", "control")) {
		t.Errorf("identity is missing the sessions:control grant")
	}
}

// TestMiddleware_RejectsMissingHeader proves an unauthenticated request (no Authorization) is a 401
// and next is NEVER called — the gateway is behind auth even locally.
func TestMiddleware_RejectsMissingHeader(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	reached := false
	handler := spine.MiddlewareFunc(func(http.ResponseWriter, *http.Request) { reached = true })

	recorder := serve(handler, httptest.NewRequest(http.MethodGet, "/sessions/x/events", http.NoBody))
	if reached {
		t.Fatal("middleware called next for an unauthenticated request")
	}
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", recorder.Code)
	}
	assertEnvelopeKind(t, recorder, "unauthenticated")
}

// TestMiddleware_RejectsForgedToken proves a token signed with the WRONG secret does not verify (the
// signature gate) — a 401, next not called.
func TestMiddleware_RejectsForgedToken(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	reached := false
	handler := spine.MiddlewareFunc(func(http.ResponseWriter, *http.Request) { reached = true })

	forger, err := edenhttp.NewHMACVerifier("a-different-secret-entirely")
	if err != nil {
		t.Fatalf("build forger: %v", err)
	}
	forged, err := forger.Sign(edenhttptest.Subject, []edenhttp.Grant{edenhttp.NewGrant("sessions", "control")}, edenhttptest.FixedInstant.Add(time.Hour))
	if err != nil {
		t.Fatalf("sign forged: %v", err)
	}

	recorder := serve(handler, authedRequest(forged))
	if reached {
		t.Fatal("middleware admitted a forged (wrong-secret) token")
	}
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", recorder.Code)
	}
}

// TestMiddleware_RejectsExpiredToken proves the exp window is enforced against the injected clock.
func TestMiddleware_RejectsExpiredToken(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	reached := false
	handler := spine.MiddlewareFunc(func(http.ResponseWriter, *http.Request) { reached = true })

	// A token that expired an hour BEFORE the fixed clock instant.
	expired := edenhttptest.MintTokenFor(edenhttptest.Subject, edenhttptest.FixedInstant.Add(-time.Hour), "sessions:control")
	recorder := serve(handler, authedRequest(expired))
	if reached {
		t.Fatal("middleware admitted an expired token")
	}
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", recorder.Code)
	}
}

// TestMiddleware_RejectsNonBearerScheme proves a non-Bearer Authorization header is a 401.
func TestMiddleware_RejectsNonBearerScheme(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	handler := spine.MiddlewareFunc(func(http.ResponseWriter, *http.Request) {})
	request := httptest.NewRequest(http.MethodGet, "/x", http.NoBody)
	request.Header.Set("Authorization", "Basic dXNlcjpwYXNz")
	recorder := serve(handler, request)
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", recorder.Code)
	}
}

// ── The 6-stage pipeline ──────────────────────────────────────────────────────.

type controlInput struct {
	Command string `json:"command"`
	Text    string `json:"text"`
}

type controlOutput struct {
	AdmittedBy string `json:"admittedBy"`
}

// TestPipeline_HappyPath proves the full parse→validate→authorize→execute→respond→action sequence:
// a valid body + a covering grant produces the uniform data envelope and runs the after-action.
func TestPipeline_HappyPath(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	var actioned bool
	pipeline := edenhttp.Handler[controlInput, controlOutput]{
		Validate: func(in controlInput) error {
			if in.Command == "" {
				return errors.New(errors.KindInvalid, "command is required")
			}
			return nil
		},
		Required: edenhttp.NewGrant("sessions", "control"),
		Execute: func(_ context.Context, id edenhttp.Identity, in controlInput) (controlOutput, error) {
			return controlOutput{AdmittedBy: id.Subject + ":" + in.Command}, nil
		},
		SuccessStatus: http.StatusAccepted,
		Action: func(context.Context, edenhttp.Identity, controlInput, controlOutput) error {
			actioned = true
			return nil
		},
	}
	handler := spine.Middleware(pipeline)

	recorder := serve(handler, jsonRequest(edenhttptest.MintToken("sessions:control"), `{"command":"prompt","text":"go"}`))
	if recorder.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope edenhttp.Envelope
	decodeBody(t, recorder, &envelope)
	if len(envelope.Errors) != 0 {
		t.Errorf("success envelope has errors: %v", envelope.Errors)
	}
	data, isObject := envelope.Data.(map[string]any)
	if !isObject {
		t.Fatalf("envelope data is not an object: %#v", envelope.Data)
	}
	if data["admittedBy"] != edenhttptest.Subject+":prompt" {
		t.Errorf("data.admittedBy = %v, want %s:prompt", data["admittedBy"], edenhttptest.Subject)
	}
	if !actioned {
		t.Error("the after-respond Action did not run")
	}
}

// TestPipeline_AuthorizeDeniesUnderGranted proves the authorize stage denies a caller whose token
// lacks the required grant — a 403, execute NEVER runs.
func TestPipeline_AuthorizeDeniesUnderGranted(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	executed := false
	pipeline := edenhttp.Handler[controlInput, controlOutput]{
		Required: edenhttp.NewGrant("sessions", "control"),
		Execute: func(context.Context, edenhttp.Identity, controlInput) (controlOutput, error) {
			executed = true
			return controlOutput{}, nil
		},
	}
	handler := spine.Middleware(pipeline)

	// A token granting only sessions:read — it does NOT cover sessions:control.
	recorder := serve(handler, jsonRequest(edenhttptest.MintToken("sessions:read"), `{"command":"prompt"}`))
	if executed {
		t.Fatal("execute ran despite an under-granted caller")
	}
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403", recorder.Code)
	}
	assertEnvelopeKind(t, recorder, "permission")
}

// TestPipeline_WildcardGrantCovers proves a "sessions:*" grant covers a sessions:control request.
func TestPipeline_WildcardGrantCovers(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	pipeline := edenhttp.Handler[controlInput, controlOutput]{
		Required: edenhttp.NewGrant("sessions", "control"),
		Execute: func(_ context.Context, _ edenhttp.Identity, _ controlInput) (controlOutput, error) {
			return controlOutput{AdmittedBy: "ok"}, nil
		},
	}
	handler := spine.Middleware(pipeline)
	recorder := serve(handler, jsonRequest(edenhttptest.MintToken("sessions:*"), `{"command":"prompt"}`))
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
}

// TestPipeline_ValidateRejectsBadInput proves the validate stage short-circuits to a 400.
func TestPipeline_ValidateRejectsBadInput(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	pipeline := edenhttp.Handler[controlInput, controlOutput]{
		Validate: func(in controlInput) error {
			if in.Command == "" {
				return errors.New(errors.KindInvalid, "command is required")
			}
			return nil
		},
		Required: edenhttp.NewGrant("sessions", "control"),
		Execute: func(context.Context, edenhttp.Identity, controlInput) (controlOutput, error) {
			return controlOutput{}, nil
		},
	}
	handler := spine.Middleware(pipeline)
	recorder := serve(handler, jsonRequest(edenhttptest.MintToken("sessions:control"), `{"text":"no command"}`))
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", recorder.Code)
	}
}

// TestPipeline_ParseRejectsMalformedJSON proves the default parse stage rejects a non-JSON body.
func TestPipeline_ParseRejectsMalformedJSON(t *testing.T) {
	t.Parallel()
	spine := newSpine(t)
	pipeline := edenhttp.Handler[controlInput, controlOutput]{
		Required: edenhttp.NewGrant("sessions", "control"),
		Execute: func(context.Context, edenhttp.Identity, controlInput) (controlOutput, error) {
			return controlOutput{}, nil
		},
	}
	handler := spine.Middleware(pipeline)
	recorder := serve(handler, jsonRequest(edenhttptest.MintToken("sessions:control"), `{not json`))
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", recorder.Code)
	}
}

// TestPipeline_RequiresIdentity proves a pipeline reached WITHOUT the middleware is unauthenticated
// (it must be mounted behind Middleware) — a defense-in-depth guard.
func TestPipeline_RequiresIdentity(t *testing.T) {
	t.Parallel()
	pipeline := edenhttp.Handler[controlInput, controlOutput]{
		Execute: func(context.Context, edenhttp.Identity, controlInput) (controlOutput, error) {
			return controlOutput{}, nil
		},
	}
	recorder := serve(pipeline, jsonRequest("", `{"command":"prompt"}`))
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401 (no identity on context)", recorder.Code)
	}
}

// ── ResolveCursor ─────────────────────────────────────────────────────────────.

func TestResolveCursor_LastEventIDWins(t *testing.T) {
	t.Parallel()
	request := httptest.NewRequest(http.MethodGet, "/sessions/x/events?from-seq=5", http.NoBody)
	request.Header.Set("Last-Event-ID", "42")
	cursor, err := edenhttp.ResolveCursor(request)
	if err != nil {
		t.Fatalf("ResolveCursor: %v", err)
	}
	if cursor != 42 {
		t.Errorf("cursor = %d, want 42 (Last-Event-ID wins over from-seq)", cursor)
	}
}

func TestResolveCursor_FromSeqQuery(t *testing.T) {
	t.Parallel()
	request := httptest.NewRequest(http.MethodGet, "/sessions/x/events?from-seq=7", http.NoBody)
	cursor, err := edenhttp.ResolveCursor(request)
	if err != nil || cursor != 7 {
		t.Fatalf("cursor=%d err=%v, want 7,nil", cursor, err)
	}
}

func TestResolveCursor_DefaultsToAll(t *testing.T) {
	t.Parallel()
	request := httptest.NewRequest(http.MethodGet, "/sessions/x/events", http.NoBody)
	cursor, err := edenhttp.ResolveCursor(request)
	if err != nil || cursor != edenhttp.CursorAll {
		t.Fatalf("cursor=%d err=%v, want CursorAll,nil", cursor, err)
	}
}

func TestResolveCursor_MalformedIsInvalid(t *testing.T) {
	t.Parallel()
	request := httptest.NewRequest(http.MethodGet, "/sessions/x/events", http.NoBody)
	request.Header.Set("Last-Event-ID", "not-a-number")
	_, err := edenhttp.ResolveCursor(request)
	requireKind(t, err, errors.KindInvalid)
}

// ── helpers ───────────────────────────────────────────────────────────────────.

func newSpine(t *testing.T) *edenhttp.Spine {
	t.Helper()
	spine, err := edenhttp.New(
		edenhttp.Config{},
		edenhttp.Deps{Verifier: edenhttptest.NewVerifier(), Clock: edenhttptest.FixedClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return spine
}

func authedRequest(token string) *http.Request {
	request := httptest.NewRequest(http.MethodGet, "/sessions/x/events", http.NoBody)
	request.Header.Set("Authorization", "Bearer "+token)
	return request
}

func jsonRequest(token, body string) *http.Request {
	request := httptest.NewRequest(http.MethodPost, "/sessions/x/control", strings.NewReader(body))
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	request.Header.Set("Content-Type", "application/json")
	return request
}

func serve(handler http.Handler, request *http.Request) *httptest.ResponseRecorder {
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	return recorder
}

func decodeBody(t *testing.T, recorder *httptest.ResponseRecorder, out any) {
	t.Helper()
	if err := json.Unmarshal(recorder.Body.Bytes(), out); err != nil {
		t.Fatalf("decode body %q: %v", recorder.Body.String(), err)
	}
}

func assertEnvelopeKind(t *testing.T, recorder *httptest.ResponseRecorder, wantKind string) {
	t.Helper()
	var envelope edenhttp.Envelope
	decodeBody(t, recorder, &envelope)
	if envelope.Kind != wantKind {
		t.Errorf("envelope kind = %q, want %q (body=%s)", envelope.Kind, wantKind, recorder.Body.String())
	}
	if envelope.Data != nil {
		t.Errorf("error envelope has non-nil data: %v", envelope.Data)
	}
}

func requireKind(t *testing.T, err error, want errors.Kind) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected an error of kind %s, got nil", want)
	}
	if got := errors.KindOf(err); got != want {
		t.Fatalf("error kind = %s, want %s (err=%v)", got, want, err)
	}
}
