// Command agent-runtime is the Eden agent-pod PID-1 entrypoint (Milestone-B B3, ADR-0022 §4). It is
// the container's main process (the workspaceprovider Entrypoint/workload-pod capability): it reads
// the pod environment, installs signal.NotifyContext (SIGINT/SIGTERM → the graceful-shutdown state
// machine), builds the agentruntime sidecar via its composition root (the real NATS/JetStream bus,
// the observability provider, the agentsession harness factory), serves the kubelet HTTP probes, and
// runs the sidecar until a signal or a control verb terminates it — mapping the typed
// TerminationReason to the process exit code.
//
// EDEN_PROBE_ONLY=1 boots ONLY the probe server (no bus, no harness) — the bootstrap smoke path that
// proves the binary serves /live and shuts down gracefully on SIGTERM without a live substrate.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/gophersys/eden/apps/agent-runtime/internal/composition"
)

func main() {
	os.Exit(realMain())
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an exit code,
// so main's only statement is os.Exit (no defer skipped by a direct os.Exit — gocritic exitAfterDefer).
func realMain() int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	environment := composition.LoadEnvironment()
	probeOnly := os.Getenv("EDEN_PROBE_ONLY") == "1"
	logger.Info("agent-runtime: starting", slog.String("agentId", environment.AgentID), slog.Bool("probeOnly", probeOnly))

	return composition.Run(ctx, logger, environment, probeOnly)
}
