//go:build load

package workspaceprovider_test

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"go.uber.org/goleak"
	"golang.org/x/sync/errgroup"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500 in-process;
// ADR-0020 dimension (e)).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentProvisionTeardownRaceClean fans out N independent Provision→use→Teardown
// cycles through ONE Provisioner concurrently and asserts every workspace is reaped (CountOwned
// post-run == 0) with no race. It stresses the Provisioner's concurrent-use guarantee (the
// reconcile loop + many request handlers provision in parallel) under -race, and goleak asserts
// the goroutine high-water returns to baseline afterward (no Run/watcher goroutine left attached) —
// ADR-0020 dimension (e).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make the high-water assertion flaky, so the fan-out load runs serially.
func TestLoad_ConcurrentProvisionTeardownRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	prov := workspaceprovidertest.FakeProvider(nil).(*workspaceprovider.Provisioner) //nolint:errcheck,forcetypeassert // FakeProvider returns the concrete *Provisioner this load drives.
	labels := map[string]string{
		workspaceprovider.LabelOrganization: "org-load",
		workspaceprovider.LabelProject:      "proj-load",
	}

	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()

	group, groupCtx := errgroup.WithContext(ctx)
	for i := range n {
		i := i
		group.Go(func() error {
			spec := workspaceprovider.WorkspaceSpec{
				Name:   fmt.Sprintf("ws-load-%d", i),
				Image:  "busybox:1.36",
				Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
				Labels: labels,
			}
			ws, err := prov.Provision(groupCtx, spec)
			if err != nil {
				return errors.Wrap(errors.KindInternal, "provision under load", err)
			}
			// Exercise the workload plane so the per-workspace state machine runs under contention.
			if _, eerr := ws.Exec(groupCtx, workspaceprovider.ExecSpec{Command: []string{"echo", "go"}}); eerr != nil {
				_ = prov.Teardown(context.WithoutCancel(groupCtx), ws.Handle()) //nolint:errcheck // best-effort reap on the error path.
				return errors.Wrap(errors.KindInternal, "exec under load", eerr)
			}
			run, rerr := ws.Run(groupCtx, workspaceprovider.RunSpec{Command: []string{"echo", "workload"}})
			if rerr != nil {
				_ = prov.Teardown(context.WithoutCancel(groupCtx), ws.Handle()) //nolint:errcheck // best-effort reap on the error path.
				return errors.Wrap(errors.KindInternal, "run under load", rerr)
			}
			drainLoadRun(groupCtx, run)
			return prov.Teardown(groupCtx, ws.Handle())
		})
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a worker faulted under fan-out: %v", err)
	}

	// Every workspace must be reaped — the ownership domain is empty.
	descs, err := prov.List(context.Background(), workspaceprovider.Selector{Labels: labels})
	if err != nil {
		t.Fatalf("List post-fan-out: %v", err)
	}
	if len(descs) != 0 {
		t.Fatalf("fan-out left %d orphaned workspace(s); want 0 (all reaped)", len(descs))
	}
}

// TestLoad_ConcurrentIdempotentRespecConverges fires N concurrent Provisions of the SAME spec
// through one Provisioner and asserts they all converge on the SAME Handle (idempotent on Name
// within a tenancy) with no race and exactly ONE workspace surviving. This stresses the
// library-owned idempotency path (the List + fingerprint compare + re-dial) under contention — the
// exact race a reconcile loop with multiple replicas hits adopting one workspace.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine assertion.
func TestLoad_ConcurrentIdempotentRespecConverges(t *testing.T) {
	defer goleak.VerifyNone(t)

	// Bound the width so the single-name contention stays meaningful without exploding the budget;
	// EDEN_LOAD_N still scales it in real runs.
	n := loadN() / 5
	if n < 20 {
		n = 20
	}
	prov := workspaceprovidertest.FakeProvider(nil).(*workspaceprovider.Provisioner) //nolint:errcheck,forcetypeassert // FakeProvider returns the concrete *Provisioner this load drives.
	labels := map[string]string{
		workspaceprovider.LabelOrganization: "org-idem",
		workspaceprovider.LabelProject:      "proj-idem",
	}
	spec := workspaceprovider.WorkspaceSpec{
		Name:   "ws-idem-load",
		Image:  "busybox:1.36",
		Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Labels: labels,
	}

	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()

	var mu sync.Mutex
	handles := map[string]struct{}{}
	group, groupCtx := errgroup.WithContext(ctx)
	for range n {
		group.Go(func() error {
			ws, err := prov.Provision(groupCtx, spec)
			if err != nil {
				return errors.Wrap(errors.KindInternal, "idempotent provision under load", err)
			}
			mu.Lock()
			handles[ws.Handle().String()] = struct{}{}
			mu.Unlock()
			return nil
		})
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a concurrent idempotent Provision faulted: %v", err)
	}
	t.Cleanup(func() {
		for h := range handles {
			parsed, perr := workspaceprovider.ParseHandle(h)
			if perr == nil {
				_ = prov.Teardown(context.Background(), parsed) //nolint:errcheck // best-effort reap on cleanup.
			}
		}
	})

	// All N concurrent Provisions of the same spec converged on exactly ONE distinct Handle.
	if len(handles) != 1 {
		t.Fatalf("concurrent idempotent Provision produced %d distinct handles; want exactly 1 (idempotent on Name)", len(handles))
	}
	descs, err := prov.List(context.Background(), workspaceprovider.Selector{Labels: labels})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(descs) != 1 {
		t.Fatalf("idempotent fan-out created %d workspaces; want exactly 1", len(descs))
	}
}

// drainLoadRun ranges a Run.Status to its terminal transition, releasing the workspace's
// one-primary-workload gate (so Teardown sees a clean handle).
func drainLoadRun(ctx context.Context, run workspaceprovider.Run) {
	for {
		status, ok := run.Status(ctx)
		if !ok || status.Phase.IsTerminal() {
			return
		}
	}
}
