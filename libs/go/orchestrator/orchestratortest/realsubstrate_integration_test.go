//go:build integration

// Package orchestratortest_test's REAL-SUBSTRATE arm (B4) proves the THIN orchestrator over
// REAL pods end-to-end — NEVER a mock of any substrate. It binds the EXISTING orchestrator
// ports to:
//
//   - a REAL workspaceprovider.Provider/Supervisor over a REAL substrate (docker
//     EphemeralContainer AND a real k3d cluster), provisioning Entrypoint workload-pods (the
//     agent-runtime sidecar IS the PID-1, OD-15-a) — so a spawned agent is a real supervised
//     pod;
//   - a REAL Postgres DesiredStore (booted docker-out-of-docker, reaped on t.Cleanup) — so
//     desired-state survives a node recycle (Resume/re-adopt across a stateless restart);
//   - the REAL SupervisedProbe — Actual derived from the provider's supervised Status (the
//     HARD lifecycle), not raw heartbeats nor the in-process liveTable;
//   - a REAL NATS (embedded real nats-server) — the SOFT control signal (stop/kill published to
//     agent.<id>.control AFTER the desired-intent is recorded).
//
// It drives the reconcile loop spawn → running → stop → resume → kill at a small real-pod fan,
// asserts the supervised truth at each step, and reaps everything (CountOwned==0), race-clean
// and leak-free. The agentsession inside is the deterministic stub harness (a real subprocess
// in production; a real-claude/omp arm SKIPS without a key — out of scope for this gate). The
// full agent-runtime-image-in-pod demo is the B8 hand-off.
//
//	go test -tags integration ./... -count=1
package orchestratortest_test

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// realTestImage is the tiny image the real Entrypoint workload-pods run. busybox is ubiquitous
// and pre-pulled by the harness so per-test provisions are fast and offline-safe.
const realTestImage = "busybox:1.36"

// entrypointSleep is the workload-pod PID-1: a long-lived sleep that keeps the supervised
// workspace Running so the reconcile loop Probes a live supervised Status (the agent-runtime
// sidecar in production; a representative real workload here — the point under test is the
// orchestrator↔provider↔NATS↔Postgres reconcile, not the agent-runtime image, which is B8).
var entrypointSleep = []string{"sh", "-c", "trap 'exit 0' TERM; sleep 3600 & wait"}

// realRequest builds a SpawnRequest for the real-runtime template under the shared tenancy.
func realRequest() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-b4", ProjectID: "proj-b4"},
		Template:   orchestrator.TemplateRef{Name: "real-runtime", Version: "1.0.0"},
		Credential: secretsRef(),
		By:         "b4-integration",
		RunID:      "run-b4",
	}
}

// TestIntegration_B4Docker is the B4 proof on a REAL docker daemon: spawn → running → recycle →
// suspend → resume → stop → kill over real Entrypoint pods, a real Postgres DesiredStore, the
// real SupervisedProbe, and the real NATS soft-control signal — at a small fan, race-clean (the
// integration lane), every pod reaped (CountOwned==0). (A short name keeps the kubernetes
// namespace-per-workspace derivation well under the 63-char DNS-label ceiling on the sibling
// k3d arm; the docker arm shares the convention.)
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-substrate lifecycle walk; serial by design (spins real pods + a real postgres).
func TestIntegration_B4Docker(t *testing.T) {
	const fan = 3
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(realTestImage))
	harness := orchestratortest.NewRealHarness(t, adapter, orchestrator.SubstrateDocker, orchestratortest.RealConfig{
		Entrypoint: entrypointSleep,
		Image:      realTestImage,
		Substrate:  orchestrator.SubstrateDocker,
		Cluster:    orchestrator.ClusterRef{ID: "local-docker"},
		MaxAgents:  fan + 2,
	})
	registerRealReaper(t, harness, adapter)

	ctx := t.Context()

	// ── spawn → running: N real Entrypoint pods, desired-state in real Postgres ──────────────.
	ids := make([]orchestrator.AgentID, fan)
	for i := range fan {
		agent, err := harness.Spawn(ctx, realRequest())
		if err != nil {
			t.Fatalf("Spawn[%d]: %v", i, err)
		}
		ids[i] = agent.ID
		if agent.Status != orchestrator.StatusPending {
			t.Fatalf("Spawn[%d] status = %v, want Pending", i, agent.Status)
		}
	}
	reconcileRealToQuiescence(t, harness)

	// Every agent converged to Running against the SUPERVISED truth (the real pod is live).
	for _, id := range ids {
		agent := mustGetReal(t, harness, id)
		if agent.Status != orchestrator.StatusRunning {
			t.Fatalf("agent %s status = %v, want Running (supervised pod live)", id, agent.Status)
		}
		// The record persisted to REAL Postgres carries the real workspace Handle (the supervised
		// read key) and the opaque SessionRef — survives a node recycle (read it back below).
		if agent.Workspace.IsZero() {
			t.Fatalf("agent %s has no persisted workspace handle after Running", id)
		}
		// The SupervisedProbe read this directly off the provider's supervised Status.
		assertSupervisedLive(ctx, t, harness, agent.Workspace)
	}

	// ── stateless restart: re-derive the SAME truth from the live substrate via default ports ─.
	// The record lives in Postgres; the supervised truth lives in docker — NEITHER is in-process,
	// so a reconcile pass through the Pool's bound (default) ports re-derives Running from reality.
	if _, err := harness.Pool().Reconcile(ctx, orchestrator.ReconcilePorts{}); err != nil {
		t.Fatalf("reconcile with default (bound) ports after a stateless restart: %v", err)
	}
	for _, id := range ids {
		fresh := mustGetReal(t, harness, id)
		if fresh.Status != orchestrator.StatusRunning {
			t.Fatalf("agent %s status after re-derive = %v, want still Running", id, fresh.Status)
		}
	}

	subs := make([]*nats.Subscription, fan)
	for i, id := range ids {
		subs[i] = harness.ControlSubscription(t, id) // attach BEFORE any publish so it is not raced
	}

	// ── resume / survive-recycle: a REAL node recycle drops the actual → Suspended → re-adopt ─.
	// Tear one agent's pod down OUT-OF-BAND (a preemption). The desired-state survives in REAL
	// Postgres; the next pass Probes a Gone supervised Status → Suspended; Resume re-provisions a
	// fresh pod and re-attaches → Running. This is the multi-node survive-recycle the plan names.
	recycleID := ids[0]
	recycled, rerr := harness.RecycleNode(ctx, recycleID)
	if rerr != nil {
		t.Fatalf("out-of-band recycle of %s: %v", recycleID, rerr)
	}
	if !recycled {
		t.Fatalf("agent %s had no live pod to recycle", recycleID)
	}
	// The reconcile loop observes the dropped actual (Gone supervised Status) → Suspended.
	driveUntilStatus(t, harness, recycleID, orchestrator.StatusSuspended)

	// Resume records the re-adopt intent; the loop re-provisions + re-attaches → Running.
	if err := harness.Resume(ctx, recycleID, "b4-resume"); err != nil {
		t.Fatalf("Resume(%s): %v", recycleID, err)
	}
	reconcileRealToQuiescence(t, harness)
	resumed := mustGetReal(t, harness, recycleID)
	if resumed.Status != orchestrator.StatusRunning {
		t.Fatalf("resumed agent %s status = %v, want Running (re-adopted over a fresh real pod)", recycleID, resumed.Status)
	}
	assertSupervisedLive(ctx, t, harness, resumed.Workspace)

	// ── stop: record desired-intent FIRST, then the SOFT signal; the loop hard-tears-down ────.
	stopID := ids[0]
	if err := harness.SoftStopThenKill(ctx, stopID, false, "b4-stop"); err != nil {
		t.Fatalf("SoftStopThenKill(stop) for %s: %v", stopID, err)
	}
	// The desired-intent was recorded FIRST (durable Stop), THEN the soft signal reached the bus.
	assertControlVerb(t, subs[0], "stop")

	reconcileRealToQuiescence(t, harness)
	stopped := mustGetReal(t, harness, stopID)
	if stopped.Status != orchestrator.StatusStopped {
		t.Fatalf("stopped agent %s status = %v, want Stopped (hard teardown)", stopID, stopped.Status)
	}
	// The HARD lifecycle: the provider tore the pod down → the supervised read is Gone.
	assertSupervisedGone(ctx, t, harness, stopped.Workspace)

	// ── kill: the soft kill signal + the hard teardown for every remaining agent ─────────────.
	for i, id := range ids {
		if err := harness.SoftStopThenKill(ctx, id, true, "b4-kill"); err != nil {
			t.Fatalf("SoftStopThenKill(kill) for %s: %v", id, err)
		}
		assertControlVerb(t, subs[i], "kill")
	}
	reconcileRealToQuiescence(t, harness)
	for _, id := range ids {
		agent := mustGetReal(t, harness, id)
		if agent.Status != orchestrator.StatusStopped {
			t.Fatalf("killed agent %s status = %v, want Stopped", id, agent.Status)
		}
		assertSupervisedGone(ctx, t, harness, agent.Workspace)
	}

	// ── reap evidence: no orphaned container left on the real daemon (CountOwned==0) ─────────.
	assertNoOwnedContainers(ctx, t, adapter)
}

// TestIntegration_B4K3d is the B4 proof on a REAL k3d cluster (k3s-in-docker — the DEFAULT
// kubernetes substrate): spawn → running → stop → kill over real Entrypoint workload-pods, the
// real Postgres DesiredStore, the real SupervisedProbe, and the real NATS soft-control signal.
// It SKIPS when k3d/docker is unavailable; REQUIRED in the devcontainer. The resume-from-recycle
// leg is exercised on docker (above) where pod churn is fast; on k3d the proof is the
// spawn→running→stop→kill core over a REAL pod-watch supervised Status — the kubernetes binding
// of the same thinned reconcile loop. A SHORT test name is load-bearing: the kubernetesadapter
// derives a namespace-per-workspace as eden-<ownership>-ws-<agentID>, RFC-1123-truncated to 63
// chars; a long test name (the ownership prefix) would truncate the per-agent discriminator and
// collide two agents onto ONE namespace. No mock.
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-cluster lifecycle walk; serial by design (spins a real k3d cluster + real pods).
func TestIntegration_B4K3d(t *testing.T) {
	const fan = 2
	adapter := workspaceprovidertest.K3dCluster(t, workspaceprovidertest.WithImages(realTestImage))
	harness := orchestratortest.NewRealHarness(t, adapter, orchestrator.SubstrateKubernetes, orchestratortest.RealConfig{
		Entrypoint: entrypointSleep,
		Image:      realTestImage,
		Substrate:  orchestrator.SubstrateKubernetes,
		Cluster:    orchestrator.ClusterRef{ID: "local-k3d"},
		MaxAgents:  fan + 2,
	})
	t.Cleanup(func() {
		// Drain every live agent and converge so no pod leaks past the test on the real cluster.
		page, err := harness.List(context.Background(), orchestrator.Filter{OnlyActive: true})
		if err == nil {
			for i := range page.Agents {
				_ = harness.Stop(context.Background(), page.Agents[i].ID, "cleanup") //nolint:errcheck // best-effort drain.
			}
		}
		for pass := 0; pass < 48; pass++ {
			report, rerr := harness.Reconcile(context.Background())
			if rerr != nil || report.Transitioned == 0 {
				break
			}
			time.Sleep(200 * time.Millisecond)
		}
	})

	ctx := t.Context()
	ids := make([]orchestrator.AgentID, fan)
	for i := range fan {
		agent, err := harness.Spawn(ctx, realRequest())
		if err != nil {
			t.Fatalf("Spawn[%d] on k3d: %v", i, err)
		}
		ids[i] = agent.ID
	}
	reconcileRealToQuiescence(t, harness)

	subs := make([]*nats.Subscription, fan)
	for i, id := range ids {
		agent := mustGetReal(t, harness, id)
		if agent.Status != orchestrator.StatusRunning {
			t.Fatalf("k3d agent %s status = %v (detail %q), want Running (supervised pod live)", id, agent.Status, agent.Detail)
		}
		assertSupervisedLive(ctx, t, harness, agent.Workspace)
		subs[i] = harness.ControlSubscription(t, id)
	}

	// Stop the first, kill the rest — the soft signal reaches the bus; the hard lifecycle reaps.
	if err := harness.SoftStopThenKill(ctx, ids[0], false, "b4-k3d-stop"); err != nil {
		t.Fatalf("SoftStopThenKill(stop) on k3d for %s: %v", ids[0], err)
	}
	assertControlVerb(t, subs[0], "stop")
	for i := 1; i < fan; i++ {
		if err := harness.SoftStopThenKill(ctx, ids[i], true, "b4-k3d-kill"); err != nil {
			t.Fatalf("SoftStopThenKill(kill) on k3d for %s: %v", ids[i], err)
		}
		assertControlVerb(t, subs[i], "kill")
	}
	reconcileRealToQuiescence(t, harness)
	for _, id := range ids {
		agent := mustGetReal(t, harness, id)
		if agent.Status != orchestrator.StatusStopped {
			t.Fatalf("k3d agent %s status = %v, want Stopped after stop/kill", id, agent.Status)
		}
		assertSupervisedGone(ctx, t, harness, agent.Workspace)
	}
}

// reconcileRealToQuiescence drives reconcile passes over the REAL bound ports until a full pass
// makes no transition (convergence), bounded so a stuck loop fails fast. Each pass talks to the
// real provider, the real Postgres, and the real supervised Status.
func reconcileRealToQuiescence(t *testing.T, harness *orchestratortest.RealHarness) {
	t.Helper()
	for pass := 0; pass < 48; pass++ {
		report, err := harness.Reconcile(context.Background())
		if err != nil {
			t.Fatalf("real Reconcile pass %d: %v", pass, err)
		}
		if report.Transitioned == 0 {
			return
		}
		time.Sleep(150 * time.Millisecond) // let the substrate settle between transitions (real pods)
	}
	t.Fatalf("real reconcile did not converge within 48 passes")
}

// driveUntilStatus reconciles until the named agent reaches want (bounded), so a real-substrate
// transition that needs several passes (the substrate settling) is awaited deterministically.
func driveUntilStatus(t *testing.T, harness *orchestratortest.RealHarness, id orchestrator.AgentID, want orchestrator.Status) {
	t.Helper()
	for pass := 0; pass < 32; pass++ {
		if _, err := harness.Reconcile(context.Background()); err != nil {
			t.Fatalf("Reconcile awaiting %v for %s: %v", want, id, err)
		}
		if mustGetReal(t, harness, id).Status == want {
			return
		}
		time.Sleep(150 * time.Millisecond)
	}
	t.Fatalf("agent %s never reached %v within 32 passes (got %v)", id, want, mustGetReal(t, harness, id).Status)
}

// mustGetReal reads one agent record from the real Pool (backed by real Postgres).
func mustGetReal(t *testing.T, harness *orchestratortest.RealHarness, id orchestrator.AgentID) orchestrator.Agent {
	t.Helper()
	agent, err := harness.Get(context.Background(), id)
	if err != nil {
		t.Fatalf("Get(%s) from real Postgres store: %v", id, err)
	}
	return agent
}

// assertSupervisedLive asserts the provider's supervised Status reports the workspace live
// (Ready/Running) — the HARD truth the orchestrator Probes (the SAME call the probe makes).
func assertSupervisedLive(ctx context.Context, t *testing.T, harness *orchestratortest.RealHarness, handle workspaceprovider.Handle) {
	t.Helper()
	st, serr := supervisedOf(ctx, harness, handle)
	if serr != nil {
		t.Fatalf("Supervised(%s): %v", handle.String(), serr)
	}
	if st.State != workspaceprovider.StateReady && st.State != workspaceprovider.StateRunning {
		t.Fatalf("supervised State = %v for %s, want Ready/Running", st.State, handle.String())
	}
}

// assertSupervisedGone asserts the provider's supervised Status reports the workspace gone (the
// HARD teardown completed — the pod is reaped). A NotFoundError or a Gone State both satisfy.
func assertSupervisedGone(ctx context.Context, t *testing.T, harness *orchestratortest.RealHarness, handle workspaceprovider.Handle) {
	t.Helper()
	if handle.IsZero() {
		return
	}
	deadline := time.Now().Add(15 * time.Second)
	for time.Now().Before(deadline) {
		st, err := supervisedOf(ctx, harness, handle)
		if err != nil { // NotFoundError → the pod is gone
			return
		}
		if st.State == workspaceprovider.StateGone {
			return
		}
		time.Sleep(300 * time.Millisecond)
	}
	t.Fatalf("supervised workspace %s never went Gone after the hard teardown", handle.String())
}

// supervisedOf reads the supervised Status for a handle off the real provider (the Supervisor
// the probe reads).
func supervisedOf(ctx context.Context, harness *orchestratortest.RealHarness, handle workspaceprovider.Handle) (workspaceprovider.Status, error) {
	return harness.Supervisor().Supervised(ctx, handle) //nolint:wrapcheck // the provider's wrapped error surfaces directly to the test.
}

// assertControlVerb asserts the next message on a control subscription carries the expected
// soft-control verb (the SOFT signal reached the REAL bus).
func assertControlVerb(t *testing.T, sub *nats.Subscription, wantVerb string) {
	t.Helper()
	message, err := sub.NextMsg(5 * time.Second)
	if err != nil {
		t.Fatalf("no soft-control message arrived (want verb %q): %v", wantVerb, err)
	}
	var control struct {
		Verb string            `json:"verb"`
		OTel map[string]string `json:"otel"`
	}
	if derr := json.Unmarshal(message.Data, &control); derr != nil {
		t.Fatalf("decode control message: %v", derr)
	}
	if control.Verb != wantVerb {
		t.Errorf("soft-control verb = %q, want %q", control.Verb, wantVerb)
	}
	if control.OTel["traceparent"] == "" {
		t.Errorf("soft-control message missing the OTel carrier (every NATS message carries trace context)")
	}
}

// assertNoOwnedContainers asserts the real docker adapter has no owned container left (the reap
// guarantee — CountOwned==0).
func assertNoOwnedContainers(ctx context.Context, t *testing.T, adapter workspaceprovider.Adapter) {
	t.Helper()
	owner, ok := adapter.(*dockeradapter.Adapter)
	if !ok {
		return
	}
	owned, err := owner.CountOwned(ctx)
	if err != nil {
		t.Errorf("CountOwned: %v", err)
		return
	}
	if owned != 0 {
		t.Errorf("reconcile left %d orphaned container(s) on the real daemon (want 0)", owned)
	}
}

// registerRealReaper records a t.Cleanup that drains every non-terminal agent and converges the
// real loop, so no pod/Postgres record leaks past the test, then asserts no owned container
// remains.
func registerRealReaper(t *testing.T, harness *orchestratortest.RealHarness, adapter workspaceprovider.Adapter) {
	t.Helper()
	t.Cleanup(func() {
		page, err := harness.List(context.Background(), orchestrator.Filter{OnlyActive: true})
		if err == nil {
			for i := range page.Agents {
				_ = harness.Stop(context.Background(), page.Agents[i].ID, "cleanup") //nolint:errcheck // best-effort cleanup drain.
			}
		}
		for pass := 0; pass < 48; pass++ {
			report, rerr := harness.Reconcile(context.Background())
			if rerr != nil || report.Transitioned == 0 {
				break
			}
			time.Sleep(100 * time.Millisecond)
		}
		assertNoOwnedContainers(context.Background(), t, adapter)
	})
}
