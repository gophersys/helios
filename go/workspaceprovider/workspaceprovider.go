// Package workspaceprovider is the Eden F1 Infrastructure (substrate) port (05 §2,
// 10 §2/§12, C23): it provisions an isolated Workspace on a substrate (the docker
// daemon or any conformant kubernetes distro), runs and execs workloads in it,
// mounts files, declares its dial-out egress, bounds its resources, and tears it
// down — one Workspace, one substrate, one lifecycle (02 §1). It is the substrate
// ABSTRACTION S2's orchestrator holds; an Adapter (dockeradapter, kubernetesadapter)
// is the only place a daemon/cluster SDK is imported (05 §1).
//
// It is ONE contract with two adapters and ZERO distro forks: a Workspace on docker
// and a Workspace on kubernetes(k3d|kind|EKS) are the same types driven by the same
// verbs. Genuine substrate divergence lives ONLY in the CapabilityManifest (05 §3);
// the conformance suite running the SAME cases over BOTH adapters against REAL
// substrates (never mocks) is the proof of distro transparency (05 §6, ADR-0016).
// The central multi-tenant cluster is an ordinary kubernetes adapter instance with
// zero special code paths (ADR-0012) — central/BYO/local differ only in injected
// client configuration.
//
// It does NOT own: what runs INSIDE an agent pod beyond launch (F4 agentsession —
// this port Starts the process and reports liveness; agentsession owns the harness
// wire format, Event stream, tool grants, transcript; agentsession.Close NEVER
// tears down the workspace — Provider.Teardown does; the only coupling is the
// Workspace path string → agentsession.Spec.Workspace); credential storage/minting
// (secrets port + vault — a spec carries an opaque secrets.Reference resolved
// server-side, never the value); the dial-out tunnel mesh (broker + apps/agent —
// this port declares the egress, the broker implements the tunnel); orchestration/
// reconcile/quota/egress-derivation policy (orchestrator + policy — this port is the
// level-based primitive a loop is built from); registry/DNS/object-store/DB/metrics
// or image building (separate F1 concerns); or usage-record normalization/billing
// (the F1 meter).
//
// Concurrency: a Provider is safe for concurrent use by S2's reconcile loop and many
// request handlers (it provisions many workspaces in parallel). A Workspace handle is
// safe for concurrent use: many callers may Exec/Status/Run one workspace at once; its
// Runs are independent. Teardown is idempotent. All blocking methods take
// context.Context first and honor cancellation. Errors are wrapped with %w and
// inspected via errors.AsType / errors.KindOf; every error carries a Kind so the
// transport boundary (10 §9) maps it without a workspaceprovider-specific table.
package workspaceprovider

import (
	"context"
	"io"
)

// Provider provisions, re-dials, lists, and tears down isolated workspaces on ONE
// substrate instance (one docker daemon, one kubernetes cluster — central, BYO, or
// local k3d/kind are all just Provider instances, ADR-0012). The orchestrator holds
// this as the port; New returns the concrete *Substrate (accept-interface,
// return-concrete). Exactly 4 methods.
type Provider interface {
	// Provision creates a fresh isolated Workspace from spec and returns a live handle
	// once it is Ready (image pulled, namespace/container created, mounts attached,
	// egress policy installed, resource limits set — the handshake confirmed). It is
	// the ownership-domain author point (05 §5): the workspace is tagged with
	// spec.Labels (incl. the tenancy keys, 07 §6) so List/Open/Teardown and drift
	// detection find exactly what Eden authored. PROVISION IS ALL-OR-NOTHING: it returns
	// a Ready Workspace or rolls back leaving NOTHING behind (no orphaned container /
	// namespace) and returns a wrapped error; it NEVER returns a non-nil Workspace with
	// a non-nil error. IDEMPOTENT on spec.Name within a tenancy: re-Provisioning an
	// existing, healthy, compatible workspace returns its handle (the level-based
	// reconcile contract, 10 §7.1).
	Provision(ctx context.Context, spec WorkspaceSpec) (Workspace, error)

	// Open re-attaches to an already-provisioned workspace by Handle (a pod recycle, a
	// control-plane restart, a second orchestrator replica adopting a workspace it did
	// not create). It is PURELY a re-dial — it provisions nothing. The Handle is the
	// ONLY durable per-workspace state the orchestrator keeps, so Open is what makes it
	// stateless across restarts. NotFoundError if the workspace no longer exists.
	Open(ctx context.Context, handle Handle) (Workspace, error)

	// List enumerates the workspaces Eden authored within a tenancy that match selector
	// — the OBSERVE step of the reconcile loop (10 §7.1) and the drift detector's
	// ownership-domain scan (05 §5). It returns Descriptors (metadata, not live
	// handles); the loop diffs observed vs desired and decides. Cross-tenant listing is
	// impossible by construction (the tenancy keys are part of the selector, 07 §6).
	List(ctx context.Context, selector Selector) ([]Descriptor, error)

	// Teardown destroys the workspace named by handle and reclaims its resources
	// (container + volumes, or namespace + all its objects — the adapter's ownership
	// domain, 05 §5). This is the call agentsession.Close deliberately does NOT make
	// (02 §1). IDEMPOTENT: tearing down an already-gone workspace is nil, not an error
	// (so a reconcile/GC loop converges without special-casing races). ctx bounds the
	// graceful drain; on ctx expiry the adapter escalates to a forced kill and returns.
	// After Teardown, Open returns NotFoundError.
	Teardown(ctx context.Context, handle Handle) error
}

// Supervisor is the SUPERVISION plane the orchestrator Probes (ADR-0022 §4): it absorbs
// IOTEA's manager.Manager shape — a global label-filtered watch (docker events on the docker
// adapter, a k8s pod-watch on the kubernetes adapter) NORMALIZED into ONE platform-neutral
// Event/Status space, plus reconcile-from-reality (list-by-label re-adoption on restart, so
// the supervised set is rebuilt from the LIVE substrate, never in-memory-only truth). The
// orchestrator THINS: it owns desired-state and reconciles, but reads the supervised Status
// here (the docker/k8s API = the HARD lifecycle) rather than raw heartbeats. The concrete
// *Provisioner implements this IN ADDITION to Provider; a consumer that only provisions holds
// Provider, a consumer that supervises holds Supervisor. Exactly 3 methods — under the ≤5
// ceiling, split from Provider along the real seam (provision vs supervise).
type Supervisor interface {
	// Supervise starts the global label-filtered watch over selector's ownership domain and
	// returns a stream of NORMALIZED Events (docker actions + k8s pod phases → the existing
	// State/Condition vocabulary). It FIRST reconciles-from-reality (list-by-label re-adoption
	// so a control-plane restart rebuilds the supervised set from the live substrate, then
	// watches for changes). The stream closes when ctx is canceled (the sole shutdown); a slow
	// reader slows its own read, never the watch (bounded buffering, the agentsession
	// backpressure ruling applied to events). Safe to call once per Supervisor; a second call
	// returns a second independent stream. UnsupportedError if no routable adapter declares
	// CapSupervise. The orchestrator ranges this to react to drift without polling each
	// workspace.
	Supervise(ctx context.Context, selector Selector) (<-chan Event, error)

	// Supervised reports the live supervised Status for ONE workspace by handle, read from the
	// substrate (reconcile-from-reality — never an in-memory cache that can lie across a
	// restart). It is the queryable Status the orchestrator Probes (NATS = the soft control
	// signal; THIS = the hard lifecycle). NotFoundError if the workspace is gone. Equivalent to
	// Open(handle).Status(ctx) but without materializing a Workspace handle — a cheap supervised
	// read.
	Supervised(ctx context.Context, handle Handle) (Status, error)

	// Reconcile rebuilds the supervised set from the LIVE substrate: it lists the ownership
	// domain by selector (the same scan List performs) so a stateless restart re-adopts exactly
	// what Eden authored, with each Descriptor's current normalized State. It is the
	// reconcile-from-reality primitive Supervise calls at startup, exposed so the orchestrator's
	// reconcile loop can force a re-adoption on demand (a drift sweep). Cross-tenant listing is
	// impossible by construction (the tenancy keys are part of the selector, 07 §6).
	Reconcile(ctx context.Context, selector Selector) ([]Descriptor, error)
}

// Workspace is ONE provisioned, isolated environment — the 02 §1 Workspace entity: an
// agent pod, a remote-VS-Code session host, a CI-runner sandbox, or a clean-room
// exercise environment (07 §4). The path the harness runs in is WorkDir(), exactly
// what flows into agentsession.Spec.Workspace. The agentsession adapter Runs into it; a
// CI executor / the engine Execs steps in it; S2 Statuses it. Exactly 5 methods — the
// ceiling, spent, not speculative. Its zero value is unusable; obtain one from
// Provider.Provision / Provider.Open.
type Workspace interface {
	// Handle is the durable, loggable identity of this workspace (the orchestrator
	// persists it; Provider.Open re-dials from it; Teardown destroys by it). Cheap,
	// non-blocking, value-typed — the join key between Eden's records and substrate
	// state. Carries the tenancy keys (Organization/Project, 07 §6) and the WorkDir;
	// NEVER carries a secret. Pure; no I/O.
	Handle() Handle

	// Run starts a long-running workload (PID 1 of the container / the pod's main
	// process): the agent harness, a remote-VS-Code server, a CI runner. ONE primary
	// workload per workspace (the 1-sandbox-per-execution rule, 07 §3) — a second Run
	// while one is Running is a NotReadyError. It returns a Run handle once the process
	// is launched (not once it exits); liveness/exit ride Run.Status, raw output rides
	// Run.Logs. The credential the workload needs is named by an opaque secrets.Reference
	// in RunSpec and resolved server-side, injected by the adapter at the injection site
	// only (env on the CHILD process / a tmpfs helper file) — never logged.
	Run(ctx context.Context, spec RunSpec) (Run, error)

	// Exec runs ONE short command to completion in the (already-Ready) workspace and
	// returns its result — the kubectl-exec / docker-exec verb (readiness probes, git
	// invocations from the gitrepository library, a one-shot go test, interactive
	// open-in-shell). Stdin/stdout/stderr ride ExecSpec/ExecResult as bounded,
	// optionally-streamed pipes. Distinct from Run: Exec is synchronous and
	// result-shaped (a command); Run is asynchronous and stream-shaped (a workload).
	// ctx bounds it; a timeout is DeadlineError. NotReadyError if the workspace is not
	// Ready; UnsupportedError if it needs CapExecPTY the adapter declares absent.
	Exec(ctx context.Context, spec ExecSpec) (ExecResult, error)

	// Files exposes the mount/copy seam: write declared inputs in (the clean-room "copy
	// ONLY declared inputs", 07 §4), read artifacts out (the worktree diff / coverage an
	// engine phase produces, 02 §2). It is a NARROW file port, NOT a shell — the adapter
	// decides whether it is a bind mount (docker), a volume + tar stream (kubernetes), or
	// a CSI volume. Returns the concrete file accessor for THIS workspace. Pure; no I/O
	// until a Files method is called.
	Files() Files

	// Status reports the current lifecycle State + a typed Condition snapshot + a
	// resource-usage snapshot (the data the F1 usage meter folds into UsageRecord, S9,
	// and the reconcile loop diffs). Non-blocking; reads cached substrate state refreshed
	// by the adapter's watch/poll; safe to poll. The drift surface (05 §5): an observed
	// State diverging from desired (a pod the cluster evicted under memory pressure) is
	// the DriftEvent the loop emits. The adapter-native phase (CrashLoopBackOff,
	// OOMKilled, ContainerCreating) rides Status.Detail VERBATIM for diagnostics without
	// leaking into the normalized State/Condition enums.
	Status(ctx context.Context) (Status, error)
}

// Run is one in-flight workload's handle — its status transitions and raw log stream.
// Exactly 2 methods: the orchestrator/CI awaits terminal Status; the chat/dashboard
// tails Logs. A workload's stdout is NOT the agent Event stream — that is agentsession's
// normalized stream layered ON TOP; Logs here is the raw container/pod log (startup
// diagnostics, crash output, code-server boot), which is exactly what the substrate
// owns and agentsession does not. It is NOT agentsession.Session.
type Run interface {
	// Status blocks until the next status transition or ctx, returning the new RunStatus
	// and ok=false at terminal (Succeeded/Failed/Killed) or ctx cancellation. The
	// orchestrator/CI ranges this to know when a workload finished and with what exit
	// signal (an OOMKill is a distinct, branchable RunStatus.Condition — the runaway-agent
	// signal the budget story 02 §2 reconciles against).
	Status(ctx context.Context) (RunStatus, bool)

	// Logs streams the workload's combined stdout/stderr from the given cursor
	// (follow-from-cursor, like kubectl logs --since / docker logs; the adapter reads
	// the substrate's log buffer). Pull-based: a slow reader slows its own read, never
	// the workload (the agentsession backpressure ruling, applied to raw logs). Cursor 0
	// is from the start where the substrate retains it. Closing ctx drops THIS reader only.
	Logs(ctx context.Context, from LogCursor) (io.ReadCloser, error)
}

// Files is the per-workspace file seam (the brief's "file mounts", plus the
// declared-inputs-in / artifacts-out of the clean room, 07 §4). Exactly 3 methods,
// under the ceiling. The adapter chooses the mechanism (bind mount, tar-over-exec,
// CSI); the consumer sees one narrow port.
type Files interface {
	// Put writes content to path inside the workspace (declared inputs: pinned source,
	// the seeded worktree). mode is the unix file mode. It is the clean-room "copy ONLY
	// declared inputs" primitive — the verifier writes nothing else (07 §4). Writing
	// under a read-only MountInputs target is a NotReadyError.
	Put(ctx context.Context, path string, content io.Reader, mode FileMode) error

	// Get reads path back out (the produced artifact: a worktree diff, a built binary, a
	// coverage profile the engine folds into Evidence, 02 §2). NotFoundError if the path
	// does not exist.
	Get(ctx context.Context, path string) (io.ReadCloser, error)

	// List enumerates entries under path (shallow) so the engine collects a produced
	// artifact set without a shell. Bounded; the substrate paginates large trees.
	List(ctx context.Context, path string) ([]FileEntry, error)
}

// Adapter is one substrate implementation: dockeradapter (the daemon, via the Docker
// SDK) and kubernetesadapter (any conformant distro, via client-go — k3d and kind are
// the same adapter pointed at a different kubeconfig). It is THIN: the library owns
// Handle assignment/routing, idempotency, the ownership-domain labeling, the state
// machine and status normalization, secret-resolution timing, and the egress/limit
// REQUEST→native translation contract; the adapter owns ONLY (a) talking to one
// substrate and (b) translating its native objects ↔ this vocabulary, INCLUDING
// rollback on partial failure. New routes to it by the spec's (or Config.Default's)
// substrate; conformance runs the SAME suite over each adapter against a REAL
// substrate. Exactly 5 methods (the ceiling, spent).
type Adapter interface {
	// Create provisions the native object (a container + volumes; a namespace + pod +
	// PVC + NetworkPolicy) from spec, with the credential ALREADY resolved by the library
	// (it called Secrets.Resolve and hands an injected credential the adapter places where
	// the substrate reads it — env on the child, a mounted tmpfs file). It returns a
	// HandleData the library wraps as a Workspace. ROLLBACK on partial failure is the
	// adapter's obligation (no orphaned namespaces); a workspace whose declared isolation
	// cannot be applied is an IsolationError, never a degraded success (07 §3).
	Create(ctx context.Context, spec WorkspaceSpec, resolved Resolved) (HandleData, error)

	// Dial re-attaches to an existing native object (the Open path); NotFoundError if
	// gone. It is the substrate-side of orchestrator statelessness.
	Dial(ctx context.Context, handle Handle) (HandleData, error)

	// List mirrors Provider over this adapter's native namespace.
	List(ctx context.Context, selector Selector) ([]Descriptor, error)

	// Destroy mirrors Teardown over this adapter's native namespace. Idempotent
	// (absent == nil).
	Destroy(ctx context.Context, handle Handle) error

	// Manifest declares which optional capabilities this substrate implements (05 §3).
	// DATA, not code. The engine/UI degrade gracefully; the conformance suite verifies
	// the manifest is TRUTHFUL — a declared capability that fails its suite blocks
	// adapter release (05 §6). This is where genuine k3d-vs-kind-vs-EKS-vs-docker
	// divergence is recorded (e.g. a distro without NetworkPolicy CRDs declares
	// CapEgressPolicy absent and the engine flags, not breaks).
	Manifest() CapabilityManifest
}

// Watcher is the OPTIONAL adapter-level supervision seam (ADR-0022 §4): the global
// label-filtered watch over a substrate (docker events on the docker adapter, a k8s pod-watch
// on the kubernetes adapter) plus the raw native event the library normalizes into the
// platform-neutral Event. An Adapter that declares CapSupervise also implements Watcher; the
// library type-asserts for it (an Adapter that does not is supervised by a polling fallback the
// library owns, so Supervise still works — degraded, not broken). It is NOT counted in the
// 5-method Adapter ceiling: it is a SEPARATE optional port the supervising provider type-asserts
// for, exactly as the workload-plane Connection sits beside the substrate-plane Adapter (the same
// split one level down). Exactly 1 method.
type Watcher interface {
	// Watch starts the substrate's global label-filtered watch over selector's ownership domain
	// and streams RAW native events (a WatchEvent per docker action / per pod-phase transition).
	// The library normalizes each into a platform-neutral Event and stamps At from the injected
	// Clock. It FIRST emits a synthetic WatchEvent per already-existing object (reconcile-from-
	// reality: list-by-label re-adoption), then streams live changes. The stream closes when ctx
	// is canceled. A transient watch fault is recovered internally (reconnect with backoff), so
	// the channel stays open across a substrate blip — the orchestrator never sees a silent gap.
	Watch(ctx context.Context, selector Selector) (<-chan WatchEvent, error)
}

// WatchEvent is the adapter's RAW supervision reading the library normalizes into Event: the
// affected workspace Handle, the native action/phase string, the lifecycle State it implies, the
// typed Conditions it carries, and the native reason verbatim. The library — not the adapter —
// maps Action→EventKind, stamps At from the Clock, and emits the platform-neutral Event (so the
// normalization table lives in ONE place, the library, never per-adapter).
type WatchEvent struct {
	Handle     Handle      // the workspace this raw event is for (the adapter derived it from the native object's labels)
	Action     string      // the native action/phase VERBATIM ("start", "die", "destroy", "oom"; "Running", "Failed", "Deleted")
	State      State       // the normalized lifecycle State the adapter read off the native object
	Conditions []Condition // the typed conditions the adapter read (ConditionOOMKilled off a cgroup/container-status, ConditionEvicted)
	Detail     string      // the native reason VERBATIM (exit code, OOMKilled, Evicted) — diagnostics, never normalized
}

// Connection is the live native handle an Adapter returns inside HandleData: the
// substrate-specific driver the library wraps with the state machine, status
// normalization, run/exec/file plumbing, and tenancy stamping. The library never
// reaches into the adapter's native client directly — it drives the substrate ONLY
// through this seam. An Adapter that supports a verb returns a non-nil Connection from
// Create/Dial; the library calls it for Run/Exec/Files/Status. Each method maps one to
// one onto the corresponding Workspace verb so the library owns sequencing/idempotency
// while the adapter owns the substrate call. (Not in the 5-method Adapter ceiling: it
// is the return-value contract of Create/Dial, the WORKLOAD-plane counterpart of the
// SUBSTRATE-plane Adapter — the same split the Provider/Workspace ports make.)
type Connection interface {
	// Run launches the primary workload with the resolved workload credential and
	// returns a native run driver the library wraps as a Run.
	Run(ctx context.Context, spec RunSpec, resolved Resolved) (RunDriver, error)

	// Exec runs one command to completion and returns its raw result.
	Exec(ctx context.Context, spec ExecSpec) (ExecResult, error)

	// Files returns the native file accessor (Put/Get/List against the substrate).
	Files() Files

	// Probe reads the live substrate state the library normalizes into Status.
	Probe(ctx context.Context) (Probe, error)
}

// RunDriver is the adapter-native in-flight workload the library wraps as a Run. Status
// reports the latest native phase; Logs streams the native log buffer from a cursor.
type RunDriver interface {
	// Status reports the latest native workload phase, blocking until it changes or ctx
	// fires; ok=false at a terminal phase or ctx cancellation.
	Status(ctx context.Context) (RunStatus, bool)
	// Logs streams the native combined stdout/stderr from cursor.
	Logs(ctx context.Context, from LogCursor) (io.ReadCloser, error)
}

// Probe is the adapter's raw lifecycle reading the library normalizes into Status: the
// native state mapped to a State, the typed Conditions, the observed usage, and the
// native phase string carried verbatim. The library — not the adapter — stamps Since
// from the injected Clock and enforces the legal State transitions (10 §9).
type Probe struct {
	State      State
	Conditions []Condition
	Usage      ResourceUsage
	Detail     string // adapter-native phase VERBATIM (CrashLoopBackOff, OOMKilled)
}

// HandleData is the adapter's normalized result: the durable Handle plus the live
// native Connection the library wraps with the state machine, status normalization,
// run/exec/file plumbing, and tenancy stamping.
type HandleData struct {
	// Handle is the assigned durable identity (the adapter echoes back the Handle the
	// library passed to Dial, or — for Create — fills it after creating the native
	// object so the library can stamp tenancy and persist it).
	Handle Handle
	// Connection is the live native driver the library drives Run/Exec/Files/Status
	// over. The library never inspects the adapter's underlying client.
	Connection Connection
}
