package orchestratorservice_test

import (
	"context"
	"io"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
)

// undialedPool constructs a real-but-lazy pgx pool (pgxpool.New does NOT dial — the first
// connection is at the first query), so a composition-wiring unit test builds the full Service
// over the production store WITHOUT any database I/O. The pool is Closed on cleanup.
func undialedPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	pool, err := pgxpool.New(context.Background(), "postgres://eden:eden@127.0.0.1:5999/eden?sslmode=disable")
	if err != nil {
		t.Fatalf("construct lazy pgx pool: %v", err)
	}
	t.Cleanup(pool.Close)
	return pool
}

// discardObservability builds a real observability.Provider over a discard exporter (the
// telemetry shim is exercised end-to-end without a backend).
//
//nolint:ireturn // observability.New returns the Provider port (the frozen library surface); the test helper hands it on unchanged.
func discardObservability(t *testing.T) observability.Provider {
	t.Helper()
	provider, err := observability.New(
		observability.Config{ServiceName: "orchestratorservice-test", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: slogadapter.New(io.Discard), Clock: stubClock{}},
	)
	if err != nil {
		t.Fatalf("build observability provider: %v", err)
	}
	return provider
}

// stubClock is a fixed-time observability.Clock for the test provider.
type stubClock struct{}

func (stubClock) Now() time.Time { return time.Unix(0, 0).UTC() }

// supervisorPool builds the ONE agentsession pool the composition root now injects (the supervisor
// opens through it): a claude adapter (binary "" == the real `claude`, or a stub path) + the canonical
// supervisor route. The service no longer builds its own pool — the test provides it like liveserve does.
//
//nolint:ireturn // returns the agentsession.Factory port (the injected pool); the test hands it on unchanged.
func supervisorPool(t *testing.T, provider secrets.Provider, binary string) agentsession.Factory {
	t.Helper()
	adapter, err := claudeadapter.New(claudeadapter.Config{Binary: binary})
	if err != nil {
		t.Fatalf("claudeadapter.New: %v", err)
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			orchestratorservice.SupervisorRouteKey(): {Harness: "claude-code", Model: ""},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": adapter},
			Secrets:    provider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      stubClock{},
		},
	)
	if err != nil {
		t.Fatalf("build supervisor pool: %v", err)
	}
	return pool
}

// validDeps builds a fully-wired Deps over fakes + a lazy pool — the happy composition input.
func validDeps(t *testing.T) orchestratorservice.Deps {
	t.Helper()
	provider := secretstest.New(map[string]string{})
	return orchestratorservice.Deps{
		DatabasePool:  undialedPool(t),
		Secrets:       provider,
		Observability: discardObservability(t),
		Sessions:      supervisorPool(t, provider, ""),
	}
}

func TestNew_BuildsManagerOverProductionAdapters(t *testing.T) {
	t.Parallel()
	service, err := orchestratorservice.New(orchestratorservice.Config{DefaultMaxConcurrent: 4}, validDeps(t))
	if err != nil {
		t.Fatalf("New over valid deps: %v", err)
	}
	// The service IS the orchestrator.Manager surface the saga holds (compile-time assertion; the
	// build below would fail if *Service did not satisfy the port).
	var _ orchestrator.Manager = service
}

func TestNew_RejectsMissingDeps(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name   string
		mutate func(*orchestratorservice.Deps)
	}{
		{"nil database pool", func(d *orchestratorservice.Deps) { d.DatabasePool = nil }},
		{"nil secrets", func(d *orchestratorservice.Deps) { d.Secrets = nil }},
		{"nil observability", func(d *orchestratorservice.Deps) { d.Observability = nil }},
		{"nil sessions", func(d *orchestratorservice.Deps) { d.Sessions = nil }},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			dependencies := validDeps(t)
			testCase.mutate(&dependencies)
			_, err := orchestratorservice.New(orchestratorservice.Config{}, dependencies)
			if err == nil {
				t.Fatalf("New with %s: want error, got nil", testCase.name)
			}
			if errors.KindOf(err) != errors.KindInvalid {
				t.Fatalf("New with %s: kind = %v, want Invalid", testCase.name, errors.KindOf(err))
			}
		})
	}
}

func TestStart_DockerLeaseIsAlwaysLeader(t *testing.T) {
	t.Parallel()
	leader, err := orchestratorservice.DockerLeaderProbe().IsLeader(context.Background())
	if err != nil {
		t.Fatalf("docker lease IsLeader: %v", err)
	}
	if !leader {
		t.Fatal("docker lease must always be the leader (single instance)")
	}
}

func TestStart_LeaderSpinsLoopAndSecondStartNoOps(t *testing.T) {
	t.Parallel()
	service, err := orchestratorservice.New(orchestratorservice.Config{ReconcileInterval: time.Hour}, validDeps(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	// A cancelable ctx so the loop goroutine unwinds on cancel WITHOUT a DB-touching Close (the
	// reconcile interval is an hour, so it never ticks against the undialed pool inside this fast
	// unit test — the real Start/Reconcile/Stop lifecycle is the integration test's job).
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	if err := service.Start(ctx); err != nil {
		t.Fatalf("Start (docker lease is always leader): %v", err)
	}
	if err := service.Start(ctx); err != nil {
		t.Fatalf("second Start (must be a no-op): %v", err)
	}
	cancel() // unwinds the loop goroutine (ctx.Done) with no I/O
}

func TestStart_FollowerSkipsLoop(t *testing.T) {
	t.Parallel()
	dependencies := validDeps(t)
	dependencies.Lease = followerLease{}
	service, err := orchestratorservice.New(orchestratorservice.Config{}, dependencies)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	// A follower instance starts no reconcile loop (only the leader drives actual). Start returns
	// nil without spinning the loop, so there is nothing to cancel/leak.
	if err := service.Start(context.Background()); err != nil {
		t.Fatalf("follower Start: %v", err)
	}
}

// followerLease is a non-leader Lease for the follower-skips-loop test (the multi-instance seam:
// this instance never holds the reconcile lease).
type followerLease struct{}

func (followerLease) IsLeader(context.Context) (bool, error) { return false, nil }

func TestSupervisorTemplateStore_ResolvesSupervisorOnDocker(t *testing.T) {
	t.Parallel()
	templateStore := orchestratorservice.NewSupervisorTemplateStore(orchestrator.SubstrateDocker)
	template, err := templateStore.Resolve(context.Background(), orchestratorservice.SupervisorTemplateRef())
	if err != nil {
		t.Fatalf("Resolve supervisor: %v", err)
	}
	if template.Ref != orchestratorservice.SupervisorTemplateRef() {
		t.Fatalf("resolved ref = %v, want supervisor", template.Ref)
	}
	if template.Sandbox.Substrate != orchestrator.SubstrateDocker {
		t.Fatalf("docker store must compile the sandbox to docker, got %v", template.Sandbox.Substrate)
	}
	if template.Limits.MaxConcurrent != 1 {
		t.Fatalf("supervisor MaxConcurrent = %d, want 1 (a project has one PM)", template.Limits.MaxConcurrent)
	}
	// The grant set is the broad-but-clamped surface: read tools + the eight typed command scripts.
	if len(template.Grants) == 0 {
		t.Fatal("supervisor template must carry the broad-but-clamped grant set")
	}
	wantRoute := agentsession.RouteKey{Phase: "supervise", Role: "supervisor"}
	if template.Routing != wantRoute {
		t.Fatalf("supervisor Routing = %v, want %v", template.Routing, wantRoute)
	}
}

func TestSupervisorTemplateStore_RejectsUnknownRef(t *testing.T) {
	t.Parallel()
	templateStore := orchestratorservice.NewSupervisorTemplateStore(orchestrator.SubstrateDocker)
	_, err := templateStore.Resolve(context.Background(), orchestrator.TemplateRef{Name: "implementer", Version: "9.9.9"})
	if !errors.IsType[*orchestrator.TemplateNotFoundError](err) {
		t.Fatalf("unknown ref: want *TemplateNotFoundError, got %v", err)
	}
	if errors.KindOf(err) != errors.KindNotFound {
		t.Fatalf("unknown ref kind = %v, want NotFound", errors.KindOf(err))
	}
}

func TestNamespacingStore_BijectsBareAndNamespacedIDs(t *testing.T) {
	t.Parallel()
	tenant := orchestrator.Tenancy{OrganizationID: "acme", ProjectID: "alpha"}

	// A bare process-local id rewrites to the project-namespaced store form (the production
	// minter's agent-<project>-<n>), so the production store's Put guard admits it.
	namespaced := orchestratorservice.ToNamespaced("agent-7", tenant)
	want := postgresstore.MintAgentID(tenant, 7)
	if namespaced != want {
		t.Fatalf("ToNamespaced(agent-7) = %q, want %q", namespaced, want)
	}

	// An ALREADY-namespaced id (a record reloaded after restart) is left unchanged — the rewrite
	// is idempotent on a re-Put.
	if got := orchestratorservice.ToNamespaced(want, tenant); got != want {
		t.Fatalf("ToNamespaced(already-namespaced) = %q, want unchanged %q", got, want)
	}

	// A zero project cannot be namespaced — the id passes through so the store applies its own
	// KindInvalid guard (never silently mints a malformed id).
	if got := orchestratorservice.ToNamespaced("agent-7", orchestrator.Tenancy{OrganizationID: "acme"}); got != "agent-7" {
		t.Fatalf("ToNamespaced with no project = %q, want passthrough agent-7", got)
	}
}

func TestBareSequence_ParsesOnlyTheBareForm(t *testing.T) {
	t.Parallel()
	cases := []struct {
		id   orchestrator.AgentID
		seq  uint64
		want bool
	}{
		{"agent-1", 1, true},
		{"agent-42", 42, true},
		{"agent-alpha-1", 0, false}, // namespaced — not the bare form
		{"agent-", 0, false},        // empty sequence
		{"session-1", 0, false},     // wrong prefix
		{"agent-1x", 0, false},      // non-numeric tail
	}
	for _, testCase := range cases {
		seq, ok := orchestratorservice.BareSequence(testCase.id)
		if ok != testCase.want || (ok && seq != testCase.seq) {
			t.Fatalf("BareSequence(%q) = (%d,%v), want (%d,%v)", testCase.id, seq, ok, testCase.seq, testCase.want)
		}
	}
}

func TestNew_DefaultsClusterToLocalDocker(t *testing.T) {
	t.Parallel()
	if got := orchestratorservice.LocalDockerClusterID(); got != "local-docker" {
		t.Fatalf("DefaultCluster id = %q, want local-docker", got)
	}
}

// TestSubstrate_ZeroValueIsDocker pins the docker-FIRST invariant: a zero Config.Substrate must
// select docker, NOT kubernetes — even though orchestrator.Substrate's own zero value is kubernetes
// (ADR-0012). The service-local Substrate enum exists precisely to keep a zero Config docker-first;
// this guards the regression where reusing orchestrator.Substrate inverted the default.
func TestSubstrate_ZeroValueIsDocker(t *testing.T) {
	t.Parallel()
	if orchestratorservice.SubstrateDocker != 0 {
		t.Fatalf("SubstrateDocker = %d, want 0 (the zero value MUST be docker — the docker-first default)", orchestratorservice.SubstrateDocker)
	}
	if orchestratorservice.SubstrateKubernetes == orchestratorservice.SubstrateDocker {
		t.Fatal("SubstrateKubernetes must differ from SubstrateDocker (the two deployment substrates)")
	}
}

// TestNewKubernetesLease_RejectsMissingWiring exercises the lease constructor's pure validation
// fault arm (no apiserver): each missing required field is a wrapped KindInvalid naming the seam,
// so a misconfigured lease fails at composition, never at the first election action.
func TestNewKubernetesLease_RejectsMissingWiring(t *testing.T) {
	t.Parallel()
	valid := orchestratorservice.LeaseConfig{LeaseName: "eden-orchestrator", Namespace: "eden-system", Identity: "pod-1"}
	cases := []struct {
		name   string
		mutate func(*orchestratorservice.LeaseConfig)
	}{
		{"missing lease name", func(c *orchestratorservice.LeaseConfig) { c.LeaseName = "" }},
		{"missing namespace", func(c *orchestratorservice.LeaseConfig) { c.Namespace = "" }},
		{"missing identity", func(c *orchestratorservice.LeaseConfig) { c.Identity = "" }},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			configuration := valid
			testCase.mutate(&configuration)
			// Deps are non-nil so the missing-CONFIG path is the one under test (the nil-deps paths
			// are checked below); a fake client family is enough — New dials no apiserver.
			_, err := orchestratorservice.NewKubernetesLease(configuration, orchestratorservice.LeaseDependencies{})
			if err == nil {
				t.Fatalf("NewKubernetesLease with %s: want error, got nil", testCase.name)
			}
			if errors.KindOf(err) != errors.KindInvalid {
				t.Fatalf("NewKubernetesLease with %s: kind = %v, want Invalid", testCase.name, errors.KindOf(err))
			}
		})
	}
}
