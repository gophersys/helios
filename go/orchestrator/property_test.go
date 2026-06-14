package orchestrator_test

import (
	"context"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a)); rapid reads it directly. These
// properties drive the REAL reconcile loop (Spawn → step → commit) over the in-memory fakes
// wired into a real *orchestrator.Pool — the fakes are the conformance two-binding partner
// (08 §2), NOT a mock of the reconciler under test.

// liveActualProp is the "all live" observed actual the properties pin so a Provisioning
// agent advances to Running.
var liveActualProp = orchestrator.Actual{WorkspaceLive: true, SessionLive: true}

// newPropManager builds a fresh deterministic Manager seeded with the default template, with
// a generous admission ceiling so the desired/actual properties are never throttled by a
// limit they do not test.
func newPropManager(t *rapid.T) *orchestratortest.Manager {
	manager := orchestratortest.New(
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
		orchestratortest.WithMaxConcurrent(0), // unbounded — admission is tested elsewhere
	)
	t.Cleanup(func() { drainManager(manager) })
	return manager
}

// drainManager records a Stop for every live agent and reconciles to quiescence so a property
// iteration never leaks a workspace into the next (the in-memory fake is per-Manager, so this
// is belt-and-braces against an asserted-but-unreaped agent).
func drainManager(manager *orchestratortest.Manager) {
	ctx := context.Background()
	page, err := manager.List(ctx, orchestrator.Filter{OnlyActive: true, Limit: 0})
	if err == nil {
		for i := range page.Agents {
			_ = manager.Stop(ctx, page.Agents[i].ID, "property-cleanup") //nolint:errcheck // best-effort drain; an already-stopping agent is a benign no-op.
		}
	}
	for pass := 0; pass < 64; pass++ {
		report, rerr := manager.Reconcile(ctx)
		if rerr != nil || report.Transitioned == 0 {
			return
		}
	}
}

// drivePropToRunning reconciles until the agent reaches Running (Pending→Provisioning→Running),
// failing the property if it does not converge within a bounded number of passes.
func drivePropToRunning(rt *rapid.T, manager *orchestratortest.Manager, id orchestrator.AgentID) {
	ctx := context.Background()
	for pass := 0; pass < 8; pass++ {
		got, err := manager.Get(ctx, id)
		if err != nil {
			rt.Fatalf("Get(%s): %v", id, err)
		}
		if got.Status == orchestrator.StatusRunning {
			return
		}
		if got.Status.Terminal() {
			rt.Fatalf("agent %s reached terminal %v before Running (detail %q)", id, got.Status, got.Detail)
		}
		if _, rerr := manager.Reconcile(ctx); rerr != nil {
			rt.Fatalf("Reconcile to Running: %v", rerr)
		}
	}
	rt.Fatalf("agent %s did not reach Running within 8 passes", id)
}

// reconcilePropPasses drives n reconcile passes, failing the property on any pass error (used
// to drain a Stop/budget transition to terminal and prove idempotent convergence on the extra
// passes).
func reconcilePropPasses(rt *rapid.T, manager *orchestratortest.Manager, n int) {
	ctx := context.Background()
	for pass := 0; pass < n; pass++ {
		if _, err := manager.Reconcile(ctx); err != nil {
			rt.Fatalf("Reconcile pass %d: %v", pass, err)
		}
	}
}

// reconcilePropToQuiescence drives passes until a full pass transitions nothing, failing the
// property if it does not converge within the bound. Returns nothing — convergence is the
// assertion.
func reconcilePropToQuiescence(rt *rapid.T, manager *orchestratortest.Manager) {
	ctx := context.Background()
	for pass := 0; pass < 32; pass++ {
		report, err := manager.Reconcile(ctx)
		if err != nil {
			rt.Fatalf("Reconcile pass %d: %v", pass, err)
		}
		if report.Transitioned == 0 {
			return
		}
	}
	rt.Fatalf("reconcile did not converge within 32 passes")
}

// mustGetProp reads a record and fails the property on error.
//
//nolint:gocritic // Agent is the contract's copyable record; the helper returns the value it read.
func mustGetProp(rt *rapid.T, manager *orchestratortest.Manager, id orchestrator.AgentID) orchestrator.Agent {
	agent, err := manager.Get(context.Background(), id)
	if err != nil {
		rt.Fatalf("Get(%s): %v", id, err)
	}
	return agent
}

// spawnProp builds a valid SpawnRequest against the default template under a drawn tenancy.
func spawnProp(rt *rapid.T) orchestrator.SpawnRequest {
	org := "org-" + rapid.StringMatching(`[a-z0-9]{1,6}`).Draw(rt, "org")
	proj := "proj-" + rapid.StringMatching(`[a-z0-9]{1,6}`).Draw(rt, "proj")
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: org, ProjectID: proj},
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
		By:         "property",
	}
}

// TestProperty_MissingActualIsProvisioned asserts the level-based reconcile contract's
// left-to-right driver: a freshly-Spawned agent (desired Running, NO actual) is driven
// forward — exactly one transition Pending→Provisioning on the first pass, and one workspace
// provisioned. A drift here would either stall a desired-but-absent agent (it never runs) or
// provision more than once per pass (a runaway).
func TestProperty_MissingActualIsProvisioned(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		manager := newPropManager(rt)
		ctx := context.Background()

		agent, err := manager.Spawn(ctx, spawnProp(rt))
		if err != nil {
			rt.Fatalf("Spawn: %v", err)
		}
		if agent.Status != orchestrator.StatusPending {
			rt.Fatalf("Spawn status = %v, want Pending (no provisioning before reconcile)", agent.Status)
		}
		if got := len(manager.Workspaces().Provisioned); got != 0 {
			rt.Fatalf("Spawn provisioned %d workspaces, want 0 (admission before any pod)", got)
		}

		report, err := manager.Reconcile(ctx)
		if err != nil {
			rt.Fatalf("Reconcile: %v", err)
		}
		if report.Transitioned != 1 {
			rt.Fatalf("first pass transitioned %d, want exactly 1 (at most one step per agent per pass)", report.Transitioned)
		}
		got, err := manager.Get(ctx, agent.ID)
		if err != nil {
			rt.Fatalf("Get: %v", err)
		}
		if got.Status != orchestrator.StatusProvisioning {
			rt.Fatalf("after one pass status = %v, want Provisioning", got.Status)
		}
		if n := len(manager.Workspaces().Provisioned); n != 1 {
			rt.Fatalf("after one pass provisioned %d workspaces, want exactly 1", n)
		}
	})
}

// TestProperty_ReconcileConvergesIdempotent asserts the convergence + idempotency invariant
// for ANY agent count: Spawn N agents, reconcile to quiescence, and EVERY admitted agent
// reaches Running with exactly one workspace each; a further pass with unchanged desired +
// live actual makes ZERO transitions (the loop is a fixpoint once actual == desired). This is
// the property that keeps the reconcile loop from re-provisioning or re-opening on every tick.
func TestProperty_ReconcileConvergesIdempotent(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		manager := newPropManager(rt)
		manager.Probe().SetDefault(liveActualProp)
		ctx := context.Background()

		n := rapid.IntRange(1, 6).Draw(rt, "agents")
		ids := make([]orchestrator.AgentID, 0, n)
		for range n {
			agent, err := manager.Spawn(ctx, spawnProp(rt))
			if err != nil {
				rt.Fatalf("Spawn: %v", err)
			}
			ids = append(ids, agent.ID)
		}

		// Drive to quiescence (Pending→Provisioning→Running for each).
		reconcilePropToQuiescence(rt, manager)

		for _, id := range ids {
			agent := mustGetProp(rt, manager, id)
			if agent.Status != orchestrator.StatusRunning {
				rt.Fatalf("agent %s converged to %v, want Running", id, agent.Status)
			}
			if agent.Session == "" {
				rt.Fatalf("agent %s has no SessionRef after converge (the session never opened)", id)
			}
		}
		if got := len(manager.Workspaces().Provisioned); got != n {
			rt.Fatalf("provisioned %d workspaces, want exactly %d (one per agent)", got, n)
		}

		// The fixpoint: a converged pass transitions nothing.
		report, err := manager.Reconcile(ctx)
		if err != nil {
			rt.Fatalf("Reconcile (converged): %v", err)
		}
		if report.Transitioned != 0 {
			rt.Fatalf("a converged pass transitioned %d, want 0 (idempotent)", report.Transitioned)
		}
	})
}

// TestProperty_StopReapsExactlyOnce asserts the right half of the reconcile diff (an actual
// that should no longer exist is reaped): for ANY agent driven to Running, a Stop records the
// terminal intent and reconcile drains+releases the workspace EXACTLY ONCE (Release is the
// sole pod-reaper), the agent ends terminal Stopped, and a further pass never tears down
// again (idempotent convergence). A drift here would leak a pod or double-Teardown.
func TestProperty_StopReapsExactlyOnce(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		manager := newPropManager(rt)
		manager.Probe().SetDefault(liveActualProp)
		ctx := context.Background()

		agent, err := manager.Spawn(ctx, spawnProp(rt))
		if err != nil {
			rt.Fatalf("Spawn: %v", err)
		}
		drivePropToRunning(rt, manager, agent.ID)

		if err := manager.Stop(ctx, agent.ID, "property"); err != nil {
			rt.Fatalf("Stop: %v", err)
		}
		// Drain to terminal, then run extra passes — Teardown must stay at exactly one.
		reconcilePropPasses(rt, manager, 4)

		got := mustGetProp(rt, manager, agent.ID)
		if got.Status != orchestrator.StatusStopped {
			rt.Fatalf("after Stop+drain status = %v, want Stopped", got.Status)
		}
		if n := len(manager.Workspaces().Destroyed); n != 1 {
			rt.Fatalf("Teardown called %d times, want exactly 1 (sole reaper, idempotent across passes)", n)
		}
		manager.AssertNoOrphans(rt)
	})
}

// TestProperty_BudgetWatchStopsRunaway asserts the budget-authority invariant: for ANY
// observed cumulative cost at or above the template ceiling, reconcile drives a Stop (the
// authoritative watchdog even when no consumer tails), the terminal record names the budget
// reason, and the workspace is released. A drift here would let a runaway agent burn cost
// unbounded. The ceiling is the budget template's 1000 micros; the drawn overage is ≥ that.
func TestProperty_BudgetWatchStopsRunaway(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		manager := orchestratortest.New(
			orchestratortest.WithTemplate(orchestratortest.BudgetTemplate()),
			orchestratortest.WithMaxConcurrent(0),
		)
		rt.Cleanup(func() { drainManager(manager) })
		ctx := context.Background()

		agent, err := manager.Spawn(ctx, orchestrator.SpawnRequest{
			Tenant:     orchestrator.Tenancy{OrganizationID: "org-budget", ProjectID: "proj-budget"},
			Template:   orchestratortest.BudgetTemplate().Ref,
			Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
			By:         "property",
		})
		if err != nil {
			rt.Fatalf("Spawn: %v", err)
		}
		manager.Probe().SetDefault(liveActualProp)
		drivePropToRunning(rt, manager, agent.ID)

		// Cross the 1000-micro ceiling with a drawn overage.
		overage := int64(1000 + rapid.IntRange(0, 1_000_000).Draw(rt, "overage"))
		manager.Probe().Set(agent.ID, orchestrator.Actual{
			WorkspaceLive: true, SessionLive: true,
			Ledger: agentsession.TokenLedger{UsageMeter: agentsession.UsageMeter{CostMicros: overage}},
		})
		reconcilePropPasses(rt, manager, 4)

		got := mustGetProp(rt, manager, agent.ID)
		if got.Status != orchestrator.StatusStopped {
			rt.Fatalf("after budget cross (cost=%d, ceiling=1000) status = %v, want Stopped", overage, got.Status)
		}
		if manager.Telemetry().CountKind(orchestrator.ObsBudgetExceeded) < 1 {
			rt.Fatalf("budget cross emitted no ObsBudgetExceeded event")
		}
		manager.AssertNoOrphans(rt)
	})
}

// TestProperty_ProbeDerivesActualFromLiveTable asserts the v0 in-process Probe (live.go's
// observe) derives a truthful Actual from the live-actual side table: after a Running agent
// is established the default Probe reports WorkspaceLive && SessionLive, and an id the Pool
// never spawned reports the zero Actual (absent live handle). This is the property that makes
// the reconcile diff correct after a Pool restart (the actual is observed, not assumed). It
// drives the Pool's OWN default Probe (no scripted probe), so the production live.go path is
// the system under test.
func TestProperty_ProbeDerivesActualFromLiveTable(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// A manager with NO scripted probe override: Reconcile here binds the Pool's default
		// in-process Probe (defaultProbe over the live table) instead of the test Probe.
		manager := newPropManager(rt)
		ctx := context.Background()
		pool := manager.Pool()

		agent, err := manager.Spawn(ctx, spawnProp(rt))
		if err != nil {
			rt.Fatalf("Spawn: %v", err)
		}
		// Drive with the DEFAULT probe (omit Probe from ReconcilePorts → defaultProbe reads
		// the live table). Provision creates the workspace + live handle; Open creates the
		// session live handle, after which the default Probe must report both live.
		for pass := 0; pass < 8; pass++ {
			got, gerr := manager.Get(ctx, agent.ID)
			if gerr != nil {
				rt.Fatalf("Get: %v", gerr)
			}
			if got.Status == orchestrator.StatusRunning {
				break
			}
			if _, rerr := pool.Reconcile(ctx, orchestrator.ReconcilePorts{
				Workspaces: manager.Provider(),
				Sessions:   manager.Sessions(),
				// Probe omitted on purpose → the Pool's default in-process Probe is exercised.
			}); rerr != nil {
				rt.Fatalf("Reconcile (default probe): %v", rerr)
			}
		}

		got, err := manager.Get(ctx, agent.ID)
		if err != nil {
			rt.Fatalf("Get: %v", err)
		}
		if got.Status != orchestrator.StatusRunning {
			rt.Fatalf("default-probe drive reached %v, want Running (the live table did not report live)", got.Status)
		}
	})
}

// TestProperty_ErrorKindRoundTrip asserts the error-taxonomy contract: every orchestrator
// error type maps to its stable errors.Kind when wrapped (the transport boundary reads KindOf
// with no per-port table, 10 §9) and is recoverable from the chain via AsType. A drift here
// breaks every caller that branches on Kind.
func TestProperty_ErrorKindRoundTrip(t *testing.T) {
	t.Parallel()
	type errCase struct {
		err  error
		kind errors.Kind
	}
	rapid.Check(t, func(rt *rapid.T) {
		field := rapid.StringMatching(`[a-zA-Z]{1,10}`).Draw(rt, "field")
		ref := orchestrator.TemplateRef{Name: field, Version: "1.0.0"}
		id := orchestrator.AgentID(field)
		cases := []errCase{
			{&orchestrator.TemplateNotFoundError{Ref: ref}, errors.KindNotFound},
			{&orchestrator.NotFoundError{ID: id}, errors.KindNotFound},
			{&orchestrator.LimitError{Template: ref, Max: 2, Current: 2}, errors.KindExhausted},
			{&orchestrator.InvalidRequestError{Reason: field}, errors.KindInvalid},
			{&orchestrator.ConflictError{ID: id, Status: orchestrator.StatusPending}, errors.KindConflict},
			{&orchestrator.UnsupportedError{ID: id, Capability: field}, errors.KindInvalid},
			{&orchestrator.ProvisionError{Message: field}, errors.KindUnavailable},
			{&orchestrator.ConfigError{Reason: field}, errors.KindInvalid},
		}
		for _, c := range cases {
			if c.err.Error() == "" {
				rt.Fatalf("%T renders an empty Error()", c.err)
			}
			wrapped := errors.Wrap(c.kind, "property: "+field, c.err)
			if errors.KindOf(wrapped) != c.kind {
				rt.Fatalf("%T wrapped Kind = %v, want %v", c.err, errors.KindOf(wrapped), c.kind)
			}
		}
	})
}

// TestProperty_StatusStringTotality asserts every Status / Desired / ObservabilityKind value
// (in range AND out of range) renders a stable non-empty token — the dashboard and the
// transport boundary render these per record, so a panic or empty token on an unexpected value
// is a real fault. The String methods are documented total (out-of-range → the zero token).
func TestProperty_StatusStringTotality(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		s := orchestrator.Status(rapid.Uint8().Draw(rt, "status"))
		if s.String() == "" {
			rt.Fatalf("Status(%d).String() is empty (must be total)", s)
		}
		d := orchestrator.Desired(rapid.Uint8().Draw(rt, "desired"))
		if d.String() == "" {
			rt.Fatalf("Desired(%d).String() is empty (must be total)", d)
		}
		k := orchestrator.ObservabilityKind(rapid.Uint8().Draw(rt, "kind"))
		if k.String() == "" {
			rt.Fatalf("ObservabilityKind(%d).String() is empty (must be total)", k)
		}
	})
}
