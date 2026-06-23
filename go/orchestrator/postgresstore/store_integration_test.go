//go:build integration

package postgresstore_test

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// This is the REAL-postgres conformance lane for the production DesiredStore — the SAME
// desiredStore-conformance cases the in-memory binding satisfies, proven against a real
// `postgres:16-alpine` (never mocked, ADR-0016 §2).
//
// Running it (it needs eden-postgres — a real postgres reachable on the docker network):
//
//	# inside the devcontainer (docker socket mounted; every gate tool present):
//	bash .devcontainer/base/ctl.sh exec -- \
//	  bash -lc 'export GOWORK=/workspace/go.work && \
//	    cd /workspace/libs/go/orchestrator && go test -tags integration -race ./postgresstore/...'
//
//	# or the per-lib gate verb (the integration dimension):
//	bash ./ctl.sh integration            # from libs/go/orchestrator
//
// The test boots its own ephemeral postgres docker-out-of-docker and reaps it on t.Cleanup, so
// it needs only a reachable docker daemon (the devcontainer's mounted socket). It SKIPS when
// docker is unavailable locally and is REQUIRED (FAIL-NOT-SKIP) in the devcontainer where it is
// live. To point at an already-running eden-postgres instead, set the EDEN_POSTGRES_DSN env var.

// newDesiredStore boots a real postgres, constructs the production PostgresStore, and applies the schema. The
// returned PostgresStore is wired to a pool reaped on t.Cleanup.
func newDesiredStore(t *testing.T) *postgresstore.PostgresStore {
	t.Helper()
	ctx := t.Context()
	dsn := realPostgresDSN(t)

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("open pgx pool: %v", err)
	}
	t.Cleanup(pool.Close)

	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: pool})
	if err != nil {
		t.Fatalf("construct production desiredStore: %v", err)
	}
	if err := desiredStore.EnsureSchema(ctx); err != nil {
		t.Fatalf("ensure schema: %v", err)
	}
	// A fresh table per test (the ephemeral container is per-test, but truncate defensively in
	// case EDEN_POSTGRES_DSN points at a shared instance).
	if _, err := pool.Exec(ctx, "TRUNCATE agents"); err != nil {
		t.Fatalf("truncate agents: %v", err)
	}
	return desiredStore
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_PutGetRoundTrip(t *testing.T) {
	desiredStore := newDesiredStore(t)
	ctx := t.Context()

	original := sampleAgent(t, tenantA(), 1, orchestrator.StatusRunning)
	if err := desiredStore.Put(ctx, original); err != nil {
		t.Fatalf("Put: %v", err)
	}
	got, err := desiredStore.Get(ctx, original.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.ID != original.ID || got.Status != original.Status || got.Workspace.String() != original.Workspace.String() {
		t.Fatalf("round-trip drifted:\n got %+v\nwant %+v", got, original)
	}
	if got.Ledger.CostMicros != original.Ledger.CostMicros || got.Limits != original.Limits {
		t.Fatalf("structured fields drifted: ledger %+v / limits %+v", got.Ledger, got.Limits)
	}
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_GetNotFound(t *testing.T) {
	desiredStore := newDesiredStore(t)
	_, err := desiredStore.Get(t.Context(), "agent-does-not-exist")
	if !errors.IsType[*orchestrator.NotFoundError](err) {
		t.Fatalf("Get absent: want *NotFoundError, got %v", err)
	}
	if errors.KindOf(err) != errors.KindNotFound {
		t.Fatalf("Get absent kind = %v, want NotFound", errors.KindOf(err))
	}
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_PutReplacesUpsert(t *testing.T) {
	desiredStore := newDesiredStore(t)
	ctx := t.Context()

	agent := sampleAgent(t, tenantA(), 1, orchestrator.StatusPending)
	if err := desiredStore.Put(ctx, agent); err != nil {
		t.Fatalf("Put initial: %v", err)
	}
	agent.Status = orchestrator.StatusRunning
	agent.Detail = "promoted"
	if err := desiredStore.Put(ctx, agent); err != nil {
		t.Fatalf("Put replace: %v", err)
	}
	got, err := desiredStore.Get(ctx, agent.ID)
	if err != nil {
		t.Fatalf("Get after replace: %v", err)
	}
	if got.Status != orchestrator.StatusRunning || got.Detail != "promoted" {
		t.Fatalf("upsert did not replace: status=%v detail=%q", got.Status, got.Detail)
	}
	// The upsert must not duplicate the row.
	page, err := desiredStore.List(ctx, orchestrator.Filter{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(page.Agents) != 1 {
		t.Fatalf("upsert produced %d rows, want 1 (no duplicate)", len(page.Agents))
	}
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_PutRejectsNonNamespacedID(t *testing.T) {
	desiredStore := newDesiredStore(t)
	// The v0 single-node `agent-<n>` form is collision-prone in a shared desiredStore → rejected.
	bare := sampleAgent(t, tenantA(), 1, orchestrator.StatusPending)
	bare.ID = "agent-1"
	err := desiredStore.Put(t.Context(), bare)
	if !errors.IsType[*orchestrator.InvalidRequestError](err) {
		t.Fatalf("Put bare id: want *InvalidRequestError, got %v", err)
	}
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("Put bare id kind = %v, want Invalid", errors.KindOf(err))
	}
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_CrossProjectNoCollision(t *testing.T) {
	desiredStore := newDesiredStore(t)
	ctx := t.Context()

	// The SAME local sequence in two projects must produce TWO distinct rows (the fix).
	a := sampleAgent(t, tenantA(), 1, orchestrator.StatusRunning)
	b := sampleAgent(t, tenantB(), 1, orchestrator.StatusRunning)
	if a.ID == b.ID {
		t.Fatalf("fixture ids collided: %q", a.ID)
	}
	for _, agent := range []orchestrator.Agent{a, b} {
		if err := desiredStore.Put(ctx, agent); err != nil {
			t.Fatalf("Put %s: %v", agent.ID, err)
		}
	}
	page, err := desiredStore.List(ctx, orchestrator.Filter{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(page.Agents) != 2 {
		t.Fatalf("cross-project Put produced %d rows, want 2 (no clobber)", len(page.Agents))
	}
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_ListFilters(t *testing.T) {
	desiredStore := newDesiredStore(t)
	ctx := t.Context()

	// Two running agents in project A (one implementer, one assistant), one stopped in A, one in B.
	implementer := sampleAgentWithTemplate(t, tenantA(), 1, orchestrator.StatusRunning, "implementer-go", "1.0.0")
	assistant := sampleAgentWithTemplate(t, tenantA(), 2, orchestrator.StatusRunning, "assistant", "0.1.0")
	stopped := sampleAgentWithTemplate(t, tenantA(), 3, orchestrator.StatusStopped, "implementer-go", "1.0.0")
	otherProject := sampleAgentWithTemplate(t, tenantB(), 1, orchestrator.StatusRunning, "implementer-go", "1.0.0")
	for _, agent := range []orchestrator.Agent{implementer, assistant, stopped, otherProject} {
		if err := desiredStore.Put(ctx, agent); err != nil {
			t.Fatalf("Put %s: %v", agent.ID, err)
		}
	}

	// Tenant isolation: project A sees only its 3 agents, never project B's.
	pageA := mustList(t, desiredStore, &orchestrator.Filter{Tenant: tenantA()})
	if len(pageA.Agents) != 3 {
		t.Fatalf("List tenant A = %d, want 3 (no cross-tenant bleed)", len(pageA.Agents))
	}
	for i := range pageA.Agents {
		if pageA.Agents[i].Tenant != tenantA() {
			t.Fatalf("List tenant A leaked %v", pageA.Agents[i].Tenant)
		}
	}

	// OnlyActive excludes the stopped agent.
	active := mustList(t, desiredStore, &orchestrator.Filter{Tenant: tenantA(), OnlyActive: true})
	if len(active.Agents) != 2 {
		t.Fatalf("List tenant A OnlyActive = %d, want 2 (excludes the stopped)", len(active.Agents))
	}

	// Template name narrows; version pins.
	byTemplate := mustList(t, desiredStore, &orchestrator.Filter{Tenant: tenantA(), Template: orchestrator.TemplateRef{Name: "implementer-go"}})
	if len(byTemplate.Agents) != 2 {
		t.Fatalf("List by template implementer-go = %d, want 2 (running + stopped)", len(byTemplate.Agents))
	}

	// Status set filter.
	byStatus := mustList(t, desiredStore, &orchestrator.Filter{Tenant: tenantA(), Statuses: []orchestrator.Status{orchestrator.StatusStopped}})
	if len(byStatus.Agents) != 1 || byStatus.Agents[0].ID != stopped.ID {
		t.Fatalf("List by status Stopped = %v, want [%s]", idStrings(byStatus.Agents), stopped.ID)
	}
}

//nolint:paralleltest // serial by design: each case boots its own ephemeral real postgres (a parallel fan-out would spin N containers).
func TestIntegration_ListPaginationDeterministicOrder(t *testing.T) {
	desiredStore := newDesiredStore(t)
	ctx := t.Context()

	const total = 5
	want := make([]orchestrator.AgentID, total)
	for i := range total {
		agent := sampleAgent(t, tenantA(), uint64(i+1), orchestrator.StatusRunning)
		want[i] = agent.ID
		if err := desiredStore.Put(ctx, agent); err != nil {
			t.Fatalf("Put %d: %v", i, err)
		}
	}

	// Page 1 (Limit 2), then resume by the returned cursor, until the whole set is walked in
	// insertion (seq) order with no gaps or repeats.
	var walked []orchestrator.AgentID
	cursor := ""
	for {
		page := mustList(t, desiredStore, &orchestrator.Filter{Tenant: tenantA(), Limit: 2, Cursor: cursor})
		for i := range page.Agents {
			walked = append(walked, page.Agents[i].ID)
		}
		if page.Next == "" {
			break
		}
		cursor = page.Next
	}
	if len(walked) != total {
		t.Fatalf("paginated walk visited %d agents, want %d", len(walked), total)
	}
	for i := range want {
		if walked[i] != want[i] {
			t.Fatalf("paginated order drifted at %d: got %s want %s (insertion order broken)", i, walked[i], want[i])
		}
	}
}

// ── fixtures + the real-postgres boot ──────────────────────────────────────────────────────.

func tenantA() orchestrator.Tenancy {
	return orchestrator.Tenancy{OrganizationID: "11111111-1111-1111-1111-111111111111", ProjectID: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
}

func tenantB() orchestrator.Tenancy {
	return orchestrator.Tenancy{OrganizationID: "22222222-2222-2222-2222-222222222222", ProjectID: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}
}

func sampleAgent(t *testing.T, tenant orchestrator.Tenancy, sequence uint64, status orchestrator.Status) orchestrator.Agent {
	t.Helper()
	return sampleAgentWithTemplate(t, tenant, sequence, status, "implementer-go", "1.0.0")
}

func sampleAgentWithTemplate(t *testing.T, tenant orchestrator.Tenancy, sequence uint64, status orchestrator.Status, templateName, templateVersion string) orchestrator.Agent {
	t.Helper()
	handle, err := workspaceprovider.ParseHandle(workspaceprovider.EncodeHandle(
		workspaceprovider.SubstrateKubernetes, "eden-agents", tenant.OrganizationID, tenant.ProjectID,
		"agent-"+strconv.FormatUint(sequence, 10), "/workspace",
	))
	if err != nil {
		t.Fatalf("build fixture handle: %v", err)
	}
	now := time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC)
	return orchestrator.Agent{
		ID:        postgresstore.MintAgentID(tenant, sequence),
		Tenant:    tenant,
		Template:  orchestrator.TemplateRef{Name: templateName, Version: templateVersion},
		RunID:     "run-" + strconv.FormatUint(sequence, 10),
		Desired:   orchestrator.DesiredRunning,
		Status:    status,
		Limits:    orchestrator.Limits{MaxConcurrent: 4, Budget: agentsession.Budget{MaxCostMicros: 8000}},
		Cluster:   orchestrator.ClusterRef{ID: "cluster-1"},
		Workspace: handle,
		Session:   orchestrator.SessionRef("session-" + strconv.FormatUint(sequence, 10)),
		Ledger:    agentsession.TokenLedger{UsageMeter: agentsession.UsageMeter{Model: "claude-fable-5", Harness: "claude-code", CostMicros: 3300}},
		By:        "operator",
		CreatedAt: now,
		UpdatedAt: now,
		Detail:    status.String(),
	}
}

func mustList(t *testing.T, desiredStore *postgresstore.PostgresStore, filter *orchestrator.Filter) orchestrator.Page {
	t.Helper()
	page, err := desiredStore.List(t.Context(), *filter)
	if err != nil {
		t.Fatalf("List(%+v): %v", filter, err)
	}
	return page
}

func idStrings(agents []orchestrator.Agent) []string {
	out := make([]string, len(agents))
	for i := range agents {
		out[i] = string(agents[i].ID)
	}
	return out
}

// realPostgresDSN returns a DSN for a real postgres: the EDEN_POSTGRES_DSN env override if set,
// else an ephemeral `postgres:16-alpine` booted docker-out-of-docker and reaped on t.Cleanup
// (the same posture as the orchestratortest RealHarness — the devcontainer shares the docker
// network, so the container's bridge IP is directly reachable). SKIPS when docker is absent.
func realPostgresDSN(t *testing.T) string {
	t.Helper()
	if dsn := strings.TrimSpace(os.Getenv("EDEN_POSTGRES_DSN")); dsn != "" {
		return dsn
	}
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH and EDEN_POSTGRES_DSN unset: the real-postgres lane is skipped")
	}
	name := "eden-postgresstore-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
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
	dsn := fmt.Sprintf("postgres://eden:eden@%s:5432/eden?sslmode=disable", dockerBridgeIP(t, name))
	waitForPostgres(t, dsn)
	return dsn
}

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

func waitForPostgres(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.After(45 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		ok := pingPostgres(ctx, dsn)
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

func pingPostgres(ctx context.Context, dsn string) bool {
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return false
	}
	defer func() { _ = conn.Close(ctx) }() //nolint:errcheck // best-effort close of the probe conn.
	var one int
	if qerr := conn.QueryRow(ctx, "SELECT 1").Scan(&one); qerr != nil {
		return false
	}
	return one == 1
}
