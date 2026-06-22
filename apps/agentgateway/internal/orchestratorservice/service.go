package orchestratorservice

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
)

// localDockerCluster is the ClusterRef a docker-first Spawn defaults to when a SpawnRequest
// names no cluster. The single local docker daemon IS this cluster; Config.DefaultCluster
// resolves a zero SpawnRequest.Cluster to it at Spawn (the orchestrator's effectiveLimits/Cluster
// fold), so a caller never has to name "local-docker" for the common path.
var localDockerCluster = orchestrator.ClusterRef{ID: "local-docker"}

// supervisorRouteKey is the route the claude Factory binds for the supervisor template (it MUST
// match the template's Routing so agentsession.Open resolves an adapter). The model is the
// account default for claude-code (empty Model == claude's own default), per the Opus directive.
var supervisorRouteKey = agentsession.RouteKey{Phase: "supervise", Role: "supervisor"}

// Config is the immutable, fully-resolved input for the docker-first orchestrator service (the
// configuration pattern: read once at the edge by the command, frozen here). It holds NO ports,
// NO live handles, and NO secret VALUE — the credential rides every SpawnRequest as an opaque
// secrets.Reference resolved server-side at agentsession.Open. The command resolves every field
// from the environment BEFORE New, so this package reads no env and the constructor stays pure.
type Config struct {
	// ReconcileInterval is the reconcile-loop tick. Zero == the orchestrator's sane default
	// (folded into orchestrator.Config.ReconcileInterval).
	ReconcileInterval time.Duration
	// ProvisionTimeout bounds a single workspaceprovider.Provision before the agent is marked
	// Failed (folded into orchestrator.Config.ProvisionTimeout). Zero == the parent ctx bounds it.
	ProvisionTimeout time.Duration
	// RetentionWindow is how long terminal agents are kept before the loop's Reap archives them
	// (folded into orchestrator.Config.RetentionWindow). Zero == retention runs out-of-band only.
	ProvisionRetention time.Duration
	// DefaultMaxConcurrent is the class ceiling for a (Tenant, Template) whose template/request
	// sets 0. Zero here == unbounded (discouraged in production); the supervisor template sets 1.
	DefaultMaxConcurrent int
	// DockerHost overrides the docker daemon endpoint (empty == the SDK FromEnv default:
	// DOCKER_HOST else the local socket). The local/BYO posture sets it at the command.
	DockerHost string
	// LabelNamespace scopes this service's docker ownership domain (the eden.namespace label);
	// empty for single-tenant local.
	LabelNamespace string
	// ClaudeBinary names the claude CLI executable the session Factory spawns ("" == "claude").
	// An integration harness points this at a trivial stub binary to exercise the real subprocess
	// lifecycle without a live authenticated claude.
	ClaudeBinary string
}

// Deps is the injected hexagon for the service (accept interfaces; New constructs the
// orchestrator-specific adapters from them). The durable database pool, the secrets provider,
// the observability provider, and the OPTIONAL cluster-Probe sources arrive here; the service
// builds the orchestrator.Pool over them.
type Deps struct {
	// DatabasePool is the ready pgx pool the production postgresstore.DesiredStore issues queries
	// against. Owned and Closed by the COMPOSITION ROOT (the command), not by the service.
	// Required.
	DatabasePool *pgxpool.Pool
	// Secrets resolves the opaque per-spawn credential reference to the harness child env at
	// agentsession.Open, server-side — the value never enters this service's surface. Required.
	Secrets secrets.Provider
	// Observability is the telemetry plane the orchestrator emits its transition/limit/ledger
	// events onto (mapped to PlaneAgent by the observabilityTelemetry shim). Required.
	Observability observability.Provider
	// Transcript is the durable replay log the agentsession.Pool appends harness events to (Seq ==
	// transcript offset). Required (agentsession.New requires it).
	Transcript agentsession.Transcript

	// Lease guards the reconcile loop in a multi-instance deployment (only the leader reconciles).
	// nil == the docker single-instance always-leader Lease (the local default).
	Lease Lease
}

// Service is the composed docker-first orchestrator: the orchestrator.Pool over its production
// adapters plus the lease-guarded reconcile loop. It exposes the Manager verbs the create-saga
// calls (Spawn/Get/List/Stop/Resume) by delegating to the embedded Pool, and owns the loop
// lifecycle (Start/Close). Safe for concurrent use (the Pool is); zero value unusable —
// construct via New.
type Service struct {
	pool        *orchestrator.Pool
	provisioner *workspaceprovider.Provisioner
	lease       Lease
}

// static assertions: the Service exposes exactly the orchestrator.Manager surface (the saga
// holds this interface, not the concrete Pool).
var _ orchestrator.Manager = (*Service)(nil)

// New is the pure composition spine New(configuration, dependencies) -> (*Service, error): it
// validates the wiring and BUILDS the orchestrator.Pool over its production adapters, doing NO
// I/O — no daemon dial (dockeradapter.New negotiates the client lazily; the first daemon call is
// at Provision), no database query (postgresstore.New is pure; EnsureSchema is the command's
// startup call), no process spawn (the claude Factory spawns nothing until the first Open), no
// reconcile loop (Start runs it). It returns a wrapped error if any seam is misconfigured.
//
//nolint:gocritic // Config is the frozen, copyable composition input (the configuration pattern); New takes it by value (the constructor spine).
func New(configuration Config, dependencies Deps) (*Service, error) {
	// Production always resolves through the supervisor TemplateStore compiled to docker (the
	// single-instance local substrate). The real-substrate integration test injects a trivial
	// busybox TemplateStore through the unexported build seam so the same production adapter
	// stack provisions a trivial workspace without the heavy supervisor image.
	return build(configuration, dependencies, newSupervisorTemplateStore(orchestrator.SubstrateDocker))
}

// build is the shared composition body New delegates to: it validates the wiring and BUILDS the
// orchestrator.Pool over its production adapters, doing NO I/O. The templates seam is the ONE
// piece New fixes (the supervisor store) and the integration test swaps (a trivial store) — the
// rest of the stack (the namespacing Postgres store, the docker provisioner, the claude Factory,
// the telemetry shim) is identical, so the test proves the production composition, not a mock.
//
//nolint:gocritic // Config is the frozen, copyable composition input; build takes it by value to match New.
func build(configuration Config, dependencies Deps, templates orchestrator.TemplateStore) (*Service, error) {
	if err := validateDeps(&dependencies); err != nil {
		return nil, err
	}
	clock := newSystemClock()

	// ── Desired: the production Postgres store, bridged to the Pool's bare id space ──
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: dependencies.DatabasePool})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "orchestratorservice: build postgres desired store", err)
	}
	desired := newNamespacingStore(desiredStore)

	// ── Provider: the workspaceprovider routed to the DOCKER adapter (the single local instance) ──
	provisioner, err := buildDockerProvisioner(&configuration, &dependencies, clock)
	if err != nil {
		return nil, err
	}

	// ── Sessions: the agentsession Pool bound to the claude Factory ──
	sessions, err := buildClaudeSessions(&configuration, &dependencies, clock)
	if err != nil {
		return nil, err
	}

	pool, err := orchestrator.New(
		orchestrator.Config{
			DefaultMaxConcurrent: configuration.DefaultMaxConcurrent,
			DefaultCluster:       localDockerCluster,
			ReconcileInterval:    configuration.ReconcileInterval,
			RetentionWindow:      configuration.ProvisionRetention,
			ProvisionTimeout:     configuration.ProvisionTimeout,
		},
		orchestrator.Deps{
			Desired:    desired,
			Templates:  templates,
			Secrets:    dependencies.Secrets,
			Telemetry:  newObservabilityTelemetry(dependencies.Observability),
			Clock:      clock,
			Workspaces: provisioner,
			Sessions:   sessions,
			// Probe left unbound: the docker-first single-instance loop uses the Pool's in-process
			// default Probe (pool.go reconcilePorts — the documented v0 single-node default). The
			// restart-survivable orchestrator/clusterprobe.Probe is the MULTI-NODE seam; it is
			// project-scoped, so the multi-node deployment binds one per tenant at its reconcile
			// call site, not here.
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "orchestratorservice: build orchestrator pool", err)
	}

	lease := dependencies.Lease
	if lease == nil {
		lease = dockerLease{} // docker single instance: always the leader
	}
	return &Service{pool: pool, provisioner: provisioner, lease: lease}, nil
}

// Start launches the reconcile loop when THIS instance holds the lease (always true on docker:
// dockerLease is the permanent leader). It consults the Lease seam once so the kubernetes
// deployment can gate the loop on leader election with no change to this service; a non-leader
// instance starts no loop (it still serves the read/admission verbs, but only the leader drives
// actual toward desired). It then delegates to the Pool's own loop (Pool.Start), which ticks
// Reconcile + Reap at Config.ReconcileInterval until ctx is canceled or Close. A second Start is
// a no-op (the Pool guards it).
func (s *Service) Start(ctx context.Context) error {
	leader, err := s.lease.IsLeader(ctx)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestratorservice: consult reconcile lease", err)
	}
	if !leader {
		return nil // a follower instance: no reconcile loop (only the leader drives actual)
	}
	if err := s.pool.Start(ctx); err != nil {
		return errors.Wrap(errors.KindInternal, "orchestratorservice: start reconcile loop", err)
	}
	return nil
}

// Close stops the reconcile loop and drains every non-terminal agent the Pool owns (the pod reap
// is reconcile's job, bounded by ctx). Idempotent. It does NOT close the injected database pool
// or observability provider — those are the command's to release (it owns their lifetime).
func (s *Service) Close(ctx context.Context) error {
	if err := s.pool.Close(ctx); err != nil {
		return errors.Wrap(errors.KindInternal, "orchestratorservice: close reconcile loop", err)
	}
	return nil
}

// Spawn records the desired intent to run one agent and returns the admitted Agent at
// StatusPending immediately (the workspace + session reconcile asynchronously). It delegates to
// the embedded Pool verbatim — the saga calls THIS.
//
//nolint:gocritic // contract §2: SpawnRequest is the frozen, copyable spawn input; the port takes it by value.
func (s *Service) Spawn(ctx context.Context, request orchestrator.SpawnRequest) (orchestrator.Agent, error) {
	return s.pool.Spawn(ctx, request) //nolint:wrapcheck // the Pool already returns wrapped, classified orchestration errors; re-wrapping double-classifies.
}

// Get returns the current Agent record or a wrapped NotFoundError.
func (s *Service) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	return s.pool.Get(ctx, id) //nolint:wrapcheck // the Pool already returns a wrapped, classified NotFoundError.
}

// List returns the Agents matching filter (the running-set snapshot the dashboard/saga reads).
//
//nolint:gocritic // contract §2: Filter is the frozen, copyable query value; the port takes it by value.
func (s *Service) List(ctx context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	return s.pool.List(ctx, filter) //nolint:wrapcheck // the Pool already returns a wrapped, classified error.
}

// Stop records the desired terminal intent (idempotent); it returns when the intent is recorded,
// not when teardown completes.
func (s *Service) Stop(ctx context.Context, id orchestrator.AgentID, by string) error {
	return s.pool.Stop(ctx, id, by) //nolint:wrapcheck // the Pool already returns a wrapped, classified error.
}

// Resume records the desired intent to re-attach a stopped/suspended agent (the reconcile loop
// drives the actual re-attach).
func (s *Service) Resume(ctx context.Context, id orchestrator.AgentID, by string) error {
	return s.pool.Resume(ctx, id, by) //nolint:wrapcheck // the Pool already returns a wrapped, classified error.
}

// buildDockerProvisioner builds the workspaceprovider.Provisioner routed to the DOCKER adapter —
// the single-instance local substrate (ADR-0012). The docker adapter is the only substrate the
// docker-first service binds; a kubernetes deployment binds the kubernetes adapter instead with
// no other change.
func buildDockerProvisioner(configuration *Config, dependencies *Deps, clock systemClock) (*workspaceprovider.Provisioner, error) {
	dockerAdapter, err := dockeradapter.New(dockeradapter.Config{
		Host:           configuration.DockerHost,
		LabelNamespace: configuration.LabelNamespace,
	})
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "orchestratorservice: build docker adapter", err)
	}
	provisioner, err := workspaceprovider.New(
		workspaceprovider.Config{
			Default:   workspaceprovider.SubstrateDocker,
			Namespace: configuration.LabelNamespace,
		},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
				workspaceprovider.SubstrateDocker: dockerAdapter,
			},
			Secrets: dependencies.Secrets,
			Clock:   clock,
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "orchestratorservice: build workspace provider", err)
	}
	return provisioner, nil
}

// buildClaudeSessions builds the agentsession.Pool bound to the claude Factory — the harness the
// orchestrator opens supervisor sessions through. The route table maps the supervisor RouteKey to
// the claude-code adapter (the standing Opus directive; the account default model).
func buildClaudeSessions(configuration *Config, dependencies *Deps, clock systemClock) (*agentsession.Pool, error) {
	claudeAdapter, err := claudeadapter.New(claudeadapter.Config{Binary: configuration.ClaudeBinary})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "orchestratorservice: build claude adapter", err)
	}
	sessions, err := agentsession.New(
		agentsession.Config{
			Routing: map[agentsession.RouteKey]agentsession.Route{
				supervisorRouteKey: {Harness: "claude-code", Model: configuration.ClaudeBinary},
			},
		},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": claudeAdapter},
			Secrets:    dependencies.Secrets,
			Transcript: dependencies.Transcript,
			Clock:      clock,
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "orchestratorservice: build agentsession pool", err)
	}
	return sessions, nil
}

// validateDeps checks the required ports BEFORE any adapter is built, returning a wrapped
// KindInvalid error naming the missing seam (never echoing a value), so a misconfigured service
// fails at composition, never at the first verb.
func validateDeps(dependencies *Deps) error {
	switch {
	case dependencies.DatabasePool == nil:
		return errors.New(errors.KindInvalid, "orchestratorservice: Deps.DatabasePool is required (the durable desired-state store)")
	case dependencies.Secrets == nil:
		return errors.New(errors.KindInvalid, "orchestratorservice: Deps.Secrets is required (the per-spawn credential resolver)")
	case dependencies.Observability == nil:
		return errors.New(errors.KindInvalid, "orchestratorservice: Deps.Observability is required (the telemetry plane)")
	case dependencies.Transcript == nil:
		return errors.New(errors.KindInvalid, "orchestratorservice: Deps.Transcript is required (the agentsession replay log)")
	}
	return nil
}
