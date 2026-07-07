package gateway_test

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/codeinsight/codeinsighttest"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// fakeLiveSessions is a minimal in-test gateway.LiveSessions: it resolves a fixed agent id to a
// worktree path (the supervisor→worktree seam GET /projects/{id}/insight resolves through). Only
// Workspace is exercised by the insight route; Session returns "not live" (the route never opens a
// session). This is the SAME seam the real *orchestratorservice.Service binds — the fake stands in
// for the orchestrator live plane so the handler resolves a project's on-disk repo without a running
// supervisor container.
type fakeLiveSessions struct {
	workspaces map[orchestrator.AgentID]string
}

// Session reports that no live session exists — the insight route only needs Workspace.
func (f *fakeLiveSessions) Session(orchestrator.AgentID) (agentsession.Session, bool) {
	return nil, false
}

// Workspace returns the materialized worktree path for id (the supervisor's cloned-repo CWD), or
// ("", false) when the id is unknown — exactly the shape resolveProjectWorktree branches on.
func (f *fakeLiveSessions) Workspace(id orchestrator.AgentID) (string, bool) {
	root, ok := f.workspaces[id]
	return root, ok
}

// newInsightServer builds a gateway with the given ProjectStore and LiveSessions (either may be nil
// to exercise a fault arm) and serves it over httptest, reaped on cleanup. It mirrors
// newProjectsServer's real record+live planes, adding the LiveSessions seam the insight route needs
// to resolve a project's worktree.
func newInsightServer(t *testing.T, projectStore gateway.ProjectStore, live gateway.LiveSessions) *httptest.Server {
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
			Credential: secrets.Ref(credentialRef),
			Routing:    gatewayRouteKey(),
			Workspace:  "/workspace/eden",
		},
		gateway.Deps{
			Manager:      orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate())),
			Sessions:     pool,
			Transcript:   transcript,
			Clock:        fixedClock{},
			Projects:     projectStore,
			LiveSessions: live,
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

// TestInsightFaultArms proves each fault arm of GET /projects/{id}/insight maps to its typed Kind:
// no ProjectStore → 503 (unavailable), no such project → 404 (not found), and a project with no
// resolvable worktree (no supervisor, or a supervisor whose session is not live) → 503 (unavailable).
// These are the pure, substrate-free branches — no git, no real repo.
func TestInsightFaultArms(t *testing.T) {
	t.Parallel()

	t.Run("no project store is 503", func(t *testing.T) {
		t.Parallel()
		server := newInsightServer(t, nil, nil)
		status, body := getInsight(t, server.URL+"/projects/project-x/insight")
		if status != http.StatusServiceUnavailable {
			t.Fatalf("no project store: status %d want 503 (%v)", status, body)
		}
		if body["kind"] != "unavailable" {
			t.Errorf("no project store: kind %v want %q", body["kind"], "unavailable")
		}
	})

	t.Run("no such project is 404", func(t *testing.T) {
		t.Parallel()
		server := newInsightServer(t, &fakeProjectStore{}, &fakeLiveSessions{})
		status, body := getInsight(t, server.URL+"/projects/does-not-exist/insight")
		if status != http.StatusNotFound {
			t.Fatalf("missing project: status %d want 404 (%v)", status, body)
		}
		if body["kind"] != "not-found" {
			t.Errorf("missing project: kind %v want %q", body["kind"], "not-found")
		}
	})

	t.Run("no resolvable worktree is 503", func(t *testing.T) {
		t.Parallel()
		store := &fakeProjectStore{}
		// A draft project with no supervisor yet — its worktree is not materialized.
		if _, err := store.Create(context.Background(), gateway.Project{ID: "project-draft", Name: "Draft"}); err != nil {
			t.Fatalf("seed project: %v", err)
		}
		// And a project whose supervisor id resolves to no live session on this node.
		if _, err := store.Create(context.Background(), gateway.Project{ID: "project-offline", Name: "Offline", SupervisorAgentID: "supervisor-gone"}); err != nil {
			t.Fatalf("seed project: %v", err)
		}
		server := newInsightServer(t, store, &fakeLiveSessions{})

		for _, id := range []string{"project-draft", "project-offline"} {
			status, body := getInsight(t, server.URL+"/projects/"+id+"/insight")
			if status != http.StatusServiceUnavailable {
				t.Fatalf("%s: status %d want 503 (%v)", id, status, body)
			}
			if body["kind"] != "unavailable" {
				t.Errorf("%s: kind %v want %q", id, body["kind"], "unavailable")
			}
		}
	})
}

// TestInsightReportsRealRepository is the REAL-substrate proof: it seeds a genuine on-disk git
// repository (git init + a Go file + commits, via the codeinsight fixture builder — never a mocked
// git), points a project's supervisor worktree at it through the LiveSessions seam, and asserts GET
// /projects/{id}/insight returns a 200 with a decodable codeinsight.Report whose entities are
// non-empty and whose HeadCommit matches the repository's real HEAD. No analyzer is mocked — the
// endpoint drives the same system-git History + native Go MetricProvider the library ships.
func TestInsightReportsRealRepository(t *testing.T) {
	t.Parallel()

	// A tiny real repository: two Go files committed across three revisions so the analyzer mines a
	// genuine history (churn, change-frequency) and parses real go/ast for the static metrics.
	seed := codeinsighttest.RepoSeed{
		Commits: []codeinsighttest.SeedCommit{
			{
				Message: "feat: add greeter",
				Files: map[string]string{
					"greeter.go": "package app\n\n// Greet returns a greeting for name.\nfunc Greet(name string) string {\n\tif name == \"\" {\n\t\treturn \"hello, world\"\n\t}\n\treturn \"hello, \" + name\n}\n",
				},
			},
			{
				Message: "feat: add counter",
				Files: map[string]string{
					"counter.go": "package app\n\n// Count returns n incremented.\nfunc Count(n int) int {\n\treturn n + 1\n}\n",
				},
			},
			{
				Message: "refactor: extend greeter",
				Files: map[string]string{
					"greeter.go": "package app\n\n// Greet returns a greeting for name, in the given locale.\nfunc Greet(name, locale string) string {\n\tif name == \"\" {\n\t\tname = \"world\"\n\t}\n\tif locale == \"es\" {\n\t\treturn \"hola, \" + name\n\t}\n\treturn \"hello, \" + name\n}\n",
				},
			},
		},
	}
	repo := codeinsighttest.NewRealRepo(t, seed)
	wantHead := gitHead(t, repo)

	const supervisorID = "supervisor-real"
	store := &fakeProjectStore{}
	if _, err := store.Create(context.Background(), gateway.Project{
		ID:                "project-real",
		Name:              "Real Project",
		SupervisorAgentID: supervisorID,
	}); err != nil {
		t.Fatalf("seed project: %v", err)
	}
	live := &fakeLiveSessions{workspaces: map[orchestrator.AgentID]string{supervisorID: repo}}
	server := newInsightServer(t, store, live)

	report := decodeReport(t, server.URL+"/projects/project-real/insight")

	if report.SchemaVersion != codeinsight.SchemaVersion {
		t.Errorf("schemaVersion = %q, want %q", report.SchemaVersion, codeinsight.SchemaVersion)
	}
	if report.Repository.Identifier != "Real Project" {
		t.Errorf("identifier = %q, want the project name %q", report.Repository.Identifier, "Real Project")
	}
	if report.Repository.HeadCommit != wantHead {
		t.Errorf("headCommit = %q, want the real repo HEAD %q", report.Repository.HeadCommit, wantHead)
	}
	if report.Repository.CommitCount != len(seed.Commits) {
		t.Errorf("commitCount = %d, want %d seeded commits", report.Repository.CommitCount, len(seed.Commits))
	}
	if len(report.Entities) == 0 {
		t.Fatalf("expected non-empty entities for a repo with two Go files, got none (%+v)", report)
	}
	// The Go files must be reported as analyzed Go entities (the native provider ran, not a skip).
	var sawGoEntity bool
	for _, entity := range report.Entities {
		if strings.HasSuffix(entity.Path, ".go") && entity.Language == "go" {
			sawGoEntity = true
			if entity.Lines == 0 {
				t.Errorf("go entity %q reported zero lines — the native provider did not parse it", entity.Path)
			}
		}
	}
	if !sawGoEntity {
		t.Errorf("no Go entity in the report — the native Go MetricProvider did not run (%+v)", report.Entities)
	}
}

// gitHead reads the real HEAD commit hash of the seeded repository (the commit the static snapshot is
// taken at), so the test asserts the served Report's HeadCommit against ground truth.
func gitHead(t *testing.T, dir string) string {
	t.Helper()
	out, err := exec.Command("git", "-C", dir, "rev-parse", "HEAD").Output() // #nosec G204 -- dir is the test's own seeded temp repo; the verb is fixed.
	if err != nil {
		t.Fatalf("git rev-parse HEAD: %v", err)
	}
	return strings.TrimSpace(string(out))
}

// getInsight GETs the insight route and returns the status + decoded error/generic body (used by the
// fault-arm assertions, which read the {kind, message} envelope).
func getInsight(t *testing.T, url string) (status int, body map[string]any) {
	t.Helper()
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, url, http.NoBody)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	return doDecode(t, request)
}

// decodeReport GETs the insight route and decodes the body into a typed codeinsight.Report, failing
// on a non-200 or a decode fault — the real-substrate assertion needs the typed shape, not a generic
// map, to read entities and the commit stamp.
func decodeReport(t *testing.T, url string) codeinsight.Report {
	t.Helper()
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, url, http.NoBody)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer func() { _ = response.Body.Close() }() //nolint:errcheck // test cleanup; a body-close fault is not a test signal.
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	if response.StatusCode != http.StatusOK {
		t.Fatalf("insight: status %d want 200: %s", response.StatusCode, string(raw))
	}
	var report codeinsight.Report
	if err := json.Unmarshal(raw, &report); err != nil {
		t.Fatalf("decode Report: %v: %s", err, string(raw))
	}
	return report
}
