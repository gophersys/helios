// Command agentgateway-live is the LIVE-LOCAL composition root for the agentsession gateway
// (Milestone-B B8, ADR-0022 #2): it serves the SAME REST+SSE surface the B7 chat UI calls, but
// over a REAL harness CLI (claude-code | omp) whose credential is resolved server-side from the
// REAL local Vault. ONE binary, no NATS, no pods — the harness runs in-process as an os/exec
// subprocess, so `deploy local` brings up the live UI + a real agent with a single command.
//
// It is the deliberate sibling of cmd/agentgateway-dev (fakes, zero substrate) and cmd/agentgateway
// (the stateless NATS→SSE production bridge). All real wiring is isolated in internal/liveserve, so
// this command stays a thin parse+listen+serve+signal shell. Every value is read from the
// environment ONCE here (the configuration pattern); a missing required one is a typed startup
// error naming the field (never echoing a value).
//
//	# brought up by `deploy local` (which seeds Vault + exports these); or directly:
//	EDEN_HARNESS=claude-code VAULT_ADDR=http://127.0.0.1:8200 \
//	  VAULT_USERNAME=eden VAULT_PASSWORD=… \
//	  EDEN_CREDENTIAL_REF=vault://eden/development#setup-token \
//	  go run ./cmd/agentgateway-live          # serves 127.0.0.1:8080
//
// The surface the frontend hits (gateway.routes): GET /healthz, POST /sessions, GET /sessions,
// GET /sessions/{id}, GET /sessions/{id}/events (SSE), the control/stop/resume verbs, and
// GET /sessions/{id}/transcript. A create request opens a live session; a prompt streams the
// REAL harness turn as the normalized agentsession.Event taxonomy over SSE.
package main

import (
	"context"
	"flag"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/liveserve"
)

// defaultAddress is the loopback address the live gateway binds when neither --address nor
// EDEN_GATEWAY_ADDRESS is set. Loopback by default so a local run never exposes the backend beyond
// the workstation (the UI reaches it same-origin through the vite proxy).
const defaultAddress = "127.0.0.1:8080"

// addressEnvVar is the environment override for the bind address (the flag wins over it).
const addressEnvVar = "EDEN_GATEWAY_ADDRESS"

// defaultVaultAddress / defaultCredentialReference / defaultHarness are the local-development
// defaults when the corresponding env var is unset (the .env.development convention).
const (
	defaultVaultAddress       = "http://127.0.0.1:8200"
	defaultCredentialRef      = "vault://eden/development#setup-token" // #nosec G101 -- an opaque vault REFERENCE (path), not a credential value.
	defaultVaultUsername      = "eden"
	defaultHarness            = "claude-code"
	defaultWorkspaceParentDir = "/tmp/eden-live-workspace"
)

// The create-saga defaults (the .env.development convention). The saga wires only when DATABASE_URL is
// also set; otherwise the create handler keeps the pre-saga draft behavior.
const (
	defaultRepositoryOwner       = "MateoSegura"
	defaultForgeCredentialRef    = "vault://eden/development#gh-token" // #nosec G101 -- an opaque vault REFERENCE (path), not a credential value.
	defaultTemplateRepositoryURL = "https://github.com/gophersys/template.git"
	defaultOrganizationID        = "eden"
)

func main() {
	os.Exit(realMain(os.Args[1:]))
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an exit
// code, so main's only statement is os.Exit (no defer skipped by a direct os.Exit).
func realMain(arguments []string) int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	address, err := resolveAddress(arguments)
	if err != nil {
		logger.Error("agentgateway-live: invalid arguments", slog.String("error", err.Error()))
		return 2
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, logger, address); err != nil {
		logger.Error("agentgateway-live: exited with error", slog.String("error", err.Error()))
		return 1
	}
	return 0
}

// resolveAddress resolves the bind address with precedence flag > EDEN_GATEWAY_ADDRESS > default.
func resolveAddress(arguments []string) (string, error) {
	flags := flag.NewFlagSet("agentgateway-live", flag.ContinueOnError)
	address := flags.String("address", "", "TCP address the live gateway binds (default "+defaultAddress+", or $"+addressEnvVar+")")
	if err := flags.Parse(arguments); err != nil {
		return "", errors.Wrap(errors.KindInvalid, "agentgateway-live: parse flags", err)
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

// run is the testable body: it reads the live configuration from the environment, builds the live
// gateway over the REAL harness + REAL Vault, ensures a real workspace directory, binds a real
// listener, logs the URL the frontend hits, and serves until the context is canceled
// (SIGINT/SIGTERM), then performs a graceful shutdown that reaps every live session.
func run(ctx context.Context, logger *slog.Logger, address string) error {
	configuration, err := loadConfiguration(logger)
	if err != nil {
		return err
	}

	gateway, supervisor, err := liveserve.BuildLiveGateway(configuration)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "agentgateway-live: build live gateway", err)
	}

	// When the create-saga is wired, the supervisor orchestrator's reconcile LOOP is the one goroutine
	// the live composition needs — owned here (the command), not the pure builder. Start it for the
	// gateway's lifetime; Close it (draining in-flight reconciles) on shutdown before the process exits.
	if supervisor != nil {
		if startErr := supervisor.Start(ctx); startErr != nil {
			return errors.Wrap(errors.KindUnavailable, "agentgateway-live: start orchestrator loop", startErr)
		}
		defer func() {
			shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			_ = supervisor.Close(shutdownCtx) //nolint:errcheck // best-effort loop drain on shutdown; the process is exiting.
		}()
		logger.Info("agentgateway-live: project-creation saga wired (real supervisor orchestrator on docker)")
	}

	listener, err := net.Listen("tcp", address)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-live: bind listener", err)
	}

	templateName, templateVersion := liveserve.DefaultCreateTemplate()
	logger.Info(
		"agentgateway-live: serving REAL-harness gateway over the local Vault",
		slog.String("url", "http://"+listener.Addr().String()),
		slog.String("healthz", "http://"+listener.Addr().String()+"/healthz"),
		slog.String("harness", configuration.Harness),
		slog.String("credentialReference", configuration.CredentialReference), // an opaque path, never a value
		slog.String("workspace", configuration.Workspace),
		slog.String("createTemplateName", templateName),
		slog.String("createTemplateVersion", templateVersion),
	)

	if err := gateway.Serve(ctx, listener); err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-live: serve", err)
	}
	logger.Info("agentgateway-live: shutdown complete")
	return nil
}

// loadConfiguration reads the live composition's configuration from the environment ONCE (the
// configuration pattern). The Vault userpass password is read but NEVER logged. The workspace is
// a real local directory the command ensures exists (the harness CWD). Defaults match the
// .env.development convention so `deploy local` needs to export only the secrets.
func loadConfiguration(logger *slog.Logger) (liveserve.Config, error) {
	workspace, err := ensureWorkspace()
	if err != nil {
		return liveserve.Config{}, err
	}
	seedRoot, err := ensureSeedCheckoutRoot()
	if err != nil {
		return liveserve.Config{}, err
	}
	return liveserve.Config{
		VaultAddress:        envOr("VAULT_ADDR", defaultVaultAddress),
		VaultUsername:       envOr("VAULT_USERNAME", defaultVaultUsername),
		VaultPassword:       os.Getenv("VAULT_PASSWORD"), // never logged; required (validated in liveserve)
		CredentialReference: envOr("EDEN_CREDENTIAL_REF", defaultCredentialRef),
		Harness:             envOr("EDEN_HARNESS", defaultHarness),
		Model:               os.Getenv("EDEN_MODEL"),
		Workspace:           workspace,
		// The dashboard's persisted-Project store DSN. Optional: when unset the /projects routes 503;
		// `deploy local` exports it (eden-postgres) so the live demo persists projects.
		DatabaseDSN: os.Getenv("DATABASE_URL"),
		// The create-saga seam: when DATABASE_URL is set these defaults wire the DB-first
		// project-creation saga (real repo → template seed → a REAL Claude supervisor on docker). The
		// gh-token reference is DISTINCT from the claude EDEN_CREDENTIAL_REF; `deploy local` seeds both
		// into Vault. Empty any of these to fall back to the pre-saga draft behavior.
		RepositoryOwner:          envOr("EDEN_REPOSITORY_OWNER", defaultRepositoryOwner),
		ForgeCredentialReference: envOr("EDEN_FORGE_CREDENTIAL_REF", defaultForgeCredentialRef),
		TemplateRepositoryURL:    envOr("EDEN_TEMPLATE_REPOSITORY_URL", defaultTemplateRepositoryURL),
		OrganizationID:           envOr("EDEN_ORGANIZATION_ID", defaultOrganizationID),
		SeedCheckoutRoot:         seedRoot,
		Logger:                   slogAdapter{logger: logger},
	}, nil
}

// ensureSeedCheckoutRoot resolves and creates the saga seeder's checkout root (EDEN_SEED_CHECKOUT_ROOT
// or a local default) — the absolute parent dir each project's template clone lands in.
func ensureSeedCheckoutRoot() (string, error) {
	root := os.Getenv("EDEN_SEED_CHECKOUT_ROOT")
	if root == "" {
		root = filepath.Join(defaultWorkspaceParentDir, "seeds")
	}
	// #nosec G304,G703 -- an OPERATOR-set env value or a fixed local default, not request input.
	if err := os.MkdirAll(root, 0o750); err != nil {
		return "", errors.Wrap(errors.KindUnavailable, "agentgateway-live: create seed checkout root", err)
	}
	return root, nil
}

// ensureWorkspace resolves and creates the harness workspace directory (EDEN_WORKSPACE or a local
// default). A real, writable CWD is required for the harness subprocess.
func ensureWorkspace() (string, error) {
	workspace := os.Getenv("EDEN_WORKSPACE")
	if workspace == "" {
		workspace = filepath.Join(defaultWorkspaceParentDir, "session")
	}
	// #nosec G304,G703 -- the workspace is an OPERATOR-set env value (EDEN_WORKSPACE) or a fixed
	// local default, not untrusted request input; this is the deploy-local harness CWD.
	if err := os.MkdirAll(workspace, 0o750); err != nil {
		return "", errors.Wrap(errors.KindUnavailable, "agentgateway-live: create workspace directory", err)
	}
	return workspace, nil
}

// envOr returns the environment value for key, or fallback when it is unset/empty.
func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// slogAdapter adapts the command's *slog.Logger onto the narrow liveserve.Logger / gateway.Logger
// port (the composition root owns the adaptation — the gateway package never depends on slog). A
// field is never a secret (the credential seam is enforced upstream by the secrets/harness contract).
type slogAdapter struct{ logger *slog.Logger }

// Info emits a structured info line; fields are passed through as slog attributes.
func (a slogAdapter) Info(message string, fields ...any) { a.logger.Info(message, fields...) }

// Error emits a structured error line; fields are passed through as slog attributes.
func (a slogAdapter) Error(message string, fields ...any) { a.logger.Error(message, fields...) }
