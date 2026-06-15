package orchestratortest

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// The canonical template refs the suite spawns against. The default template runs the
// clean happy path; the budget template carries a small MaxCostMicros ceiling so the
// budget-watch case can cross it.
var (
	defaultTemplateRef = orchestrator.TemplateRef{Name: "implementer-go", Version: "1.0.0"}
	budgetTemplateRef  = orchestrator.TemplateRef{Name: "budget-bound", Version: "1.0.0"}
)

// DefaultTemplate is the canonical AgentTemplate the suite seeds and spawns: a docker
// sandbox with an image (workspaceprovider requires Name+Image), a write grant, and a
// generous budget. Exported so a consumer wiring its own newManager seeds the same shape.
func DefaultTemplate() orchestrator.AgentTemplate {
	return orchestrator.AgentTemplate{
		Ref:         defaultTemplateRef,
		Description: "the canonical conformance implementer template",
		Grants:      []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		Routing:     agentsession.RouteKey{Phase: "implement", Role: "implementer"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate:   orchestrator.SubstrateDocker,
			Image:       "ghcr.io/eden/agent-runtime:1.0.0",
			Resources:   orchestrator.ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096},
			EgressAllow: []string{"api.anthropic.com"},
		},
		Limits: orchestrator.Limits{
			Budget: agentsession.Budget{MaxCostMicros: 1_000_000},
		},
	}
}

// BudgetTemplate is the canonical small-budget template the budget-watch case spawns: a
// MaxCostMicros ceiling of 1000 so a 5000-micro observed ledger crosses it.
func BudgetTemplate() orchestrator.AgentTemplate {
	template := DefaultTemplate()
	template.Ref = budgetTemplateRef
	template.Description = "a budget-bounded template (1000 micros) for the runaway-stop case"
	template.Routing = agentsession.RouteKey{Phase: "implement", Role: "budget"}
	template.Limits.Budget = agentsession.Budget{MaxCostMicros: 1000}
	return template
}

// request builds the canonical SpawnRequest the suite spawns (default tenant, default
// template, the seeded credential ref — the VALUE never rides it).
func request() orchestrator.SpawnRequest {
	return requestFor(defaultTemplateRef)
}

// requestFor builds a SpawnRequest for a specific template ref under the default tenant.
func requestFor(ref orchestrator.TemplateRef) orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-test", ProjectID: "proj-test"},
		Template:   ref,
		Credential: secrets.Ref(credentialRef),
		By:         "tester",
		RunID:      "run-1",
	}
}

// requestForTenant builds a default-template SpawnRequest under a specific tenancy (the
// per-tenancy admission/isolation case).
func requestForTenant(tenant orchestrator.Tenancy) orchestrator.SpawnRequest {
	req := request()
	req.Tenant = tenant
	return req
}

// mustSpawn spawns the canonical request and fails on error.
func mustSpawn(t *testing.T, manager orchestrator.Manager) orchestrator.Agent {
	t.Helper()
	agent, err := manager.Spawn(context.Background(), request())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	return agent
}

// mustReconcile drives one pass and fails on a pass error.
func mustReconcile(t *testing.T, harness Harness) orchestrator.ReconcileReport {
	t.Helper()
	report, err := harness.Reconcile(context.Background())
	if err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	return report
}

// mustGet reads a record and fails on error.
func mustGet(t *testing.T, manager orchestrator.Manager, id orchestrator.AgentID) orchestrator.Agent {
	t.Helper()
	agent, err := manager.Get(context.Background(), id)
	if err != nil {
		t.Fatalf("Get(%s): %v", id, err)
	}
	return agent
}

// assertStatus fails t unless the agent's reconciled status equals want.
func assertStatus(t *testing.T, manager orchestrator.Manager, id orchestrator.AgentID, want orchestrator.Status) {
	t.Helper()
	got := mustGet(t, manager, id)
	if got.Status != want {
		t.Fatalf("agent %s status = %v, want %v (detail %q)", id, got.Status, want, got.Detail)
	}
}

// driveToRunning reconciles until the agent reaches Running (Pending→Provisioning→Running),
// failing if it does not converge within a bounded number of passes.
func driveToRunning(t *testing.T, manager orchestrator.Manager, harness Harness, id orchestrator.AgentID) {
	t.Helper()
	for range 5 {
		agent := mustGet(t, manager, id)
		if agent.Status == orchestrator.StatusRunning {
			return
		}
		if agent.Status.Terminal() {
			t.Fatalf("agent %s reached terminal %v before Running (detail %q)", id, agent.Status, agent.Detail)
		}
		mustReconcile(t, harness)
	}
	t.Fatalf("agent %s did not reach Running within 5 passes (status %v)", id, mustGet(t, manager, id).Status)
}

// assertNoOrphans bridges the suite's Manager interface to the runnable leak guard when
// the concrete type exposes it (the v0 *Manager does).
func assertNoOrphans(t *testing.T, manager orchestrator.Manager) {
	t.Helper()
	if asserter, ok := manager.(interface{ AssertNoOrphans(TestingT) }); ok {
		asserter.AssertNoOrphans(t)
	}
}

// assertNoSecretInRecord bridges the suite to the runnable credential-seam guard.
func assertNoSecretInRecord(t *testing.T, manager orchestrator.Manager, canary string) {
	t.Helper()
	if asserter, ok := manager.(interface {
		AssertNoSecretInRecord(TestingT, string)
	}); ok {
		asserter.AssertNoSecretInRecord(t, canary)
	}
}

// containsBudgetReason reports whether a terminal detail names a budget stop.
func containsBudgetReason(detail string) bool {
	return strings.Contains(strings.ToLower(detail), "budget")
}

// workspaceNameOf extracts the deterministic workspace Name from a record's Handle (the
// Provision idempotency key), so a re-provision case asserts the SAME Name was re-adopted
// rather than a duplicate identity minted.
func workspaceNameOf(handle workspaceprovider.Handle) string { return handle.Name() }

// assertBudgetEventMatchesRecord asserts the emitted ObsBudgetExceeded event's To field
// equals wantTo — the "event == committed transition" invariant: the budget verdict and the
// recorded transition must AGREE (both Stopping), never the observability/record disagreement
// the over-promise hid (the event used to claim To:Stopping while the record went straight to
// Stopped). It also cross-checks that an ObsTransition committing the same agent's transition
// carries the same To.
func assertBudgetEventMatchesRecord(t *testing.T, harness Harness, wantTo orchestrator.Status) {
	t.Helper()
	events := harness.Telemetry.Snapshot()
	var budget *orchestrator.ObservabilityEvent
	for i := range events {
		if events[i].Kind == orchestrator.ObsBudgetExceeded {
			budget = &events[i]
		}
	}
	if budget == nil {
		t.Fatalf("no ObsBudgetExceeded event emitted (want one with To=%v)", wantTo)
	}
	if budget.To != wantTo {
		t.Fatalf("ObsBudgetExceeded To = %v, want %v (the event must match the committed transition)", budget.To, wantTo)
	}
	// The committed transition this step must agree with the event: find the ObsTransition for
	// the same agent whose To equals the event's To and whose From matches.
	matched := false
	for i := range events {
		e := events[i]
		if e.Kind == orchestrator.ObsTransition && e.AgentID == budget.AgentID && e.To == budget.To && e.From == budget.From {
			matched = true
			break
		}
	}
	if !matched {
		t.Fatalf("ObsBudgetExceeded (%v→%v) has no matching committed ObsTransition for %s — event/record disagree",
			budget.From, budget.To, budget.AgentID)
	}
}
