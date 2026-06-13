package orchestratortest

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// Harness gives the suite the scripted dependencies it drives a pass against. Workspaces
// is the frozen-seam fake (workspaceprovidertest), not an orchestrator-owned double (Q8).
type Harness struct {
	Reconcile  func(context.Context) (orchestrator.ReconcileReport, error) // one deterministic pass
	Workspaces *workspaceprovidertest.Adapter
	Probe      *Probe
	Telemetry  *Telemetry
	Clock      *Clock
}

// RunManagerSuite asserts the port contract against a freshly-constructed Manager wired
// with the supplied fakes (or a real adapter set). newManager returns a Manager plus the
// scripted Harness a test drives a pass against. It is the ONE conformance entrypoint so
// any orchestrator.Manager/Reconciler (the v0 *Pool or a future multi-node build) proves
// substitutable against the lifecycle/limit/credential properties (contract §4).
func RunManagerSuite(t *testing.T, newManager func() (orchestrator.Manager, Harness)) {
	t.Helper()
	suite := []struct {
		name string
		run  func(*testing.T, orchestrator.Manager, Harness)
	}{
		{"SpawnRecordsDesiredDoesNotBlock", caseSpawnDoesNotBlock},
		{"ReconcileConvergentIdempotent", caseConvergentIdempotent},
		{"LifecycleLegality", caseLifecycleLegality},
		{"LimitEnforcementBeforeProvisioning", caseLimitBeforeProvisioning},
		{"WorkspaceLifecycleNoLeak", caseWorkspaceNoLeak},
		{"ProvisionFailureMarksFailed", caseProvisionFailure},
		{"BudgetAuthorityStopsRunaway", caseBudgetAuthority},
		{"StopDrainsThenReleasesOnce", caseStopReleasesOnce},
		{"ResumeReattaches", caseResumeReattaches},
		{"GetListReadRecords", caseGetListReadRecords},
		{"CredentialSeamNeverLeaks", caseCredentialSeam},
		{"ObservabilityCompleteness", caseObservabilityCompleteness},
		{"TenancyIsolation", caseTenancyIsolation},
		{"WatchSnapshotThenTail", caseWatchSnapshotThenTail},
	}
	for _, tc := range suite {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			manager, harness := newManager()
			tc.run(t, manager, harness)
		})
	}
}

// ── individual property cases ───────────────────────────────────────────────────.

// caseSpawnDoesNotBlock asserts Spawn returns StatusPending immediately and provisions NO
// workspace; the workspace/session appear only after a Reconcile pass.
func caseSpawnDoesNotBlock(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	agent, err := manager.Spawn(ctx, request())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	if agent.Status != orchestrator.StatusPending {
		t.Fatalf("Spawn returned status %v, want Pending (must not block)", agent.Status)
	}
	if len(harness.Workspaces.Provisioned) != 0 {
		t.Fatalf("Spawn provisioned %d workspaces, want 0 (no provisioning before reconcile)", len(harness.Workspaces.Provisioned))
	}

	if _, err := harness.Reconcile(ctx); err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	if len(harness.Workspaces.Provisioned) != 1 {
		t.Fatalf("after one pass provisioned %d workspaces, want 1", len(harness.Workspaces.Provisioned))
	}
}

// caseConvergentIdempotent asserts one pass takes Pending→Provisioning→Running across two
// passes, and a further pass with unchanged desired is a no-op (at most one transition per
// agent per pass).
func caseConvergentIdempotent(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	agent := mustSpawn(t, manager)

	// Pass 1: Pending → Provisioning (exactly one transition).
	report1 := mustReconcile(t, harness)
	if report1.Transitioned != 1 {
		t.Fatalf("pass 1 transitioned %d, want 1", report1.Transitioned)
	}
	assertStatus(t, manager, agent.ID, orchestrator.StatusProvisioning)

	// Make the actual live so pass 2 can move Provisioning → Running.
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})

	// Pass 2: Provisioning → Running.
	report2 := mustReconcile(t, harness)
	if report2.Transitioned != 1 {
		t.Fatalf("pass 2 transitioned %d, want 1", report2.Transitioned)
	}
	assertStatus(t, manager, agent.ID, orchestrator.StatusRunning)

	// Pass 3: unchanged desired + live actual == no transition (idempotent/convergent).
	report3 := mustReconcile(t, harness)
	if report3.Transitioned != 0 {
		t.Fatalf("pass 3 (converged) transitioned %d, want 0 (idempotent)", report3.Transitioned)
	}
}

// caseLifecycleLegality asserts an illegal Resume (non-resumable status) is ConflictError.
func caseLifecycleLegality(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	agent := mustSpawn(t, manager)

	// A Pending agent is not resumable → ConflictError.
	err := manager.Resume(ctx, agent.ID, "operator")
	if err == nil {
		t.Fatalf("Resume on a Pending agent: want ConflictError, got nil")
	}
	if typed, ok := errors.AsType[*orchestrator.ConflictError](err); !ok || typed == nil {
		t.Fatalf("Resume on a Pending agent: want *ConflictError, got %v (kind %v)", err, errors.KindOf(err))
	}
	if errors.KindOf(err) != errors.KindConflict {
		t.Fatalf("Resume conflict kind = %v, want conflict", errors.KindOf(err))
	}

	// Resume on an unknown id → NotFoundError.
	err = manager.Resume(ctx, "agent-does-not-exist", "operator")
	if typed, ok := errors.AsType[*orchestrator.NotFoundError](err); !ok || typed == nil {
		t.Fatalf("Resume unknown: want *NotFoundError, got %v", err)
	}
}

// caseLimitBeforeProvisioning asserts the (Tenant, Template) MaxConcurrent ceiling rejects
// an over-limit Spawn with LimitError/KindExhausted (carrying Max+Current) BEFORE
// provisioning, emits ObsLimitRejected, and that a Stop frees a slot.
func caseLimitBeforeProvisioning(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	// The suite manager is wired with MaxConcurrent=2 (see newManager). Spawn 2, then a 3rd
	// must be rejected.
	a1 := mustSpawn(t, manager)
	_ = mustSpawn(t, manager)

	_, err := manager.Spawn(ctx, request())
	if err == nil {
		t.Fatalf("3rd Spawn over MaxConcurrent=2: want LimitError, got nil")
	}
	var limit *orchestrator.LimitError
	limit, ok := errors.AsType[*orchestrator.LimitError](err)
	if !ok {
		t.Fatalf("over-limit Spawn: want *LimitError, got %v (kind %v)", err, errors.KindOf(err))
	}
	if errors.KindOf(err) != errors.KindExhausted {
		t.Fatalf("LimitError kind = %v, want exhausted", errors.KindOf(err))
	}
	if limit.Max != 2 || limit.Current != 2 {
		t.Fatalf("LimitError Max/Current = %d/%d, want 2/2", limit.Max, limit.Current)
	}
	// No workspace was provisioned by the refused spawn (admission is before any pod).
	if len(harness.Workspaces.Provisioned) != 0 {
		t.Fatalf("refused spawn provisioned %d workspaces, want 0 (admission before provisioning)", len(harness.Workspaces.Provisioned))
	}
	if harness.Telemetry.CountKind(orchestrator.ObsLimitRejected) != 1 {
		t.Fatalf("ObsLimitRejected emitted %d times, want 1", harness.Telemetry.CountKind(orchestrator.ObsLimitRejected))
	}

	// Stop one agent → a slot frees → the next Spawn is admitted.
	if err := manager.Stop(ctx, a1.ID, "operator"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	mustReconcile(t, harness) // drain the stopped agent so it is terminal (frees the slot)
	if _, err := manager.Spawn(ctx, request()); err != nil {
		t.Fatalf("Spawn after a slot freed: %v", err)
	}
}

// caseWorkspaceNoLeak asserts every terminal transition tears down the workspace exactly
// once, and a provisioning failure marks the agent Failed and still tears down any partial
// workspace, with AssertNoOrphans holding at end.
func caseWorkspaceNoLeak(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	agent := mustSpawn(t, manager)
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	driveToRunning(t, manager, harness, agent.ID)

	if err := manager.Stop(ctx, agent.ID, "operator"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	mustReconcile(t, harness) // Stopping → Stopped (Close-then-Teardown)
	assertStatus(t, manager, agent.ID, orchestrator.StatusStopped)

	if len(harness.Workspaces.Destroyed) != 1 {
		t.Fatalf("Teardown called %d times, want exactly 1 (sole reaper)", len(harness.Workspaces.Destroyed))
	}
	assertNoOrphans(t, manager)
}

// caseProvisionFailure asserts a forced provisioning fault marks the agent Failed (with a
// redacted reason) and leaves no orphaned workspace — the all-or-nothing provision +
// fail-cheap path.
func caseProvisionFailure(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	agent := mustSpawn(t, manager)
	// Force the next Provision (the first reconcile pass) to fail with a quota fault.
	harness.Workspaces.FailProvisionWith(&workspaceprovider.QuotaExceededError{Resource: "workspaces"})

	mustReconcile(t, harness)
	failed := mustGet(t, manager, agent.ID)
	if failed.Status != orchestrator.StatusFailed {
		t.Fatalf("after forced provision failure status = %v, want Failed", failed.Status)
	}
	if failed.Detail == "" {
		t.Fatalf("Failed record carries no detail (want a redacted provision reason)")
	}
	// A forced provision failure provisioned nothing live, so nothing leaks.
	assertNoOrphans(t, manager)
}

// caseBudgetAuthority asserts that when the observed Actual.Ledger crosses
// Limits.Budget.MaxCostMicros, reconcile drives a Stop, the terminal record carries the
// budget reason, and ObsBudgetExceeded is emitted.
func caseBudgetAuthority(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	// budgetTemplate sets MaxCostMicros=1000; spawn against it.
	agent, err := manager.Spawn(ctx, requestFor(budgetTemplateRef))
	if err != nil {
		t.Fatalf("Spawn budget agent: %v", err)
	}
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	driveToRunning(t, manager, harness, agent.ID)

	// Cross the budget: the observed ledger reports cost above the ceiling.
	harness.Probe.Set(agent.ID, orchestrator.Actual{
		WorkspaceLive: true, SessionLive: true,
		Ledger: agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{CostMicros: 5000},
		},
	})

	// One pass detects the runaway and drives a Stop (Running → Stopped, with the workspace
	// torn down). A budget stop is a single bounded transition.
	mustReconcile(t, harness)
	stopped := mustGet(t, manager, agent.ID)
	if stopped.Status != orchestrator.StatusStopped {
		t.Fatalf("after budget cross status = %v, want Stopped", stopped.Status)
	}
	if stopped.Detail == "" || !containsBudgetReason(stopped.Detail) {
		t.Fatalf("terminal record detail = %q, want a budget reason", stopped.Detail)
	}
	if harness.Telemetry.CountKind(orchestrator.ObsBudgetExceeded) != 1 {
		t.Fatalf("ObsBudgetExceeded emitted %d times, want 1", harness.Telemetry.CountKind(orchestrator.ObsBudgetExceeded))
	}
	assertNoOrphans(t, manager)
}

// caseStopReleasesOnce asserts Stop drains the session + releases the workspace exactly
// once (Release is the sole teardown), and is idempotent.
func caseStopReleasesOnce(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	agent := mustSpawn(t, manager)
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	driveToRunning(t, manager, harness, agent.ID)

	if err := manager.Stop(ctx, agent.ID, "operator"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	// A second Stop before reconcile is an idempotent no-op success.
	if err := manager.Stop(ctx, agent.ID, "operator"); err != nil {
		t.Fatalf("idempotent Stop: %v", err)
	}
	mustReconcile(t, harness)
	// A further pass on the terminal agent does not tear down again.
	mustReconcile(t, harness)

	if len(harness.Workspaces.Destroyed) != 1 {
		t.Fatalf("Teardown called %d times across Stop+reconcile, want exactly 1", len(harness.Workspaces.Destroyed))
	}
	// A Stop on an already-terminal agent is a no-op success.
	if err := manager.Stop(ctx, agent.ID, "operator"); err != nil {
		t.Fatalf("Stop on terminal agent: want nil, got %v", err)
	}
}

// caseResumeReattaches asserts Resume on a Suspended agent re-attaches it (back to
// Running) via reconcile, threading Spec.ResumeFrom.
func caseResumeReattaches(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	agent := mustSpawn(t, manager)
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	driveToRunning(t, manager, harness, agent.ID)

	// Drop the actual (workspace/session gone): reconcile moves Running → Suspended.
	harness.Probe.Set(agent.ID, orchestrator.Actual{WorkspaceLive: false, SessionLive: false})
	mustReconcile(t, harness)
	assertStatus(t, manager, agent.ID, orchestrator.StatusSuspended)

	// Resume records the intent (Suspended → Resuming).
	if err := manager.Resume(ctx, agent.ID, "operator"); err != nil {
		t.Fatalf("Resume: %v", err)
	}
	assertStatus(t, manager, agent.ID, orchestrator.StatusResuming)

	// The actual recovers; reconcile re-attaches (Resuming → Running).
	harness.Probe.Set(agent.ID, orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	mustReconcile(t, harness)
	assertStatus(t, manager, agent.ID, orchestrator.StatusRunning)
}

// caseGetListReadRecords asserts Get/List read the reconciled record (and List filters).
func caseGetListReadRecords(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	a1 := mustSpawn(t, manager)
	a2 := mustSpawn(t, manager)
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	driveToRunning(t, manager, harness, a1.ID)
	driveToRunning(t, manager, harness, a2.ID)

	got := mustGet(t, manager, a1.ID)
	if got.ID != a1.ID || got.Status != orchestrator.StatusRunning {
		t.Fatalf("Get(%s) = %+v, want Running", a1.ID, got)
	}

	page, err := manager.List(ctx, orchestrator.Filter{OnlyActive: true})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(page.Agents) != 2 {
		t.Fatalf("List OnlyActive returned %d agents, want 2", len(page.Agents))
	}

	// Unknown id → NotFoundError.
	_, err = manager.Get(ctx, "agent-nope")
	if typed, ok := errors.AsType[*orchestrator.NotFoundError](err); !ok || typed == nil {
		t.Fatalf("Get unknown: want *NotFoundError, got %v", err)
	}
}

// caseCredentialSeam asserts the opaque secrets.Reference threads through but the VALUE
// never enters any record/Event/store/error (AssertNoSecretInRecord runnable). The session
// adapter resolves the credential server-side at Open; the canary must appear nowhere.
func caseCredentialSeam(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	agent := mustSpawn(t, manager)
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	driveToRunning(t, manager, harness, agent.ID)

	// Reaching Running is the NON-VACUOUS proof the opaque credential threaded through to
	// agentsession.Open: Open resolves the reference server-side and fails (→ StatusFailed)
	// when it cannot, so a Running agent with a Session ref means the credential flowed.
	running := mustGet(t, manager, agent.ID)
	if running.Session == "" {
		t.Fatalf("Running agent has no SessionRef — the credential did not thread through Open")
	}

	// The record carries the loggable ref's downstream, never the value. Drive a full
	// stop so the credential has flowed through Open and the record is finalized.
	if err := manager.Stop(context.Background(), agent.ID, "operator"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	mustReconcile(t, harness)

	assertNoSecretInRecord(t, manager, SeededCanary)
}

// caseObservabilityCompleteness asserts every reconcile transition emits exactly one
// ObsTransition and the spawn emits ObsSpawnAdmitted.
func caseObservabilityCompleteness(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	agent := mustSpawn(t, manager)
	if harness.Telemetry.CountKind(orchestrator.ObsSpawnAdmitted) != 1 {
		t.Fatalf("ObsSpawnAdmitted emitted %d times, want 1", harness.Telemetry.CountKind(orchestrator.ObsSpawnAdmitted))
	}
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})

	// Pending → Provisioning, then Provisioning → Running: two transitions, two ObsTransition.
	mustReconcile(t, harness)
	mustReconcile(t, harness)
	assertStatus(t, manager, agent.ID, orchestrator.StatusRunning)
	if got := harness.Telemetry.CountKind(orchestrator.ObsTransition); got != 2 {
		t.Fatalf("ObsTransition emitted %d times, want 2 (provision + open)", got)
	}
}

// caseTenancyIsolation asserts List with a Tenant filter never returns another project's
// agents, and admission counts are per-tenancy.
func caseTenancyIsolation(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx := context.Background()
	tenantA := orchestrator.Tenancy{OrganizationID: "org-A", ProjectID: "proj-A"}
	tenantB := orchestrator.Tenancy{OrganizationID: "org-B", ProjectID: "proj-B"}

	for range 2 {
		if _, err := manager.Spawn(ctx, requestForTenant(tenantA)); err != nil {
			t.Fatalf("Spawn tenant A: %v", err)
		}
	}
	if _, err := manager.Spawn(ctx, requestForTenant(tenantB)); err != nil {
		t.Fatalf("Spawn tenant B (separate ceiling): %v", err)
	}

	pageA, err := manager.List(ctx, orchestrator.Filter{Tenant: tenantA})
	if err != nil {
		t.Fatalf("List tenant A: %v", err)
	}
	if len(pageA.Agents) != 2 {
		t.Fatalf("List tenant A returned %d, want 2 (no cross-tenant bleed)", len(pageA.Agents))
	}
	for i := range pageA.Agents {
		if pageA.Agents[i].Tenant != tenantA {
			t.Fatalf("List tenant A returned a %v agent (cross-tenant leak)", pageA.Agents[i].Tenant)
		}
	}
}

// caseWatchSnapshotThenTail asserts a fresh Watch subscriber sees current state first then
// transitions, gap-free.
func caseWatchSnapshotThenTail(t *testing.T, manager orchestrator.Manager, harness Harness) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	agent := mustSpawn(t, manager)
	watcher, ok := manager.(orchestrator.Watcher)
	if !ok {
		t.Fatalf("Manager does not implement Watcher")
	}
	stream, err := watcher.Watch(ctx, orchestrator.Filter{})
	if err != nil {
		t.Fatalf("Watch: %v", err)
	}

	// Snapshot: the first emission is the agent's current state (Pending).
	event, ok := stream.Next(ctx)
	if !ok {
		t.Fatalf("Watch snapshot: stream ended early")
	}
	if event.AgentID != agent.ID || event.To != orchestrator.StatusPending {
		t.Fatalf("Watch snapshot = %+v, want Pending for %s", event, agent.ID)
	}

	// Tail: a reconcile transition (Pending → Provisioning) arrives next.
	harness.Probe.SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	mustReconcile(t, harness)
	next, ok := stream.Next(ctx)
	if !ok {
		t.Fatalf("Watch tail: stream ended before the transition")
	}
	if next.To != orchestrator.StatusProvisioning {
		t.Fatalf("Watch tail = %+v, want a transition to Provisioning", next)
	}
}
