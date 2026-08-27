package orchestrator_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
)

// sink keeps the benchmarked work observable so the compiler cannot prove the result dead and
// elide it (a package-level `any` per ADR-0020 dimension (g); kept off any sentinel path).
//
//nolint:gochecknoglobals // benchmark sink must be package-level so the compiler cannot elide the work.
var sink any

// benchRequest is a representative SpawnRequest the hot-path benchmarks drive (the seeded
// credential ref — the VALUE never rides it).
var benchRequest = orchestrator.SpawnRequest{
	Tenant:     orchestrator.Tenancy{OrganizationID: "org-bench", ProjectID: "proj-bench"},
	Template:   orchestratortest.DefaultTemplate().Ref,
	Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
	By:         "bench",
	RunID:      "run-bench",
}

// BenchmarkSpawn measures the Spawn admission hot path over the in-memory fakes (request-shape
// validation + template resolve + effective-limits fold + the count-then-record critical
// section + the desired Put + the spawn-inputs stash + the spawn-admitted emit) — every
// LIBRARY-owned step a real Spawn pays before reconcile ever runs. It is the per-admission cost
// the control plane pays on every "start an agent". Each iteration runs on a FRESH single-agent
// Pool so the measured cost is one admission, not the O(n) admission-scan growth of an
// accumulating store (which would make the baseline drift with iteration count).
func BenchmarkSpawn(b *testing.B) {
	ctx := context.Background()
	b.ReportAllocs()
	var agent orchestrator.Agent
	for b.Loop() {
		b.StopTimer()
		manager := orchestratortest.New(
			orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
			orchestratortest.WithMaxConcurrent(0),
		)
		b.StartTimer()
		var err error
		agent, err = manager.Spawn(ctx, benchRequest)
		if err != nil {
			b.Fatalf("Spawn: %v", err)
		}
	}
	sink = agent
}

// BenchmarkReconcileConverged measures a CONVERGED reconcile pass over a populated Pool (List
// desired + Observe actual + the per-agent diff that decides "no transition") — the steady-state
// cost the loop pays on EVERY tick once the running set is stable, which dominates a long-lived
// fleet's CPU. The agents are driven to Running first so the measured passes are pure no-op
// diffs (the idempotent hot path), not transitions.
func BenchmarkReconcileConverged(b *testing.B) {
	manager := orchestratortest.New(
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
		orchestratortest.WithMaxConcurrent(0),
	)
	manager.Probe().SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})
	ctx := context.Background()
	// Reap every opened session + workspace before goleak's TestMain runs (the benchmarks open
	// REAL agentsession sessions whose pump goroutines must be drained, else the leak lane fails
	// the binary on benchmark-leaked goroutines).
	b.Cleanup(func() { reapBench(manager) })
	for range 16 {
		if _, err := manager.Spawn(ctx, benchRequest); err != nil {
			b.Fatalf("Spawn: %v", err)
		}
	}
	// Drive to quiescence so the measured passes are converged no-op diffs.
	for pass := 0; pass < 64; pass++ {
		report, err := manager.Reconcile(ctx)
		if err != nil {
			b.Fatalf("Reconcile: %v", err)
		}
		if report.Transitioned == 0 {
			break
		}
	}
	b.ReportAllocs()
	var report orchestrator.ReconcileReport
	for b.Loop() {
		var err error
		report, err = manager.Reconcile(ctx)
		if err != nil {
			b.Fatalf("Reconcile: %v", err)
		}
	}
	sink = report
}

// BenchmarkReconcileProvision measures the TRANSITION hot path: a pass that drives a fresh
// Pending agent to Provisioning (the diff + the workspace Provision + the record commit + the
// emit + the watcher notify). It re-spawns a single agent per iteration so each measured pass
// does exactly one provision transition — the per-agent cost the loop pays when the desired set
// grows.
func BenchmarkReconcileProvision(b *testing.B) {
	ctx := context.Background()
	b.ReportAllocs()
	// Provisioning a workspace leaves a live workspace handle on the side table; collect every
	// fresh Pool and reap them all before goleak's TestMain runs.
	var pools []*orchestratortest.Manager
	b.Cleanup(func() {
		for _, p := range pools {
			reapBench(p)
		}
	})
	var report orchestrator.ReconcileReport
	for b.Loop() {
		b.StopTimer()
		// A fresh single-agent Pool per iteration so the measured pass is exactly one provision.
		fresh := orchestratortest.New(
			orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
			orchestratortest.WithMaxConcurrent(0),
		)
		pools = append(pools, fresh)
		if _, err := fresh.Spawn(ctx, benchRequest); err != nil {
			b.Fatalf("Spawn: %v", err)
		}
		b.StartTimer()
		var err error
		report, err = fresh.Reconcile(ctx)
		if err != nil {
			b.Fatalf("Reconcile: %v", err)
		}
	}
	sink = report
}

// reapBench drains every non-terminal agent a benchmark Pool owns and Closes it, so no
// agentsession pump goroutine or provisioned workspace leaks into goleak's end-of-binary
// VerifyTestMain check.
func reapBench(manager *orchestratortest.Manager) {
	ctx := context.Background()
	_ = manager.Pool().Close(ctx) //nolint:errcheck // best-effort reap; Close records Stop intents and drives the final drain pass.
	// Close drives one final reconcile pass; run a few more so every drained agent's workspace
	// is released and every session pump is reaped before the leak check.
	for pass := 0; pass < 8; pass++ {
		report, err := manager.Reconcile(ctx)
		if err != nil || report.Transitioned == 0 {
			return
		}
	}
}

// BenchmarkStatusString measures the Status token rendering the dashboard and transport boundary
// call per record (a pure, allocation-sensitive lookup).
func BenchmarkStatusString(b *testing.B) {
	b.ReportAllocs()
	var s string
	for b.Loop() {
		s = orchestrator.StatusRunning.String()
	}
	sink = s
}

// BenchmarkObservabilityKindString measures the orchestration-plane event-kind token rendering
// the telemetry boundary calls per emitted event.
func BenchmarkObservabilityKindString(b *testing.B) {
	b.ReportAllocs()
	var s string
	for b.Loop() {
		s = orchestrator.ObsTransition.String()
	}
	sink = s
}
