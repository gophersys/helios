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
	"github.com/gophersys/libs/go/workspaceprovider"
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
// cutoff and is idempotent. The two-phase stop drains to terminal across two passes.
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
	// Two-phase stop: Running → Stopping → Stopped (terminal).
	for range 2 {
		if _, err := manager.Reconcile(context.Background()); err != nil {
			t.Fatalf("Reconcile drain: %v", err)
		}
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

	// Idempotent: the record's fold material is gone, so a second Reap finds nothing.
	report2, err := manager.Pool().Reap(context.Background(), manager.Clock().Now())
	if err != nil {
		t.Fatalf("second Reap: %v", err)
	}
	if report2.Reaped != 0 {
		t.Fatalf("second Reap reaped %d, want 0 (idempotent)", report2.Reaped)
	}
}

// TestReap_TearsDownLingeringWorkspace proves Reap is HONEST about its doc-promise to
// "release any lingering workspace lease": a terminal agent whose workspace was provisioned
// but never torn down (an orphan the drain pass never reaped) is Released by Reap, not
// silently dropped. The orphan is constructed deterministically — provision a real workspace
// through the bound provider, then seed a terminal Failed record holding its (still-live)
// handle — so Reap's Teardown is the only thing that can release it.
func TestReap_TearsDownLingeringWorkspace(t *testing.T) {
	t.Parallel()
	manager := newPool(t)
	ctx := context.Background()

	// Provision a real workspace through the bound provider (the same seam reconcile uses), so
	// the workspace fake holds a live native object the only release of which is a Teardown.
	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-orphan",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     "ghcr.io/eden/agent-runtime:1.0.0",
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "o",
			workspaceprovider.LabelProject:      "p",
		},
	}
	workspace, err := manager.Provider().Provision(ctx, spec)
	if err != nil {
		t.Fatalf("Provision orphan workspace: %v", err)
	}
	handle := workspace.Handle()
	if handle.IsZero() {
		t.Fatalf("provisioned orphan has a zero handle")
	}
	if len(manager.Workspaces().Destroyed) != 0 {
		t.Fatalf("orphan workspace already torn down before Reap (Destroyed=%d)", len(manager.Workspaces().Destroyed))
	}

	// Seed a terminal Failed record holding the lingering handle, older than the cutoff.
	old := manager.Clock().Now().Add(-48 * time.Hour)
	orphan := orchestrator.Agent{
		ID:        "agent-orphan",
		Tenant:    orchestrator.Tenancy{OrganizationID: "o", ProjectID: "p"},
		Template:  orchestratortest.DefaultTemplate().Ref,
		Desired:   orchestrator.DesiredStopped,
		Status:    orchestrator.StatusFailed,
		Workspace: handle,
		UpdatedAt: old,
		Detail:    "seeded orphan (workspace never reaped)",
	}
	if err := manager.DesiredStore().Put(ctx, orphan); err != nil {
		t.Fatalf("seed orphan record: %v", err)
	}

	// Reap with a cutoff after the orphan's UpdatedAt: it must TEAR DOWN the lingering
	// workspace (the honest behavior the doc promises), not merely drop the record.
	report, err := manager.Pool().Reap(ctx, manager.Clock().Now())
	if err != nil {
		t.Fatalf("Reap: %v", err)
	}
	if report.Reaped != 1 {
		t.Fatalf("Reap reaped %d, want 1 (the orphan)", report.Reaped)
	}
	if got := len(manager.Workspaces().Destroyed); got != 1 {
		t.Fatalf("Reap tore down %d workspaces, want exactly 1 (the lingering orphan lease)", got)
	}
	if manager.Workspaces().Destroyed[0].String() != handle.String() {
		t.Fatalf("Reap tore down %s, want the orphan handle %s", manager.Workspaces().Destroyed[0], handle)
	}
	manager.AssertNoOrphans(t)
}

// TestProvisionTimeout_HungProvisionMarksFailed proves Config.ProvisionTimeout is WIRED: a
// hung workspaceprovider.Provision trips the per-provision deadline and the agent is marked
// Failed (KindDeadline in the redacted reason) rather than wedged in Provisioning forever.
func TestProvisionTimeout_HungProvisionMarksFailed(t *testing.T) {
	t.Parallel()
	// A tiny ProvisionTimeout + a provider that hangs until ctx is canceled.
	manager := newPool(t, orchestratortest.WithProvisionTimeout(50*time.Millisecond))
	manager.BlockProvision()

	agent, err := manager.Spawn(context.Background(), spawnReq())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}

	// One reconcile pass attempts Provision; the hung call trips the ProvisionTimeout deadline
	// and the agent is marked Failed (not left in Provisioning).
	if _, err := manager.Reconcile(context.Background()); err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	failed, err := manager.Get(context.Background(), agent.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if failed.Status != orchestrator.StatusFailed {
		t.Fatalf("after a hung provision status = %v, want Failed (ProvisionTimeout must fire, detail %q)", failed.Status, failed.Detail)
	}
	if failed.Detail == "" {
		t.Fatalf("Failed record carries no detail (want a redacted deadline reason)")
	}
	manager.AssertNoOrphans(t)
}

// TestRetentionWindow_LoopReapsAgedTerminal proves Config.RetentionWindow is WIRED: the Start
// loop reaps terminal agents older than the window on its OWN cadence (no out-of-band Reap
// caller), releasing a lingering workspace lease. The orphan (a terminal agent whose workspace
// was never torn down) is seeded with a provisioned-but-undestroyed handle so the loop's
// retention pass is the only thing that can release it (Destroyed goes 0 → 1) — and only once
// it ages past the window.
func TestRetentionWindow_LoopReapsAgedTerminal(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	manager := newPool(
		t,
		orchestratortest.WithReconcileInterval(2*time.Millisecond),
		orchestratortest.WithRetentionWindow(time.Hour),
	)

	// Provision a real workspace through the bound provider, then seed a terminal Failed record
	// holding its still-live handle (a lingering lease the drain never reaped).
	workspace, err := manager.Provider().Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      "ws-retained",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     "ghcr.io/eden/agent-runtime:1.0.0",
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "o",
			workspaceprovider.LabelProject:      "p",
		},
	})
	if err != nil {
		t.Fatalf("Provision retained workspace: %v", err)
	}
	// Seed the record YOUNGER than the window first (UpdatedAt == now), so the loop's early
	// ticks must NOT reap it.
	now := manager.Clock().Now()
	orphan := orchestrator.Agent{
		ID:        "agent-retained",
		Tenant:    orchestrator.Tenancy{OrganizationID: "o", ProjectID: "p"},
		Template:  orchestratortest.DefaultTemplate().Ref,
		Desired:   orchestrator.DesiredStopped,
		Status:    orchestrator.StatusFailed,
		Workspace: workspace.Handle(),
		UpdatedAt: now,
		Detail:    "seeded retained orphan",
	}
	if err := manager.DesiredStore().Put(ctx, orphan); err != nil {
		t.Fatalf("seed retained orphan: %v", err)
	}

	pool := manager.Pool()
	if err := pool.Start(ctx); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() {
		if err := pool.Close(context.Background()); err != nil {
			t.Errorf("Close: %v", err)
		}
	})

	// Poll the RECORD (a mutex-safe store read) rather than the racy fake slice: Reap zeroes the
	// workspace handle on the record after releasing the lease, so a zero handle is the
	// observable "reaped" signal that does not race the live loop's appends.
	// The record is younger than the window: the loop must NOT reap it yet.
	time.Sleep(40 * time.Millisecond)
	stillYoung, err := manager.Get(ctx, orphan.ID)
	if err != nil {
		t.Fatalf("Get retained (young): %v", err)
	}
	if stillYoung.Workspace.IsZero() {
		t.Fatalf("loop reaped a record younger than the retention window (handle already released)")
	}

	// Age the record past the window; the loop's next retention pass releases the lingering lease.
	manager.Advance(2 * time.Hour)
	deadline := time.Now().Add(2 * time.Second)
	reaped := false
	for time.Now().Before(deadline) {
		got, gerr := manager.Get(ctx, orphan.ID)
		if gerr == nil && got.Workspace.IsZero() {
			reaped = true
			break
		}
		time.Sleep(5 * time.Millisecond)
	}
	if !reaped {
		t.Fatalf("RetentionWindow loop did not reap the aged terminal agent within the deadline (handle still set)")
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
