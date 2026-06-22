package composition_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agent-runtime/internal/composition"
)

// The wiring suite proves the W2 composition-root wiring on REAL library types (a genuine
// agentsession.Pool over a scripted fake adapter, a real observability.Provider) — no mocks of the
// substrate: (1) the supervisor route resolves to opus-4.8 through buildRouting; (2) buildSpec
// threads EDEN_ROLE/EDEN_PHASE instead of hardcoding "assistant", and the supervisor gets the larger
// Budget; (3) buildAdvisor wires a non-nil agentsession.PermissionAdvisor when a credential is
// configured, and a TRUE nil interface (the documented degrade) when it is not.

// credentialRef is the loggable opaque reference the test credential resolves under (the value never
// rides it). It mirrors the production EDEN_CREDENTIAL_REF shape.
const credentialRef = "vault://eden/anthropic#setup-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// fixedClock is a deterministic observability.Clock so the real provider the test builds is
// reproducible (the composition root reads the wall clock; the test pins it).
type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 22, 12, 0, 0, 0, time.UTC) }

// noopExporter is a real, non-blocking observability.Exporter (the test's telemetry boundary). It
// drops records — the test asserts wiring, not telemetry content, so a real-but-silent exporter is
// the right substrate (never a mock of the Provider itself, which stays the genuine library type).
type noopExporter struct{}

func (noopExporter) Export(context.Context, []observability.Record) error { return nil }

// newProvider builds a REAL observability.Provider (the genuine library type) over the noop exporter
// + the fixed clock — the same shape the composition root's build() constructs.
//
//nolint:ireturn // observability.New returns the Provider port (the frozen surface); the test helper forwards it.
func newProvider(t *testing.T) observability.Provider {
	t.Helper()
	provider, err := observability.New(
		observability.Config{ServiceName: "agent-runtime-test"},
		observability.Deps{Exporter: noopExporter{}, Clock: fixedClock{}},
	)
	if err != nil {
		t.Fatalf("build observability provider: %v", err)
	}
	return provider
}

// newFakeFactory builds a REAL agentsession.Pool over the scripted fake adapter using the SAME
// routing the composition root produces (buildRouting), so an Open against the supervisor route
// exercises the real Pool resolveRoute path. The fake adapter is registered under BOTH harness keys
// the routing can name (claude-code, omp) so either route resolves to it.
//
//nolint:ireturn,gocritic // ireturn: agentsession.New returns the Factory port the sidecar holds; gocritic: Environment is the frozen copyable input taken by value, mirroring Run.
func newFakeFactory(t *testing.T, environment composition.Environment) agentsession.Factory {
	t.Helper()
	adapter := agentsessiontest.New(agentsessiontest.CanonicalScript()...)
	provider := secretstest.New(map[string]string{credentialRef: agentsessiontest.SeededCanary})
	pool, err := agentsession.New(
		agentsession.Config{Routing: composition.BuildRoutingForTest(environment)},
		agentsession.Deps{
			Adapters: map[string]agentsession.Adapter{
				"claude-code": adapter,
				"omp":         adapter,
			},
			Secrets:    provider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      sessionClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct test Pool: %v", err)
	}
	return pool
}

// sessionClock is a deterministic agentsession.Clock for the test Pool.
type sessionClock struct{}

func (sessionClock) Now() time.Time { return time.Date(2026, time.June, 22, 12, 0, 0, 0, time.UTC) }

// TestSupervisorRouteResolves proves the supervisor route is registered and resolves: a supervisor
// Spec opens a live session through a REAL Pool built from the composition root's own routing,
// without a RouteError. It also asserts the route's concrete binding is opus-4.8 over claude-code,
// and that the assistant route still resolves (existing behavior intact).
func TestSupervisorRouteResolves(t *testing.T) {
	t.Parallel()
	environment := composition.Environment{Harness: "claude-code", Model: "claude-fable-5", CredentialRef: credentialRef}

	routing := composition.BuildRoutingForTest(environment)

	supervisorRoute, ok := routing[agentsession.RouteKey{Role: composition.RoleSupervisorForTest}]
	if !ok {
		t.Fatal("supervisor route is not registered in the composition routing table")
	}
	if supervisorRoute.Harness != "claude-code" {
		t.Errorf("supervisor route Harness = %q, want %q", supervisorRoute.Harness, "claude-code")
	}
	if supervisorRoute.Model != composition.SupervisorModelForTest {
		t.Errorf("supervisor route Model = %q, want the opus-4.8 id %q", supervisorRoute.Model, composition.SupervisorModelForTest)
	}
	// Cross-check the pinned model id is the canonical opus-4.8 selector (one home: harnesses model id).
	if composition.SupervisorModelForTest != "claude-opus-4-8" {
		t.Errorf("supervisor model id = %q, want the canonical opus-4.8 id %q", composition.SupervisorModelForTest, "claude-opus-4-8")
	}
	if _, assistantPresent := routing[agentsession.RouteKey{Role: composition.RoleAssistantForTest}]; !assistantPresent {
		t.Fatal("assistant route disappeared — existing behavior broken")
	}

	// Resolve the supervisor route end-to-end through a REAL Pool: Open resolves the route before
	// spawning, so a successful Open over the supervisor RouteKey proves the route resolves.
	factory := newFakeFactory(t, environment)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	session, err := factory.Open(ctx, agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    agentsession.RouteKey{Role: composition.RoleSupervisorForTest},
		Credential: secrets.Ref(credentialRef),
	})
	if err != nil {
		t.Fatalf("Open supervisor session: route did not resolve: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort reap.
}

// TestBuildSpecThreadsRole proves buildSpec no longer hardcodes the role: EDEN_ROLE drives the
// routing role (defaulting to assistant), EDEN_PHASE rides through, and the supervisor gets the
// larger Budget while the assistant keeps the zero (environment-bounded) Budget.
func TestBuildSpecThreadsRole(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name       string
		role       string
		phase      string
		wantRole   string
		wantBudget agentsession.Budget
	}{
		{name: "default unset role is assistant", role: "", phase: "", wantRole: composition.RoleAssistantForTest, wantBudget: agentsession.Budget{}},
		{name: "supervisor role routes supervisor with larger budget", role: "supervisor", phase: "review", wantRole: composition.RoleSupervisorForTest, wantBudget: composition.SupervisorBudgetForTest},
		{name: "assistant role explicit keeps zero budget", role: "assistant", phase: "implement", wantRole: composition.RoleAssistantForTest, wantBudget: agentsession.Budget{}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			spec := composition.BuildSpecForTest(composition.Environment{
				Workspace:     "/workspace/eden",
				Role:          tc.role,
				Phase:         tc.phase,
				CredentialRef: credentialRef,
			})
			if spec.Routing.Role != tc.wantRole {
				t.Errorf("Spec.Routing.Role = %q, want %q", spec.Routing.Role, tc.wantRole)
			}
			if spec.Routing.Phase != tc.phase {
				t.Errorf("Spec.Routing.Phase = %q, want %q (EDEN_PHASE must thread through)", spec.Routing.Phase, tc.phase)
			}
			if spec.Budget != tc.wantBudget {
				t.Errorf("Spec.Budget = %+v, want %+v", spec.Budget, tc.wantBudget)
			}
			if spec.Credential.IsZero() {
				t.Error("Spec.Credential must carry the configured opaque reference")
			}
		})
	}
}

// TestBuildAdvisorWired proves the known unwired gap is closed: buildAdvisor returns a non-nil
// agentsession.PermissionAdvisor when a credential is configured, and that value is a usable port.
func TestBuildAdvisorWired(t *testing.T) {
	t.Parallel()
	environment := composition.Environment{Harness: "claude-code", Model: "claude-fable-5", Workspace: "/workspace/eden", CredentialRef: credentialRef}
	provider := newProvider(t)
	factory := newFakeFactory(t, environment)

	advisor, err := composition.BuildAdvisorForTest(environment, provider, factory)
	if err != nil {
		t.Fatalf("buildAdvisor: %v", err)
	}
	if advisor == nil {
		t.Fatal("Advisor is NOT wired: buildAdvisor returned a nil PermissionAdvisor with a credential configured (the known unwired gap)")
	}
	// The wired advisor is a usable port: with the SAME factory injected, it can adjudicate a
	// request (the scripted reviewer fake answers; a malformed/empty verdict fails safe to deny).
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	decision, adviseErr := advisor.Advise(
		ctx,
		agentsession.PermissionRequest{RequestID: "req-1", Tool: "Read", Reason: "inspect a file"},
		agentsession.AdviceContext{Role: composition.RoleAssistantForTest, Risk: agentsession.RiskLow},
	)
	if adviseErr != nil {
		t.Fatalf("Advise (wired advisor) returned a transport error, want a decided verdict: %v", adviseErr)
	}
	// The scripted canonical reviewer reply is prose ("Hello, world"), not the structured frame, so
	// the advisor parses it as a fail-safe DENY — proving the advisor actually drove the reviewer
	// session through the injected factory (not a stub).
	if decision.Allow {
		t.Errorf("Advise allowed an unstructured reviewer reply; want the fail-safe deny (decision=%+v)", decision)
	}
}

// TestBuildAdvisorAbsentWithoutCredential proves the degrade path: with NO credential reference, the
// advisor is a TRUE nil interface (not a typed-nil pointer), so agentsession's optional-port nil
// check sees it as absent and the chain degrades to OnPermission/default-deny with no regression.
func TestBuildAdvisorAbsentWithoutCredential(t *testing.T) {
	t.Parallel()
	environment := composition.Environment{Harness: "claude-code", Workspace: "/workspace/eden"} // no CredentialRef
	provider := newProvider(t)
	factory := newFakeFactory(t, environment)

	advisor, err := composition.BuildAdvisorForTest(environment, provider, factory)
	if err != nil {
		t.Fatalf("buildAdvisor (no credential): %v", err)
	}
	if advisor != nil {
		t.Fatalf("Advisor must be a TRUE nil interface without a credential (the typed-nil trap defeats agentsession's nil check); got %T", advisor)
	}
}
