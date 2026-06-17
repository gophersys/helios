package gateway_test

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"sort"
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

// fakeAgentConfigStore is a minimal in-test gateway.AgentConfigStore — enough to prove the handler
// contract without a database (the real Postgres binding is proven in agentconfigpersistence's
// //go:build integration test, the deterministic dev binding in the create-product E2E).
type fakeAgentConfigStore struct {
	mutex   sync.Mutex
	configs map[string]gateway.AgentConfig
}

//nolint:gocritic // matches the gateway.AgentConfigStore port (Put takes the configuration by value).
func (s *fakeAgentConfigStore) Put(_ context.Context, configuration gateway.AgentConfig) (gateway.AgentConfig, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if s.configs == nil {
		s.configs = map[string]gateway.AgentConfig{}
	}
	s.configs[configuration.AgentType] = configuration
	return configuration, nil
}

func (s *fakeAgentConfigStore) Get(_ context.Context, agentType string) (gateway.AgentConfig, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	configuration, ok := s.configs[agentType]
	if !ok {
		return gateway.AgentConfig{}, errors.New(errors.KindNotFound, "fake: no configuration for "+agentType)
	}
	return configuration, nil
}

func (s *fakeAgentConfigStore) List(_ context.Context) ([]gateway.AgentConfig, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	out := make([]gateway.AgentConfig, 0, len(s.configs))
	for _, configuration := range s.configs {
		out = append(out, configuration)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].AgentType < out[j].AgentType })
	return out, nil
}

// newAgentConfigsServer builds a gateway with the given AgentConfigStore (or nil) over httptest.
func newAgentConfigsServer(t *testing.T, configStore gateway.AgentConfigStore) *httptest.Server {
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
			Manager:      manager,
			Sessions:     pool,
			Transcript:   transcript,
			Clock:        fixedClock{},
			AgentConfigs: configStore,
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

// TestAgentConfigsUnavailableWhenNotConfigured proves the /agent-configs routes 503 when no store is
// wired (the optional-dependency contract).
func TestAgentConfigsUnavailableWhenNotConfigured(t *testing.T) {
	t.Parallel()
	server := newAgentConfigsServer(t, nil)

	get, err := http.Get(server.URL + "/agent-configs") //nolint:gosec // test drives a local httptest URL
	if err != nil {
		t.Fatalf("GET /agent-configs: %v", err)
	}
	defer get.Body.Close() //nolint:errcheck // test
	if get.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("GET /agent-configs without a store: status %d, want 503", get.StatusCode)
	}
}

// TestPutAndListAgentConfig proves PUT upserts a normalized configuration (the sandbox posture is
// constrained, an unknown value clearing to "inherit") and GET lists it back.
func TestPutAndListAgentConfig(t *testing.T) {
	t.Parallel()
	server := newAgentConfigsServer(t, &fakeAgentConfigStore{})

	// PUT a configuration for the implementer (a valid strict posture + a model + grants).
	saved := envelopeData(t, putJSON(t, server.URL+"/agent-configs/implementer",
		`{"model":"claude-fable-5","toolGrants":["Read","Write"],"sandboxPosture":"strict"}`, http.StatusOK))
	if saved["agentType"] != "implementer" || saved["model"] != "claude-fable-5" || saved["sandboxPosture"] != "strict" {
		t.Fatalf("put implementer: projection drift: %+v", saved)
	}
	if !hasString(toStrings(saved["toolGrants"]), "Write") {
		t.Fatalf("put implementer: toolGrants = %v, want to contain Write", saved["toolGrants"])
	}

	// PUT a configuration with a NONSENSE posture — it normalizes to "" (inherit), never a junk value.
	architect := envelopeData(t, putJSON(t, server.URL+"/agent-configs/architect",
		`{"model":"","toolGrants":[],"sandboxPosture":"bogus"}`, http.StatusOK))
	if architect["sandboxPosture"] != "" {
		t.Fatalf("put architect: a nonsense posture must normalize to inherit, got %v", architect["sandboxPosture"])
	}

	// GET lists both, sorted by agent type (architect before implementer).
	list := envelopeData(t, getJSON(t, server.URL+"/agent-configs", http.StatusOK))
	configs, ok := list["configs"].([]any)
	if !ok || len(configs) != 2 {
		t.Fatalf("list: got %v, want 2 configs", list["configs"])
	}
	first, isObject := configs[0].(map[string]any)
	if !isObject || first["agentType"] != "architect" {
		t.Fatalf("list: first configuration = %v, want architect (sorted)", configs[0])
	}
}

// putJSON issues a PUT with a JSON body and asserts the status, returning the decoded envelope.
func putJSON(t *testing.T, url, body string, wantStatus int) map[string]any {
	t.Helper()
	request, err := http.NewRequest(http.MethodPut, url, bytes.NewReader([]byte(body)))
	if err != nil {
		t.Fatalf("build PUT %s: %v", url, err)
	}
	request.Header.Set("content-type", "application/json")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("PUT %s: %v", url, err)
	}
	defer response.Body.Close() //nolint:errcheck // test
	if response.StatusCode != wantStatus {
		t.Fatalf("PUT %s: status %d, want %d", url, response.StatusCode, wantStatus)
	}
	return decodeEnvelope(t, response)
}
