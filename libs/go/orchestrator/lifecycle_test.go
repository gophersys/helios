//go:build lifecycle

package orchestrator_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
)

// TestLifecycle_PoolDoubleCloseIdempotentNoOrphans is the full-object-lifecycle conformance
// (ADR-0020 dimension (c)) for the orchestrator's one closeable handle: the *Pool returned by
// orchestrator.New. Its "owned resources" are the live agents it tracks — each a provisioned
// workspace + an open agentsession.Session riding the in-process side table. It drives
// testing.AssertLifecycle over a probe whose Use spawns an agent and drives it to Running,
// whose Close is Pool.Close (which records a Stopping intent for every non-terminal agent and
// drives the final reconcile pass that drains the session + RELEASES the workspace — the sole
// pod reaper), and whose CountOwned counts non-terminal agents. After the double-Close,
// CountOwned must read zero (every agent drained, no orphan workspace) AND the second Close is
// a no-op (Close is idempotent). The orphan-GOROUTINE half — the reconcile loop goroutine
// started by Start must be reaped by Close, no Watch ctx-reaper left attached — is asserted by
// the surrounding goleak.VerifyNone. Tagged `//go:build lifecycle` so the heavy drive stays
// out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_PoolDoubleCloseIdempotentNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newPoolProbe)
}

// poolProbe is the testing.LifecycleProbe binding for an orchestrator.Pool. Its owned
// resources are the agents it tracks; CountOwned reads the store for non-terminal agents,
// which Pool.Close must drive to zero.
type poolProbe struct {
	manager *orchestratortest.Manager
	ids     []orchestrator.AgentID
}

// newPoolProbe constructs a fresh live Pool over the in-memory fakes (a real orchestrator.New
// wired to the scripted agentsession + workspaceprovidertest seams), with Start NOT yet run —
// Use starts the loop AND spawns. It is the testing.LifecycleFactory the driver invokes once.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newPoolProbe(_ context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	manager := orchestratortest.New(
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
		orchestratortest.WithMaxConcurrent(0),
	)
	manager.Probe().SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	probe := &poolProbe{manager: manager}
	// Teardown is a final best-effort Close so a failed assertion never leaks the Pool's loop
	// goroutine or a provisioned workspace.
	teardown := func() { _ = probe.manager.Pool().Close(context.Background()) } //nolint:errcheck // best-effort final reap; the assertions own the real Close checks.
	return probe, teardown, nil
}

// Use exercises the live Pool once: start the reconcile loop goroutine (so the orphan-goroutine
// half has something to reap), spawn a handful of agents, and drive each to Running by hand so
// every agent owns a live workspace + session before the reap. Driving by hand (rather than
// waiting on the loop tick) keeps the lifecycle drive deterministic.
func (p *poolProbe) Use(ctx context.Context) error {
	if err := p.manager.Pool().Start(ctx); err != nil {
		return err
	}
	for range 3 {
		agent, err := p.manager.Spawn(ctx, lifecycleRequest())
		if err != nil {
			return err
		}
		p.ids = append(p.ids, agent.ID)
	}
	// Drive each Pending agent to Running (Pending→Provisioning→Running).
	for pass := 0; pass < 6; pass++ {
		running := 0
		for _, id := range p.ids {
			agent, err := p.manager.Get(ctx, id)
			if err != nil {
				return err
			}
			if agent.Status == orchestrator.StatusRunning {
				running++
			}
		}
		if running == len(p.ids) {
			return nil
		}
		if _, err := p.manager.Reconcile(ctx); err != nil {
			return err
		}
	}
	return nil
}

// Close reaps the Pool via Pool.Close, which records a Stopping intent for every non-terminal
// agent and drives the final pass that drains+releases each. The contract guarantees Close is
// idempotent, so the driver's SECOND call must also return nil (the double-close invariant).
func (p *poolProbe) Close(ctx context.Context) error {
	return p.manager.Pool().Close(ctx)
}

// CountOwned reports how many agents the Pool still owns live (non-terminal). After Close it
// must be zero: every agent was drained to Stopped and its workspace released — no orphan.
func (p *poolProbe) CountOwned(ctx context.Context) (int, error) {
	page, err := p.manager.List(ctx, orchestrator.Filter{OnlyActive: true, Limit: 0})
	if err != nil {
		return 0, err
	}
	return len(page.Agents), nil
}

// lifecycleRequest is the canonical SpawnRequest the lifecycle probe spawns (the seeded
// credential ref — the VALUE never rides it).
func lifecycleRequest() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-lifecycle", ProjectID: "proj-lifecycle"},
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
		By:         "lifecycle",
	}
}

// ── *testing.T adapters for the testing.Harness / testing.Report ports ────────────────.

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup and
// Context are exercised by AssertLifecycle; the deterministic-source accessors are part of the
// frozen 5-method port and are never called on this path. Cleanup delegates to
// *testing.T.Cleanup so the teardown runs (LIFO) at test end — keeping the goleak check at the
// top of the test honest even if an assertion fails mid-run.
type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract §2: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract §2: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
