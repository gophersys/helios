package gateway_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// postJSONTo sends a JSON body to an absolute URL and returns the status and decoded response. It
// is the non-method counterpart of harness.postJSON (the product tests build their own servers to
// wire a Proposer, so they post against the returned URL directly).
func postJSONTo(t *testing.T, url string, body any) (status int, decoded map[string]any) {
	t.Helper()
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(body); err != nil {
		t.Fatalf("encode body: %v", err)
	}
	request, err := http.NewRequestWithContext(context.Background(), http.MethodPost, url, &buf)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer func() { _ = response.Body.Close() }() //nolint:errcheck // test cleanup; a body-close fault is not a test signal.
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	out := map[string]any{}
	if len(bytes.TrimSpace(raw)) > 0 {
		if err := json.Unmarshal(raw, &out); err != nil {
			t.Fatalf("decode body (%d): %v: %s", response.StatusCode, err, string(raw))
		}
	}
	return response.StatusCode, out
}

// lastPromptSent returns the Text of the last CommandPrompt the scripted adapter received — the
// opening turn the gateway sent (the product preamble + the user prompt, or the prompt verbatim).
func lastPromptSent(t *testing.T, adapter *agentsessiontest.Adapter) string {
	t.Helper()
	var last string
	var found bool
	for _, command := range adapter.Received() {
		if command.Kind == agentsession.CommandPrompt {
			last = command.Text
			found = true
		}
	}
	if !found {
		t.Fatalf("scripted adapter never received a CommandPrompt; received %v", adapter.Received())
	}
	return last
}

// recordingProposer is a deterministic gateway.Proposer for the wizard test: it records the prompt
// it was called with and returns a PARTIAL ProductConfig (only name+kind+summary set), so the test
// also proves the gateway NORMALIZES a partial proposal into a complete, valid spec (the same
// behavior the live proposer's parse-failure fallback relies on). No model call, no I/O.
type recordingProposer struct {
	prompt string
}

//nolint:ireturn // satisfies the gateway.Proposer port the gateway holds.
func (p *recordingProposer) Propose(_ context.Context, prompt string) (gateway.ProductConfig, error) {
	p.prompt = prompt
	return gateway.ProductConfig{
		ProductName: "Invoice Service", // mixed-case + space → the gateway slugifies it
		ProductKind: "service",
		Summary:     "A billing API.",
		// Everything else intentionally empty: the gateway fills it with Eden's sane defaults.
	}, nil
}

// newProposeHarness builds the wizard-capable gateway (a Proposer is wired) over a scripted chat
// session. It is a thin specialization of the shared fakes so /product/propose and the product-on-
// create path are driven over the SAME real library seams the chat tests use.
func newProposeHarness(t *testing.T, proposer gateway.Proposer, script ...agentsession.Event) *httptest.Server {
	t.Helper()

	adapter := agentsessiontest.New(script...)
	provider := secretstest.New(map[string]string{credentialRef: agentsessiontest.SeededCanary})
	transcript := agentsessiontest.NewTranscript()

	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			gatewayRouteKey(): {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}

	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))

	g, err := gateway.New(
		gateway.Config{
			Credential: secrets.Ref(credentialRef),
			Routing:    gatewayRouteKey(),
			Workspace:  "/workspace/eden",
			Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		},
		gateway.Deps{
			Manager:    manager,
			Sessions:   pool,
			Transcript: transcript,
			Clock:      fixedClock{},
			Proposer:   proposer,
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
	return server
}

// TestProductProposeReturnsValidConfig proves POST /product/propose returns a COMPLETE, VALID
// ProductConfig in the {data,errors,kind} envelope, even when the Proposer returns only a partial
// config: the gateway normalizes every empty field with Eden's sane defaults (Go 1.26 backend,
// claude harness, the four-phase SDLC, strict sandbox). This is the wizard's step-1 contract.
func TestProductProposeReturnsValidConfig(t *testing.T) {
	t.Parallel()
	proposer := &recordingProposer{}
	server := newProposeHarness(t, proposer, chatScript()...)

	status, body := postJSONTo(t, server.URL+"/product/propose", map[string]any{"prompt": "build an invoice service with postgres"})
	if status != http.StatusOK {
		t.Fatalf("propose: status %d, body %v", status, body)
	}
	// The prompt reached the Proposer verbatim (the wizard's free text).
	if proposer.prompt != "build an invoice service with postgres" {
		t.Fatalf("proposer received prompt %q, want the verbatim prompt", proposer.prompt)
	}

	// The {data,errors,kind} envelope carries the config under data.
	data, ok := body["data"].(map[string]any)
	if !ok {
		t.Fatalf("propose response has no data object: %v", body)
	}
	if errs, _ := body["errors"].([]any); len(errs) != 0 { //nolint:errcheck // a non-empty errors array is asserted by the length check.
		t.Fatalf("propose response carried errors: %v", body["errors"])
	}

	// The proposed name is slugified into a valid Eden identifier (mixed-case + space → kebab).
	if got := data["productName"]; got != "invoice-service" {
		t.Fatalf("productName = %v, want invoice-service (slugified)", got)
	}
	if got := data["productKind"]; got != "service" {
		t.Fatalf("productKind = %v, want service", got)
	}
	if got := data["summary"]; got != "A billing API." {
		t.Fatalf("summary = %v, want the proposed summary", got)
	}

	// Every empty field was filled with an Eden default → the spec is wizard-ready.
	assertEdenDefaultsApplied(t, data)
}

// assertEdenDefaultsApplied proves the propose response's normalized config carries Eden's sane
// defaults in every field the partial proposal left empty: a Go backend, the claude harness with a
// standing tool grant, the four-phase SDLC, and the strict sandbox posture. It is the wizard-ready
// guarantee NormalizeProductConfig makes, observed on the wire.
func assertEdenDefaultsApplied(t *testing.T, data map[string]any) {
	t.Helper()
	stack, ok := data["stack"].(map[string]any)
	if !ok {
		t.Fatalf("stack missing/!object: %v", data["stack"])
	}
	if languages, _ := stack["languages"].([]any); len(languages) == 0 || languages[0] != "go" { //nolint:errcheck // an empty languages slice fails the length check.
		t.Fatalf("default languages = %v, want [go]", stack["languages"])
	}
	caps, ok := data["capabilities"].(map[string]any)
	if !ok {
		t.Fatalf("capabilities missing/!object: %v", data["capabilities"])
	}
	if caps["harness"] != "claude" {
		t.Fatalf("default harness = %v, want claude", caps["harness"])
	}
	if grants, _ := caps["toolGrants"].([]any); len(grants) == 0 { //nolint:errcheck // an empty grants slice fails the length check.
		t.Fatalf("default toolGrants empty: %v", caps["toolGrants"])
	}
	if phases, _ := data["sdlcPhases"].([]any); len(phases) == 0 { //nolint:errcheck // an absent/!array sdlcPhases fails the length check.
		t.Fatalf("default sdlcPhases empty: %v", data["sdlcPhases"])
	}
	if sandbox, ok := data["sandbox"].(map[string]any); !ok || sandbox["posture"] != "strict" {
		t.Fatalf("default sandbox posture = %v, want strict", data["sandbox"])
	}
}

// TestProductProposeRejectsEmptyPrompt proves the propose route validates a missing prompt as a
// typed 400 with the stable Kind envelope (the proposer is never called).
func TestProductProposeRejectsEmptyPrompt(t *testing.T) {
	t.Parallel()
	proposer := &recordingProposer{}
	server := newProposeHarness(t, proposer, chatScript()...)

	status, body := postJSONTo(t, server.URL+"/product/propose", map[string]any{"prompt": "   "})
	if status != http.StatusBadRequest {
		t.Fatalf("empty-prompt propose: status %d, body %v", status, body)
	}
	if body["kind"] != "invalid" {
		t.Fatalf("empty-prompt propose: kind = %v, want invalid", body["kind"])
	}
	if proposer.prompt != "" {
		t.Fatalf("proposer was called on an empty prompt (%q)", proposer.prompt)
	}
}

// TestProductProposeUnavailableWhenNotConfigured proves a composition that does NOT wire a Proposer
// (the production stateless gateway, e.g.) answers the propose route with a 503 — the wizard is an
// optional surface, not a hard dependency.
func TestProductProposeUnavailableWhenNotConfigured(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...) // newHarness wires NO Proposer

	status, body := h.postJSON(t, "/product/propose", map[string]any{"prompt": "anything"})
	if status != http.StatusServiceUnavailable {
		t.Fatalf("propose without a Proposer: status %d, body %v", status, body)
	}
	if body["kind"] != "unavailable" {
		t.Fatalf("propose without a Proposer: kind = %v, want unavailable", body["kind"])
	}
}

// TestCreateSessionAcceptsProductSpec proves POST /sessions accepts the optional "product"
// ProductConfig alongside the existing fields, creates the session (the existing harness+prompt
// path stays green), and folds the spec into the agent's opening turn: the synthesized preamble
// ("Build <name> (<kind>): <summary>. ...") is the first prompt the scripted adapter receives.
func TestCreateSessionAcceptsProductSpec(t *testing.T) {
	t.Parallel()
	adapter := agentsessiontest.New(chatScript()...)
	provider := secretstest.New(map[string]string{credentialRef: agentsessiontest.SeededCanary})
	transcript := agentsessiontest.NewTranscript()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			gatewayRouteKey(): {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}
	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))
	g, err := gateway.New(
		gateway.Config{Credential: secrets.Ref(credentialRef), Routing: gatewayRouteKey(), Workspace: "/workspace/eden"},
		gateway.Deps{Manager: manager, Sessions: pool, Transcript: transcript, Clock: fixedClock{}},
	)
	if err != nil {
		t.Fatalf("gateway.New: %v", err)
	}
	server := httptest.NewServer(g.Handler())
	t.Cleanup(func() {
		server.Close()
		_ = g.Close(context.Background()) //nolint:errcheck // test cleanup reap.
	})

	createWithProduct := map[string]any{
		"organizationId":  "org-eden",
		"projectId":       "proj-chat",
		"templateName":    orchestratortest.DefaultTemplate().Ref.Name,
		"templateVersion": orchestratortest.DefaultTemplate().Ref.Version,
		"prompt":          "make it production-ready",
		"product": map[string]any{
			"productName": "Invoice Service",
			"productKind": "service",
			"summary":     "A billing API.",
			"services":    []string{"postgres"},
			"sdlcPhases":  []string{"architecture", "implementation"},
		},
	}
	status, body := postJSONTo(t, server.URL+"/sessions", createWithProduct)
	if status != http.StatusCreated {
		t.Fatalf("create with product: status %d, body %v", status, body)
	}
	if id, _ := body["id"].(string); id == "" { //nolint:errcheck // an empty/absent id fails this check.
		t.Fatalf("create with product: empty id in %v", body)
	}

	// The scripted adapter received the opening prompt: the synthesized product preamble, then the
	// user prompt. This proves the gateway FOLDS the product spec into the agent's initial context.
	prompt := lastPromptSent(t, adapter)
	for _, want := range []string{
		"Build invoice-service (service): A billing API.",
		"Services postgres.",
		"Run phases architecture, implementation.",
		"make it production-ready",
	} {
		if !strings.Contains(prompt, want) {
			t.Fatalf("opening prompt %q missing %q", prompt, want)
		}
	}
}

// TestCreateSessionWithoutProductIsUnchanged proves the existing create path stays green when no
// product is supplied: the opening turn is the user's prompt verbatim (no preamble prepended).
func TestCreateSessionWithoutProductIsUnchanged(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	_ = h.createSession(t, "just build it")

	prompt := lastPromptSent(t, h.adapter)
	if prompt != "just build it" {
		t.Fatalf("opening prompt = %q, want the verbatim prompt (no preamble)", prompt)
	}
	if strings.Contains(prompt, "Build ") {
		t.Fatalf("opening prompt unexpectedly carried a product preamble: %q", prompt)
	}
}
