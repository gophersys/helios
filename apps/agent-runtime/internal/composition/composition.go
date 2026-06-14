// Package composition is the agent-runtime app's composition root: it reads the pod's environment,
// dials the REAL NATS/JetStream bus, builds the observability provider + the agentsession harness
// factory, constructs the agentruntime sidecar, serves its kubelet HTTP probes, and runs it as PID-1
// until a signal or a control verb terminates it. The kernel/library code owns all behavior; this
// package owns only the wiring (the listener, the NATS dial, the env parse, graceful shutdown).
package composition

import (
	"context"
	"log/slog"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/natsbus"
	"github.com/gophersys/libs/go/agentruntime/otelobserver"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// Environment is the parsed pod environment (the configuration pattern: read once at the edge). A
// missing required value is a typed startup error, not a silent default.
type Environment struct {
	AgentID       string // EDEN_AGENT_ID — the agent this pod runs (scopes the three subjects)
	NATSURL       string // EDEN_NATS_URL — the bus to dial; "" == nats.DefaultURL
	Workspace     string // EDEN_WORKSPACE — the harness CWD (the provisioned workspace)
	Harness       string // EDEN_HARNESS — the adapter key (claude-code|omp|codex)
	Model         string // EDEN_MODEL — the model id passed to the harness
	CredentialRef string // EDEN_CREDENTIAL_REF — the opaque secrets.Reference for the harness credential
	ProbeAddr     string // EDEN_PROBE_ADDR — the HTTP probe listener; "" == ":8081"
	InitialPrompt string // EDEN_INITIAL_PROMPT — optional seed prompt (the batch path)
}

// LoadEnvironment reads the pod environment. Only EDEN_AGENT_ID is strictly required to construct;
// the harness fields are required only when a real session is opened (Run), so a probe-only smoke
// boot needs just the id.
func LoadEnvironment() Environment {
	return Environment{
		AgentID:       os.Getenv("EDEN_AGENT_ID"),
		NATSURL:       os.Getenv("EDEN_NATS_URL"),
		Workspace:     os.Getenv("EDEN_WORKSPACE"),
		Harness:       os.Getenv("EDEN_HARNESS"),
		Model:         os.Getenv("EDEN_MODEL"),
		CredentialRef: os.Getenv("EDEN_CREDENTIAL_REF"),
		ProbeAddr:     os.Getenv("EDEN_PROBE_ADDR"),
		InitialPrompt: os.Getenv("EDEN_INITIAL_PROMPT"),
	}
}

// systemClock is the production agentruntime.Clock / agentsession.Clock (the wall clock; the app is
// the one place a real clock is read — the libraries stay pure).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }

// Run is the testable composition body: it dials the bus, builds the sidecar + probes, and runs the
// PID-1 loop until ctx is canceled or a control verb terminates it. It returns the process exit code
// mapped from the typed TerminationReason. The probeOnly flag boots ONLY the probe server (no NATS,
// no harness) for the smoke test — the bootstrap-phase verification that the binary serves /live and
// shuts down gracefully on SIGTERM without a live bus or an authenticated harness.
//
//nolint:gocritic // Environment is the frozen, copyable pod-environment input (the configuration pattern); the entry takes it by value.
func Run(ctx context.Context, logger *slog.Logger, environment Environment, probeOnly bool) int {
	if environment.AgentID == "" {
		logger.Error("agent-runtime: EDEN_AGENT_ID is required")
		return 2
	}
	if probeOnly {
		return runProbeOnly(ctx, logger, &environment)
	}

	runtime, cleanup, err := build(logger, &environment)
	if err != nil {
		logger.Error("agent-runtime: composition failed", slog.String("error", err.Error()))
		return 2
	}
	defer cleanup()

	probeServer := startProbeServer(ctx, logger, &environment, runtime.ProbeHandler())
	defer shutdownProbeServer(logger, probeServer)

	reason, runErr := runtime.Run(ctx)
	if runErr != nil {
		logger.Error("agent-runtime: run faulted", slog.String("reason", reason.String()), slog.String("error", runErr.Error()))
		return 1
	}
	logger.Info("agent-runtime: stopped", slog.String("reason", reason.String()))
	if reason.IsGraceful() {
		return 0
	}
	return 1
}

// build wires the real adapters into an agentruntime.Runtime: the NATS/JetStream bus, the
// observability-backed observer, and the agentsession factory over the configured harness adapter. It
// returns the runtime + a cleanup that closes the NATS connection (the sidecar owns its conn).
func build(logger *slog.Logger, environment *Environment) (*agentruntime.Runtime, func(), error) {
	connection, jetStream, err := dialBus(environment)
	if err != nil {
		return nil, nil, err
	}
	bus, err := natsbus.New(
		natsbus.Config{EnsureStream: true},
		natsbus.Deps{Conn: connection, JetStream: jetStream},
	)
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "agent-runtime: build natsbus", err)
	}

	provider, err := observability.New(
		observability.Config{ServiceName: "agent-runtime", Environment: os.Getenv("EDEN_ENVIRONMENT")},
		observability.Deps{Exporter: stdoutExporter{logger: logger}, Clock: systemClock{}},
	)
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "agent-runtime: build observability", err)
	}

	factory, err := buildSessionFactory(environment, provider)
	if err != nil {
		connection.Close()
		return nil, nil, err
	}

	runtime, err := agentruntime.New(
		agentruntime.Config{
			AgentID:       agentruntime.AgentID(environment.AgentID),
			Spec:          buildSpec(environment),
			InitialPrompt: environment.InitialPrompt,
		},
		agentruntime.Deps{
			Sessions: factory,
			Bus:      bus,
			Observer: otelobserver.New(provider),
			Clock:    systemClock{},
		},
	)
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindInvalid, "agent-runtime: construct runtime", err)
	}
	cleanup := func() { connection.Close() }
	return runtime, cleanup, nil
}

// dialBus dials the NATS server and derives a JetStream context.
//
//nolint:ireturn // nats.JetStreamContext is the vendor SDK's own interface; the composition returns it as the SDK vends it.
func dialBus(environment *Environment) (*nats.Conn, nats.JetStreamContext, error) {
	url := environment.NATSURL
	if url == "" {
		url = nats.DefaultURL
	}
	connection, err := nats.Connect(url, nats.Timeout(10*time.Second), nats.Name("agent-runtime:"+environment.AgentID))
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "agent-runtime: dial nats", err)
	}
	jetStream, err := connection.JetStream()
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindUnavailable, "agent-runtime: jetstream context", err)
	}
	return connection, jetStream, nil
}

// buildSessionFactory wires the REAL agentsession.Pool: the configured harness adapter (claude-code |
// omp), the secrets Mediator over the production Vault backend (ADR-0022 #1, the credential resolved
// server-side from the opaque Reference), an in-process Transcript (Seq assignment; the DURABLE
// stream is the JetStream publish the sidecar performs), and the system clock. The adapters do their
// I/O lazily on Open, so build stays cheap.
//
//nolint:ireturn // returns the agentsession.Factory port the sidecar holds (the frozen surface).
func buildSessionFactory(environment *Environment, _ observability.Provider) (agentsession.Factory, error) {
	provider, err := buildSecretsProvider()
	if err != nil {
		return nil, err
	}
	harness := environment.Harness
	if harness == "" {
		harness = "claude-code"
	}
	routing := map[agentsession.RouteKey]agentsession.Route{
		{Role: "assistant"}: {Harness: harness, Model: environment.Model},
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: routing},
		agentsession.Deps{
			Adapters: map[string]agentsession.Adapter{
				"claude-code": claudeadapter.New(),
				"omp":         ompadapter.New(),
			},
			Secrets:    provider,
			Transcript: newTranscript(),
			Clock:      systemClock{},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build agentsession factory", err)
	}
	return pool, nil
}

// buildSecretsProvider builds the production secrets Mediator over the Vault backend. The mode is
// chosen by EDEN_VAULT_MODE: "token-file" (the kubernetes ServiceAccount path) else userpass (local).
//
//nolint:ireturn // returns the secrets.Provider port (the frozen surface the factory holds).
func buildSecretsProvider() (secrets.Provider, error) {
	address := os.Getenv("VAULT_ADDR")
	if address == "" {
		address = "http://127.0.0.1:8200"
	}
	var adapter secrets.Provider
	var err error
	if os.Getenv("EDEN_VAULT_MODE") == "token-file" {
		adapter, err = vaultadapter.New(
			vaultadapter.Config{Address: address, Mode: vaultadapter.ModeTokenFile, TokenFilePath: os.Getenv("EDEN_VAULT_TOKEN_FILE")},
			vaultadapter.Dependencies{},
		)
	} else {
		adapter, err = vaultadapter.New(
			vaultadapter.Config{Address: address, Mode: vaultadapter.ModeUserpass},
			vaultadapter.Dependencies{Username: os.Getenv("VAULT_USERNAME"), Password: os.Getenv("VAULT_PASSWORD")},
		)
	}
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build vault backend", err)
	}
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build secrets mediator", err)
	}
	return mediator, nil
}

// buildSpec builds the agentsession.Spec from the environment (the workspace, the routing key, and the
// opaque credential reference resolved server-side by agentsession).
func buildSpec(environment *Environment) agentsession.Spec {
	return agentsession.Spec{
		Workspace:  environment.Workspace,
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(environment.CredentialRef),
	}
}

// startProbeServer binds the kubelet probe listener and serves the handler in the background. The
// listener address is EDEN_PROBE_ADDR or :8081.
func startProbeServer(ctx context.Context, logger *slog.Logger, environment *Environment, handler http.Handler) *http.Server {
	addr := environment.ProbeAddr
	if addr == "" {
		addr = ":8081"
	}
	server := &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}
	go func() {
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("agent-runtime: probe server error", slog.String("error", err.Error()))
		}
	}()
	logger.Info("agent-runtime: probe server listening", slog.String("addr", addr))
	return server
}

// shutdownProbeServer gracefully stops the probe listener (bounded).
func shutdownProbeServer(logger *slog.Logger, server *http.Server) {
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		logger.Warn("agent-runtime: probe server shutdown error", slog.String("error", err.Error()))
	}
}

// runProbeOnly boots ONLY the probe server (no NATS, no harness) and blocks until ctx is canceled —
// the bootstrap smoke path proving the binary serves /live and shuts down gracefully on SIGTERM
// without a live bus or an authenticated harness.
func runProbeOnly(ctx context.Context, logger *slog.Logger, environment *Environment) int {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /live", func(writer http.ResponseWriter, _ *http.Request) {
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write([]byte("live agents=0\n")) //nolint:errcheck // probe write failure is a dead client socket.
	})
	server := startProbeServer(ctx, logger, environment, mux)
	defer shutdownProbeServer(logger, server)
	logger.Info("agent-runtime: probe-only smoke mode (no bus, no harness); awaiting signal")
	<-ctx.Done()
	logger.Info("agent-runtime: shutdown signal received")
	return 0
}

// stdoutExporter is the production observability.Exporter: it renders each Record as a structured log
// line. It is the app's outbound telemetry boundary (a real OTLP exporter slots here later).
type stdoutExporter struct{ logger *slog.Logger }

// Export renders each record as an info log line (best-effort; never blocks the run loop on I/O of
// consequence — slog's handler is synchronous but cheap to stdout).
func (e stdoutExporter) Export(_ context.Context, records []observability.Record) error {
	for index := range records {
		e.logger.Info("telemetry", slog.Int("record", index), slog.Int("total", len(records)))
	}
	return nil
}
