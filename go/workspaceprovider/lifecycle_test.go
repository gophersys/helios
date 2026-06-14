//go:build lifecycle

package workspaceprovider_test

import (
	"bytes"
	"context"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// TestLifecycle_WorkspaceDoubleTeardownIdempotentNoOrphans is the full-object-lifecycle
// conformance (ADR-0020 dimension (c)) for the workspaceprovider closeable handle: the live
// Workspace returned by Provider.Provision, whose external resource is reaped by
// Provider.Teardown (the Workspace itself has no Close — Teardown is the reap verb, 02 §1). It
// drives testing.AssertLifecycle over a probe whose owned resource is the provisioned workspace:
// construct -> use (Exec + Files round-trip) -> first Teardown -> SECOND Teardown is a no-op ->
// CountOwned()==0 (the workspace was reaped, no orphan container/cluster). The orphan-GOROUTINE
// half (no watcher/run goroutine left attached) is asserted by the surrounding goleak.VerifyNone.
// Tagged `//go:build lifecycle` so the double-teardown/reap drive stays out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_WorkspaceDoubleTeardownIdempotentNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newWorkspaceProbe)
}

// workspaceProbe is the testing.LifecycleProbe binding for a workspaceprovider Workspace. Its
// "owned resource" is the provisioned workspace itself, counted by listing the ownership domain:
// after the double-Teardown, CountOwned must read zero — the workspace was reaped exactly once and
// the orphan budget is clean.
type workspaceProbe struct {
	prov   *workspaceprovider.Provisioner
	ws     workspaceprovider.Workspace
	labels map[string]string
	name   string
}

// newWorkspaceProbe constructs a fresh live Workspace over a real Provisioner + the in-memory
// fake adapter, provisioned and Ready. It is the testing.LifecycleFactory the driver invokes once
// per run.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newWorkspaceProbe(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	prov := workspaceprovidertest.FakeProvider(nil).(*workspaceprovider.Provisioner) //nolint:errcheck,forcetypeassert // FakeProvider returns the concrete *Provisioner the lifecycle probe drives.
	labels := map[string]string{
		workspaceprovider.LabelOrganization: "org-lifecycle",
		workspaceprovider.LabelProject:      "proj-lifecycle",
	}
	const name = "ws-lifecycle"
	ws, err := prov.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:   name,
		Image:  "busybox:1.36",
		Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Labels: labels,
	})
	if err != nil {
		return nil, nil, err
	}
	probe := &workspaceProbe{prov: prov, ws: ws, labels: labels, name: name}
	// Teardown is a final best-effort reap so a failed assertion never leaks the workspace.
	teardown := func() { _ = probe.prov.Teardown(context.Background(), probe.ws.Handle()) } //nolint:errcheck // best-effort final reap; the assertions own the real Teardown checks.
	return probe, teardown, nil
}

// Use exercises the live workspace once: an Exec to completion and a Files Put/Get round-trip, so
// the full workload plane runs before the reap.
func (p *workspaceProbe) Use(ctx context.Context) error {
	if _, err := p.ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"echo", "alive"}}); err != nil {
		return err
	}
	want := []byte("artifact\n")
	if err := p.ws.Files().Put(ctx, "/workspace/out.txt", bytes.NewReader(want), 0o644); err != nil {
		return err
	}
	rc, err := p.ws.Files().Get(ctx, "/workspace/out.txt")
	if err != nil {
		return err
	}
	_ = rc.Close() //nolint:errcheck // closing a fully-modeled in-memory stream has no actionable error.
	return nil
}

// Close reaps the workspace via Provider.Teardown. The contract guarantees Teardown is idempotent,
// so the driver's SECOND call must also return nil (the double-close invariant).
func (p *workspaceProbe) Close(ctx context.Context) error {
	return p.prov.Teardown(ctx, p.ws.Handle())
}

// CountOwned reports how many workspaces with this probe's Name still exist in its tenancy. After
// Teardown it must be zero: the workspace was reaped exactly once with no orphan.
func (p *workspaceProbe) CountOwned(ctx context.Context) (int, error) {
	descs, err := p.prov.List(ctx, workspaceprovider.Selector{Labels: p.labels})
	if err != nil {
		return 0, err
	}
	owned := 0
	for i := range descs {
		if descs[i].Name == p.name {
			owned++
		}
	}
	return owned, nil
}

// ── *testing.T adapters for the testing.Harness / testing.Report ports ────────────────.

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup and
// Context are exercised by AssertLifecycle; the deterministic-source accessors are part of the
// frozen 5-method port and are never called on this path.
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
