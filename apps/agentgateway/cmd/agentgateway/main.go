// Command agentgateway is the PRODUCTION composition root for the stateless agentsession gateway
// (ADR-0022 #3): it dials the REAL NATS/JetStream bus, builds the edenhttp dev-JWT spine (the
// identity gate whose HMAC signing key is resolved from Vault — behind auth even locally), the
// natssse JetStream→SSE bridge, and the natscontrol publisher, wires them onto the stateless.Gateway
// handler, and serves it over HTTP until a signal. The gateway is STATELESS — any replica serves any
// session via JetStream durable replay; it holds no per-session state.
//
// The kernel/library code owns all behavior; this command owns only the wiring (the listener, the
// NATS dial, the env parse, the JWT verifier, graceful shutdown). Like every OTHER Eden credential,
// the JWT signing key is NEVER a raw env value: EDEN_GATEWAY_JWT_SECRET_REF names an opaque vault://
// reference (environment.go) resolved through the dual-mode Vault secrets provider point-of-use, and
// zeroized immediately — it never reaches a log or a field. The dev counterpart is
// cmd/agentgateway-dev (the in-process Pool over fakes), which imports NO real bus and NO test fakes
// into THIS command.
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

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/natssse"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/natscontrol"
	"github.com/gophersys/eden/apps/agentgateway/internal/stateless"
)

// defaultAddress is the bind address when EDEN_GATEWAY_ADDRESS is unset.
const defaultAddress = ":8080"

// readHeaderTimeout bounds the request-header read (the SSE route is exempt — it is long-lived).
const readHeaderTimeout = 10 * time.Second

func main() {
	os.Exit(realMain())
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an exit code,
// so main's only statement is os.Exit (no defer skipped by a direct os.Exit — gocritic exitAfterDefer).
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

// run is the testable composition body: it reads the configuration from the environment ONCE (the
// configuration pattern), builds the dual-mode Vault secrets provider, resolves the dev-JWT signing
// key from its opaque vault:// reference (point-of-use, zeroized), dials the bus, builds the
// stateless gateway from the edenhttp spine + the natssse bridge + the natscontrol publisher, binds
// a listener, and serves until the context is canceled, then performs a graceful shutdown. A missing
// required value is a typed KindInvalid startup error naming the field (never echoing a value).
func run(ctx context.Context, logger *slog.Logger) error {
	configured, err := parseConfiguration(os.Getenv)
	if err != nil {
		return err
	}

	provider, err := buildSecretsProvider(&configured)
	if err != nil {
		return err
	}

	// Resolve the dev-JWT HMAC signing key from Vault ONCE at startup: the secret value is used to
	// construct the verifier and zeroized immediately (resolveVerifier owns the point-of-use scope) —
	// only the opaque reference is loggable, never the value.
	verifier, err := resolveVerifier(ctx, provider, secrets.Ref(configured.JWTSecretReference))
	if err != nil {
		return err
	}

	connection, jetStream, err := dialBus(configured.NATSURL)
	if err != nil {
		return err
	}
	defer connection.Close()

	gateway, err := build(configured, verifier, jetStream, connection, logAdapter{logger: logger})
	if err != nil {
		return err
	}

	listener, err := net.Listen("tcp", configured.Address)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway: bind listener", err)
	}

	logger.Info(
		"agentgateway: serving stateless NATS→SSE gateway",
		slog.String("address", listener.Addr().String()),
		slog.String("jwtSecretReference", configured.JWTSecretReference), // an opaque path, never a value
	)
	return serve(ctx, gateway.Handler(), listener)
}

// build wires the edenhttp spine (the dev-JWT identity gate) over the ALREADY-RESOLVED verifier, the
// natssse JetStream→SSE bridge, and the natscontrol publisher into the stateless.Gateway. PURE in the
// gateway sense (no listen, no goroutine, no secret resolution) — the JWT signing key was resolved +
// zeroized by run() before this is called; build only assembles the ports over the verifier.
func build(configured configuration, verifier *edenhttp.HMACVerifier, jetStream nats.JetStreamContext, connection *nats.Conn, logger edenhttp.Logger) (*stateless.Gateway, error) {
	spine, err := edenhttp.New(
		edenhttp.Config{},
		edenhttp.Deps{Verifier: verifier, Clock: systemClock{}, Logger: logger},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentgateway: build edenhttp spine", err)
	}
	bridge, err := natssse.New(
		natssse.Config{HeartbeatInterval: spine.HeartbeatInterval()},
		natssse.Deps{JetStream: jetStream, Clock: spine.Clock()},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway: build sse bridge", err)
	}
	control, err := natscontrol.New(connection)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway: build control publisher", err)
	}
	gateway, err := stateless.New(
		stateless.Config{EventsStream: configured.EventsStream},
		stateless.Deps{Spine: spine, Bridge: bridge, Control: control, Logger: logger},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentgateway: build stateless gateway", err)
	}
	return gateway, nil
}

// dialBus dials the NATS server (the configured URL, or the SDK default when empty) and derives a
// JetStream context.
//
//nolint:ireturn // nats.JetStreamContext is the vendor SDK's own interface; the composition returns it as the SDK vends it.
func dialBus(url string) (*nats.Conn, nats.JetStreamContext, error) {
	if url == "" {
		url = nats.DefaultURL
	}
	connection, err := nats.Connect(url, nats.Timeout(10*time.Second), nats.Name("agentgateway"))
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "agentgateway: dial nats", err)
	}
	jetStream, err := connection.JetStream()
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindUnavailable, "agentgateway: jetstream context", err)
	}
	return connection, jetStream, nil
}

// serve runs the HTTP server until ctx is canceled, then performs a graceful shutdown.
func serve(ctx context.Context, handler http.Handler, listener net.Listener) error {
	server := &http.Server{
		Handler:           handler,
		ReadHeaderTimeout: readHeaderTimeout,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}
	serveErr := make(chan error, 1)
	go func() { serveErr <- server.Serve(listener) }()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx) //nolint:errcheck // shutdown best-effort; the bus conn is closed by the deferred connection.Close.
		return nil
	case err := <-serveErr:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return errors.Wrap(errors.KindUnavailable, "agentgateway: serve", err)
	}
}

// systemClock is the production edenhttp.Clock (the wall clock; the app is the one place a real clock
// is read — the libraries stay pure).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }

// logAdapter adapts the command's *slog.Logger onto the narrow edenhttp.Logger port (the composition
// root owns the adaptation — edenhttp never depends on slog). A field is never a secret.
type logAdapter struct{ logger *slog.Logger }

// Info emits a structured info line.
func (a logAdapter) Info(message string, fields ...any) { a.logger.Info(message, fields...) }

// Error emits a structured error line.
func (a logAdapter) Error(message string, fields ...any) { a.logger.Error(message, fields...) }
