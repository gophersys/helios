package gateway_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// This file proves the ADR-0025 permission-resolve path end-to-end through the gateway's
// HTTP surface: POST /sessions/{id}/permissions/{requestId} reaches the LIVE session's
// Resolve method (the session's OWN method, distinct from the prompt/steer/abort Command
// verbs) with the EXACT agentsession.Decision the wire body maps to, and maps the Resolve
// fault Kinds onto the right HTTP status (UnknownPermissionError → 404, KindPermission →
// 403). It drives a RECORDING fake session through a fake Factory so the precise Decision
// argument is inspectable — the one thing the scripted-adapter round-trip cannot surface.

// resolveHarness builds a gateway over a recording fake session and serves it via httptest,
// returning the harness plus the AgentID a created session is registered under.
type resolveHarness struct {
	server  *httptest.Server
	gateway *gateway.Gateway
	session *recordingSession
	agentID string
}

// newResolveHarness builds a gateway whose live plane is the recording fake Factory, creates
// one session (so it is registered under a known AgentID), and serves it. resolveErr, when
// non-nil, is the error the fake session's Resolve returns (so the status-mapping cases drive
// a specific fault).
func newResolveHarness(t *testing.T, resolveErr error) *resolveHarness {
	t.Helper()

	session := &recordingSession{sessionID: "session-resolve-fake", resolveErr: resolveErr}
	factory := &recordingFactory{session: session}
	transcript := agentsessiontest.NewTranscript()
	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))

	g, err := gateway.New(
		gateway.Config{
			Credential: secrets.Ref(credentialRef),
			Routing:    gatewayRouteKey(),
			Workspace:  "/workspace/eden",
		},
		gateway.Deps{
			Manager:    manager,
			Sessions:   factory,
			Transcript: transcript,
			Clock:      fixedClock{},
			Logger:     &recordingLogger{},
		},
	)
	if err != nil {
		t.Fatalf("gateway.New: %v", err)
	}

	server := httptest.NewServer(g.Handler())
	t.Cleanup(func() {
		server.Close()
		_ = g.Close(context.Background()) //nolint:errcheck // test cleanup reap; a close fault is not a test signal.
	})

	h := &resolveHarness{server: server, gateway: g, session: session}

	// Create a session so it is registered under an AgentID the resolve route resolves.
	status, body := postJSONTo(t, server.URL+"/sessions", createBody(""))
	if status != http.StatusCreated {
		t.Fatalf("create session: status %d (%v)", status, body)
	}
	id, ok := body["id"].(string)
	if !ok || id == "" {
		t.Fatalf("create session: empty id (%v)", body)
	}
	h.agentID = id
	return h
}

// resolveCase is one row of the Decision-mapping table.
type resolveCase struct {
	name      string
	verdict   string
	scope     string
	by        string
	wantAllow bool
	wantScope agentsession.DecisionScope
	wantBy    string
}

// TestResolveReachesSessionWithRightDecision is the cardinal proof: a resolve POST reaches
// Session.Resolve with the EXACT Decision the wire body maps to — the requestId from the path,
// Allow from the verdict, the scope mapped to its DecisionScope, and By stamped
// "human:<principal>". The session's Resolve is called (NOT a prompt/steer Command).
func TestResolveReachesSessionWithRightDecision(t *testing.T) {
	t.Parallel()
	cases := []resolveCase{
		{"allow once", "allow", "once", "founder", true, agentsession.ScopeOnce, "human:founder"},
		{"allow session", "allow", "session", "founder", true, agentsession.ScopeSession, "human:founder"},
		{"deny once", "deny", "once", "founder", false, agentsession.ScopeOnce, "human:founder"},
		{"default scope is once", "allow", "", "founder", true, agentsession.ScopeOnce, "human:founder"},
		{"absent by defaults to anonymous", "allow", "once", "", true, agentsession.ScopeOnce, "human:anonymous"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			h := newResolveHarness(t, nil)

			reqBody := map[string]any{"verdict": tc.verdict, "scope": tc.scope}
			if tc.by != "" {
				reqBody["by"] = tc.by
			}
			status, body := postJSONTo(t, h.url("/sessions/"+h.agentID+"/permissions/req-42"), reqBody)
			if status != http.StatusOK {
				t.Fatalf("resolve: status %d (%v)", status, body)
			}
			if _, ok := body["admittedSeq"]; !ok {
				t.Fatalf("resolve: missing admittedSeq (%v)", body)
			}
			assertResolvedDecision(t, h.session.lastResolve(), &tc)
		})
	}
}

// assertResolvedDecision proves the recorded Resolve call carries the requestId from the path
// and the exact Decision the case maps to.
func assertResolvedDecision(t *testing.T, got *resolveCall, tc *resolveCase) {
	t.Helper()
	if got == nil {
		t.Fatal("Session.Resolve was never called (a Command verb was issued instead?)")
	}
	if got.requestID != "req-42" {
		t.Fatalf("Resolve requestID = %q, want req-42 (the path wildcard)", got.requestID)
	}
	if got.decision.Allow != tc.wantAllow {
		t.Fatalf("Decision.Allow = %v, want %v", got.decision.Allow, tc.wantAllow)
	}
	if got.decision.Scope != tc.wantScope {
		t.Fatalf("Decision.Scope = %v, want %v", got.decision.Scope, tc.wantScope)
	}
	if got.decision.By != tc.wantBy {
		t.Fatalf("Decision.By = %q, want %q (the human:<principal> audit stamp)", got.decision.By, tc.wantBy)
	}
}

// TestResolveUnknownRequestIs404 proves an UnknownPermissionError (an unknown or
// already-resolved requestId — KindNotFound) maps to 404 through the shared Kind→status table.
func TestResolveUnknownRequestIs404(t *testing.T) {
	t.Parallel()
	unknown := errors.Wrap(errors.KindNotFound, "agentsession: resolve permission",
		agentsession.UnknownPermissionError{RequestID: "req-gone"})
	h := newResolveHarness(t, unknown)

	status, body := postJSONTo(t, h.url("/sessions/"+h.agentID+"/permissions/req-gone"),
		map[string]any{"verdict": "allow", "scope": "once"})
	if status != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown permission, got %d (%v)", status, body)
	}
	if body["kind"] != "not-found" {
		t.Fatalf("expected kind=not-found, got %v", body["kind"])
	}
}

// TestResolvePolicyRefusalIs403 proves a KindPermission fault (a verdict the policy wall
// refuses) maps to 403 through the shared Kind→status table.
func TestResolvePolicyRefusalIs403(t *testing.T) {
	t.Parallel()
	refused := errors.New(errors.KindPermission, "agentsession: resolve permission refused by policy")
	h := newResolveHarness(t, refused)

	status, body := postJSONTo(t, h.url("/sessions/"+h.agentID+"/permissions/req-42"),
		map[string]any{"verdict": "allow", "scope": "once"})
	if status != http.StatusForbidden {
		t.Fatalf("expected 403 for a policy refusal, got %d (%v)", status, body)
	}
	if body["kind"] != "permission" {
		t.Fatalf("expected kind=permission, got %v", body["kind"])
	}
}

// TestResolveUnknownSessionIs404 proves a resolve to an unregistered session is a 404.
func TestResolveUnknownSessionIs404(t *testing.T) {
	t.Parallel()
	h := newResolveHarness(t, nil)
	status, body := postJSONTo(t, h.url("/sessions/agent-nope/permissions/req-1"),
		map[string]any{"verdict": "deny"})
	if status != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown session, got %d (%v)", status, body)
	}
	if body["kind"] != "not-found" {
		t.Fatalf("expected kind=not-found, got %v", body["kind"])
	}
}

// TestResolveValidation proves a malformed resolve body is a typed 400 (an unknown verdict or
// scope is rejected at the boundary — the gateway never guesses a permission verdict), and the
// session's Resolve is NEVER reached on a malformed request.
func TestResolveValidation(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		body map[string]any
	}{
		{"unknown verdict", map[string]any{"verdict": "maybe", "scope": "once"}},
		{"empty verdict", map[string]any{"scope": "once"}},
		{"unknown scope", map[string]any{"verdict": "allow", "scope": "forever"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			h := newResolveHarness(t, nil)
			status, body := postJSONTo(t, h.url("/sessions/"+h.agentID+"/permissions/req-42"), tc.body)
			if status != http.StatusBadRequest {
				t.Fatalf("expected 400 for %s, got %d (%v)", tc.name, status, body)
			}
			if body["kind"] != "invalid" {
				t.Fatalf("expected kind=invalid, got %v", body["kind"])
			}
			if got := h.session.lastResolve(); got != nil {
				t.Fatalf("Session.Resolve was called on a malformed request (decision %+v)", got.decision)
			}
		})
	}
}

// url joins a path onto the harness server's base URL.
func (h *resolveHarness) url(path string) string { return h.server.URL + path }

// ── the recording fake live plane ────────────────────────────────────────────.

// recordingFactory is an agentsession.Factory whose Open always returns the one recording
// session, so the created gateway session registers the inspectable handle.
type recordingFactory struct{ session *recordingSession }

//nolint:ireturn // satisfies the agentsession.Factory port (returns the frozen Session surface).
func (f *recordingFactory) Open(context.Context, agentsession.Spec) (agentsession.Session, error) {
	return f.session, nil
}

// resolveCall captures the arguments of one Session.Resolve invocation.
type resolveCall struct {
	requestID string
	decision  agentsession.Decision
}

// recordingSession is a fake agentsession.Session that records every Resolve call (the exact
// Decision argument) so the test asserts the gateway forwarded the right one. Events returns a
// single-event stream carrying its SessionID (so the create-flow peek and the SSE route never
// block); Control/Close are inert. resolveErr, when set, is returned by Resolve (to drive the
// fault-status mapping).
type recordingSession struct {
	sessionID  string
	resolveErr error

	mu    sync.Mutex
	calls []resolveCall
	seq   uint64
}

//nolint:ireturn // satisfies the agentsession.Session port (returns the frozen Stream surface).
func (s *recordingSession) Events(context.Context, agentsession.Cursor) agentsession.Stream {
	return &oneEventStream{event: agentsession.Event{SessionID: s.sessionID, Seq: 1, Kind: agentsession.EventSessionState}}
}

func (s *recordingSession) Control(context.Context, agentsession.Command) (agentsession.Ack, error) {
	return agentsession.Ack{}, nil
}

//nolint:gocritic // Decision is the contract's copyable value record; the fake records it by value.
func (s *recordingSession) Resolve(_ context.Context, requestID string, decision agentsession.Decision) (agentsession.Ack, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.resolveErr != nil {
		return agentsession.Ack{}, s.resolveErr
	}
	s.seq++
	s.calls = append(s.calls, resolveCall{requestID: requestID, decision: decision})
	return agentsession.Ack{Seq: s.seq}, nil
}

func (s *recordingSession) Close(context.Context) error { return nil }

// lastResolve returns the most recent recorded Resolve call, or nil if Resolve was never
// called (the malformed-request and command-verb checks rely on nil).
func (s *recordingSession) lastResolve() *resolveCall {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.calls) == 0 {
		return nil
	}
	last := s.calls[len(s.calls)-1]
	return &last
}

// oneEventStream is a single-shot agentsession.Stream: it yields one event then reports
// end-of-stream, so peekSessionID learns the SessionID without blocking and the SSE route
// drains cleanly.
type oneEventStream struct {
	event agentsession.Event
	done  bool
}

//nolint:gocritic // Event is the contract's copyable value record; the fake stream returns it by value.
func (s *oneEventStream) Next(context.Context) (agentsession.Event, bool) {
	if s.done {
		return agentsession.Event{}, false
	}
	s.done = true
	return s.event, true
}

func (s *oneEventStream) Err() error { return nil }
