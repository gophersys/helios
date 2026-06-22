//go:build integration

package orchestratorservice_test

import (
	"context"
	"fmt"
	"io"
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
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
)

// This is the REAL-substrate lane for the docker-first orchestrator service: it composes the
// IDENTICAL production adapter stack the Service wires — the namespacing production
// postgresstore.DesiredStore over a REAL postgres, the workspaceprovider over the REAL docker
// daemon, and the agentsession claude Factory — and drives a full Spawn -> reconcile-to-Running
// -> Stop -> reconcile-to-Stopped cycle. NOTHING is mocked (ADR-0016 §2): a real container is
// created on the real daemon and a real row is upserted into a real postgres.
//
// The ONLY substitutions vs production are (a) a TRIVIAL busybox TemplateStore (so the workspace
// is a tiny long-lived container, not the heavy supervisor image) and (b) a stub `claude` binary
// (a scripted stand-in emitting the stream-json handshake, so the session opens without a live
// authenticated claude). Both are the standard real-substrate test substitutions the
// orchestrator's own realsubstrate lane uses — the production composition (the namespacing id
// bridge, the docker provisioner, the claude Factory, the telemetry shim) is exercised verbatim.
//
// Running it (inside the devcontainer; docker socket mounted, every gate tool present):
//
//	bash .devcontainer/base/ctl.sh exec -- bash -lc 'export GOWORK=/workspace/go.work && \
//	  cd /workspace/apps/agentgateway && go test -tags integration -race ./internal/orchestratorservice/...'
//
// It boots its own ephemeral postgres (reaped on t.Cleanup) and reaps every docker workspace it
// authors under a unique label namespace. It SKIPS when docker is unavailable locally and is
// REQUIRED (FAIL-NOT-SKIP) in the devcontainer where docker is live.

// busyboxImage is the tiny, ubiquitous image the trivial workspace runs (mirrors the
// orchestrator's own realsubstrate lane). It is long-lived so the provisioned workspace stays
// Ready while the reconcile pass opens the session.
const busyboxImage = "busybox:1.36"

// trivialTemplateRef is the template the integration test's TemplateStore resolves — a busybox
// sandbox compiled to docker, replacing the heavy supervisor image for a hermetic real-substrate run.
var trivialTemplateRef = orchestrator.TemplateRef{Name: "trivial-workspace", Version: "0.1.0"}

// credentialReference is the opaque secrets.Reference (a vault:// LOCATOR, never a credential
// value) the SpawnRequest threads; the seeded secrets provider resolves it server-side at the
// stub session's Open (the value never enters a record or a log).
const credentialReference = "vault://eden/test#stub-token" // #nosec G101 -- a secrets.Reference LOCATOR, not a credential value

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres + real docker workspaces (a parallel fan-out would spin N substrates).
func TestIntegration_SpawnReconcilesToRunningThenStop(t *testing.T) {
	requireDocker(t)
	ctx := t.Context()

	service := buildRealService(t)

	// The store's org_id/project_id columns are UUID (07 §6), so the tenancy keys are real UUIDs.
	tenant := orchestrator.Tenancy{
		OrganizationID: "11111111-1111-1111-1111-111111111111",
		ProjectID:      "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
	}
	admitted, err := service.Spawn(ctx, orchestrator.SpawnRequest{
		Tenant:     tenant,
		Template:   trivialTemplateRef,
		Credential: secrets.Ref(credentialReference),
		By:         "integration-test",
	})
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	if admitted.Status != orchestrator.StatusPending {
		t.Fatalf("Spawn admitted at %v, want Pending", admitted.Status)
	}
	// The Spawn returns a BARE process-local id (the Pool's id space). The namespacing store
	// rewrote it to the project-namespaced form for the real postgres row, transparently — the
	// caller sees only the bare id, and Get round-trips it back.
	if admitted.Cluster.ID != "local-docker" {
		t.Fatalf("Spawn cluster = %q, want local-docker (the docker-first default)", admitted.Cluster.ID)
	}
	t.Cleanup(func() {
		// Best-effort terminal reap: record Stop + drive passes so no real container leaks even if
		// an assertion fails mid-cycle.
		_ = service.Stop(context.Background(), admitted.ID, "cleanup") //nolint:errcheck // best-effort reap.
		for range 6 {
			_, _ = service.ReconcileOnce(context.Background()) //nolint:errcheck // best-effort drain.
		}
	})

	// ── Drive reconcile to Running: Pending -> Provisioning (REAL container created) -> Running
	// (stub session opened). Each pass is at most one transition per agent, so a few passes reach
	// Running. ──
	running := driveUntilStatus(t, service, admitted.ID, orchestrator.StatusRunning)
	if running.Status != orchestrator.StatusRunning {
		t.Fatalf("agent never reached Running; last status %v / %q", running.Status, running.Detail)
	}
	if running.Workspace.IsZero() {
		t.Fatal("a Running agent must carry a provisioned workspace handle")
	}
	if running.Session == "" {
		t.Fatal("a Running agent must carry an open session ref")
	}

	// Get over the BARE id must round-trip the namespaced row back to the bare id (the
	// namespacing bridge proven against REAL postgres).
	got, err := service.Get(ctx, admitted.ID)
	if err != nil {
		t.Fatalf("Get running agent: %v", err)
	}
	if got.ID != admitted.ID {
		t.Fatalf("Get returned id %q, want the bare id %q (namespacing bridge must de-namespace)", got.ID, admitted.ID)
	}

	// ── Stop: record the terminal intent, then drive passes draining Running -> Stopping ->
	// Stopped (the REAL container is torn down on the real daemon). ──
	if err := service.Stop(ctx, admitted.ID, "integration-test"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	stopped := driveUntilStatus(t, service, admitted.ID, orchestrator.StatusStopped)
	if stopped.Status != orchestrator.StatusStopped {
		t.Fatalf("agent never reached Stopped; last status %v / %q", stopped.Status, stopped.Detail)
	}
}

// driveUntilStatus drives reconcile passes (one transition per agent per pass) until the agent
// reaches want or a bound is hit, returning the last-observed record. It re-reads the record via
// the Service's Get between passes so the assertion sees the persisted real-postgres state.
func driveUntilStatus(t *testing.T, service *orchestratorservice.Service, id orchestrator.AgentID, want orchestrator.Status) orchestrator.Agent {
	t.Helper()
	ctx := t.Context()
	const maxPasses = 20
	var last orchestrator.Agent
	for range maxPasses {
		if _, err := service.ReconcileOnce(ctx); err != nil {
			t.Fatalf("reconcile pass: %v", err)
		}
		agent, err := service.Get(ctx, id)
		if err != nil {
			t.Fatalf("get during reconcile: %v", err)
		}
		last = agent
		if agent.Status == want || agent.Status == orchestrator.StatusFailed {
			return agent
		}
		// A short settle so the real docker workspace reaches Ready between the provision pass and
		// the open pass (the daemon needs a beat to start the busybox container).
		time.Sleep(200 * time.Millisecond)
	}
	return last
}

// buildRealService composes the production Service over a REAL postgres + REAL docker + a stub
// claude binary, via the BuildWithTemplates seam (a trivial busybox TemplateStore). Every
// substrate is reaped on t.Cleanup.
func buildRealService(t *testing.T) *orchestratorservice.Service {
	t.Helper()
	ctx := context.Background()

	// REAL postgres: an ephemeral container, the production desired-state store, schema applied.
	pool := bootPostgres(t)
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: pool})
	if err != nil {
		t.Fatalf("construct postgres store: %v", err)
	}
	if err := desiredStore.EnsureSchema(ctx); err != nil {
		t.Fatalf("ensure schema: %v", err)
	}

	// The stub claude binary (the scripted stand-in) + the seeded credential the stub session
	// resolves server-side.
	stub := buildStubClaude(t)
	provider := secretstest.New(map[string]string{credentialReference: "stub-setup-token"})

	// A unique docker label namespace so every workspace this run authors is reaped on cleanup
	// (no orphan container survives the test).
	namespace := "edentest-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	t.Cleanup(func() { reapNamespace(namespace) })

	service, err := orchestratorservice.BuildWithTemplates(
		orchestratorservice.Config{
			DefaultMaxConcurrent: 4,
			ReconcileInterval:    time.Hour, // the test drives Reconcile by hand; the timed loop never ticks
			ProvisionTimeout:     60 * time.Second,
			LabelNamespace:       namespace,
			ClaudeBinary:         stub,
		},
		orchestratorservice.Deps{
			DatabasePool:  pool,
			Secrets:       provider,
			Observability: discardProvider(t),
			Transcript:    agentsessiontest.NewTranscript(),
		},
		trivialTemplateStore{},
	)
	if err != nil {
		t.Fatalf("BuildWithTemplates: %v", err)
	}
	return service
}

// trivialTemplateStore resolves the trivial busybox template (a docker sandbox running a
// long-lived sleep), replacing the heavy supervisor image for the hermetic real-substrate run.
// It is the ONLY production substitution vs the Service's supervisor store — the rest of the
// composition is verbatim.
type trivialTemplateStore struct{}

//nolint:gocritic // contract: TemplateStore.Resolve takes the TemplateRef by value (the frozen port surface).
func (trivialTemplateStore) Resolve(_ context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	if ref != trivialTemplateRef {
		return orchestrator.AgentTemplate{}, fmt.Errorf("trivialTemplateStore: unknown ref %v", ref)
	}
	return orchestrator.AgentTemplate{
		Ref:     trivialTemplateRef,
		Routing: agentsession.RouteKey{Phase: "supervise", Role: "supervisor"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate: orchestrator.SubstrateDocker,
			Image:     busyboxImage,
			Resources: orchestrator.ResourceEnvelope{CPUMillis: 250, MemoryMiB: 64, EphemeralMiB: 64},
		},
		Limits: orchestrator.Limits{MaxConcurrent: 4},
	}, nil
}

// discardProvider builds a real observability.Provider over a discard exporter.
//
//nolint:ireturn // observability.New returns the Provider port (the frozen library surface); the helper hands it on unchanged.
func discardProvider(t *testing.T) observability.Provider {
	t.Helper()
	provider, err := observability.New(
		observability.Config{ServiceName: "orchestratorservice-integration", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: slogadapter.New(io.Discard), Clock: integrationClock{}},
	)
	if err != nil {
		t.Fatalf("build observability provider: %v", err)
	}
	return provider
}

type integrationClock struct{}

func (integrationClock) Now() time.Time { return time.Now() }

// ── REAL-substrate boot/reap helpers (mirror the postgresstore + orchestrator realsubstrate lanes).

// requireDocker skips locally when no docker daemon is reachable; in the devcontainer docker is
// live, so the lane is REQUIRED there (the run that omits it is the CI failure, not this skip).
func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-substrate lane is skipped (REQUIRED in the devcontainer)")
	}
}

// bootPostgres starts an ephemeral postgres container, returns a connected pool, and reaps the
// container on cleanup. It honors EDEN_POSTGRES_DSN to target an already-running instance.
func bootPostgres(t *testing.T) *pgxpool.Pool {
	t.Helper()
	ctx := context.Background()
	dsn := strings.TrimSpace(os.Getenv("EDEN_POSTGRES_DSN"))
	if dsn == "" {
		name := "eden-orchsvc-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
		// #nosec G204 -- fixed `docker run` of the official postgres image; name is time-derived, not user input.
		run := exec.Command("docker", "run", "-d", "--rm", "--name", name,
			"-e", "POSTGRES_PASSWORD=eden", "-e", "POSTGRES_USER=eden", "-e", "POSTGRES_DB=eden",
			"postgres:16-alpine", "-c", "fsync=off")
		if out, err := run.CombinedOutput(); err != nil {
			t.Skipf("could not start postgres container (image unavailable?): %v\n%s", err, out)
		}
		t.Cleanup(func() {
			// #nosec G204 -- fixed `docker rm -f` of the just-created container by its time-derived name.
			_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck // best-effort reap.
		})
		dsn = fmt.Sprintf("postgres://eden:eden@%s:5432/eden?sslmode=disable", dockerBridgeIP(t, name))
		waitForPostgres(t, dsn)
	}
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("open pgx pool: %v", err)
	}
	t.Cleanup(pool.Close)
	return pool
}

// dockerBridgeIP returns the container's bridge IP (reachable from inside the devcontainer on the
// shared docker network).
func dockerBridgeIP(t *testing.T, name string) string {
	t.Helper()
	// #nosec G204 -- fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	return ip
}

// waitForPostgres polls until the postgres at dsn accepts a ping or a deadline elapses.
func waitForPostgres(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.After(45 * time.Second)
	for {
		pingCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		ok := pingPostgres(pingCtx, dsn)
		cancel()
		if ok {
			return
		}
		select {
		case <-deadline:
			t.Fatalf("postgres at %s never became ready", dsn)
		case <-time.After(300 * time.Millisecond):
		}
	}
}

// pingPostgres reports whether a fresh connection to dsn succeeds (and closes it).
func pingPostgres(ctx context.Context, dsn string) bool {
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return false
	}
	_ = conn.Close(ctx) //nolint:errcheck // best-effort close of the probe connection.
	return true
}

// reapNamespace removes any docker container still labeled with this run's namespace (a
// defensive backstop to the orchestrator's own Teardown, so an aborted test leaves no orphan).
func reapNamespace(namespace string) {
	// #nosec G204 -- fixed `docker ps` filtered by the run's time-derived label namespace.
	out, err := exec.Command("docker", "ps", "-aq", "--filter", "label=eden.namespace="+namespace).Output()
	if err != nil {
		return
	}
	for _, id := range strings.Fields(string(out)) {
		// #nosec G204 -- fixed `docker rm -f` of a container id this run authored.
		_ = exec.Command("docker", "rm", "-f", id).Run() //nolint:errcheck // best-effort reap.
	}
}

// buildStubClaude writes a tiny POSIX shell stand-in for the `claude` CLI into t.TempDir(): it
// emits the stream-json handshake (a system/init line confirming StateReady, an assistant line,
// and a terminal result with a token ledger), reads stdin to EOF (the library's Close closes
// stdin), and exits 0 — so the session opens on a REAL os/exec subprocess WITHOUT a live
// authenticated claude. It is never shipped.
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
