// Command gateway is the composition ROOT for an http-gateway application generated from this
// template (ADR-0023). It owns ONLY the wiring — the libraries own all behavior. The wiring is the
// IOTEA assembly, in order:
//
//	configuration  → parse the process environment ONCE at the edge (the configuration pattern).
//	secrets        → build the redaction Mediator over Vault; resolve credentials by Reference.
//	observability  → build the Provider (slog exporter) the server logs structured Events on.
//	substrate      → detect kubernetes/docker/bare-process (orchestrator.Substrate) so the server
//	                 knows where it runs, mirroring the orchestrator's F1 adapter selection.
//	persistence    → open the typed pgx data layer when a DSN reference is configured (OPTIONAL: no
//	                 DSN → boot probe-only, so the health probes serve before a database exists). Its
//	                 reachability backs the readiness probe.
//	server.New     → assemble the edenhttp spine + the v1 routes behind it (the pure constructor),
//	                 with the readiness probes and the rate-limit budget resolved here.
//	signal drain   → serve until SIGINT/SIGTERM, then a graceful shutdown.
//
// This is the composition root in full: every value is resolved from the environment at the edge and
// threaded through the pure New constructors. The libraries downstream read no env and resolve no
// credential of their own — the wiring is chosen here, once.
package main

import (
	"context"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/healthcheck"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/middleware"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/runtime"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// defaultAddress is the bind address when EDEN_GATEWAY_ADDRESS is unset.
const defaultAddress = ":8080"

// readHeaderTimeout bounds the request-header read (a long-lived SSE route, if added, is exempt).
const readHeaderTimeout = 10 * time.Second

// shutdownGrace bounds the graceful drain after a signal.
const shutdownGrace = 10 * time.Second

func main() {
	os.Exit(realMain())
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an exit
// code, so main's only statement is os.Exit (no defer skipped by a direct os.Exit).
func realMain() int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, logger); err != nil {
		logger.Error("gateway: exited with error", slog.String("error", err.Error()))
		return 1
	}
	return 0
}

// run is the testable composition body. Every required value is read from the environment ONCE
// here (the configuration pattern); a missing one is a typed startup error, never a silent default.
func run(ctx context.Context, logger *slog.Logger) error {
	// 1. configuration — parse the environment at the edge into the frozen, fully-resolved input.
	environment, err := loadEnvironment()
	if err != nil {
		return err
	}

	// 2. secrets — the redaction Mediator. The composition root is the ONLY place a credential
	// value is resolved; it never reaches a log line (the secrets no-leak contract).
	mediator, err := buildSecrets(&environment)
	if err != nil {
		return err
	}

	// 3. observability — the Provider the server emits structured Events on. The stage value
	// (development|…|production) arrives only here, from configuration (10 §2).
	provider, err := observability.New(
		observability.Config{
			ServiceName:    "http-gateway",
			ServiceVersion: environment.ServiceVersion,
			Environment:    environment.Stage,
			MinSeverity:    observability.SeverityInfo,
		},
		observability.Deps{Exporter: slogadapter.NewWithLogger(logger), Clock: systemClock{}},
	)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "gateway: build observability provider", err)
	}
	defer func() {
		flushCtx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
		defer cancel()
		_ = provider.Flush(flushCtx) //nolint:errcheck // best-effort drain at shutdown.
	}()

	// 4. substrate — detect where we run (docker vs kubernetes), mirroring the orchestrator's F1
	// adapter selection, so the server records its substrate and a future deploy path can branch.
	substrate := runtime.DetectSubstrate(environment.SubstrateHint)
	provider.Log(ctx, observability.SeverityInfo, "gateway: detected substrate",
		observability.String("substrate", substrate.String()))

	// 5. persistence — open the typed pgx data layer when a DSN reference is configured. It is
	// OPTIONAL: with no DSN the gateway boots probe-only (liveness/readiness serve before a database
	// exists), so the binary comes up for the health probes even when Postgres is not yet provisioned.
	// When wired, its reachability backs the readiness probe (503 until the pool round-trips).
	var readinessProbes []healthcheck.Probe
	var resources resource.Persistence
	if !environment.PersistenceDSNRef.IsZero() {
		dataStore, dataErr := persistence.New(
			ctx,
			persistence.Config{DSN: environment.PersistenceDSNRef},
			persistence.Deps{Secrets: mediator, Observability: provider},
		)
		if dataErr != nil {
			return errors.Wrap(errors.KindUnavailable, "gateway: open persistence", dataErr)
		}
		defer dataStore.Close()
		readinessProbes = append(readinessProbes, postgresProbe(dataStore))
		// The persisted `resource` routes get the typed CRUD store; with no DSN this stays nil and
		// only the no-persistence `ping` reference is mounted (the probe-only boot).
		resources = dataStore.Resources()
	}

	// 6. server.New — the pure constructor that assembles the edenhttp spine + the v1 routes, with
	// the readiness probes and the rate-limit budget the composition root resolved.
	srv, err := server.New(
		server.Config{
			JWTSecretRef:      environment.JWTSecretRef,
			HeartbeatInterval: environment.HeartbeatInterval,
			Substrate:         substrate,
			RateLimit: middleware.RateLimitConfig{
				Limit:  environment.RateLimit,
				Window: environment.RateLimitWindow,
			},
		},
		server.Deps{
			Secrets:         mediator,
			Observability:   provider,
			ReadinessProbes: readinessProbes,
			Resources:       resources,
		},
	)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "gateway: build server", err)
	}

	// 7. serve — bind the listener and run until the signal context is canceled, then drain.
	listener, err := net.Listen("tcp", address(&environment))
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: bind listener", err)
	}
	logger.Info("gateway: serving", slog.String("address", listener.Addr().String()))
	return serve(ctx, srv.Handler(), listener)
}

// postgresProbe builds the readiness probe backed by the persistence pool: it reports the pool
// reachable iff a trivial round-trip query succeeds, so readiness answers 503 (naming "postgres")
// until the database is reachable. It is the composition root's adaptation of the concrete data
// layer onto the server's narrow healthcheck.Probe port (return-concrete: a usable NamedProbe).
func postgresProbe(dataStore *persistence.Persistence) healthcheck.NamedProbe {
	return healthcheck.NamedProbe{
		Label: "postgres",
		CheckFunc: func(ctx context.Context) error {
			// A bounded list of at most one row round-trips the pool to Postgres and back — the
			// cheapest honest "can I serve traffic" signal over the real connection.
			if _, err := dataStore.Resources().List(ctx, 1, 0); err != nil {
				return errors.Wrap(errors.KindUnavailable, "gateway: postgres readiness probe", err)
			}
			return nil
		},
	}
}

// buildSecrets wires the secrets Mediator over the REAL Vault backend (the IOTEA way, mirroring
// agent-runtime's composition). The mode is chosen by EDEN_VAULT_MODE: "token-file" (the
// kubernetes ServiceAccount path) else userpass (local). The composition root is the ONLY place a
// resolver adapter is bound; the server downstream holds the narrow secrets.Provider port.
func buildSecrets(environment *Environment) (*secrets.Mediator, error) {
	address := environment.VaultAddress
	if address == "" {
		address = "http://127.0.0.1:8200"
	}
	var adapter secrets.Provider
	var err error
	if vaultadapter.ParseMode(environment.VaultMode) == vaultadapter.ModeTokenFile {
		adapter, err = vaultadapter.New(
			vaultadapter.Config{Address: address, Mode: vaultadapter.ModeTokenFile, TokenFilePath: os.Getenv("EDEN_VAULT_TOKEN_FILE")},
			vaultadapter.Deps{},
		)
	} else {
		adapter, err = vaultadapter.New(
			vaultadapter.Config{Address: address, Mode: vaultadapter.ModeUserpass},
			vaultadapter.Deps{Username: os.Getenv("VAULT_USERNAME"), Password: os.Getenv("VAULT_PASSWORD")},
		)
	}
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "gateway: build vault backend", err)
	}
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "gateway: build secrets mediator", err)
	}
	return mediator, nil
}

// serve runs the HTTP server until ctx is canceled, then performs a graceful shutdown.
func serve(ctx context.Context, handler http.Handler, listener net.Listener) error {
	httpServer := &http.Server{
		Handler:           handler,
		ReadHeaderTimeout: readHeaderTimeout,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}
	serveErr := make(chan error, 1)
	go func() { serveErr <- httpServer.Serve(listener) }()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
		defer cancel()
		_ = httpServer.Shutdown(shutdownCtx) //nolint:errcheck // shutdown best-effort on signal drain.
		return nil
	case err := <-serveErr:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return errors.Wrap(errors.KindUnavailable, "gateway: serve", err)
	}
}

// address resolves the bind address (EDEN_GATEWAY_ADDRESS or the default).
func address(environment *Environment) string {
	if environment.Address != "" {
		return environment.Address
	}
	return defaultAddress
}

// systemClock is the production time source. The app is the one place a real clock is read — the
// libraries stay pure (10 §4).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }
