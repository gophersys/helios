//go:build integration

// Package projectcreate_test — the REAL-substrate saga integration lane. It drives the production saga
// stack against REAL substrates: forge.githubadapter creates a throwaway repository on github.com under
// the configured owner; the gitrepository SystemGit Seeder really clones gophersys/template, flattens
// it, re-points origin at the new repo, and PUSHES the seed; and the production orchestratorservice
// (real docker + real postgres) really Spawns a supervisor container — the saga asserts the project
// walks to supervisor_ready, then tears the repository + container + database down.
//
// GATING (skips, never fails, when a substrate is absent — REQUIRED in the devcontainer):
//   - EDEN_FORGE_GITHUB_TOKEN  a real PAT with the `repo` + `delete_repo` scopes (the gh-token).
//   - EDEN_FORGE_GITHUB_OWNER  the account/org repos are created under (e.g. MateoSegura).
//   - docker on PATH           the orchestrator workspace substrate.
//   - EDEN_POSTGRES_DSN        OPTIONAL — an already-running postgres; else an ephemeral container.
//
// The orchestrator RUNS this against the live environment. Every resource (repo, container, database) is
// reaped on t.Cleanup, under a unique time-namespaced label, even on a mid-test failure.
package projectcreate_test

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/forge/githubadapter"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/createsteppersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectpersistence"
)

const (
	envForgeToken    = "EDEN_FORGE_GITHUB_TOKEN" //nolint:gosec // env var NAME, not a credential.
	envForgeOwner    = "EDEN_FORGE_GITHUB_OWNER"
	envPostgresDSN   = "EDEN_POSTGRES_DSN"
	templateCloneURL = "https://github.com/gophersys/template.git"
	tokenRef         = "gh://token" // the saga's loggable credential reference; the value is env-seeded.
)

// TestIntegration_Saga_RealForgeGitOrchestrator drives the FULL saga against real substrates and asserts
// the project reaches supervisor_ready, then reaps the repository + container + database.
//
//nolint:paralleltest // serial by design: it boots a real postgres + real docker workspace + a real GitHub repo.
func TestIntegration_Saga_RealForgeGitOrchestrator(t *testing.T) {
	token := os.Getenv(envForgeToken)
	owner := os.Getenv(envForgeOwner)
	if token == "" || owner == "" {
		t.Skipf("saga integration needs %s and %s in the environment (a real PAT cannot be synthesized)", envForgeToken, envForgeOwner)
	}
	requireDocker(t)

	// One env-seeded secrets provider resolves the gh-token reference server-side for BOTH the forge
	// (repo create + template clone) and the git push — the value never enters the saga's surface.
	provider := secretstest.New(map[string]string{tokenRef: token})

	// REAL postgres (one instance, shared): the project row store + the saga ledger + the orchestrator
	// desired-state pool all run on it.
	dsn := postgresDSN(t)

	// ── the production adapters the saga drives, over REAL substrates ──
	forgeAdapter := buildRealForge(t, provider)
	seeder := buildRealSeeder(t, provider)
	supervisor := buildRealOrchestrator(t, provider, dsn)
	projectStore := buildProjectStore(t, dsn)
	stepStore := buildStepStore(t, dsn)

	saga, err := projectcreate.New(
		projectcreate.Config{
			RepositoryOwner:        owner,
			PrivateRepository:      true,
			ForgeCredential:        secrets.Ref(tokenRef),
			TemplateRepositoryURL:  templateCloneURL,
			TemplateReference:      "gophersys/template@main",
			SupervisorTemplate:     orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"},
			OrganizationID:         "eden-integration",
			SupervisorReadyTimeout: 4 * time.Minute,
			SupervisorPollInterval: 3 * time.Second,
		},
		projectcreate.Deps{
			Projects: projectStore, Steps: stepStore,
			Forge: forgeAdapter, Seeder: seeder, Supervisor: supervisor,
			Clock: realClock{},
		},
	)
	if err != nil {
		t.Fatalf("projectcreate.New: %v", err)
	}

	// Start the orchestrator reconcile loop so a Spawn actually provisions the workspace + opens the
	// session (driving the agent to StatusRunning the readiness step waits on).
	loopCtx, stopLoop := context.WithCancel(context.Background())
	t.Cleanup(stopLoop)
	if startErr := supervisor.Start(loopCtx); startErr != nil {
		t.Fatalf("start orchestrator loop: %v", startErr)
	}
	t.Cleanup(func() { _ = supervisor.Close(context.Background()) }) //nolint:errcheck // best-effort loop teardown on cleanup.

	// DB-FIRST: write the DRAFT row the handler would write, then run the saga. The project name is
	// an EPHEMERAL eden-it-* name on purpose: its derived repo slug is the only shape the guarded
	// forge.DeleteRepo will reap — a real repo name would be refused (that is the delete guard).
	suffix := strconv.FormatInt(time.Now().UnixNano(), 36)
	projectName := "eden-it-saga-" + suffix
	projectID := "project-" + suffix
	if _, createErr := projectStore.Create(context.Background(), gateway.Project{
		ID: projectID, Name: projectName, Status: gateway.ProjectStatusCreating,
	}); createErr != nil {
		t.Fatalf("seed draft row: %v", createErr)
	}

	// ALWAYS reap the GitHub repository under the derived slug, even on a mid-test failure — through
	// the GUARDED forge.DeleteRepo, so only the throwaway eden-it-* repo can ever be deleted.
	registerRepoReap(t, projectStore, projectID, provider, owner)

	runCtx, cancel := context.WithTimeout(context.Background(), 6*time.Minute)
	defer cancel()
	if runErr := saga.Run(runCtx, projectID); runErr != nil {
		t.Fatalf("saga.Run: %v", runErr)
	}

	project := assertSupervisorReady(t, projectStore, projectID)

	// Stop the supervisor so its container is reaped by the loop (the namespace cleanup is the backstop).
	if stopErr := supervisor.Stop(context.Background(), orchestrator.AgentID(project.SupervisorAgentID), "integration-teardown"); stopErr != nil {
		t.Errorf("stop supervisor: %v", stopErr)
	}
}

// registerRepoReap schedules a cleanup that deletes the throwaway repository the saga created (read
// from the project row's recorded slug) — through the GUARDED forge.DeleteRepo. The reaper connector
// opts into EnableEphemeralDelete, but the guard still confines deletion to ephemeral eden-it-* names
// off the protected denylist, so a real repository can never be deleted even by this teardown.
func registerRepoReap(t *testing.T, projectStore gateway.ProjectStore, projectID string, provider *secretstest.Provider, owner string) {
	t.Helper()
	reaper, err := githubadapter.New(
		githubadapter.Config{UserAgent: "eden-projectcreate-integration-reaper", EnableEphemeralDelete: true},
		githubadapter.Deps{HTTP: &http.Client{Timeout: 30 * time.Second}, Secrets: provider},
	)
	if err != nil {
		t.Fatalf("reaper githubadapter.New: %v", err)
	}
	t.Cleanup(func() {
		project, getErr := projectStore.Get(context.Background(), projectID)
		if getErr != nil || project.GitHubRepo == "" {
			return // step 1 never recorded a repo (nothing to reap) or the row is gone.
		}
		delErr := reaper.DeleteRepo(context.Background(), forge.DeleteRepoRequest{
			Owner: owner, Name: project.GitHubRepo, Credential: secrets.Ref(tokenRef),
		})
		if delErr != nil {
			t.Errorf("teardown: delete throwaway repo %s/%s: %v", owner, project.GitHubRepo, delErr)
		}
	})
}

// assertSupervisorReady reads the final project and asserts it reached the terminal wizard status
// (supervisor ready) with every saga-scratch field recorded.
func assertSupervisorReady(t *testing.T, projectStore gateway.ProjectStore, projectID string) gateway.Project {
	t.Helper()
	project, err := projectStore.Get(context.Background(), projectID)
	if err != nil {
		t.Fatalf("read final project: %v", err)
	}
	if project.Status != gateway.ProjectStatusWizard {
		t.Fatalf("final status = %q, want wizard (supervisor ready); lastError=%q step=%q", project.Status, project.LastError, project.SagaStep)
	}
	if project.GitHubRepo == "" || project.RepoURL == "" {
		t.Errorf("repo coordinates not recorded: %+v", project)
	}
	if project.SupervisorAgentID == "" {
		t.Errorf("supervisor agent not recorded")
	}
	return project
}

// ── real-substrate builders ───────────────────────────────────────────────────────────────────────.

func buildRealForge(t *testing.T, provider *secretstest.Provider) *projectcreate.ForgeAdapter {
	t.Helper()
	connector, err := githubadapter.New(
		githubadapter.Config{UserAgent: "eden-projectcreate-integration"},
		githubadapter.Deps{HTTP: &http.Client{Timeout: 30 * time.Second}, Secrets: provider},
	)
	if err != nil {
		t.Fatalf("githubadapter.New: %v", err)
	}
	adapter, err := projectcreate.NewForgeAdapter(connector)
	if err != nil {
		t.Fatalf("NewForgeAdapter: %v", err)
	}
	return adapter
}

func buildRealSeeder(t *testing.T, provider *secretstest.Provider) *projectcreate.Seeder {
	t.Helper()
	seeder, err := projectcreate.NewSeeder(
		projectcreate.SeederConfig{CheckoutRoot: t.TempDir()},
		projectcreate.SeederDeps{Backend: gitrepository.SystemGit(), Secrets: provider, Clock: realClock{}},
	)
	if err != nil {
		t.Fatalf("NewSeeder: %v", err)
	}
	return seeder
}

// buildRealOrchestrator composes the production orchestratorservice over a REAL postgres + REAL docker.
// It mirrors the orchestratorservice integration lane: the desired-state SCHEMA is applied to the fresh
// database (the composition root's startup step — New is pure and never touches the DB), and the
// supervisor session runs a STUB claude binary on a REAL busybox docker workspace via the
// BuildWithTemplates seam. The saga + orchestrator + workspace provisioning are exercised end-to-end on
// real substrates; the harness alone is a scripted stand-in (a live Claude Opus credential cannot be
// synthesized in CI — the real-claude supervisor is proven by the gated claudeadapter live lane and the
// live demo). Every workspace it authors is reaped under a unique label namespace on cleanup.
func buildRealOrchestrator(t *testing.T, provider *secretstest.Provider, dsn string) *orchestratorservice.Service {
	t.Helper()
	ctx := context.Background()
	namespace := "edensaga-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	t.Cleanup(func() { reapNamespace(namespace) })

	pool := postgresPool(t, dsn)

	// Apply the orchestrator's desired-state schema (CREATE TABLE/INDEX IF NOT EXISTS) to the fresh
	// database. Without it the first agents-table query fails with relation "agents" does not exist.
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: pool})
	if err != nil {
		t.Fatalf("construct postgres desired store: %v", err)
	}
	if schemaErr := desiredStore.EnsureSchema(ctx); schemaErr != nil {
		t.Fatalf("ensure orchestrator schema: %v", schemaErr)
	}

	service, err := orchestratorservice.New(
		orchestratorservice.Config{
			DefaultMaxConcurrent: 2,
			ReconcileInterval:    2 * time.Second,
			ProvisionTimeout:     3 * time.Minute,
			LabelNamespace:       namespace,
			ClaudeBinary:         buildStubClaude(t),
		},
		orchestratorservice.Deps{
			DatabasePool:  pool,
			Secrets:       provider,
			Observability: discardObservability(t),
			Transcript:    agentsessiontest.NewTranscript(),
			Templates:     supervisorBusyboxTemplateStore{}, // the production Deps.Templates seam: busybox in place of the heavy supervisor image
		},
	)
	if err != nil {
		t.Fatalf("orchestratorservice.New: %v", err)
	}
	return service
}

// supervisorTemplateRef is the ref the saga's Config.SupervisorTemplate names. The integration template
// store resolves it to a trivial busybox docker workspace — the ONE production substitution (the heavy
// supervisor image is swapped for busybox), keeping the spawn hermetic while still real-substrate.
var supervisorTemplateRef = orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"}

// supervisorBusyboxTemplateStore resolves the saga's supervisor TemplateRef to a long-lived busybox
// sandbox compiled to docker, so the production orchestrator stack provisions a real container without
// the heavy supervisor image. It is the only substitution vs production; the rest is verbatim.
type supervisorBusyboxTemplateStore struct{}

//nolint:gocritic // contract: TemplateStore.Resolve takes the TemplateRef by value (the frozen port surface).
func (supervisorBusyboxTemplateStore) Resolve(_ context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	if ref != supervisorTemplateRef {
		return orchestrator.AgentTemplate{}, fmt.Errorf("supervisorBusyboxTemplateStore: unknown ref %v", ref)
	}
	return orchestrator.AgentTemplate{
		Ref:     supervisorTemplateRef,
		Routing: agentsession.RouteKey{Phase: "supervise", Role: "supervisor"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate: orchestrator.SubstrateDocker,
			Image:     "busybox:1.36",
			Resources: orchestrator.ResourceEnvelope{CPUMillis: 250, MemoryMiB: 64, EphemeralMiB: 64},
		},
		Limits: orchestrator.Limits{MaxConcurrent: 1},
	}, nil
}

// buildStubClaude writes a POSIX stub `claude` that emits the system/init (Ready) frame, one assistant
// turn, and a success result, then drains stdin — enough for the session to Open and the agent to reach
// StatusRunning (the readiness step's success condition) without a live authenticated claude. Identical
// in shape to the orchestratorservice integration lane's stub.
func buildStubClaude(t *testing.T) string {
	t.Helper()
	if runtime.GOOS == "windows" {
		t.Skip("the POSIX stub claude is not built on windows")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "claude-stub.sh")
	const script = `#!/bin/sh
printf '%s\n' '{"type":"system","subtype":"init","session_id":"stub-1","model":"stub-fable","tools":["Read"]}'
printf '%s\n' '{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"text","text":"ready"}]}}'
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"num_turns":1,"duration_ms":10,"total_cost_usd":0.0,"result":"ready","stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}'
cat >/dev/null
exit 0
`
	if err := os.WriteFile(path, []byte(script), 0o755); err != nil { //nolint:gosec // an executable test stub must be +x.
		t.Fatalf("write stub claude: %v", err)
	}
	return path
}

func buildProjectStore(t *testing.T, dsn string) *projectpersistence.PostgresProjectStore {
	t.Helper()
	persistence, err := projectpersistence.NewPostgres(context.Background(), dsn, projectpersistence.WithClock(realClock{}))
	if err != nil {
		t.Fatalf("projectpersistence.NewPostgres: %v", err)
	}
	t.Cleanup(persistence.Close)
	return persistence
}

func buildStepStore(t *testing.T, dsn string) *createsteppersistence.PostgresCreateStepStore {
	t.Helper()
	persistence, err := createsteppersistence.NewPostgres(context.Background(), dsn, createsteppersistence.WithClock(realClock{}))
	if err != nil {
		t.Fatalf("createsteppersistence.NewPostgres: %v", err)
	}
	t.Cleanup(persistence.Close)
	return persistence
}

// ── teardown + helpers ────────────────────────────────────────────────────────────────────────────.

// (The throwaway repository is reaped through the guarded forge.DeleteRepo in registerRepoReap —
// there is no raw, unguarded DELETE in this test.)

// reapNamespace removes every docker container/volume/network labeled eden.namespace=<namespace> — the
// backstop that no workspace this run authored survives the test.
func reapNamespace(namespace string) {
	filter := "eden.namespace=" + namespace
	ids, err := exec.Command("docker", "ps", "-aq", "--filter", "label="+filter).Output() //nolint:gosec // a fixed argv with a generated label; no user input.
	if err != nil {
		return
	}
	for _, id := range strings.Fields(string(ids)) {
		_ = exec.Command("docker", "rm", "-f", id).Run() //nolint:gosec,errcheck // best-effort reap.
	}
}

func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker not on PATH: the saga real-substrate lane is skipped (REQUIRED in the devcontainer)")
	}
}

// postgresDSN returns an EDEN_POSTGRES_DSN target or boots an ephemeral postgres container (reaped on
// cleanup) and returns its DSN.
func postgresDSN(t *testing.T) string {
	t.Helper()
	if dsn := strings.TrimSpace(os.Getenv(envPostgresDSN)); dsn != "" {
		return dsn
	}
	return bootEphemeralPostgres(t)
}

func discardObservability(t *testing.T) observability.Provider { //nolint:ireturn // returns the Provider port (frozen library surface).
	t.Helper()
	provider, err := observability.New(
		observability.Config{ServiceName: "projectcreate-integration", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: slogadapter.New(discardWriter{}), Clock: realClock{}},
	)
	if err != nil {
		t.Fatalf("observability.New: %v", err)
	}
	return provider
}

type discardWriter struct{}

func (discardWriter) Write(p []byte) (int, error) { return len(p), nil }

type realClock struct{}

func (realClock) Now() time.Time { return time.Now() }

// postgresPool opens a pgx pool against dsn (the orchestrator's desired-state store), closed on cleanup.
func postgresPool(t *testing.T, dsn string) *pgxpool.Pool {
	t.Helper()
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("pgxpool.New: %v", err)
	}
	t.Cleanup(pool.Close)
	return pool
}

// bootEphemeralPostgres boots a REAL postgres:16-alpine container (docker-out-of-docker), reaped on
// cleanup, returning a DSN reachable over the container's docker-bridge IP (mirrors the per-lib
// integration harness). SKIPS when the image is unavailable.
func bootEphemeralPostgres(t *testing.T) string {
	t.Helper()
	name := "eden-projectcreate-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	//nolint:gosec // G204: a fixed `docker run` of the official postgres image; the name is time-derived, not user input.
	run := exec.Command("docker", "run", "-d", "--rm", "--name", name,
		"-e", "POSTGRES_PASSWORD=eden", "-e", "POSTGRES_USER=eden", "-e", "POSTGRES_DB=eden",
		"postgres:16-alpine", "-c", "fsync=off")
	if out, err := run.CombinedOutput(); err != nil {
		t.Skipf("could not start postgres container (image unavailable?): %v\n%s", err, out)
	}
	t.Cleanup(func() {
		_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck,gosec // best-effort reap of the time-named container.
	})

	//nolint:gosec // G204: a fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	dsn := fmt.Sprintf("postgres://eden:eden@%s:5432/eden?sslmode=disable", ip)
	waitForPostgres(t, dsn)
	return dsn
}

// waitForPostgres polls until the container accepts a connection and SELECT 1 succeeds.
func waitForPostgres(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.After(45 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		conn, err := pgx.Connect(ctx, dsn)
		if err == nil {
			var one int
			scanErr := conn.QueryRow(ctx, "SELECT 1").Scan(&one)
			_ = conn.Close(ctx) //nolint:errcheck // best-effort close of the probe conn.
			cancel()
			if scanErr == nil && one == 1 {
				return
			}
		} else {
			cancel()
		}
		select {
		case <-deadline:
			t.Fatalf("postgres at %s never became ready", dsn)
		case <-time.After(300 * time.Millisecond):
		}
	}
}
