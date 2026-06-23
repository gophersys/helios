package gateway_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// TestEditorReturnsCodeServerURL proves GET /sessions/{id}/workspace/../editor forms the read-only VS
// Code URL under the configured base, pointing ?folder= at the session's worktree (the dir the file
// API serves) and echoing the optional ssh-remote host. This is the substrate-agnostic contract the UI
// opens — only the base URL differs local (localhost) vs kubernetes (the ingress host).
func TestEditorReturnsCodeServerURL(t *testing.T) {
	t.Parallel()
	workspaceDir := t.TempDir()
	server := newEditorServer(t, workspaceDir, "http://localhost:8500/", "ssh.example")

	status, body := getWorkspace(t, server.URL+"/sessions/agent-x/editor")
	if status != http.StatusOK {
		t.Fatalf("editor: status %d (%v)", status, body)
	}
	wantURL := "http://localhost:8500/?folder=" + url.QueryEscape(workspaceDir)
	if body["url"] != wantURL {
		t.Errorf("url = %v, want %s", body["url"], wantURL)
	}
	if body["worktreePath"] != workspaceDir {
		t.Errorf("worktreePath = %v, want %s", body["worktreePath"], workspaceDir)
	}
	if body["sshHost"] != "ssh.example" {
		t.Errorf("sshHost = %v, want ssh.example", body["sshHost"])
	}
	// The base's trailing slash must not double up before ?folder.
	if strings.Contains(wantURL, "//?folder") {
		t.Fatalf("URL has a doubled slash: %s", wantURL)
	}
}

// TestEditorUnconfiguredIs503 proves a composition that does not run code-server (no EditorURLBase)
// reports the editor as unavailable rather than handing back a broken URL — so the UI hides/falls back.
func TestEditorUnconfiguredIs503(t *testing.T) {
	t.Parallel()
	server := newEditorServer(t, t.TempDir(), "", "")
	status, _ := getWorkspace(t, server.URL+"/sessions/agent-x/editor")
	if status != http.StatusServiceUnavailable {
		t.Fatalf("an unconfigured editor must be 503, got %d", status)
	}
}

// newEditorServer builds a gateway whose Config carries the editor base URL + ssh host (and a workspace
// root the editor opens), served over httptest. Mirrors newWorkspaceServer; reaped on cleanup.
func newEditorServer(t *testing.T, dir, editorBase, sshHost string) *httptest.Server {
	t.Helper()
	provider := secretstest.New(map[string]string{credentialRef: agentsessiontest.SeededCanary})
	transcript := agentsessiontest.NewTranscript()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			gatewayRouteKey(): {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": agentsessiontest.New()},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}
	g, err := gateway.New(
		gateway.Config{
			Credential:    secrets.Ref(credentialRef),
			Routing:       gatewayRouteKey(),
			Workspace:     dir,
			EditorURLBase: editorBase,
			EditorSSHHost: sshHost,
		},
		gateway.Deps{
			Manager:    orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate())),
			Sessions:   pool,
			Transcript: transcript,
			Clock:      fixedClock{},
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
