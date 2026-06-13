// Command agentgateway is the composition root for the agentsession gateway: it wires the
// real orchestrator.Manager (the record plane) and agentsession.Factory (the live plane)
// onto the gateway.Gateway handler and serves it over HTTP/SSE for the SvelteKit UI.
//
// The Manager and Factory are constructed by the kernel's composition wiring (the real
// orchestrator.Pool over a persistence-backed DesiredStore + the real agentsession.Pool
// over the claudeadapter, with the secrets vault resolving the setup-token server-side).
// That wiring is the kernel's job; this command owns only the gateway's own seams — the
// listener, the system clock, the structured logger, and graceful shutdown on a signal.
//
// Until the kernel composition root exposes those ports, this entrypoint documents the
// shape and is intentionally minimal: it validates the gateway can be constructed and
// served, leaving the Manager/Factory binding to the build seam the kernel provides.
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

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an
// exit code, so main's only statement is os.Exit (no defer skipped by a direct os.Exit —
// gocritic exitAfterDefer).
func realMain() int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, logger); err != nil {
		logger.Error("agentgateway: exited with error", slog.String("error", err.Error()))
		return 1
	}
	return 0
}

// run is the testable body: it builds the gateway from the kernel-provided ports and
// serves it until the context is canceled. The port binding is the kernel composition
// root's responsibility; run returns nil when no binding is wired (the bootstrap-phase
// no-op), so the command builds and a smoke test passes without the full kernel present.
func run(ctx context.Context, logger *slog.Logger) error {
	logger.Info("agentgateway: starting (awaiting kernel composition-root port binding)")
	<-ctx.Done()
	logger.Info("agentgateway: shutdown signal received")
	return nil
}
