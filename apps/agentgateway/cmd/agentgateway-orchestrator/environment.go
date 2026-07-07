package main

import (
	"context"
	"log/slog"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"k8s.io/client-go/kubernetes"
	coordinationv1client "k8s.io/client-go/kubernetes/typed/coordination/v1"
	corev1client "k8s.io/client-go/kubernetes/typed/core/v1"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
)

// serviceName is the OTel service.name the orchestrator role emits telemetry under.
const serviceName = "agentgateway-orchestrator"

// substrateKubernetes is the EDEN_WORKSPACE_SUBSTRATE wire VALUE that selects the
// namespace-per-workspace kubernetes adapter (the manifest sets it). Any other value (including
// empty) folds to the docker-first zero default (orchestratorservice.SubstrateDocker) — the same
// zero-docker rule the service enforces, kept in ONE place here at the edge.
const substrateKubernetes = "kubernetes"

// defaultAddress is the health-probe bind address when EDEN_ORCHESTRATOR_ADDRESS is unset. It
// matches the deployment's containerPort + readiness/liveness httpGet port (:8080).
const defaultAddress = ":8080"

// defaultHarness is the supervisor harness when EDEN_HARNESS is unset (the account default is
// claude-code — the standing Opus directive routes the supervisor to it at the Opus model).
const defaultHarness = "claude-code"

// readHeaderTimeout bounds the health server's request-header read (there is no long-lived route
// here — the orchestrator role serves only the liveness probe).
const readHeaderTimeout = 10 * time.Second

// shutdownTimeout bounds the graceful drain of the reconcile loop + the health server on a signal.
const shutdownTimeout = 30 * time.Second

// configuration is the fully-resolved composition input read ONCE from the environment (the
// configuration pattern). It holds NO live handles and NO secret VALUE — the harness credential is
// the opaque CredentialReference (vault://…) resolved server-side at agentsession.Open. run() builds
// the live ports from it; parseConfiguration is the pure env→configuration seam the unit test drives.
type configuration struct {
	// Substrate selects the workspaceprovider adapter the reconcile loop provisions through: the
	// kubernetes namespace-per-workspace adapter (EDEN_WORKSPACE_SUBSTRATE=kubernetes) or the
	// docker-first zero default. The orchestrator ROLE deployment always sets kubernetes.
	Substrate orchestratorservice.Substrate
	// LabelNamespace scopes this orchestrator's ownership domain (the per-project namespace-name
	// prefix + the eden.* labels), from EDEN_LABEL_NAMESPACE.
	LabelNamespace string
	// DatabaseURL is the desired-state Postgres DSN (DATABASE_URL). Required — the orchestrator's
	// DesiredStore is durable.
	DatabaseURL string
	// NATSURL is the event bus the in-pod supervisor sidecar dials (EDEN_NATS_URL). Passed to the
	// service's SupervisorNATSURL; read on the in-pod supervisor path only.
	NATSURL string

	// Lease is the leader-election wiring (EDEN_LEASE_NAME / EDEN_LEASE_NAMESPACE /
	// EDEN_LEASE_IDENTITY). LeaseName is the contended object all replicas share; Identity is the
	// pod name (the downward API), so the three replicas present distinct holder identities. All
	// required on the kubernetes substrate (the HA guarantee has no meaning without them).
	Lease orchestratorservice.LeaseConfig

	// VaultMode / VaultAddress / VaultTokenFilePath / VaultUsername / VaultPassword are the
	// dual-mode Vault bootstrap the secrets provider is built over (EDEN_VAULT_MODE selects the
	// production token-file path — the K8s-SA sidecar output — vs the local userpass path). The
	// password is read but NEVER logged; it lives only in this struct and the adapter login body.
	VaultMode          vaultadapter.Mode
	VaultAddress       string
	VaultTokenFilePath string
	VaultUsername      string
	VaultPassword      string

	// CredentialReference is the opaque vault:// reference the supervisor session's Spec folds; it
	// resolves server-side at Open to the harness credential VALUE (EDEN_CREDENTIAL_REF). An
	// opaque path, safe to log.
	CredentialReference string
	// Harness is the supervisor harness adapter key (EDEN_HARNESS): claude-code (default) or omp.
	Harness string

	// Address is the health-probe bind address (EDEN_ORCHESTRATOR_ADDRESS or :8080).
	Address string
}

// vaultTokenFilePath is the default sidecar token-file path when EDEN_VAULT_TOKEN_FILE is unset on
// the production path (matches the agent-runtime deployment's EDEN_VAULT_TOKEN_FILE).
const vaultTokenFilePath = "/vault/secrets/token" // #nosec G101 -- a sidecar output PATH, not a credential value.

// parseConfiguration resolves the composition configuration from env ONCE (the configuration
// pattern), validating the fields the composition genuinely requires and returning a wrapped
// KindInvalid error naming the missing field (never echoing a value). It is the PURE env→config
// seam the unit test drives via a table over the environment map; run() calls it at the edge and
// builds the live ports from the result.
//
// getenv is injected so the test drives it deterministically without mutating the process
// environment; run() passes os.Getenv.
func parseConfiguration(getenv func(string) string) (configuration, error) {
	substrate := orchestratorservice.SubstrateDocker
	if getenv("EDEN_WORKSPACE_SUBSTRATE") == substrateKubernetes {
		substrate = orchestratorservice.SubstrateKubernetes
	}

	configured := configuration{
		Substrate:      substrate,
		LabelNamespace: getenv("EDEN_LABEL_NAMESPACE"),
		DatabaseURL:    getenv("DATABASE_URL"),
		NATSURL:        getenv("EDEN_NATS_URL"),
		Lease: orchestratorservice.LeaseConfig{
			LeaseName: getenv("EDEN_LEASE_NAME"),
			Namespace: getenv("EDEN_LEASE_NAMESPACE"),
			Identity:  getenv("EDEN_LEASE_IDENTITY"),
		},
		VaultMode:           vaultadapter.ParseMode(getenv("EDEN_VAULT_MODE")),
		VaultAddress:        getenv("VAULT_ADDR"),
		VaultTokenFilePath:  envOr(getenv, "EDEN_VAULT_TOKEN_FILE", vaultTokenFilePath),
		VaultUsername:       getenv("VAULT_USERNAME"),
		VaultPassword:       getenv("VAULT_PASSWORD"),
		CredentialReference: getenv("EDEN_CREDENTIAL_REF"),
		Harness:             envOr(getenv, "EDEN_HARNESS", defaultHarness),
		Address:             envOr(getenv, "EDEN_ORCHESTRATOR_ADDRESS", defaultAddress),
	}

	if err := configured.validate(); err != nil {
		return configuration{}, err
	}
	return configured, nil
}

// validate checks the fields the composition genuinely requires, returning a wrapped KindInvalid
// error naming the missing seam (never echoing a value). The lease fields are required only on the
// kubernetes substrate — a docker fallback run (the zero substrate) uses the always-leader
// dockerLease and needs no election wiring. The Vault credential is validated per the resolved Mode:
// the local userpass path needs the username/password (the production token-file path needs only the
// token-file path, which parseConfiguration always defaults, so there is nothing to require here) —
// mirroring vaultadapter.New's own per-Mode contract, failing at the edge instead of at first Resolve.
func (c *configuration) validate() error {
	if c.DatabaseURL == "" {
		return errors.New(errors.KindInvalid, "agentgateway-orchestrator: DATABASE_URL is required (the durable desired-state store)")
	}
	if c.CredentialReference == "" {
		return errors.New(errors.KindInvalid, "agentgateway-orchestrator: EDEN_CREDENTIAL_REF is required (the opaque vault:// supervisor credential reference)")
	}
	if c.VaultAddress == "" {
		return errors.New(errors.KindInvalid, "agentgateway-orchestrator: VAULT_ADDR is required (the secrets provider backend)")
	}
	if c.Substrate == orchestratorservice.SubstrateKubernetes {
		switch {
		case c.Lease.LeaseName == "":
			return errors.New(errors.KindInvalid, "agentgateway-orchestrator: EDEN_LEASE_NAME is required on the kubernetes substrate (the contended Lease object)")
		case c.Lease.Namespace == "":
			return errors.New(errors.KindInvalid, "agentgateway-orchestrator: EDEN_LEASE_NAMESPACE is required on the kubernetes substrate (the Lease's control-plane namespace)")
		case c.Lease.Identity == "":
			return errors.New(errors.KindInvalid, "agentgateway-orchestrator: EDEN_LEASE_IDENTITY is required on the kubernetes substrate (this replica's holder identity, the pod name)")
		}
	}
	if c.VaultMode == vaultadapter.ModeUserpass {
		switch {
		case c.VaultUsername == "":
			return errors.New(errors.KindInvalid, "agentgateway-orchestrator: VAULT_USERNAME is required in the local userpass Vault mode")
		case c.VaultPassword == "":
			return errors.New(errors.KindInvalid, "agentgateway-orchestrator: VAULT_PASSWORD is required in the local userpass Vault mode (the bootstrap credential)")
		}
	}
	return nil
}

// run is the testable composition body: it reads the configuration from the environment ONCE,
// builds the durable pool (ensuring the orchestrator schema), the dual-mode Vault secrets provider,
// the observability plane, the shared agentsession pool (the supervisor route), and — on the
// kubernetes substrate — the leader-election Lease, composes the orchestratorservice.Service over
// them, starts the election + the leader-gated reconcile loop, serves the liveness probe on :8080,
// and drains everything on a signal. It owns (and releases) the database pool + the Vault provider;
// the Service borrows both.
func run(ctx context.Context, logger *slog.Logger) error {
	configured, err := parseConfiguration(os.Getenv)
	if err != nil {
		return err
	}

	// The durable desired-state pool — OWNED by this command (Closed on exit). Building the store
	// here (rather than only inside the Service) lets the command run the startup EnsureSchema:
	// postgresstore.New is pure, so a first-boot pod creates the schema before the loop ticks.
	pool, err := pgxpool.New(ctx, configured.DatabaseURL)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: open desired-state database pool", err)
	}
	defer pool.Close()
	if schemaErr := ensureSchema(ctx, pool); schemaErr != nil {
		return schemaErr
	}

	provider, err := buildSecretsProvider(&configured)
	if err != nil {
		return err
	}

	telemetry, err := buildObservability()
	if err != nil {
		return err
	}
	defer func() {
		flushCtx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		_ = telemetry.Flush(flushCtx) //nolint:errcheck // best-effort telemetry flush on shutdown; the process is exiting.
	}()

	sessions, err := buildSessions(&configured, provider)
	if err != nil {
		return err
	}

	lease, leaseStart, err := buildLease(&configured)
	if err != nil {
		return err
	}

	service, err := orchestratorservice.New(
		orchestratorservice.Config{
			Substrate:         configured.Substrate,
			LabelNamespace:    configured.LabelNamespace,
			SupervisorNATSURL: configured.NATSURL,
		},
		orchestratorservice.Deps{
			DatabasePool:  pool,
			Secrets:       provider,
			Observability: telemetry,
			Sessions:      sessions,
			Lease:         lease, // nil on the docker fallback → the always-leader dockerLease
		},
	)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build orchestrator service", err)
	}
	defer func() {
		drainCtx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		_ = service.Close(drainCtx) //nolint:errcheck // best-effort loop drain on shutdown; the process is exiting.
	}()

	// Launch the leader election (a background goroutine) BEFORE the leadership supervisor consults
	// IsLeader; leaseStart is nil on the docker fallback. The returned cancel releases the Lease
	// (ReleaseOnCancel) on a graceful shutdown so a peer leads immediately.
	if leaseStart != nil {
		defer leaseStart(ctx)()
	}

	logger.Info(
		"agentgateway-orchestrator: serving the reconcile role under the lease",
		slog.String("substrate", substrateName(configured.Substrate)),
		slog.String("leaseName", configured.Lease.LeaseName),
		slog.String("leaseNamespace", configured.Lease.Namespace),
		slog.String("leaseIdentity", configured.Lease.Identity),
		slog.String("labelNamespace", configured.LabelNamespace),
		slog.String("harness", configured.Harness),
		slog.String("credentialReference", configured.CredentialReference), // an opaque path, never a value
		slog.String("address", configured.Address),
	)

	// The health probe and the leadership supervisor run CONCURRENTLY: a follower must be Ready
	// (the Deployment's readinessProbe hits /healthz on every replica) the whole time it waits to
	// acquire the Lease. Service.Start consults IsLeader exactly ONCE (service.go:269) — leadership
	// TRANSITIONS are therefore the command's job: superviseLeadership starts the loop when this
	// replica acquires the Lease and exits the process when a started leader is deposed (the
	// kubelet restarts the pod → a clean re-election; an in-process restart would race the Pool's
	// closed state and risk a deposed leader still driving actual).
	healthErr := make(chan error, 1)
	go func() { healthErr <- serveHealth(ctx, configured.Address, logger) }()
	leaderErr := make(chan error, 1)
	go func() { leaderErr <- superviseLeadership(ctx, lease, service.Start, leadershipPollInterval, logger) }()

	select {
	case err := <-leaderErr:
		return err // nil on graceful ctx cancel; an error demands the restart-for-re-election exit
	case err := <-healthErr:
		return err // the probe listener failed (or drained nil on ctx cancel)
	}
}

// leadershipPollInterval is the supervisor's IsLeader consult cadence. It matches client-go's
// default election RetryPeriod (2s), so a transition is observed within one election action.
const leadershipPollInterval = 2 * time.Second

// leaseConsulter is the narrow slice of the Lease seam the supervisor needs (consumer-defined
// port), so the unit test drives transitions with a fake without a real election.
type leaseConsulter interface {
	IsLeader(ctx context.Context) (bool, error)
}

// superviseLeadership drives the reconcile loop across leadership TRANSITIONS — the seam
// Service.Start deliberately does not own (it consults IsLeader once; the composition root gates
// the loop on the live election). Semantics:
//
//   - lease == nil (the docker fallback): the Service folds nil to its always-leader dockerLease —
//     start the loop immediately and return nil (the loop ticks until ctx cancel / Close).
//   - follower: poll IsLeader at the election cadence, staying healthy but idle, until this
//     replica ACQUIRES the Lease → start the loop (exactly once).
//   - a STARTED leader that is deposed (renewal failed, partition): return a typed error so the
//     process exits nonzero and the kubelet restarts it — the k8s leader-election convention. A
//     fresh pod re-enters the election cleanly; an in-process stop/restart would race the Pool's
//     closed state and leave a mid-tick deposed leader driving actual.
//   - ctx canceled (the signal): return nil — the graceful drain path (run()'s defers release the
//     Lease and Close the service).
//
// interval is the consult cadence (leadershipPollInterval in production; the unit test injects a
// millisecond cadence so transition coverage stays fast).
func superviseLeadership(ctx context.Context, lease leaseConsulter, start func(context.Context) error, interval time.Duration, logger *slog.Logger) error {
	if lease == nil {
		if err := start(ctx); err != nil {
			return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: start reconcile loop", err)
		}
		logger.Info("agentgateway-orchestrator: reconcile loop started (docker fallback — always leader)")
		// Service.Start is NON-blocking (the Pool runs the loop on its own goroutine), so returning
		// here would resolve run()'s select and exit the process, tearing the just-started loop down
		// (the review-fleet HIGH). Park until the signal cancels ctx — the daemon stays serving.
		<-ctx.Done()
		return nil
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	started := false
	for {
		leader, err := lease.IsLeader(ctx)
		if err != nil {
			return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: consult reconcile lease", err)
		}
		switch {
		case leader && !started:
			// Service.Start re-consults IsLeader itself (its once-at-start gate) — a deposition in
			// the microseconds between this poll and that consult makes Start a follower no-op, and
			// the NEXT poll observes the deposition and exits for a clean re-election. The double
			// consult is redundant but harmless; the poll below owns transitions.
			if startErr := start(ctx); startErr != nil {
				return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: start reconcile loop on acquired leadership", startErr)
			}
			started = true
			logger.Info("agentgateway-orchestrator: acquired the lease — reconcile loop started")
		case !leader && started:
			return errors.New(errors.KindUnavailable,
				"agentgateway-orchestrator: leadership lost — exiting for a clean restart + re-election (the kubelet restart policy re-enters the election)")
		}
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

// ensureSchema runs the orchestrator's startup schema migration over the durable pool. The Service
// deliberately does NOT do this (postgresstore.New is pure; EnsureSchema is the command's startup
// call — service.go's New doc), so a first-boot orchestrator pod creates the schema here before the
// reconcile loop issues its first desired-state query.
func ensureSchema(ctx context.Context, pool *pgxpool.Pool) error {
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: pool})
	if err != nil {
		return errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build desired-state store", err)
	}
	if schemaErr := desiredStore.EnsureSchema(ctx); schemaErr != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: ensure orchestrator schema", schemaErr)
	}
	return nil
}

// buildSecretsProvider builds the secrets Mediator over the dual-mode Vault backend: the PRODUCTION
// token-file path (ModeTokenFile — the K8s-SA sidecar output at VaultTokenFilePath, re-read per
// Resolve) on the cluster, or the LOCAL userpass bootstrap for a docker fallback run. It mirrors
// liveserve.buildSecretsProvider's mediator wiring (one scheme, "vault"); the ONLY difference is
// the per-Mode backend Config/Deps, resolved at the edge from EDEN_VAULT_MODE. The bootstrap is
// lazy (first Resolve), so New stays cheap and a Vault briefly unreachable at startup does not fail
// construction.
//
//nolint:ireturn // returns the secrets.Provider port the agentsession Pool holds (the frozen surface).
func buildSecretsProvider(configured *configuration) (secrets.Provider, error) {
	adapter, err := vaultadapter.New(
		vaultadapter.Config{
			Address:       configured.VaultAddress,
			Mode:          configured.VaultMode,
			TokenFilePath: configured.VaultTokenFilePath, // read only on ModeTokenFile
		},
		vaultadapter.Deps{
			Username: configured.VaultUsername, // read only on ModeUserpass
			Password: configured.VaultPassword, // read only on ModeUserpass; never logged
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build vault backend", err)
	}
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build secrets mediator", err)
	}
	return mediator, nil
}

// buildObservability builds the telemetry plane the orchestrator emits its transition/limit/ledger
// events onto. The orchestrator role has no OTLP collector wired in this composition yet, so the
// exporter is the stdout slog adapter (the pod's structured log stream) at PlaneAgent — the same
// plane the Service's observabilityTelemetry shim stamps.
func buildObservability() (observability.Provider, error) {
	telemetry, err := observability.New(
		observability.Config{ServiceName: serviceName, DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: slogadapter.New(os.Stdout), Clock: systemClock{}},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build observability", err)
	}
	return telemetry, nil
}

// buildSessions builds the ONE shared agentsession pool the orchestrator opens supervisor sessions
// through — the claude + omp adapters over the Vault-backed secrets provider, the in-process
// transcript, and the system clock. The route table binds the canonical supervisor RouteKey
// (orchestratorservice.SupervisorRouteKey) to claude-code at the Opus model (the standing Opus
// directive; the empty account default can drift to Sonnet), mirroring liveserve's pool routing —
// one routing table, one adapter set.
func buildSessions(configured *configuration, provider secrets.Provider) (agentsession.Factory, error) {
	claudeAdapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build claude adapter", err)
	}
	ompAdapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build omp adapter", err)
	}
	pool, err := agentsession.New(
		agentsession.Config{
			Routing: map[agentsession.RouteKey]agentsession.Route{
				orchestratorservice.SupervisorRouteKey(): {Harness: configured.Harness, Model: "opus"},
			},
		},
		agentsession.Deps{
			Adapters: map[string]agentsession.Adapter{
				"claude-code": claudeAdapter,
				"omp":         ompAdapter,
			},
			Secrets:    provider,
			Transcript: newTranscript(),
			Clock:      systemClock{},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build agentsession pool", err)
	}
	return pool, nil
}

// leaseStarter launches the leader election and returns the cancel that releases the Lease. It is
// nil on the docker fallback (no election), so run() guards the call.
type leaseStarter func(ctx context.Context) context.CancelFunc

// buildLease builds the reconcile Lease for the resolved substrate: on kubernetes, the REAL
// coordination.k8s.io/v1 leader-election Lease (orchestratorservice.NewKubernetesLease) over the
// in-cluster coordination + core clients; on the docker fallback, nil (the Service folds nil to its
// always-leader dockerLease). It returns the Lease seam, its election starter (nil on docker), and
// a wrapped error. NewKubernetesLease is pure (no apiserver dial); the first Lease get/create
// happens when the returned starter runs the election.
//
//nolint:ireturn // returns the orchestratorservice.Lease seam the Service holds (nil-able; the frozen surface).
func buildLease(configured *configuration) (orchestratorservice.Lease, leaseStarter, error) {
	if configured.Substrate != orchestratorservice.SubstrateKubernetes {
		return nil, nil, nil // docker fallback: the Service's always-leader dockerLease
	}
	coordination, core, err := kubernetesClients()
	if err != nil {
		return nil, nil, err
	}
	lease, err := orchestratorservice.NewKubernetesLease(
		configured.Lease,
		orchestratorservice.LeaseDependencies{Coordination: coordination, Events: core},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "agentgateway-orchestrator: build kubernetes lease", err)
	}
	return lease, lease.Start, nil
}

// kubernetesClients builds the coordination + core typed clients the leader-election LeaseLock
// contends through, from the SAME in-cluster REST posture the workspaceprovider kubernetesadapter
// uses (Config.Kubeconfig="" → rest.InClusterConfig, falling back to the default loading rules).
// This mirrors kubernetesadapter.loadRESTConfig (that helper is unexported, so the posture is
// replicated here, not re-imported) so the lease client and the workspace client resolve the SAME
// cluster: the pod's projected ServiceAccount token. Unlike the adapter's pure New, the composition
// root DEMANDS a resolvable in-cluster config — a failure to build it is a hard startup error (the
// orchestrator role cannot elect a leader without a cluster), returned wrapped. It returns the exact
// typed-client interfaces orchestratorservice.LeaseDependencies expects.
func kubernetesClients() (coordinationv1client.CoordinationV1Interface, corev1client.CoreV1Interface, error) {
	restConfig, err := inClusterRESTConfig()
	if err != nil {
		return nil, nil, err
	}
	clientset, err := kubernetes.NewForConfig(restConfig)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: build kubernetes clientset", err)
	}
	return clientset.CoordinationV1(), clientset.CoreV1(), nil
}

// inClusterRESTConfig resolves the in-cluster REST config (the pod's projected ServiceAccount
// token), falling back to the default kubeconfig loading rules (KUBECONFIG / ~/.kube/config) for a
// local run. It mirrors kubernetesadapter.loadRESTConfig's Kubeconfig="" branch, but — because the
// orchestrator role's leader election has no meaning without a cluster — it RETURNS the resolution
// error (KindUnavailable) rather than deferring it to first use as the adapter's pure New does.
func inClusterRESTConfig() (*rest.Config, error) {
	if inCluster, err := rest.InClusterConfig(); err == nil {
		return inCluster, nil
	}
	clientConfig := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(
		clientcmd.NewDefaultClientConfigLoadingRules(),
		&clientcmd.ConfigOverrides{},
	)
	restConfig, err := clientConfig.ClientConfig()
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: resolve in-cluster kubeconfig", err)
	}
	return restConfig, nil
}

// serveHealth serves ONLY the liveness/readiness probe the deployment's readinessProbe +
// livenessProbe hit (GET /healthz on :8080). Any replica is healthy the instant its process is up
// (the reconcile loop is leader-gated, not a health condition — a follower is healthy, it just does
// not reconcile). It runs until ctx is canceled (the signal), then drains gracefully.
func serveHealth(ctx context.Context, address string, logger *slog.Logger) error {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", handleHealth)

	listener, err := net.Listen("tcp", address)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: bind health listener", err)
	}
	server := &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: readHeaderTimeout,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}
	serveErr := make(chan error, 1)
	go func() { serveErr <- server.Serve(listener) }()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		_ = server.Shutdown(shutdownCtx) //nolint:errcheck // shutdown best-effort; the reconcile loop + pool are drained by the deferred Close/pool.Close.
		logger.Info("agentgateway-orchestrator: shutdown complete")
		return nil
	case err := <-serveErr:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return errors.Wrap(errors.KindUnavailable, "agentgateway-orchestrator: serve health", err)
	}
}

// handleHealth is the liveness probe (no reconcile state, no credential path) — the same
// {"status":"ok"} envelope the gateway's /healthz serves.
func handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`)) //nolint:errcheck // a closed probe connection is the client's concern; the status is already committed.
}

// substrateName renders the resolved substrate for the startup log line (diagnostics only).
func substrateName(substrate orchestratorservice.Substrate) string {
	if substrate == orchestratorservice.SubstrateKubernetes {
		return substrateKubernetes
	}
	return "docker"
}

// envOr returns the environment value for key, or fallback when it is unset/empty.
func envOr(getenv func(string) string, key, fallback string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return fallback
}

// systemClock is the production observability.Clock / agentsession.Clock (the wall clock; the
// composition root is the one place a real clock is read — the libraries stay pure).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }
