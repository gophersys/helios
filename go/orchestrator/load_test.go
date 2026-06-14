//go:build load

package orchestrator_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500
// in-process; ADR-0020 dimension (e)).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// loadActual is the "all live" probe reading every observed agent reports under load.
var loadActual = orchestrator.Actual{WorkspaceLive: true, SessionLive: true}

// newLoadManager builds a Manager whose admission ceiling is generous enough for the fan-out,
// seeded with the canonical template, every probe default live.
func newLoadManager(maxConcurrent int) *orchestratortest.Manager {
	manager := orchestratortest.New(
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
		orchestratortest.WithMaxConcurrent(maxConcurrent),
	)
	manager.Probe().SetDefault(loadActual)
	return manager
}

// loadRequest builds a SpawnRequest under the shared load tenancy (the seeded credential ref —
// the VALUE never rides it).
func loadRequest() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-load", ProjectID: "proj-load"},
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
		By:         "load",
		RunID:      "run-load",
	}
}

// reconcileToQuiescence drives reconcile passes until a full pass makes no transition
// (convergence), bounded so a stuck loop fails fast rather than spins forever.
func reconcileToQuiescence(t *testing.T, manager *orchestratortest.Manager) {
	t.Helper()
	for pass := 0; pass < 256; pass++ {
		report, err := manager.Reconcile(context.Background())
		if err != nil {
			t.Fatalf("Reconcile pass %d: %v", pass, err)
		}
		if report.Transitioned == 0 {
			return
		}
	}
	t.Fatalf("reconcile did not converge within 256 passes")
}

// loadPump runs Reconcile on a 1ms ticker until stop is called, on its own goroutine, so the
// verbs (Spawn/Stop) race the loop under the race detector. It returns a stop func that joins
// the goroutine.
func loadPump(manager *orchestratortest.Manager) (stop func()) {
	done := make(chan struct{})
	closed := make(chan struct{})
	go func() {
		defer close(closed)
		ticker := time.NewTicker(time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				_, _ = manager.Reconcile(context.Background()) //nolint:errcheck // a pass error is non-fatal; the pump retries on the next tick.
			}
		}
	}()
	return func() {
		close(done)
		<-closed
	}
}

// TestLoad_ConcurrentSpawnReconcileRaceClean fans out N concurrent Spawns against ONE Pool
// while a reconcile pump races the verbs, then converges and asserts every admitted agent
// reached Running with exactly one workspace provisioned each — race-clean, no deadlock within
// the context deadline. It stresses the single admission authority + the per-agent transition
// serialization under contention (the exact race the multi-handler control plane hits), and
// goleak asserts the goroutine high-water returns to baseline (the pump joined, every Watch
// reaped) — ADR-0020 dimension (e).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make the high-water assertion flaky, so the fan-out load runs serially.
func TestLoad_ConcurrentSpawnReconcileRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	manager := newLoadManager(n)

	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()

	// Race N concurrent Spawns against a live reconcile pump.
	stop := loadPump(manager)
	ids := make([]orchestrator.AgentID, n)
	var wg sync.WaitGroup
	for i := range n {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			agent, err := manager.Spawn(ctx, loadRequest())
			if err != nil {
				t.Errorf("Spawn[%d]: %v", idx, err)
				return
			}
			ids[idx] = agent.ID
		}(i)
	}
	wg.Wait()
	stop()

	// Converge deterministically, then assert every agent reached Running.
	reconcileToQuiescence(t, manager)
	running := 0
	for _, agent := range loadList(t, manager) {
		if agent.Status == orchestrator.StatusRunning {
			running++
		}
	}
	if running != n {
		t.Fatalf("converged %d agents to Running, want %d", running, n)
	}
	if got := len(manager.Workspaces().Provisioned); got != n {
		t.Fatalf("provisioned %d workspaces, want %d (one per agent)", got, n)
	}

	// Reap everything so no workspace leaks past the test.
	for _, id := range ids {
		if id == "" {
			continue
		}
		_ = manager.Stop(context.Background(), id, "load") //nolint:errcheck // idempotent Stop; an already-stopping agent is a benign no-op.
	}
	reconcileToQuiescence(t, manager)
	manager.AssertNoOrphans(t)
}

// TestLoad_ConcurrentStopDrainRaceClean drives a fan-out of Spawn→Running→concurrent-Stop
// interleaved with a reconcile pump, then converges and asserts EVERY agent ended terminal
// with its workspace released (no leak). This is the teardown-under-contention invariant: many
// Stops (record mutations) race the loop (the side-effecting drain+release) safely, and every
// pod is reaped exactly once.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine assertion.
func TestLoad_ConcurrentStopDrainRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	// Bound the width so the concurrent-stop contention stays meaningful without exploding the
	// budget; EDEN_LOAD_N still scales it in real runs.
	n := loadN() / 2
	if n < 20 {
		n = 20
	}
	manager := newLoadManager(n)

	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()

	// Spawn n agents and converge them to Running.
	ids := make([]orchestrator.AgentID, 0, n)
	for range n {
		agent, err := manager.Spawn(ctx, loadRequest())
		if err != nil {
			t.Fatalf("Spawn: %v", err)
		}
		ids = append(ids, agent.ID)
	}
	reconcileToQuiescence(t, manager)

	// Concurrently Stop every agent while a reconcile pump races the Stops.
	stop := loadPump(manager)
	var wg sync.WaitGroup
	for _, id := range ids {
		wg.Add(1)
		go func(id orchestrator.AgentID) {
			defer wg.Done()
			if err := manager.Stop(ctx, id, "load"); err != nil {
				t.Errorf("Stop(%s): %v", id, err)
			}
		}(id)
	}
	wg.Wait()
	stop()

	// Converge and assert every agent terminal, every workspace released.
	reconcileToQuiescence(t, manager)
	for _, agent := range loadList(t, manager) {
		if !agent.Status.Terminal() {
			t.Fatalf("agent %s not terminal after concurrent stop (status %v)", agent.ID, agent.Status)
		}
	}
	if got := len(manager.Workspaces().Destroyed); got != n {
		t.Fatalf("Teardown called %d times, want exactly %d (one release per agent)", got, n)
	}
	manager.AssertNoOrphans(t)
}

// loadList pages through every agent the manager tracks (List is paginated).
func loadList(t *testing.T, manager *orchestratortest.Manager) []orchestrator.Agent {
	t.Helper()
	var all []orchestrator.Agent
	cursor := ""
	for {
		page, err := manager.List(context.Background(), orchestrator.Filter{Cursor: cursor, Limit: 100})
		if err != nil {
			t.Fatalf("List: %v", err)
		}
		all = append(all, page.Agents...)
		if page.Next == "" || len(page.Agents) == 0 {
			return all
		}
		cursor = page.Next
	}
}
