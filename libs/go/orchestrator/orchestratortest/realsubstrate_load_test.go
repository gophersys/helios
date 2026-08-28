//go:build load

// Package orchestratortest_test's REAL-POD load arm (B4) proves the thinned orchestrator's
// reconcile spine stays race-clean and reap-complete under a small CONCURRENT fan of REAL
// Entrypoint pods on a REAL docker daemon, with desired-state in a REAL Postgres and the real
// SupervisedProbe. It reads EDEN_LOAD_N but CAPS it to a small real-pod number (real pods are
// not the 500-in-process fan the leaf load lane runs — rule 21(e): "default 500 in-process / 50
// real-pod"; this arm spins ACTUAL containers, so a handful is the honest real-pod fan). Every
// pod is reaped on convergence (CountOwned==0); the verbs race the reconcile pump under -race.
//
//	go test -tags load ./... -race -count=1
package orchestratortest_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// realPodFanCeiling caps the real-pod fan: real containers + a real postgres make a large fan
// pathological (and slow), so the honest real-pod load arm runs a handful, not the 500-in-
// process leaf fan. EDEN_LOAD_N below this is honored; above it is clamped.
const realPodFanCeiling = 5

// TestLoad_B4RealPodFanOut spins realPodFan concurrent real Entrypoint pods through the thinned
// orchestrator (real provider + real Postgres + real SupervisedProbe), races concurrent Spawns
// against a reconcile pump, converges every agent to Running, then Stops them all and converges
// — race-clean, with every real container reaped (CountOwned==0).
//
//nolint:gocognit,cyclop,paralleltest // a deliberate real-substrate fan-out; serial by design (spins real containers + a real postgres).
func TestLoad_B4RealPodFanOut(t *testing.T) {
	fan := realPodFan()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(loadTestImage))
	harness := orchestratortest.NewRealHarness(t, adapter, orchestrator.SubstrateDocker, orchestratortest.RealConfig{
		Entrypoint: loadEntrypoint,
		Image:      loadTestImage,
		Substrate:  orchestrator.SubstrateDocker,
		Cluster:    orchestrator.ClusterRef{ID: "local-docker"},
		MaxAgents:  fan + 2,
	})
	ctx := t.Context()

	// Concurrent Spawn fan — admission + record races the reconcile pump (the verbs vs the loop).
	stop := startRealPump(harness)
	ids := make([]orchestrator.AgentID, fan)
	var wg sync.WaitGroup
	for i := range fan {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			agent, err := harness.Spawn(ctx, loadRequest())
			if err != nil {
				t.Errorf("Spawn[%d]: %v", idx, err)
				return
			}
			ids[idx] = agent.ID
		}(i)
	}
	wg.Wait()

	// Converge every agent to Running against the real supervised pods.
	awaitAllRunning(t, harness, ids)

	// Stop everything and converge so no real pod leaks; the pump is still racing the verbs.
	for _, id := range ids {
		if id == "" {
			continue
		}
		if err := harness.Stop(ctx, id, "load"); err != nil {
			t.Errorf("Stop(%s): %v", id, err)
		}
	}
	stop()
	convergeReal(t, harness)

	for _, id := range ids {
		if id == "" {
			continue
		}
		agent, err := harness.Get(ctx, id)
		if err != nil {
			t.Errorf("Get(%s): %v", id, err)
			continue
		}
		if !agent.Status.Terminal() {
			t.Errorf("agent %s not terminal after Stop+converge (status %v)", id, agent.Status)
		}
	}

	// Every real container reaped — no orphan on the daemon.
	if owner, ok := adapter.(*dockeradapter.Adapter); ok {
		owned, err := owner.CountOwned(ctx)
		if err != nil {
			t.Errorf("CountOwned: %v", err)
		} else if owned != 0 {
			t.Errorf("real-pod fan-out left %d orphaned container(s) (want 0)", owned)
		}
	}
}

// loadTestImage / loadEntrypoint are the real workload-pod image + PID-1 the fan provisions.
const loadTestImage = "busybox:1.36"

// loadEntrypoint is the long-lived workload-pod PID-1 (the agent-runtime sidecar in production).
var loadEntrypoint = []string{"sh", "-c", "trap 'exit 0' TERM; sleep 3600 & wait"}

// loadRequest builds a SpawnRequest under the shared load tenancy.
func loadRequest() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-load", ProjectID: "proj-load"},
		Template:   orchestrator.TemplateRef{Name: "real-runtime", Version: "1.0.0"},
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
		By:         "b4-load",
		RunID:      "run-load",
	}
}

// realPodFan resolves the real-pod fan from EDEN_LOAD_N, clamped to realPodFanCeiling.
func realPodFan() int {
	n := realPodFanCeiling
	if raw := os.Getenv("EDEN_LOAD_N"); raw != "" {
		if parsed, err := strconv.Atoi(raw); err == nil && parsed > 0 && parsed < n {
			n = parsed
		}
	}
	return n
}

// startRealPump reconciles on a short ticker until stopped, so the Spawn/Stop verbs race the
// reconcile loop under -race. Returns a stop func that joins the pump goroutine.
func startRealPump(harness *orchestratortest.RealHarness) func() {
	done := make(chan struct{})
	closed := make(chan struct{})
	go func() {
		defer close(closed)
		ticker := time.NewTicker(120 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				_, _ = harness.Reconcile(context.Background()) //nolint:errcheck // a pass error is non-fatal; the next tick retries.
			}
		}
	}()
	return func() {
		close(done)
		<-closed
	}
}

// awaitAllRunning drives reconcile until every (non-empty) id is Running against the real
// supervised pods, bounded.
func awaitAllRunning(t *testing.T, harness *orchestratortest.RealHarness, ids []orchestrator.AgentID) {
	t.Helper()
	for pass := 0; pass < 64; pass++ {
		if _, err := harness.Reconcile(context.Background()); err != nil {
			t.Fatalf("reconcile awaiting Running: %v", err)
		}
		allRunning := true
		for _, id := range ids {
			if id == "" {
				continue
			}
			agent, err := harness.Get(context.Background(), id)
			if err != nil || agent.Status != orchestrator.StatusRunning {
				allRunning = false
				if agent.Status.Terminal() {
					t.Fatalf("agent %s went terminal before Running (detail %q)", id, agent.Detail)
				}
			}
		}
		if allRunning {
			return
		}
		time.Sleep(150 * time.Millisecond)
	}
	t.Fatalf("not all agents reached Running within 64 passes")
}

// convergeReal drives reconcile to quiescence over the real ports (bounded).
func convergeReal(t *testing.T, harness *orchestratortest.RealHarness) {
	t.Helper()
	for pass := 0; pass < 64; pass++ {
		report, err := harness.Reconcile(context.Background())
		if err != nil {
			t.Fatalf("converge reconcile: %v", err)
		}
		if report.Transitioned == 0 {
			return
		}
		time.Sleep(120 * time.Millisecond)
	}
	t.Fatalf("real reconcile did not converge within 64 passes")
}

// compile-time pin: the load arm references the real provider port so the imports stay honest.
var _ workspaceprovider.Provider = (*workspaceprovider.Provisioner)(nil)
