package gateway_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// fakeProjectStore is a minimal in-test gateway.ProjectStore (newest-first, no pagination) — enough
// to prove the handler contract without a database (the real Postgres binding is proven in
// projectpersistence's //go:build integration test, the deterministic dev binding in the
// create-product E2E).
type fakeProjectStore struct {
	mutex sync.Mutex
	items []gateway.Project
}

//nolint:gocritic // matches the gateway.ProjectStore port (Create takes the Project by value).
func (s *fakeProjectStore) Create(_ context.Context, project gateway.Project) (gateway.Project, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	s.items = append(s.items, project)
	return project, nil
}

func (s *fakeProjectStore) Get(_ context.Context, id string) (gateway.Project, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.items {
		if s.items[i].ID == id {
			return s.items[i], nil
		}
	}
	return gateway.Project{}, errors.New(errors.KindNotFound, "fake: no project with id "+id)
}

func (s *fakeProjectStore) List(_ context.Context, _ gateway.ProjectFilter) (gateway.ProjectPage, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	out := make([]gateway.Project, 0, len(s.items))
	for i := len(s.items) - 1; i >= 0; i-- {
		out = append(out, s.items[i])
	}
	return gateway.ProjectPage{Projects: out}, nil
}

// newProjectsServer builds a gateway with the given ProjectStore (or nil) and serves it over httptest.
func newProjectsServer(t *testing.T, projectStore gateway.ProjectStore) *httptest.Server {
	t.Helper()
	adapter := agentsessiontest.New()
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
			Projects:   projectStore,
		},
	)
	if err != nil {
		t.Fatalf("gateway.New: %v", err)
	}
	server := httptest.NewServer(g.Handler())
	t.Cleanup(func() {
		server.Close()
		_ = g.Close(context.Background()) //nolint:errcheck // test cleanup reap.
	})
	return server
}

// TestProjectsUnavailableWhenNotConfigured proves the /projects routes 503 (kind "unavailable") when
// no ProjectStore is wired — the optional-dependency contract (mirrors the Proposer).
func TestProjectsUnavailableWhenNotConfigured(t *testing.T) {
	t.Parallel()
	server := newProjectsServer(t, nil)

	post, err := http.Post(server.URL+"/projects", "application/json", strings.NewReader(`{"product":{}}`))
	if err != nil {
		t.Fatalf("POST /projects: %v", err)
	}
	defer post.Body.Close() //nolint:errcheck // test
	if post.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("POST /projects without a store: status %d, want 503", post.StatusCode)
	}

	get, err := http.Get(server.URL + "/projects")
	if err != nil {
		t.Fatalf("GET /projects: %v", err)
	}
	defer get.Body.Close() //nolint:errcheck // test
	if get.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("GET /projects without a store: status %d, want 503", get.StatusCode)
	}
}

// TestCreateProjectPersistsAndProjects proves the full surface: POST persists a normalized Project
// (id minted, status BUILDING with a session, name + kind + harness + stacks derived); GET lists it;
// GET by id returns it; a missing id is 404.
func TestCreateProjectPersistsAndProjects(t *testing.T) {
	t.Parallel()
	server := newProjectsServer(t, &fakeProjectStore{})

	body := `{
		"idea": "ship a payments backend",
		"sessionId": "sess-1",
		"product": {
			"productName": "pay-backend",
			"productKind": "service",
			"stack": {"languages": ["go"], "frameworks": []},
			"services": ["postgres"],
			"capabilities": {"harness": "claude", "model": "claude-fable-5"}
		}
	}`
	created := envelopeData(t, postJSON(t, server.URL+"/projects", body, http.StatusCreated))
	id := fmt.Sprint(created["id"])
	if !strings.HasPrefix(id, "project-") {
		t.Fatalf("create: id = %q, want a project-* id", id)
	}
	if created["name"] != "pay-backend" || created["kind"] != "service" || created["harness"] != "claude" {
		t.Fatalf("create: projection drift: %+v", created)
	}
	if created["status"] != gateway.ProjectStatusBuilding {
		t.Fatalf("create: status = %v, want %q (a session was supplied)", created["status"], gateway.ProjectStatusBuilding)
	}
	if !hasString(toStrings(created["stacks"]), "go") {
		t.Fatalf("create: stacks = %v, want to contain go", created["stacks"])
	}
	if !hasString(toStrings(created["services"]), "postgres") {
		t.Fatalf("create: services = %v, want to contain postgres", created["services"])
	}

	// GET /projects lists the created project.
	list := envelopeData(t, getJSON(t, server.URL+"/projects", http.StatusOK))
	projects, ok := list["projects"].([]any)
	if !ok {
		t.Fatalf("list: projects is not an array: %v", list["projects"])
	}
	if len(projects) != 1 {
		t.Fatalf("list: got %d projects, want 1", len(projects))
	}

	// GET /projects/{id} returns it; a missing id is 404.
	one := envelopeData(t, getJSON(t, server.URL+"/projects/"+id, http.StatusOK))
	if one["id"] != id {
		t.Fatalf("get: id = %v, want %s", one["id"], id)
	}
	missing := getJSON(t, server.URL+"/projects/project-missing", http.StatusNotFound)
	if missing["kind"] != "not-found" {
		t.Fatalf("get missing: kind = %v, want not-found", missing["kind"])
	}
}

// TestCreateProjectRequiresProduct proves POST /projects without a product is a 400 (KindInvalid).
func TestCreateProjectRequiresProduct(t *testing.T) {
	t.Parallel()
	server := newProjectsServer(t, &fakeProjectStore{})
	body := postJSON(t, server.URL+"/projects", `{"idea":"no product here"}`, http.StatusBadRequest)
	if body["kind"] != "invalid" {
		t.Fatalf("create without product: kind = %v, want invalid", body["kind"])
	}
}

// ── small test helpers ───────────────────────────────────────────────────────.

func postJSON(t *testing.T, url, body string, wantStatus int) map[string]any {
	t.Helper()
	response, err := http.Post(url, "application/json", bytes.NewReader([]byte(body))) //nolint:gosec // test drives a local httptest URL
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	defer response.Body.Close() //nolint:errcheck // test
	if response.StatusCode != wantStatus {
		t.Fatalf("POST %s: status %d, want %d", url, response.StatusCode, wantStatus)
	}
	return decodeEnvelope(t, response)
}

func getJSON(t *testing.T, url string, wantStatus int) map[string]any {
	t.Helper()
	response, err := http.Get(url) //nolint:gosec // test drives a local httptest URL
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	defer response.Body.Close() //nolint:errcheck // test
	if response.StatusCode != wantStatus {
		t.Fatalf("GET %s: status %d, want %d", url, response.StatusCode, wantStatus)
	}
	return decodeEnvelope(t, response)
}

func decodeEnvelope(t *testing.T, response *http.Response) map[string]any {
	t.Helper()
	var envelope map[string]any
	if err := json.NewDecoder(response.Body).Decode(&envelope); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	return envelope
}

// decodeData returns the `data` object of a success envelope.
func envelopeData(t *testing.T, envelope map[string]any) map[string]any {
	t.Helper()
	data, ok := envelope["data"].(map[string]any)
	if !ok {
		t.Fatalf("envelope has no data object: %+v", envelope)
	}
	return data
}

func toStrings(value any) []string {
	raw, ok := value.([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, item := range raw {
		if s, ok := item.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

func hasString(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}
