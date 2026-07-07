// Command agentgateway-orchestrator is the KUBERNETES ORCHESTRATOR-ROLE composition root for the
// agentgateway app (W5, ADR-0022 #4): it runs orchestratorservice.Service.Start under a REAL
// coordination.k8s.io/v1 Lease (orchestratorservice.NewKubernetesLease), so in a replicas:3 HA
// Deployment ONLY the lease holder reconciles desired toward actual — two controllers never both
// provision the same Pending agent. A follower replica serves the health probe and waits on the
// election (superviseLeadership promotes it the moment it acquires the Lease; a deposed leader
// exits for a clean restart + re-election). It is the binary the deploy manifest
// (apps/agentgateway/deploy/kubernetes/40-orchestrator-deployment.yaml) and README promise.
//
// It is the deliberate sibling of the other agentgateway composition roots, and imports NO test
// fakes (unlike the dev/live convenience binaries):
//
//   - cmd/agentgateway            — the STATELESS NATS→SSE production bridge (any replica serves any session).
//   - cmd/agentgateway-live       — the LIVE-LOCAL single-process demo (REAL harness + REAL Vault, in-process).
//   - cmd/agentgateway-dev        — the in-process Pool over fakes (fast UI dev; no substrate).
//   - cmd/agentgateway-orchestrator — the kubernetes reconcile-loop role under the Lease.          ← here
//
// Every value the composition needs is read from the environment ONCE here (the configuration
// pattern, environment.go); a missing required one is a typed KindInvalid startup error naming the
// field (never echoing a value). The kubernetes ServiceAccount's projected token IS the in-cluster
// kubeconfig the workspaceprovider kubernetesadapter (Config.Kubeconfig="" → rest.InClusterConfig)
// AND this command's leaderelection client resolve, so no kubeconfig env is read on the cluster.
//
// The harness credential is NEVER a raw env value: it rides every SpawnRequest as an opaque
// secrets.Reference (vault://…) resolved server-side at agentsession.Open through the dual-mode
// Vault provider (EDEN_VAULT_MODE selects the production token-file path). This binary owns the
// database pool (it Closes it) and the observability provider; the Service borrows both and never
// releases them (service.go's Close contract).
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	os.Exit(realMain())
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an exit
// code, so main's only statement is os.Exit (no defer skipped by a direct os.Exit — gocritic
// exitAfterDefer). It mirrors cmd/agentgateway's realMain shape exactly.
func realMain() int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, logger); err != nil {
		logger.Error("agentgateway-orchestrator: exited with error", slog.String("error", err.Error()))
		return 1
	}
	return 0
}
