// Command agentgateway-dev is the DEV-ONLY composition root for the agentsession gateway: it
// serves a fully working REST+SSE backend the SvelteKit frontend develops against, wired over
// IN-MEMORY FAKES (scripted agents, a seeded fake setup-token, an in-memory record plane and
// transcript) — NO real claude setup-token, NO harness process, NO container, NO network
// substrate beyond the loopback listener.
//
// It is the deliberate counterpart to cmd/agentgateway (the production entrypoint, which
// awaits the kernel composition root + real adapters and imports NO test fakes). All fake
// wiring is isolated in internal/devserve, so this command stays a thin listen+serve+signal
// shell and the production command stays fake-free.
//
//	go run ./cmd/agentgateway-dev                       # serves 127.0.0.1:8080
//	go run ./cmd/agentgateway-dev --address 127.0.0.1:9090
//	EDEN_DEV_ADDRESS=0.0.0.0:8080 go run ./cmd/agentgateway-dev
//
// The surface the frontend hits (gateway.routes): GET /healthz, POST /sessions,
// GET /sessions, GET /sessions/{id}, GET /sessions/{id}/events (SSE), the control/stop/resume
// verbs, and GET /sessions/{id}/transcript. A create request streams the realistic demo turn.
package main

import (
	"context"
	"flag"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/devserve"
)

// defaultAddress is the loopback address the dev gateway binds when neither --address nor
// EDEN_DEV_ADDRESS is set. Loopback by default so a dev run never exposes the fake backend
// beyond the workstation.
const defaultAddress = "127.0.0.1:8080"

// addressEnvVar is the environment override for the bind address (the flag wins over it).
const addressEnvVar = "EDEN_DEV_ADDRESS"

func main() {
	os.Exit(realMain(os.Args[1:]))
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an
// exit code, so main's only statement is os.Exit (no defer skipped by a direct os.Exit —
// gocritic exitAfterDefer).
func realMain(arguments []string) int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	address, err := resolveAddress(arguments)
	if err != nil {
		logger.Error("agentgateway-dev: invalid arguments", slog.String("error", err.Error()))
		return 2
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, logger, address); err != nil {
		logger.Error("agentgateway-dev: exited with error", slog.String("error", err.Error()))
		return 1
	}
	return 0
}

// resolveAddress resolves the bind address with precedence flag > EDEN_DEV_ADDRESS > default.
// It parses a fresh FlagSet over the given arguments so the body is testable and main stays a
// one-liner.
func resolveAddress(arguments []string) (string, error) {
	flags := flag.NewFlagSet("agentgateway-dev", flag.ContinueOnError)
	address := flags.String("address", "", "TCP address the dev gateway binds (default "+defaultAddress+", or $"+addressEnvVar+")")
	if err := flags.Parse(arguments); err != nil {
		return "", errors.Wrap(errors.KindInvalid, "agentgateway-dev: parse flags", err)
	}
	switch {
	case *address != "":
		return *address, nil
	case os.Getenv(addressEnvVar) != "":
		return os.Getenv(addressEnvVar), nil
	default:
		return defaultAddress, nil
	}
}

// run is the testable body: it builds the dev gateway over in-memory fakes, binds a real
// listener on address, logs the URL the frontend hits, and serves until the context is
// canceled (SIGINT/SIGTERM), then performs a graceful shutdown that reaps every live session.
func run(ctx context.Context, logger *slog.Logger, address string) error {
	gateway, err := devserve.BuildDevGateway(devserve.Config{Logger: slogAdapter{logger: logger}})
	if err != nil {
		return errors.Wrap(errors.KindInternal, "agentgateway-dev: build dev gateway", err)
	}

	listener, err := net.Listen("tcp", address)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-dev: bind listener", err)
	}

	templateName, templateVersion := devserve.DefaultCreateTemplate()
	logger.Info(
		"agentgateway-dev: serving fake-wired gateway (no real auth)",
		slog.String("url", "http://"+listener.Addr().String()),
		slog.String("healthz", "http://"+listener.Addr().String()+"/healthz"),
		slog.String("createTemplateName", templateName),
		slog.String("createTemplateVersion", templateVersion),
	)

	if err := gateway.Serve(ctx, listener); err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-dev: serve", err)
	}
	logger.Info("agentgateway-dev: shutdown complete")
	return nil
}

// slogAdapter adapts the command's *slog.Logger onto the narrow devserve.Logger /
// gateway.Logger port (the composition root owns the adaptation — the gateway package never
// depends on slog). A field is never a secret (the credential seam is enforced upstream).
type slogAdapter struct{ logger *slog.Logger }

// Info emits a structured info line; fields are passed through as slog attributes.
func (a slogAdapter) Info(message string, fields ...any) { a.logger.Info(message, fields...) }

// Error emits a structured error line; fields are passed through as slog attributes.
func (a slogAdapter) Error(message string, fields ...any) { a.logger.Error(message, fields...) }
