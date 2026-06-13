//go:build integration

// Package orchestratortest_test's integration arm drives the reconcile loop end-to-end
// under the RACE DETECTOR against the REAL agentsession library (its agentsessiontest
// scripted Adapter wired into a real agentsession.Pool) and the REAL workspaceprovider
// port (its workspaceprovidertest frozen-seam Adapter wired into a real Provisioner),
// stressing concurrent Spawn/Stop/Resume of MANY agents converging, with every
// workspace/session reaped on t.Cleanup (no leak). It is gated behind the `integration`
// build tag so the default `go test` (and the pre-commit hook) stays fast; run it with
//
//	go test -tags integration ./... -race
//
// Everything is in-process (no real subprocess, no pod, no network): the proof here is the
// CONCURRENCY/CONVERGENCE/ADMISSION/RELEASE invariants of the orchestration spine, not a
// real cluster (the real-cluster arm runs against k3d in release pipelines once the
// workspaceprovider real adapters land — ADR-0016, that contract's harnesses).
package orchestratortest_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
)

// liveActual is the "all live" probe reading every observed agent reports.
var liveActual = orchestrator.Actual{WorkspaceLive: true, SessionLive: true}

// newScaleManager builds a Manager whose admission ceiling is generous enough for the
// fan-out scale tests, seeded with the canonical template, every probe default live.
func newScaleManager(maxConcurrent int) *orchestratortest.Manager {
	manager := orchestratortest.New(
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
		orchestratortest.WithMaxConcurrent(maxConcurrent),
	)
	manager.Probe().SetDefault(liveActual)
	return manager
}

// scaleRequest builds a SpawnRequest for the i-th agent under the shared tenancy.
func scaleRequest() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-scale", ProjectID: "proj-scale"},
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secretsRef(),
		By:         "integration",
		RunID:      "run-scale",
	}
}

// reconcileToQuiescence drives reconcile passes until a full pass makes no transition
// (convergence), bounded so a stuck loop fails fast rather than spins forever.
func reconcileToQuiescence(t *testing.T, manager *orchestratortest.Manager) {
	t.Helper()
	for pass := 0; pass < 64; pass++ {
		report, err := manager.Reconcile(context.Background())
		if err != nil {
			t.Fatalf("Reconcile pass %d: %v", pass, err)
		}
		if report.Transitioned == 0 {
			return
		}
	}
	t.Fatalf("reconcile did not converge within 64 passes")
}

// TestIntegration_ManyConcurrentSpawnConvergesToRunning spawns HUNDREDS of agents
// concurrently, then reconciles to quiescence, and asserts every admitted agent converged
// to Running with exactly one workspace provisioned each — the bounded concurrent fan that
// converges (100s-of-agents scale is not pathological), race-checked.
func TestIntegration_ManyConcurrentSpawnConvergesToRunning(t *testing.T) {
	t.Parallel()
	const agents = 300
	manager := newScaleManager(agents)
	registerReaper(t, manager)

	spawnAllConcurrently(t, manager, agents)
	reconcileToQuiescence(t, manager)

	running := 0
	for _, agent := range listAll(t, manager) {
		if agent.Status == orchestrator.StatusRunning {
			running++
		}
	}
	if running != agents {
		t.Fatalf("converged %d agents to Running, want %d", running, agents)
	}
	if got := len(manager.Workspaces().Provisioned); got != agents {
		t.Fatalf("provisioned %d workspaces, want %d (one per agent)", got, agents)
	}
}

// TestIntegration_ConcurrentSpawnStopResumeRaceClean drives a churn of concurrent
// Spawn/Stop/Resume across many agents interleaved with reconcile passes, and asserts the
// loop stays race-clean and every workspace is released by the end (no leak). This is the
// concurrency invariant: the verbs (record mutations) race the loop (the side-effecting
// reconcile) safely.
func TestIntegration_ConcurrentSpawnStopResumeRaceClean(t *testing.T) {
	t.Parallel()
	const agents = 120
	manager := newScaleManager(agents)
	registerReaper(t, manager)

	ids := spawnAllConcurrently(t, manager, agents)
	reconcileToQuiescence(t, manager)

	// Churn the agents (Stop half, drop-and-Resume the other half) while a reconcile pump
	// races the verbs — all under the race detector.
	stop := reconcilePump(manager)
	churnAgents(t, manager, ids)
	time.Sleep(10 * time.Millisecond) // let the pump observe the dropped actuals (→ Suspended)
	resumeDropped(manager, ids)
	time.Sleep(10 * time.Millisecond) // let the pump re-attach the resumed agents

	// Stop everything and converge so no workspace leaks.
	stopAll(manager, ids)
	stop()
	reconcileToQuiescence(t, manager)

	// Every agent terminal, every workspace released — no orphan.
	for _, agent := range listAll(t, manager) {
		if !agent.Status.Terminal() {
			t.Fatalf("agent %s not terminal after full churn (status %v)", agent.ID, agent.Status)
		}
	}
	manager.AssertNoOrphans(t)
}

// TestIntegration_AdmissionRefusesOverCeilingUnderConcurrency asserts that under a
// concurrent burst of Spawns exceeding MaxConcurrent, EXACTLY the ceiling is admitted and
// every excess Spawn is refused with LimitError BEFORE any workspace is provisioned (the
// single admission authority holds under a race).
func TestIntegration_AdmissionRefusesOverCeilingUnderConcurrency(t *testing.T) {
	t.Parallel()
	const ceiling = 8
	const burst = 200
	manager := newScaleManager(ceiling)
	registerReaper(t, manager)

	var (
		admitted int
		refused  int
		mu       sync.Mutex
		wg       sync.WaitGroup
	)
	for i := range burst {
		wg.Add(1)
		go func(int) {
			defer wg.Done()
			_, err := manager.Spawn(context.Background(), scaleRequest())
			mu.Lock()
			defer mu.Unlock()
			if err == nil {
				admitted++
				return
			}
			if isLimitError(err) {
				refused++
				return
			}
			t.Errorf("unexpected Spawn error: %v", err)
		}(i)
	}
	wg.Wait()

	if admitted != ceiling {
		t.Fatalf("admitted %d, want exactly the ceiling %d (single admission authority under race)", admitted, ceiling)
	}
	if refused != burst-ceiling {
		t.Fatalf("refused %d, want %d", refused, burst-ceiling)
	}
	// The refused spawns provisioned NOTHING (admission is before any pod) — only the
	// admitted ceiling becomes workspaces once reconciled.
	reconcileToQuiescence(t, manager)
	if got := len(manager.Workspaces().Provisioned); got != ceiling {
		t.Fatalf("provisioned %d workspaces, want exactly the ceiling %d", got, ceiling)
	}
}
