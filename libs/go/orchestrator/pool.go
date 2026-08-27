package orchestrator

import (
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// defaultPageSize is the List/Watch page size when Filter.Limit is zero.
const defaultPageSize = 100

// defaultReconcileInterval is the loop tick when Config.ReconcileInterval is zero.
const defaultReconcileInterval = 2 * time.Second

// Config is the immutable, fully-resolved input (the configuration pattern). It holds
// NO ports and NO secrets — only scalar policy knobs the routing/limits logic needs,
// frozen at the edge.
type Config struct {
	DefaultMaxConcurrent int           // class ceiling when a template/request sets 0; 0 here == unbounded (discouraged in production)
	DefaultCluster       ClusterRef    // the cluster a zero-Cluster SpawnRequest resolves to (ADR-0012)
	ReconcileInterval    time.Duration // the loop tick when run via Start; 0 == a sane default
	RetentionWindow      time.Duration // how long terminal Agents are kept before Reap archives them
	ProvisionTimeout     time.Duration // max wait for workspaceprovider.Provision before marking the agent Failed
}

// Deps is the injected hexagon (accept interfaces; New constructs none). The durable
// DESIRED record and cross-cutting ports live here; the side-effecting reconcile ports
// (workspaceprovider.Provider, agentsession.Factory, Probe) MAY be supplied here as
// defaults for Start's loop and are overridden per-pass via ReconcilePorts.
type Deps struct {
	Desired   DesiredStore     // durable desired-state records (in-memory v0; Postgres multi-node) — the ONE swap for multi-node
	Templates TemplateStore    // resolves a TemplateRef to its immutable AgentTemplate (read-only)
	Secrets   secrets.Provider // the seam the credential ref is carried THROUGH; agentsession.Open resolves it server-side
	Telemetry Telemetry        // emits the orchestration-plane observability Events (transitions, limit hits, ledger ticks)
	Clock     Clock            // injected time source so New stays pure and reconcile is deterministic

	// Reconcile-time defaults for Start's loop; a per-pass ReconcilePorts overrides them.
	Workspaces workspaceprovider.Provider // the frozen S2 seam (docker/k3d v0; kubernetes later)
	Sessions   agentsession.Factory
	Probe      Probe
}

// Pool is the concrete Manager + Watcher + Reconciler returned by New (named for the
// pool of tracked agents, mirroring agentsession.Pool). It holds the desired-state
// seam, runs the reconcile loop (after Start), enforces limits, folds ledgers, and
// emits observability Events. Safe for concurrent use; zero value unusable.
type Pool struct {
	configuration Config
	dependencies  Deps

	// mu serializes admission (the count-then-record window must be atomic so two
	// concurrent Spawns cannot both pass a ceiling of one) and per-agent transitions.
	mu sync.Mutex

	// idSeq monotonically numbers spawned agents (the AgentID before a session is open;
	// it stays the stable handle for the agent's whole life).
	idSeq uint64

	// inputs is the per-agent fold side table (credential ref, permission decider,
	// resolved template, tightening) — out-of-band of the serializable record so no
	// secret value and no live closure enters the DesiredStore. Lazily constructed so
	// New stays pure.
	inputsOnce sync.Once
	inputs     *spawnInputsTable

	// live is the per-agent live-actual side table (the open Session + Workspace) — the
	// in-process object graph the record deliberately does not hold, so reconcile can
	// Close-then-Teardown and the default Probe reads a truthful actual. Lazily
	// constructed so New stays pure.
	liveOnce sync.Once
	live     *liveTable

	// watchers is the set of live Watch subscribers the verbs/reconcile notify.
	watchersMu sync.Mutex
	watchers   map[*watchSubscription]struct{}

	// loop lifecycle (Start/Close). started guards a single Start; closed makes Close
	// idempotent; done is closed when the loop goroutine exits.
	loopMu  sync.Mutex
	started bool
	closed  bool
	stop    chan struct{}
	done    chan struct{}
}

// Static assertions: *Pool is the Manager, Watcher, and Reconciler.
var (
	_ Manager    = (*Pool)(nil)
	_ Watcher    = (*Pool)(nil)
	_ Reconciler = (*Pool)(nil)
)

// New is the pure constructor spine: no I/O, no clock read, no env read, no
// provisioning, no goroutine started. It validates Config + Deps and returns the
// concrete *Pool. The reconcile loop starts only at Pool.Start (so New stays pure and a
// test drives Reconcile by hand). Returns a wrapped ConfigError (errors.AsType) for an
// invalid Config or a nil required Dep.
//
//nolint:gocritic // contract §6: Config is the frozen, copyable configuration input (the configuration pattern); New takes it by value.
func New(configuration Config, dependencies Deps) (*Pool, error) {
	if dependencies.Desired == nil {
		return nil, wrapKind(&ConfigError{Reason: "a DesiredStore is required (the durable desired-state seam)"})
	}
	if dependencies.Templates == nil {
		return nil, wrapKind(&ConfigError{Reason: "a TemplateStore is required to resolve a TemplateRef"})
	}
	if dependencies.Secrets == nil {
		return nil, wrapKind(&ConfigError{Reason: "a secrets.Provider is required to carry the credential reference"})
	}
	if dependencies.Telemetry == nil {
		return nil, wrapKind(&ConfigError{Reason: "a Telemetry seam is required to emit orchestration-plane events"})
	}
	if dependencies.Clock == nil {
		return nil, wrapKind(&ConfigError{Reason: "an injected Clock is required so reconcile is deterministic"})
	}
	if configuration.DefaultMaxConcurrent < 0 {
		return nil, wrapKind(&ConfigError{Reason: "DefaultMaxConcurrent must not be negative"})
	}
	return &Pool{
		configuration: configuration,
		dependencies:  dependencies,
		watchers:      make(map[*watchSubscription]struct{}),
	}, nil
}

// now reads the injected Clock (the sole time source after New).
func (p *Pool) now() time.Time { return p.dependencies.Clock.Now() }

// reconcilePorts resolves the per-pass ports, falling back to the Deps defaults Start's
// loop supplies. A test passes them explicitly; a single-node app supplies them once in
// Deps.
func (p *Pool) reconcilePorts(ports ReconcilePorts) ReconcilePorts {
	if ports.Workspaces == nil {
		ports.Workspaces = p.dependencies.Workspaces
	}
	if ports.Sessions == nil {
		ports.Sessions = p.dependencies.Sessions
	}
	if ports.Probe == nil {
		ports.Probe = p.dependencies.Probe
	}
	if ports.Probe == nil {
		// No Probe bound: fall back to the in-process live-actual table (the v0 single-node
		// default). Multi-node binds a cluster-query Probe instead, no surface change.
		ports.Probe = defaultProbe{table: p.ensureLive()}
	}
	return ports
}
