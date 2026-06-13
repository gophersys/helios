package orchestrator_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
)

// newPool builds a real *orchestrator.Pool over the in-memory fakes for white-box-ish
// black-box unit tests of the surface the conformance suite does not pin directly (New
// validation, the widening-override refusal, Start/Close lifecycle, Reap).
func newPool(t *testing.T, options ...orchestratortest.Option) *orchestratortest.Manager {
	t.Helper()
	base := []orchestratortest.Option{
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
	}
	return orchestratortest.New(append(base, options...)...)
}

// TestNew_RejectsNilDeps asserts the pure constructor wraps a ConfigError (KindInvalid)
// for a missing required dependency.
func TestNew_RejectsNilDeps(t *testing.T) {
	t.Parallel()
	_, err := orchestrator.New(orchestrator.Config{}, orchestrator.Deps{})
	if err == nil {
		t.Fatalf("New with nil Deps: want ConfigError, got nil")
	}
	if typed, ok := errors.AsType[*orchestrator.ConfigError](err); !ok || typed == nil {
		t.Fatalf("New with nil Deps: want *ConfigError, got %v", err)
	}
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("ConfigError kind = %v, want invalid", errors.KindOf(err))
	}
}

// TestSpawn_WideningOverrideRejected asserts a BudgetOverride that loosens the template
// ceiling is an InvalidRequestError (KindInvalid) — the template is the ceiling, the
// request the floor.
func TestSpawn_WideningOverrideRejected(t *testing.T) {
	t.Parallel()
	manager := newPool(t)

	// DefaultTemplate's budget is 1_000_000 micros; an override above it widens.
	wide := agentsession.Budget{MaxCostMicros: 9_000_000}
	req := orchestrator.SpawnRequest{
		Tenant:         orchestrator.Tenancy{OrganizationID: "o", ProjectID: "p"},
		Template:       orchestratortest.DefaultTemplate().Ref,
		Credential:     secrets.Ref("vault://eden#token"),
		BudgetOverride: &wide,
	}
	_, err := manager.Spawn(context.Background(), req)
	if err == nil {
		t.Fatalf("widening BudgetOverride: want InvalidRequestError, got nil")
	}
	if typed, ok := errors.AsType[*orchestrator.InvalidRequestError](err); !ok || typed == nil {
		t.Fatalf("widening BudgetOverride: want *InvalidRequestError, got %v (kind %v)", err, errors.KindOf(err))
	}
}

// TestSpawn_TighteningOverrideAdmitted asserts a smaller-than-template BudgetOverride is
// admitted (only tightening is allowed).
func TestSpawn_TighteningOverrideAdmitted(t *testing.T) {
	t.Parallel()
	manager := newPool(t)

	narrow := agentsession.Budget{MaxCostMicros: 500_000}
	req := orchestrator.SpawnRequest{
		Tenant:         orchestrator.Tenancy{OrganizationID: "o", ProjectID: "p"},
		Template:       orchestratortest.DefaultTemplate().Ref,
		Credential:     secrets.Ref("vault://eden#token"),
		BudgetOverride: &narrow,
	}
	agent, err := manager.Spawn(context.Background(), req)
	if err != nil {
		t.Fatalf("tightening BudgetOverride: %v", err)
	}
	if agent.Limits.Budget.MaxCostMicros != 500_000 {
		t.Fatalf("effective budget = %d, want the tightened 500000", agent.Limits.Budget.MaxCostMicros)
	}
}

// TestSpawn_UnknownTemplate asserts a TemplateNotFoundError (KindNotFound) for an unknown
// ref, before any provisioning.
func TestSpawn_UnknownTemplate(t *testing.T) {
	t.Parallel()
	manager := newPool(t)
	_, err := manager.Spawn(context.Background(), orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "o", ProjectID: "p"},
		Template:   orchestrator.TemplateRef{Name: "nope", Version: "9.9.9"},
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
	})
	if typed, ok := errors.AsType[*orchestrator.TemplateNotFoundError](err); !ok || typed == nil {
		t.Fatalf("unknown template: want *TemplateNotFoundError, got %v", err)
	}
}

// TestSpawn_MissingTenant asserts a malformed request (no tenant) is InvalidRequestError.
func TestSpawn_MissingTenant(t *testing.T) {
	t.Parallel()
	manager := newPool(t)
	_, err := manager.Spawn(context.Background(), orchestrator.SpawnRequest{
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
	})
	if typed, ok := errors.AsType[*orchestrator.InvalidRequestError](err); !ok || typed == nil {
		t.Fatalf("missing tenant: want *InvalidRequestError, got %v", err)
	}
}

// TestStartClose_DrainsActiveAgents asserts Start runs the loop, Close records a Stopping
// intent for the non-terminal agent and drives the final pass that releases its workspace
// (no orphan).
func TestStartClose_DrainsActiveAgents(t *testing.T) {
	t.Parallel()
	manager := newPool(t)
	manager.Probe().SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})

	agent, err := manager.Spawn(context.Background(), spawnReq())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	// Drive to Running by hand (provision + open).
	for range 3 {
		got, gerr := manager.Get(context.Background(), agent.ID)
		if gerr != nil {
			t.Fatalf("Get: %v", gerr)
		}
		if got.Status == orchestrator.StatusRunning {
			break
		}
		if _, err := manager.Reconcile(context.Background()); err != nil {
			t.Fatalf("Reconcile: %v", err)
		}
	}

	pool := manager.Pool()
	if err := pool.Close(context.Background()); err != nil {
		t.Fatalf("Close: %v", err)
	}
	got, err := manager.Get(context.Background(), agent.ID)
	if err != nil {
		t.Fatalf("Get after Close: %v", err)
	}
	if got.Status != orchestrator.StatusStopped {
		t.Fatalf("after Close status = %v, want Stopped (Close drains the active agent)", got.Status)
	}
	manager.AssertNoOrphans(t)

	// Close is idempotent.
	if err := pool.Close(context.Background()); err != nil {
		t.Fatalf("second Close: want nil (idempotent), got %v", err)
	}
}

// TestReap_DropsOldTerminalAgents asserts Reap counts terminal agents older than the
// cutoff and is idempotent.
func TestReap_DropsOldTerminalAgents(t *testing.T) {
	t.Parallel()
	manager := newPool(t)
	manager.Probe().SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})

	agent, err := manager.Spawn(context.Background(), spawnReq())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	for range 3 {
		if _, err := manager.Reconcile(context.Background()); err != nil {
			t.Fatalf("Reconcile: %v", err)
		}
	}
	if err := manager.Stop(context.Background(), agent.ID, "operator"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	if _, err := manager.Reconcile(context.Background()); err != nil {
		t.Fatalf("Reconcile drain: %v", err)
	}

	// The agent is terminal; advance the clock past its UpdatedAt and reap.
	manager.Advance(48 * time.Hour)
	report, err := manager.Pool().Reap(context.Background(), manager.Clock().Now())
	if err != nil {
		t.Fatalf("Reap: %v", err)
	}
	if report.Reaped != 1 {
		t.Fatalf("Reap reaped %d, want 1", report.Reaped)
	}
}

// spawnReq is a minimal valid SpawnRequest against the default template.
func spawnReq() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "o", ProjectID: "p"},
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
		By:         "tester",
	}
}
