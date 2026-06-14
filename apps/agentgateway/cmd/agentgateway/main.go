// Command agentgateway is the PRODUCTION composition root for the stateless agentsession gateway
// (ADR-0022 #3): it dials the REAL NATS/JetStream bus, builds the edenhttp dev-JWT spine (the
// EDEN_GATEWAY_JWT_SECRET-signed identity gate — behind auth even locally), the natssse JetStream→SSE
// bridge, and the natscontrol publisher, wires them onto the stateless.Gateway handler, and serves
// it over HTTP until a signal. The gateway is STATELESS — any replica serves any session via
// JetStream durable replay; it holds no per-session state.
//
// The kernel/library code owns all behavior; this command owns only the wiring (the listener, the
// NATS dial, the env parse, the JWT secret, graceful shutdown). The dev counterpart is
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

// run is the testable composition body: it dials the bus, builds the stateless gateway from the
// edenhttp spine + the natssse bridge + the natscontrol publisher, binds a listener, and serves until
// the context is canceled, then performs a graceful shutdown. Every required value is read from the
// environment ONCE here (the configuration pattern); a missing one is a typed startup error.
func run(ctx context.Context, logger *slog.Logger) error {
	secret := os.Getenv("EDEN_GATEWAY_JWT_SECRET")
	if secret == "" {
		return errors.New(errors.KindInvalid, "agentgateway: EDEN_GATEWAY_JWT_SECRET is required (the gateway is behind auth even locally)")
	}

	connection, jetStream, err := dialBus()
	if err != nil {
		return err
	}
	defer connection.Close()

	gateway, err := build(secret, jetStream, connection, logAdapter{logger: logger})
	if err != nil {
		return err
	}

	address := os.Getenv("EDEN_GATEWAY_ADDRESS")
	if address == "" {
		address = defaultAddress
	}
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway: bind listener", err)
	}

	logger.Info("agentgateway: serving stateless NATS→SSE gateway", slog.String("address", listener.Addr().String()))
	return serve(ctx, gateway.Handler(), listener)
}

// build wires the edenhttp spine (the dev-JWT identity gate), the natssse JetStream→SSE bridge, and
// the natscontrol publisher into the stateless.Gateway. PURE in the gateway sense (no listen, no
// goroutine) — only the JWT verifier + the bridge + the adapter are constructed.
func build(secret string, jetStream nats.JetStreamContext, connection *nats.Conn, logger edenhttp.Logger) (*stateless.Gateway, error) {
	verifier, err := edenhttp.NewHMACVerifier(secret)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentgateway: build jwt verifier", err)
	}
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
		stateless.Config{EventsStream: os.Getenv("EDEN_GATEWAY_EVENTS_STREAM")},
		stateless.Deps{Spine: spine, Bridge: bridge, Control: control, Logger: logger},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentgateway: build stateless gateway", err)
	}
	return gateway, nil
}

// dialBus dials the NATS server (EDEN_NATS_URL or the default) and derives a JetStream context.
//
//nolint:ireturn // nats.JetStreamContext is the vendor SDK's own interface; the composition returns it as the SDK vends it.
func dialBus() (*nats.Conn, nats.JetStreamContext, error) {
	url := os.Getenv("EDEN_NATS_URL")
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
