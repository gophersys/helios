// Command agentgateway is the PRODUCTION composition root for the STATELESS agentsession gateway
// (ADR-0022 #3). It mounts a COMBINED HTTP surface over one listener:
//
//   - the pod LIVE plane — the stateless NATS/JetStream→SSE bridge (internal/stateless): any replica
//     serves any pod's session via JetStream durable replay; it holds no per-session state. This owns
//     /sessions/{id}/events + /control|/prompt|/steer|/abort|/stop|/kill behind the edenhttp dev-JWT.
//   - the REST / RECORD plane — the FULL internal/gateway surface the SvelteKit UI consumes
//     (internal/prodserve): POST /product/propose (a real claude turn), POST/GET /projects,
//     /projects/{id}/insight, GET/PUT /agent-configs, and POST/GET /sessions. It is wired over REAL
//     cluster substrates — a Postgres-backed orchestrator DesiredStore (the record plane) + the
//     dashboard/Settings Postgres stores + the dual-mode Vault provider in token-file mode. STATELESS:
//     POST /sessions writes DESIRED state and returns; the separately-deployed orchestrator reconciles
//     the record into a pod, whose live plane is served by the bridge above. No workload runs here.
//
// The full REST plane is wired only when EDEN_GATEWAY_DATABASE_DSN_REF is set (FullSurfaceConfigured);
// absent it, the command serves the bridge ALONE (the pre-v0.1.7 behavior), so a partial rollout
// degrades honestly rather than failing to boot. The DSN and the JWT signing key are NEVER raw env
// values: each is an opaque vault:// reference (environment.go) resolved through the Vault provider
// point-of-use and zeroized immediately — never a log or a field. The dev counterpart is
// cmd/agentgateway-dev / the live-local sibling internal/liveserve (which imports test fakes and is
// NOT the production path); THIS command imports no test fakes.
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

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/natscontrol"
	"github.com/gophersys/eden/apps/agentgateway/internal/prodserve"
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

	bridge, err := build(&configured, verifier, jetStream, connection, logAdapter{logger: logger})
	if err != nil {
		return err
	}

	// The FULL REST/record plane (prodserve) is wired only when the DSN reference is configured; absent
	// it the command serves the NATS→SSE bridge ALONE. The DSN is resolved point-of-use (a secret: it
	// carries the Postgres password) and never logged; the built gateway owns the durable pools and is
	// drained on shutdown via the returned teardown.
	handler := bridge.Handler()
	if configured.FullSurfaceConfigured() {
		restGateway, teardown, restErr := buildRestPlane(ctx, &configured, provider, logAdapter{logger: logger})
		if restErr != nil {
			return restErr
		}
		defer func() {
			shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			_ = teardown(shutdownCtx) //nolint:errcheck // best-effort store drain on shutdown; the process is exiting.
		}()
		handler = combinedHandler(bridge, restGateway)
	}

	listener, err := net.Listen("tcp", configured.Address)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway: bind listener", err)
	}

	logger.Info(
		"agentgateway: serving agentsession gateway",
		slog.String("address", listener.Addr().String()),
		slog.String("jwtSecretReference", configured.JWTSecretReference), // an opaque path, never a value
		slog.Bool("fullSurface", configured.FullSurfaceConfigured()),
	)
	return serve(ctx, handler, listener)
}

// buildRestPlane resolves the Postgres DSN from its opaque Vault reference (point-of-use, never
// logged) and builds the STATELESS full REST/record-plane gateway (prodserve) over the real cluster
// substrates. It returns the gateway, the teardown that drains its owned pools, and a wrapped error.
func buildRestPlane(ctx context.Context, configured *configuration, provider secrets.Provider, logger prodserve.Logger) (*gateway.Gateway, func(context.Context) error, error) {
	dsn, err := resolveDSN(ctx, provider, secrets.Ref(configured.DatabaseDSNReference))
	if err != nil {
		return nil, nil, err
	}
	restGateway, teardown, err := prodserve.BuildProductionGateway(prodserve.Config{
		Provider:            provider,
		DatabaseURL:         dsn,
		CredentialReference: configured.CredentialReference,
		Harness:             configured.Harness,
		Model:               configured.Model,
		Workspace:           configured.Workspace,
		Logger:              logger,
	})
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindOf(err), "agentgateway: build production rest plane", err)
	}
	return restGateway, teardown, nil
}

// combinedHandler composes the two planes onto ONE http.ServeMux: the stateless NATS→SSE bridge owns
// the pod LIVE-plane routes (events + the control verbs, behind the dev-JWT), and the full prodserve
// gateway owns EVERYTHING ELSE via the "/" catch-all (the REST/record plane). Go 1.22's ServeMux
// gives the specific bridge patterns precedence over the catch-all, so a pod-live request routes to
// the bridge (JetStream replay / control publish) and every REST request falls through to the full
// gateway — one surface, no per-route ambiguity. The bridge's own /healthz is a specific pattern too,
// so liveness stays the bridge's unauthenticated probe.
func combinedHandler(bridge *stateless.Gateway, restGateway *gateway.Gateway) http.Handler {
	return composeMux(bridge.Handler(), restGateway.Handler())
}

// livePlanePatterns is the closed set of pod LIVE-plane routes the stateless NATS→SSE bridge owns —
// the JetStream events stream + the NATS control verbs. Everything NOT in this set is the REST/record
// plane the full gateway serves via the "/" catch-all. Kept as ONE named list so composeMux and its
// test agree on the exact bridge surface (10 §9: one home).
var livePlanePatterns = []string{
	"GET /sessions/{id}/events",
	"POST /sessions/{id}/control",
	"POST /sessions/{id}/prompt",
	"POST /sessions/{id}/steer",
	"POST /sessions/{id}/abort",
	"POST /sessions/{id}/stop",
	"POST /sessions/{id}/kill",
}

// composeMux is the pure route-composition seam combinedHandler delegates to (so a test drives it
// with cheap stub handlers, no real substrates): the bridge handler owns livePlanePatterns; the rest
// handler owns everything else via the "/" catch-all. Go 1.22's ServeMux gives the specific bridge
// patterns precedence over the catch-all, so a pod-live request routes to the bridge and every REST
// request falls through — one surface, no per-route ambiguity. A pattern conflict would panic HERE at
// registration, so the composition is proven conflict-free the instant it is built.
func composeMux(bridgeHandler, restHandler http.Handler) *http.ServeMux {
	mux := http.NewServeMux()
	for _, pattern := range livePlanePatterns {
		mux.Handle(pattern, bridgeHandler)
	}
	// Everything else — the REST/record plane (propose, projects, insight, agent-configs, sessions
	// create/list/get, workspace, transcript, editor, healthz) — falls through to the full gateway.
	mux.Handle("/", restHandler)
	return mux
}

// build wires the edenhttp spine (the dev-JWT identity gate) over the ALREADY-RESOLVED verifier, the
// natssse JetStream→SSE bridge, and the natscontrol publisher into the stateless.Gateway. PURE in the
// gateway sense (no listen, no goroutine, no secret resolution) — the JWT signing key was resolved +
// zeroized by run() before this is called; build only assembles the ports over the verifier.
func build(configured *configuration, verifier *edenhttp.HMACVerifier, jetStream nats.JetStreamContext, connection *nats.Conn, logger edenhttp.Logger) (*stateless.Gateway, error) {
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
	statelessGateway, err := stateless.New(
		stateless.Config{EventsStream: configured.EventsStream},
		stateless.Deps{Spine: spine, Bridge: bridge, Control: control, Logger: logger},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentgateway: build stateless gateway", err)
	}
	return statelessGateway, nil
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
