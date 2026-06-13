package gateway_test

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// chatScript is the canonical full-taxonomy chat run: message + thinking + text deltas, a
// granted tool start/end, a four-token usage tick, and a clean terminal Result. It exercises
// every REQ-0024 distinct event type.
func chatScript() []agentsession.Event {
	return agentsessiontest.CanonicalScript()
}

// TestNewRejectsMissingDependencies proves the pure constructor validates the injected
// ports and configuration and returns a typed, classified ConfigError.
func TestNewRejectsMissingDependencies(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name          string
		configuration gateway.Config
		dependencies  gateway.Deps
		field         string
	}{
		{
			name:          "missing manager",
			configuration: gateway.Config{Credential: secrets.Ref(credentialRef)},
			dependencies:  gateway.Deps{Sessions: stubFactory{}, Clock: fixedClock{}},
			field:         "Manager",
		},
		{
			name:          "missing sessions",
			configuration: gateway.Config{Credential: secrets.Ref(credentialRef)},
			dependencies:  gateway.Deps{Manager: orchestratortest.New(), Clock: fixedClock{}},
			field:         "Sessions",
		},
		{
			name:          "missing clock",
			configuration: gateway.Config{Credential: secrets.Ref(credentialRef)},
			dependencies:  gateway.Deps{Manager: orchestratortest.New(), Sessions: stubFactory{}},
			field:         "Clock",
		},
		{
			name:          "missing credential",
			configuration: gateway.Config{},
			dependencies:  gateway.Deps{Manager: orchestratortest.New(), Sessions: stubFactory{}, Clock: fixedClock{}},
			field:         "Credential",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			_, err := gateway.New(tc.configuration, tc.dependencies)
			if err == nil {
				t.Fatalf("expected a ConfigError for %s", tc.field)
			}
			configErr, ok := errors.AsType[gateway.ConfigError](err)
			if !ok {
				t.Fatalf("expected gateway.ConfigError, got %T: %v", err, err)
			}
			if configErr.Field != tc.field {
				t.Fatalf("expected field %q, got %q", tc.field, configErr.Field)
			}
			if errors.KindOf(err) != errors.KindInvalid {
				t.Fatalf("expected KindInvalid, got %s", errors.KindOf(err))
			}
		})
	}
}

// stubFactory is a no-op agentsession.Factory for the New-validation table (those cases
// never reach Open).
type stubFactory struct{}

//nolint:ireturn // satisfies the agentsession.Factory port for the New-validation table.
func (stubFactory) Open(context.Context, agentsession.Spec) (agentsession.Session, error) {
	return nil, errors.New(errors.KindUnavailable, "stub")
}

// TestCreateListGetLifecycle proves the REST record plane: create returns the AgentID, the
// session appears in the project-scoped list (REQ-0022), and the get-one record is
// queryable (REQ-0020).
func TestCreateListGetLifecycle(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)

	id := h.createSession(t, "build the thing")

	status, listBody := h.getJSON(t, "/sessions?organizationId=org-eden&projectId=proj-chat")
	if status != http.StatusOK {
		t.Fatalf("list: status %d", status)
	}
	sessions, ok := listBody["sessions"].([]any)
	if !ok || len(sessions) != 1 {
		t.Fatalf("expected 1 session in list, got %d (%v)", len(sessions), listBody)
	}
	first, ok := sessions[0].(map[string]any)
	if !ok {
		t.Fatalf("session 0 is not an object: %v", sessions[0])
	}
	if first["id"] != id {
		t.Fatalf("list session id = %v, want %s", first["id"], id)
	}
	if first["projectId"] != "proj-chat" {
		t.Fatalf("list session projectId = %v, want proj-chat", first["projectId"])
	}

	getStatus, getBody := h.getJSON(t, "/sessions/"+id)
	if getStatus != http.StatusOK {
		t.Fatalf("get: status %d", getStatus)
	}
	if getBody["id"] != id {
		t.Fatalf("get session id = %v, want %s", getBody["id"], id)
	}

	// The gateway emitted a redaction-safe creation log line (the structured-log seam is
	// wired and observable).
	if !anyLineContains(h.logger.snapshot(), "session created") {
		t.Fatalf("expected a 'session created' log line, got %v", h.logger.snapshot())
	}
}

// anyLineContains reports whether any log line contains the substring.
func anyLineContains(lines []string, substr string) bool {
	for _, line := range lines {
		if strings.Contains(line, substr) {
			return true
		}
	}
	return false
}

// TestCreateValidation proves a malformed create request is a typed 400 with a stable Kind
// envelope, and a missing template surfaces the orchestrator's classified error.
func TestCreateValidation(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)

	status, body := h.postJSON(t, "/sessions", map[string]any{"organizationId": "org-eden"})
	if status != http.StatusBadRequest {
		t.Fatalf("expected 400 for missing project, got %d (%v)", status, body)
	}
	if body["kind"] != "invalid" {
		t.Fatalf("expected kind=invalid, got %v", body["kind"])
	}

	unknown := map[string]any{
		"organizationId": "org-eden", "projectId": "proj-chat",
		"templateName": "does-not-exist", "templateVersion": "9.9.9",
	}
	notFoundStatus, notFoundBody := h.postJSON(t, "/sessions", unknown)
	if notFoundStatus != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown template, got %d (%v)", notFoundStatus, notFoundBody)
	}
	if notFoundBody["kind"] != "not-found" {
		t.Fatalf("expected kind=not-found, got %v", notFoundBody["kind"])
	}
}

// TestGetUnknownSessionIs404 proves the Kind->status mapping for a missing record.
func TestGetUnknownSessionIs404(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	status, body := h.getJSON(t, "/sessions/agent-does-not-exist")
	if status != http.StatusNotFound {
		t.Fatalf("expected 404, got %d (%v)", status, body)
	}
	if body["kind"] != "not-found" {
		t.Fatalf("expected kind=not-found, got %v", body["kind"])
	}
}

// TestSSEStreamsFullTaxonomy proves the SSE route streams every REQ-0024 event type as a
// distinct, individually-typed frame with a monotonic id (seq), ending cleanly on the
// terminal Result (REQ-0023 clean end, REQ-0020 deltas/tools/usage reach the client).
func TestSSEStreamsFullTaxonomy(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	response := h.openSSE(ctx, t, id, "", "")
	if response.StatusCode != http.StatusOK {
		t.Fatalf("sse status = %d", response.StatusCode)
	}
	if ct := response.Header.Get("Content-Type"); ct != "text/event-stream; charset=utf-8" {
		t.Fatalf("sse content-type = %q", ct)
	}

	frames := readFramesUntilTerminal(t, response)

	// Every distinct REQ-0024 event type must appear as its own typed frame.
	want := []string{
		"session-state", // ready transition
		"message-start",
		"thinking-delta",
		"text-delta",
		"tool-start",
		"tool-end",
		"usage",
		"message-end",
		"result",
	}
	got := kinds(frames)
	for _, kind := range want {
		if !contains(got, kind) {
			t.Fatalf("missing event kind %q in stream; got %v", kind, got)
		}
	}

	// The ids (seqs) are strictly monotonic and start at 1 (Seq == transcript offset).
	assertMonotonicIDs(t, ids(frames))

	// The terminal frame is the Result, carrying the authoritative four-token ledger.
	last := frames[len(frames)-1]
	if last.Event != "result" {
		t.Fatalf("stream did not end on result, ended on %q", last.Event)
	}
}

// TestUsageFrameCarriesAllFourTokenKinds proves the token/cost meter reflects all four
// token kinds + per-model attribution (REQ-0024).
func TestUsageFrameCarriesAllFourTokenKinds(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	frames := readFramesUntilTerminal(t, h.openSSE(ctx, t, id, "", ""))

	var meter map[string]any
	for _, f := range frames {
		if f.Event == "usage" {
			data := decodeData(t, f.Data)
			meter, _ = data["usage"].(map[string]any) //nolint:errcheck // a missing usage sub-payload is asserted below (meter == nil).
			break
		}
	}
	if meter == nil {
		t.Fatal("no usage frame found (or usage sub-payload absent)")
	}
	for _, field := range []string{"inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens"} {
		if _, ok := meter[field]; !ok {
			t.Fatalf("usage frame missing token kind %q: %v", field, meter)
		}
	}
	if meter["model"] != "fake-fable-5" {
		t.Fatalf("usage model attribution = %v, want fake-fable-5", meter["model"])
	}
}

// TestControlAbortMidStream proves the control channel: an abort takes effect mid-session,
// returns the admitted seq, and the stream ends on the aborted terminal (REQ-0020).
func TestControlAbortMidStream(t *testing.T) {
	t.Parallel()
	// A script that never terminates on its own (no Result), so the session stays running
	// until the abort drives the terminal.
	script := []agentsession.Event{
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.TextDelta("thinking hard"),
	}
	h := newHarness(t, script...)
	id := h.createSession(t, "long task")

	status, body := h.postJSON(t, "/sessions/"+id+"/control", map[string]any{"command": "abort"})
	if status != http.StatusOK {
		t.Fatalf("abort control: status %d (%v)", status, body)
	}
	if _, ok := body["admittedSeq"]; !ok {
		t.Fatalf("abort control: missing admittedSeq (%v)", body)
	}

	// The scripted adapter recorded the abort command.
	assertReceivedCommand(t, h.adapter, agentsession.CommandAbort)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	frames := readFramesUntilTerminal(t, h.openSSE(ctx, t, id, "", ""))
	last := frames[len(frames)-1]
	if last.Event != "aborted" {
		t.Fatalf("stream did not end on aborted, ended on %q (%v)", last.Event, kinds(frames))
	}
}

// TestControlUnknownVerbIs400 proves an unknown control verb is a typed 400.
func TestControlUnknownVerbIs400(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")
	status, body := h.postJSON(t, "/sessions/"+id+"/control", map[string]any{"command": "explode"})
	if status != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d (%v)", status, body)
	}
}

// TestControlUnknownSessionIs404 proves a control to an unregistered session is a 404.
func TestControlUnknownSessionIs404(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	status, _ := h.postJSON(t, "/sessions/agent-nope/control", map[string]any{"command": "abort"})
	if status != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", status)
	}
}

// TestTranscriptQueryableAfterTerminal proves the persisted Run is queryable AFTER the
// session ends (REQ-0020 persisted Run; REQ-0023 reconstruct from persisted events).
func TestTranscriptQueryableAfterTerminal(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	// Drain the live stream to terminal so the full Run is persisted.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = readFramesUntilTerminal(t, h.openSSE(ctx, t, id, "", ""))

	// Stop the session (reaps the live handle) — the transcript must STILL be queryable.
	stopStatus, _ := h.postJSON(t, "/sessions/"+id+"/stop", nil)
	if stopStatus != http.StatusOK {
		t.Fatalf("stop: status %d", stopStatus)
	}

	status, body := h.getJSON(t, "/sessions/"+id+"/transcript")
	if status != http.StatusOK {
		t.Fatalf("transcript: status %d (%v)", status, body)
	}
	events, ok := body["events"].([]any)
	if !ok || len(events) == 0 {
		t.Fatalf("transcript empty after terminal (%v)", body)
	}
	if body["complete"] != true {
		t.Fatalf("transcript not marked complete (no terminal): %v", body["complete"])
	}
}

// TestHealthz proves the liveness probe.
func TestHealthz(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	status, body := h.getJSON(t, "/healthz")
	if status != http.StatusOK || body["status"] != "ok" {
		t.Fatalf("healthz = %d %v", status, body)
	}
}

// contains reports whether haystack contains needle.
func contains(haystack []string, needle string) bool {
	for _, s := range haystack {
		if s == needle {
			return true
		}
	}
	return false
}
