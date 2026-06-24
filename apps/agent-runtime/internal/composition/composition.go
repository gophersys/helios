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
	Role          string // EDEN_ROLE — the session's agentconfiguration role (assistant|supervisor|...); "" == "assistant"
	Phase         string // EDEN_PHASE — the SDLC phase the session runs in (implement|review|...); "" == interactive
	CredentialRef string // EDEN_CREDENTIAL_REF — the opaque secrets.Reference for the harness credential
	ProbeAddr     string // EDEN_PROBE_ADDR — the HTTP probe listener; "" == ":8081"
	InitialPrompt string // EDEN_INITIAL_PROMPT — optional seed prompt (the batch path)

	// WorkdirRepo / WorkdirRepoCred / WorkdirRepoRef drive the IN-POD clone-on-boot path (workdir.go,
	// the in-pod analog of the host-side projectcreate.Materializer). WorkdirRepo is the clone URL of
	// the seeded project repo; "" == NO in-pod clone (the existing assistant/probe boot, byte-unchanged
	// — prepareWorkdir returns Workspace verbatim). WorkdirRepoCred is the OPAQUE clone-credential
	// reference (resolved server-side, never the value); WorkdirRepoRef is an optional branch/tag.
	WorkdirRepo     string // EDEN_WORKDIR_REPO — the seeded project clone URL; "" == no in-pod clone
	WorkdirRepoCred string // EDEN_WORKDIR_REPO_CRED — the OPAQUE clone-credential reference
	WorkdirRepoRef  string // EDEN_WORKDIR_REPO_REF — optional branch/tag to check out; "" == default branch
}

// LoadEnvironment reads the pod environment. Only EDEN_AGENT_ID is strictly required to construct;
// the harness fields are required only when a real session is opened (Run), so a probe-only smoke
// boot needs just the id.
func LoadEnvironment() Environment {
	return Environment{
		AgentID:         os.Getenv("EDEN_AGENT_ID"),
		NATSURL:         os.Getenv("EDEN_NATS_URL"),
		Workspace:       os.Getenv("EDEN_WORKSPACE"),
		Harness:         os.Getenv("EDEN_HARNESS"),
		Model:           os.Getenv("EDEN_MODEL"),
		Role:            os.Getenv("EDEN_ROLE"),
		Phase:           os.Getenv("EDEN_PHASE"),
		CredentialRef:   os.Getenv("EDEN_CREDENTIAL_REF"),
		ProbeAddr:       os.Getenv("EDEN_PROBE_ADDR"),
		InitialPrompt:   os.Getenv("EDEN_INITIAL_PROMPT"),
		WorkdirRepo:     os.Getenv(envWorkdirRepo),
		WorkdirRepoCred: os.Getenv(envWorkdirRepoCredential),
		WorkdirRepoRef:  os.Getenv(envWorkdirRepoRef),
	}
}

// Role keys (agentconfiguration RouteKey.Role values, 02 §5). The session's role selects the
// (harness, model) Route. The default is the interactive assistant; a supervisor session
// (EDEN_ROLE=supervisor) routes to the strongest reasoning model with a larger budget.
const (
	roleAssistant  = "assistant"
	roleSupervisor = "supervisor"
)

// supervisorModel is the model id the supervisor route resolves to: opus-4.8, the strongest
// reasoning model. The id is the opaque value passed through to the claude-code harness (the
// agentsession Route.Model carries it verbatim). The pinned CLI VERSION that speaks to it lives in
// harnesses/versions.env (CLAUDE_CODE_VERSION, ADR-0021); this is the model selector, not the CLI pin.
const supervisorModel = "claude-opus-4-8"

// supervisorBudget is the larger ceiling the supervisor route launches with: a supervisor reasons
// over more turns and spends more than an interactive assistant turn, so its soft cap is raised
// (the engine's TokenBudget remains the authoritative hard cap, 02 §2). The assistant route keeps
// the environment/unbounded default.
var supervisorBudget = agentsession.Budget{
	MaxCostMicros: 2_000_000, // ~$2.00 soft ceiling for a supervisor adjudication/planning span
	MaxTurns:      40,        // a supervisor plans/reviews over more turns than a single assistant reply
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

	runtime, cleanup, err := build(ctx, logger, &environment)
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
// returns the runtime + a cleanup that closes the NATS connection (the sidecar owns its conn). The
// ctx bounds the one startup network side effect — provisioning the durable events stream.
func build(ctx context.Context, logger *slog.Logger, environment *Environment) (*agentruntime.Runtime, func(), error) {
	connection, jetStream, err := dialBus(environment)
	if err != nil {
		return nil, nil, err
	}
	bus, err := natsbus.New(
		natsbus.Config{},
		natsbus.Deps{Conn: connection, JetStream: jetStream},
	)
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "agent-runtime: build natsbus", err)
	}
	// Provision the durable events stream explicitly (New is pure; this is the one startup side
	// effect). Idempotent — a stream already provisioned out-of-band is a no-op.
	if ensureErr := bus.EnsureStream(ctx); ensureErr != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindUnavailable, "agent-runtime: ensure events stream", ensureErr)
	}

	provider, err := observability.New(
		observability.Config{ServiceName: "agent-runtime", Environment: os.Getenv("EDEN_ENVIRONMENT")},
		observability.Deps{Exporter: stdoutExporter{logger: logger}, Clock: systemClock{}},
	)
	if err != nil {
		connection.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "agent-runtime: build observability", err)
	}

	// In-pod clone-on-boot (workdir.go): when EDEN_WORKDIR_REPO is set, clone the seeded project repo
	// + overlay the supervisor .claude manual INTO the pod and re-point the harness CWD at the clone.
	// GATED on a non-empty EDEN_WORKDIR_REPO — a NO-OP returning environment.Workspace verbatim
	// otherwise, so the existing assistant/probe boot is byte-unchanged. It runs BEFORE the session
	// factory so the Advisor's ReviewerWorkspace + the Spec.Workspace both observe the cloned CWD.
	secretsProvider, err := buildSecretsProvider()
	if err != nil {
		connection.Close()
		return nil, nil, err
	}
	workDir, err := newWorkdirCloner(secretsProvider).prepareWorkdir(ctx, environment)
	if err != nil {
		connection.Close()
		return nil, nil, err
	}
	environment.Workspace = workDir

	factory, err := buildSessionFactory(environment, provider, secretsProvider)
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

// buildSessionFactory wires the REAL agentsession.Pool: the configured harness adapters (claude-code
// | omp), the secrets Mediator over the production Vault backend (ADR-0022 #1, the credential
// resolved server-side from the opaque Reference), an in-process Transcript (Seq assignment; the
// DURABLE stream is the JetStream publish the sidecar performs), the system clock, AND the permission
// Advisor (the ratified out-of-grant chain: an out-of-grant tool request the human/policy did not
// resolve consults the bounded reviewer advisor before the default-deny terminal). The adapters do
// their I/O lazily on Open, so build stays cheap.
//
// The Advisor opens its bounded, tool-less reviewer session through a SEPARATE Pool (its Sessions
// factory) so the wiring has no cycle: the reviewer pool carries the SAME adapters/secrets/transcript
// but NO advisor, and the advisor never recurses (the reviewer's Spec denies every out-of-grant
// request in-process). The main Pool then receives the constructed advisor as Deps.Advisor.
//
// secretsProvider is built ONCE in build (the in-pod clone and the session factory share one Vault
// Mediator) and threaded in, so the pod dials Vault once — the clone credential and the harness
// credential resolve through the SAME server-side seam.
//
//nolint:ireturn // returns the agentsession.Factory port the sidecar holds (the frozen surface).
func buildSessionFactory(environment *Environment, provider observability.Provider, secretsProvider secrets.Provider) (agentsession.Factory, error) {
	adapters, err := buildAdapters()
	if err != nil {
		return nil, err
	}
	routing := buildRouting(environment)

	// The reviewer Pool the Advisor opens its bounded reviewer session through. It shares the
	// adapters/secrets but carries NO advisor — the reviewer denies every out-of-grant request in
	// its Spec, so there is no advisor recursion and no cycle in the wiring.
	reviewerPool, err := agentsession.New(
		agentsession.Config{Routing: routing},
		agentsession.Deps{
			Adapters:   adapters,
			Secrets:    secretsProvider,
			Transcript: newTranscript(),
			Clock:      systemClock{},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build reviewer agentsession pool", err)
	}

	advisor, err := buildAdvisor(environment, provider, reviewerPool)
	if err != nil {
		return nil, err
	}

	pool, err := agentsession.New(
		agentsession.Config{Routing: routing},
		agentsession.Deps{
			Adapters:   adapters,
			Secrets:    secretsProvider,
			Transcript: newTranscript(),
			Clock:      systemClock{},
			Advisor:    advisor,
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build agentsession factory", err)
	}
	return pool, nil
}

// buildAdapters constructs the per-harness agentsession.Adapter set the Pool routes Open to. The
// adapters are pure (no I/O until Spawn), so this is cheap and shared by the reviewer + main pools.
func buildAdapters() (map[string]agentsession.Adapter, error) {
	claudeAdapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build claude adapter", err)
	}
	ompAdapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agent-runtime: build omp adapter", err)
	}
	return map[string]agentsession.Adapter{
		"claude-code": claudeAdapter,
		"omp":         ompAdapter,
	}, nil
}

// buildRouting builds the agentconfiguration projection (RouteKey -> Route, 02 §5) the Pool resolves
// each Open against. The assistant route honors the pod's EDEN_HARNESS/EDEN_MODEL (the interactive
// default); the supervisor route pins the claude-code harness at opus-4.8 (the strongest reasoning
// model) so a supervisor session always lands on the strong reasoner regardless of the pod's
// per-session harness/model. The advisor's reviewer session resolves through the SAME table — it is
// opened under whichever role the pod runs as (the reviewer Spec carries the no-tools guarantee).
func buildRouting(environment *Environment) map[agentsession.RouteKey]agentsession.Route {
	harness := environment.Harness
	if harness == "" {
		harness = "claude-code"
	}
	return map[agentsession.RouteKey]agentsession.Route{
		{Role: roleAssistant}:  {Harness: harness, Model: environment.Model},
		{Role: roleSupervisor}: {Harness: "claude-code", Model: supervisorModel},
	}
}

// buildAdvisor constructs the agentruntime permission Advisor wired into agentsession.Deps.Advisor
// (the ratified out-of-grant chain). It routes its bounded reviewer session through the supervisor
// route (the strong reasoner adjudicates a permission request well), runs the reviewer in the pod's
// own workspace (the reviewer has NO write grants — read-only reasoning), and resolves the same
// opaque credential reference server-side. The reviewer's bounds (wall-clock + cost + turns) default
// inside NewAdvisor, so a wedged reviewer is a deny, never a hang.
//
// The advisor is built only when a credential reference is configured: the reviewer is a REAL harness
// session that needs a resolvable credential, so a credential-less boot wires NO advisor (returns a
// nil INTERFACE — not a typed-nil pointer, which would defeat agentsession's nil check), and the
// out-of-grant chain degrades to Spec.OnPermission / default-deny with NO regression
// (agentsession.Deps.Advisor is the OPTIONAL port). This preserves the existing credential-less
// boot path instead of moving its failure earlier to composition time. It returns the
// agentsession.PermissionAdvisor port (not the concrete *Advisor) precisely so the absent case is a
// true nil interface.
//
//nolint:ireturn // returns the agentsession.PermissionAdvisor port so the absent case is a TRUE nil interface (a typed-nil *Advisor would make Deps.Advisor non-nil and NPE on Advise) — the nil-interface guarantee is the reason this returns the port, not the concrete type.
func buildAdvisor(environment *Environment, provider observability.Provider, sessions agentsession.Factory) (agentsession.PermissionAdvisor, error) {
	// Guard the empty string BEFORE secrets.Ref: Ref panics on an empty reference (it is the
	// bare-name ergonomic constructor), so an unset EDEN_CREDENTIAL_REF must short-circuit to the
	// nil-advisor degrade here rather than reach Ref.
	if environment.CredentialRef == "" {
		return nil, nil //nolint:nilnil // an absent credential wires NO advisor; the chain degrades to OnPermission/default-deny (the optional port's documented nil case), not an error.
	}
	advisor, err := agentruntime.NewAdvisor(
		agentruntime.AdvisorConfig{
			ReviewerRoute:      agentsession.RouteKey{Role: roleSupervisor},
			ReviewerWorkspace:  environment.Workspace,
			ReviewerCredential: secrets.Ref(environment.CredentialRef),
		},
		agentruntime.AdvisorDeps{
			Sessions: sessions,
			Observer: otelobserver.New(provider),
			Clock:    systemClock{},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agent-runtime: build permission advisor", err)
	}
	return advisor, nil
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
	if vaultadapter.ParseMode(os.Getenv("EDEN_VAULT_MODE")) == vaultadapter.ModeTokenFile {
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

// buildSpec builds the agentsession.Spec from the environment (the workspace, the routing key derived
// from EDEN_ROLE/EDEN_PHASE, the per-role Budget, and the opaque credential reference resolved
// server-side by agentsession). The Role is NO LONGER hardcoded: it is read from EDEN_ROLE
// (defaulting to "assistant") so the same binary boots an assistant or a supervisor session; a
// supervisor route lands on opus-4.8 with a larger Budget.
func buildSpec(environment *Environment) agentsession.Spec {
	role := resolveRole(environment.Role)
	return agentsession.Spec{
		Workspace:  environment.Workspace,
		Routing:    agentsession.RouteKey{Role: role, Phase: environment.Phase},
		Budget:     budgetForRole(role),
		Credential: secrets.Ref(environment.CredentialRef),
	}
}

// resolveRole maps the EDEN_ROLE env value to a routing role. The empty/unset value defaults to the
// interactive assistant (the existing behavior); "supervisor" selects the supervisor route. An
// unrecognized value is passed through verbatim so a future agentconfiguration role routes without a
// composition-root change (the Pool's resolveRoute returns a typed RouteError if no route is
// registered — fail fast and loud, never a silent assistant fallback).
func resolveRole(envRole string) string {
	if envRole == "" {
		return roleAssistant
	}
	return envRole
}

// budgetForRole returns the soft Budget ceiling for a role: the supervisor gets the larger ceiling;
// every other role keeps the zero Budget (environment/engine-bounded, the existing assistant
// behavior). The engine's TokenBudget remains the single authoritative hard cap (02 §2).
func budgetForRole(role string) agentsession.Budget {
	if role == roleSupervisor {
		return supervisorBudget
	}
	return agentsession.Budget{}
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
