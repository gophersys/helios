# Contract — workspaceprovider

> Status: Frozen (ADR-0016) · 2026-06-13 · Reconciled from independent producer/consumer drafts
> (09 §4 step 2) and frozen with the library built: the exported surface is mechanically recorded
> at `libs/go/workspaceprovider/.apibaseline` (the freeze made mechanical, ADR-0020) and the
> docker + kubernetes (k3d default, kind second) adapters + the ADR-0020 8-dimension test taxonomy
> are green. The ratified amendment (§7 Q13) is now part of the frozen surface: the concrete
> Provider is `*Provisioner` (not `*Substrate` — that name collides with `type Substrate string`),
> and the adapter's workload-plane seam is an exported `Connection` port (+ `RunDriver`/`Probe`).
> The **F1 Infrastructure (substrate) connector port** (05 §2, 10 §12, C23 "sandbox") — the
> substrate abstraction S2's orchestrator provisions/tears down isolated workspaces over, runs
> workloads in, and execs/mounts/dials-out from. Adapters: `docker` (the daemon) and `kubernetes`
> (any conformant distro; **k3d** the default local/test substrate, **kind** the second conformance
> target, ADR-0016). It composes with the frozen `secrets`/`errors`/`dependencies`/`testing`
> patterns and sits **beneath** the frozen `agentsession` contract: it produces the workspace whose
> path `agentsession.Spec.Workspace` names; `agentsession.Close` never tears down the pod (02 §1) —
> *this* port does. A breaking change to the surface requires a contract revision (ADR-0016 §1) +
> re-recording the `.apibaseline` — the cardinal sin otherwise (10 §9).

## 1. Scope

`workspaceprovider` is the port that **provisions an isolated workspace on a substrate, runs and
execs workloads inside it, mounts files into it, declares its dial-out egress, bounds its resources,
and tears it down** — *one workspace, on one substrate, with one lifecycle* (the 02 §1 Workspace;
where agent sessions run, C22/C23). It is **one contract with two adapters and zero distro forks**: a
workspace on `docker` and a workspace on `kubernetes`-via-k3d or kubernetes-via-kind are the same
`Workspace` driven by the same verbs; distro divergence lives **only** in the `CapabilityManifest`
(05 §3), and the conformance suite running over both adapters against **real substrates** is the
proof of that claim (05 §6, ADR-0016 §2/§4). The central multi-tenant cluster is an ordinary
`kubernetes` adapter instance with **zero special code paths** (ADR-0012): central, BYO, and local
are the same `Substrate` over the same adapter, differing only in the injected client configuration.

It owns exactly four things:

1. **Substrate lifecycle** — provision an isolated workspace, re-attach to an existing one by handle
   (the stateless-orchestrator re-dial across restarts), list the ones Eden authored (the
   drift-detection ownership domain, 05 §5), and tear one down. This is the half S2's reconcile loop
   (`Reconcile(ctx, key)`, 10 §7.1) drives.
2. **Workload control** — start a long-running workload in a workspace (the agent harness, a
   remote-VS-Code server, a CI step), exec a one-shot command in a running workspace (the
   `kubectl exec` / `docker exec` plane), and observe workload state. This is what the F4
   `agentsession` adapter spawns *into* (05 §2: "the F4 connector owns what runs inside the pod" —
   this port owns the pod).
3. **The mount, file, and dial-out surface, declared as data** — file mounts (workspace source,
   read-only clean-room inputs, tmpfs for credential vehicles), a narrow file seam
   (declared-inputs-in / artifacts-out, 07 §4), resource limits (cpu/memory/storage/pids), and the
   **declared egress set** the workspace needs (model-provider + granted-tool endpoints), from which
   the kubernetes adapter derives a `NetworkPolicy` and the docker adapter derives firewall rules.
   Default-deny is the contract; the workspace **declares** its egress, the adapter **enforces** it
   (07 §3). Dial-out-only is structural — the spec carries no ingress field, so a listener cannot be
   requested.
4. **Configurability** — which substrate adapter serves a request, and the per-workspace spec
   (image/template, mounts, limits, egress, tenancy keys), resolved upstream and handed in frozen.

It explicitly does **not** own (the consumer must not expect these here):

- **What runs *inside* an agent pod beyond launch** — harness invocation, the normalized event
  stream, tool grants, transcript capture are the **F4 `agentsession` port** (05 §2, agentsession.md).
  This port `Start`s the harness *process group* / spawns *into* the workspace and reports liveness; it
  does not parse a harness wire format or own the Event taxonomy. The seam is exact and bidirectionally
  cited: `agentsession.Adapter.Spawn` runs in a workspace this port provisioned (reached via
  `Provider.Open`), and `agentsession.Session.Close` **never** tears down the workspace —
  `Provider.Teardown` (this port) does. The only coupling is a **path string**
  (`Workspace` → `agentsession.Spec.Workspace`); no type dependency either direction.
- **Credential storage / minting** — the `secrets` port + vault (07 §2). A `WorkspaceSpec` /
  `MountSpec` / `RunSpec` / `EgressRule` carries an opaque `secrets.Reference` (a registry pull-secret,
  a workload token, TLS material); the value is resolved server-side by the **library** at the
  injection time via the injected `secrets.Provider` and **never** enters the `Spec`, a `Handle`, a
  `Status`, a log, an `Event`, or an image layer. This port carries refs, never values.
- **The dial-out broker / tunnel mesh** — WireGuard mesh + DERP relay (`broker`, 10 §12) and the
  in-workspace dial-out agent (`apps/agent`, the `management` pattern, 07 §3) are separate libraries.
  This port **provisions the workspace the dial-out agent runs in** and **declares the egress it
  needs**; it does not implement the tunnel. `EgressRule` is the data the broker and the adapter's
  NetworkPolicy consume; this port opens no socket.
- **Orchestration / reconcile policy** — the desired-vs-actual loop, idle/hibernate, pre-warm pools,
  quotas (`orchestrator`, `policy`, 10 §12) are S2's. This port exposes the level-based primitives
  (`Provision`/`Open`/`List`/`Teardown`) a reconcile loop is built *from*; it is not itself the loop.
  `List` over the ownership domain is the observe step; the loop diffs and decides. The egress-derivation
  policy (`agentsession` `Route`+`Grants` → `[]EgressRule`) is **orchestrator-owned**, not substrate-owned.
- **Registry, DNS, object storage, Postgres-class DB, metrics ingestion** — the F1 family contract
  *summary* (05 §2) lists these as substrate obligations, but they are **separate ports** under the
  same family, negotiated separately (one concept, one home). This contract is the **compute-substrate**
  core: workspaces, workloads, exec, mounts, files, egress, limits. (Open question Q1 records the
  boundary and the additive seam if they later land here.)
- **Image building / registry push** — a separate Package-phase concern; this port pulls an image by
  ref, it does not build or push one.
- **Usage metering / billing** — the F1 usage meter normalizes consumption into `UsageRecord`
  (05 §1, S9). This port **emits** resource-observation data on `Status`; folding it into
  `UsageRecord` and enforcing quotas is the meter's / `policy`'s job.

It cites, never redefines: `Workspace` / `Environment` / `Platform(substrate)` / `Connector` /
`CapabilityManifest` / `DriftEvent` (02 §1), `Secret` / `Reference` (secrets.md), `Kind` / `*Error`
(errors.md), `Clock` / `RandomSource` (dependencies.md), the `Suite[S]`/`Factory[S]`/`Harness`/`RunSuite`
conformance construct (testing.md). It sits beneath `agentsession` (agentsession.md §1).

## 2. Contract

```go
// Package workspaceprovider is the Eden F1 Infrastructure (substrate) port (05 §2,
// 10 §2/§12, C23): it provisions an isolated Workspace on a substrate (the docker
// daemon or any conformant kubernetes distro), runs and execs workloads in it,
// mounts files, declares its dial-out egress, bounds its resources, and tears it
// down — one Workspace, one substrate, one lifecycle (02 §1). It is the substrate
// ABSTRACTION S2's orchestrator holds; an Adapter (dockeradapter, kubernetesadapter)
// is the only place a daemon/cluster SDK is imported (05 §1).
//
// It is ONE contract with two adapters and ZERO distro forks: a Workspace on docker
// and a Workspace on kubernetes(k3d|kind|EKS|…) are the same types driven by the same
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
// Module: github.com/gophersys/libs/go/workspaceprovider  (go 1.26)
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
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/secrets"
)

// ── The two ports (split to honor the ≤5-method ceiling, 10 §9) ───────────────
//
// Provider is the SUBSTRATE plane (provision/open/list/teardown) S2's reconcile loop
// drives. Workspace is the WORKLOAD plane (run/exec/files/status) a handle exposes.
// Splitting keeps each interface ≤5 methods AND models the real seam: the orchestrator
// holds a Provider; the agentsession adapter, the engine's clean-room harness, and the
// chat backend's editor backend hold a Workspace.

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
	// reconcile contract, 10 §7.1). Errors: InvalidSpecError (Kind=Invalid);
	// ConflictError (Kind=Conflict — same Name, incompatible spec); QuotaExceededError
	// (Kind=Exhausted — tenancy quota, 07 §6); ImageError (Kind=Invalid — unpullable
	// image / denied pull-secret); IsolationError (Kind=Permission — declared
	// egress/mounts/limits could not be applied; FAIL-CLOSED, never returned Ready);
	// SubstrateUnavailableError (Kind=Unavailable — daemon/apiserver unreachable, the
	// one retryable signal).
	Provision(ctx context.Context, spec WorkspaceSpec) (Workspace, error)

	// Open re-attaches to an already-provisioned workspace by Handle (a pod recycle, a
	// control-plane restart, a second orchestrator replica adopting a workspace it did
	// not create). It is PURELY a re-dial — it provisions nothing. The Handle is the
	// ONLY durable per-workspace state the orchestrator keeps, so Open is what makes it
	// stateless across restarts. NotFoundError (Kind=NotFound) if the workspace no
	// longer exists (torn down, evicted, GC'd).
	Open(ctx context.Context, handle Handle) (Workspace, error)

	// List enumerates the workspaces Eden authored within a tenancy that match selector
	// — the OBSERVE step of the reconcile loop (10 §7.1) and the drift detector's
	// ownership-domain scan (05 §5). It returns Descriptors (metadata, not live
	// handles); the loop diffs observed vs desired and decides. MUST page internally
	// and return the full set (the loop needs the complete domain to detect orphans).
	// Cross-tenant listing is impossible by construction (the tenancy keys are part of
	// the selector, enforced by the adapter, 07 §6).
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
	// while one is Running is a NotReadyError-class StateError. It returns a Run handle
	// once the process is launched (not once it exits); liveness/exit ride Run.Status,
	// raw output rides Run.Logs. The credential the workload needs is named by an opaque
	// secrets.Reference in RunSpec and resolved server-side, injected by the adapter at
	// the injection site only (env on the CHILD process / a tmpfs helper file) — never
	// logged, never in RunSpec-as-logged (07 §2). The agentsession adapter's Spawn is a
	// Run with the harness argv + the InjectedCredential vehicle. NotReadyError if the
	// workspace is not Ready; QuotaExceededError if the run would breach bound limits.
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
	// under a read-only MountInputs target is a StateError.
	Put(ctx context.Context, path string, content io.Reader, mode FileMode) error
	// Get reads path back out (the produced artifact: a worktree diff, a built binary, a
	// coverage profile the engine folds into Evidence, 02 §2). NotFoundError if the path
	// does not exist.
	Get(ctx context.Context, path string) (io.ReadCloser, error)
	// List enumerates entries under path (shallow) so the engine collects a produced
	// artifact set without a shell. Bounded; the substrate paginates large trees.
	List(ctx context.Context, path string) ([]FileEntry, error)
}

// ── The adapter seam (the ONLY place a substrate SDK is imported, 05 §1) ──────
//
// Adapter is the per-substrate implementation: dockeradapter (the daemon, via the
// Docker SDK) and kubernetesadapter (any conformant distro, via client-go — k3d and
// kind are the same adapter pointed at a different kubeconfig). It is THIN: the library
// owns Handle assignment/routing, idempotency, the ownership-domain labelling, the
// state machine and status normalization, secret-resolution timing, and the
// egress/limit REQUEST→native translation contract; the adapter owns ONLY (a) talking
// to one substrate and (b) translating its native objects ↔ this vocabulary, INCLUDING
// rollback on partial failure. Exactly 5 methods (the ceiling, spent).

// Adapter is one substrate implementation. New routes to it by the spec's (or
// Config.Default's) substrate; conformance runs the SAME suite over each adapter
// against a REAL substrate.
type Adapter interface {
	// Create provisions the native object (a container + volumes; a namespace + pod +
	// PVC + NetworkPolicy) from spec, with the credential ALREADY resolved by the library
	// (it called Secrets.Resolve and hands an InjectedCredential the adapter places where
	// the substrate reads it — env on the child, a mounted tmpfs file). It returns a
	// HandleData the library wraps as a Workspace. ROLLBACK on partial failure is the
	// adapter's obligation (no orphaned namespaces); a workspace whose declared isolation
	// cannot be applied is an IsolationError, never a degraded success (07 §3).
	Create(ctx context.Context, spec WorkspaceSpec, resolved Resolved) (HandleData, error)
	// Dial re-attaches to an existing native object (the Open path); NotFoundError if
	// gone. It is the substrate-side of orchestrator statelessness.
	Dial(ctx context.Context, handle Handle) (HandleData, error)
	// List / Destroy mirror Provider over this adapter's native namespace. Destroy is
	// idempotent (absent == nil).
	List(ctx context.Context, selector Selector) ([]Descriptor, error)
	Destroy(ctx context.Context, handle Handle) error
	// Manifest declares which optional capabilities this substrate implements (05 §3).
	// DATA, not code. The engine/UI degrade gracefully; the conformance suite verifies
	// the manifest is TRUTHFUL — a declared capability that fails its suite blocks
	// adapter release (05 §6). This is where genuine k3d-vs-kind-vs-EKS-vs-docker
	// divergence is recorded (e.g. a distro without NetworkPolicy CRDs declares
	// CapEgressPolicy absent and the engine flags, not breaks).
	Manifest() CapabilityManifest
}

// HandleData is the adapter's normalized result: the durable Handle plus the live native
// Connection the library wraps with the state machine, status normalization, run/exec/file
// plumbing, and tenancy stamping. The library never reaches into the adapter's underlying
// client — it drives the substrate ONLY through the Connection seam.
//
// ⚠️ DRAFT AMENDMENT (Q13): the original draft left the native field UNEXPORTED ("the
// adapter's native client/conn"). In the implementation the workload-plane seam is an
// EXPORTED port — Connection — exactly mirroring the SUBSTRATE-plane Adapter split (the same
// Provider/Workspace split the §2 ports make). An Adapter.Create/Dial returns a Connection;
// the library calls it for Run/Exec/Files/Probe. This is additive (a new exported port + two
// small value/port types), not a change to the frozen Provider/Workspace/Run/Files/Adapter
// surfaces. See §7 Q13.
type HandleData struct {
	Handle     Handle
	Connection Connection // the live native driver the library drives Run/Exec/Files/Status over
}

// Connection is the live native handle an Adapter returns inside HandleData — the
// WORKLOAD-plane counterpart of the SUBSTRATE-plane Adapter (the library owns sequencing/
// idempotency/state-machine; the adapter owns the substrate call). Exactly 4 methods.
type Connection interface {
	// Run launches the primary workload with the resolved workload credential and returns a
	// native RunDriver the library wraps as a Run.
	Run(ctx context.Context, spec RunSpec, resolved Resolved) (RunDriver, error)
	// Exec runs one command to completion and returns its raw result.
	Exec(ctx context.Context, spec ExecSpec) (ExecResult, error)
	// Files returns the native file accessor (Put/Get/List against the substrate).
	Files() Files
	// Probe reads the live substrate state the library normalizes into Status.
	Probe(ctx context.Context) (Probe, error)
}

// RunDriver is the adapter-native in-flight workload the library wraps as a Run: Status
// reports the latest native phase (RunKilled/ConditionOOMKilled for a cgroup OOM-kill); Logs
// streams the native log buffer from a cursor. (Exactly 2 methods, mirroring Run.)
type RunDriver interface {
	Status(ctx context.Context) (RunStatus, bool)
	Logs(ctx context.Context, from LogCursor) (io.ReadCloser, error)
}

// Probe is the adapter's raw lifecycle reading the library normalizes into Status: the native
// state mapped to a State, the typed Conditions, the observed usage, and the native phase
// string verbatim. The library — not the adapter — stamps Since from the injected Clock and
// enforces the legal State transitions (10 §9).
type Probe struct {
	State      State
	Conditions []Condition
	Usage      ResourceUsage
	Detail     string // adapter-native phase VERBATIM (CrashLoopBackOff, OOMKilled)
}

// ── The constructor spine (10 §4) — PURE ──────────────────────────────────────

// New is the pure constructor spine: no I/O, no clock read, no env read, no daemon
// dial, no apiserver call. It validates Config + Deps and returns the concrete
// *Provisioner. The first substrate I/O happens only at Provider.Provision/Open/List.
//
// ⚠️ DRAFT AMENDMENT (Q13, pending Mateo's ratification): the original draft wrote
// `New(...) (*Substrate, error)`, but `type Substrate string` (the substrate-selector,
// below) already owns that name — a Go program cannot declare both. The concrete
// Provider returned by New is therefore named *Provisioner. See §7 Q13.
func New(configuration Config, dependencies Deps) (*Provisioner, error) { return nil, nil }

// Config is the immutable, fully-resolved input (the configuration pattern: parsed at
// the edge, frozen). It holds the substrate-routing default and the tenancy namespace;
// it reads NO env, NO clock, NO secret value.
type Config struct {
	// Default routes a WorkspaceSpec that names no Substrate (the common single-
	// substrate app). Empty means "require an explicit Substrate" (a substrate-less spec
	// then yields InvalidSpecError). The central/local/BYO posture selects WHICH adapter
	// this default binds at the composition root (ADR-0012's "zero special code paths").
	Default Substrate
	// Namespace is the workspace-id / k8s-namespace / docker-label prefix that scopes
	// THIS Provider's ownership domain (05 §5) and keeps tenancies disjoint
	// (namespace-per-project on the multi-tenant central cluster, 07 §6); empty for
	// single-tenant local/BYO.
	Namespace string
}

// Deps is the injected hexagon. New constructs no ports.
type Deps struct {
	// Adapters maps a Substrate to its Adapter (the lower substrate seam). At least one
	// is required; New errors otherwise. The docker adapter and the kubernetes adapter
	// are the two v1 entries (05 §2); a managed kubernetes (EKS/GKE/AKS/DO) is the SAME
	// kubernetes adapter with a different client config — not a new adapter (02 §1: cloud
	// vendors are managed adapters of the kubernetes substrate, not substrates).
	Adapters map[Substrate]Adapter
	// Secrets resolves the opaque secrets.Reference in a spec (registry pull-secret,
	// workload token, TLS material) to a short-lived *secrets.Secret at Provision/Run
	// time, server-side, so the value reaches the substrate per the credential seam and
	// NEVER enters the spec, a Handle, a Status, a log, or an Event (07 §2). The library
	// resolves; the adapter injects.
	Secrets secrets.Provider
	// Clock stamps Descriptor/Status timestamps and bounds graceful-drain waits. Injected
	// so New stays pure and the fake is deterministic (dependencies.Clock).
	Clock dependencies.Clock
}

// Provisioner is the concrete Provider returned by New (⚠️ DRAFT AMENDMENT Q13: the draft
// called this *Substrate, which collides with `type Substrate string`; renamed to
// *Provisioner). It routes each Provision/Open/List/Teardown to the Deps.Adapters entry
// for the spec's (or Config.Default's) Substrate, resolves secrets.References server-side
// before handing control to the adapter, assigns/validates Handles and stamps them with
// tenancy keys, wraps adapter HandleData as Workspaces, and enforces the ownership-domain
// labelling. It ALSO owns idempotency: it stamps a spec fingerprint into the persisted
// labels at Provision so a same-Name re-Provision is COMPATIBLE (re-dial) or INCOMPATIBLE
// (ConflictError). Safe for concurrent use. Zero value unusable; construct via New.
type Provisioner struct{ /* unexported */ }

func (s *Provisioner) Provision(ctx context.Context, spec WorkspaceSpec) (Workspace, error) { return nil, nil }
func (s *Provisioner) Open(ctx context.Context, handle Handle) (Workspace, error)           { return nil, nil }
func (s *Provisioner) List(ctx context.Context, sel Selector) ([]Descriptor, error)         { return nil, nil }
func (s *Provisioner) Teardown(ctx context.Context, handle Handle) error                    { return nil }

// ── Identity ──────────────────────────────────────────────────────────────────

// Handle is the durable, loggable identity of a provisioned workspace — the join key
// between Eden's records and substrate state, and the ONLY durable per-workspace state
// the orchestrator keeps (Open re-dials from it across restarts). Comparable (a map key
// for the reconcile loop), loggable by contract (carries no secret), and tenancy-bearing.
// Constructed by the library at Provision (never by a consumer); ParseHandle round-trips
// its canonical string for persistence. Zero value: invalid (IsZero true).
type Handle struct {
	raw string // canonical, e.g. "kubernetes://eden/org-7/proj-42/ws-9f3a" or "docker://ws-9f3a"
}

// ParseHandle reconstructs a Handle from its persisted canonical form. PURE;
// shape-validated; InvalidHandleError (Kind=Invalid) on malformed input. The
// orchestrator stores Handle.String() and re-hydrates with this across restarts.
func ParseHandle(s string) (Handle, error) { return Handle{}, nil }

func (h Handle) String() string       { return h.raw } // loggable by design
func (h Handle) Substrate() Substrate  { return "" }    // "docker" | "kubernetes" — routes Open/Teardown
func (h Handle) WorkDir() string       { return "" }    // the path the harness runs in → agentsession.Spec.Workspace
func (h Handle) Organization() string  { return "" }    // tenancy key (07 §6); "" for single-tenant local/BYO
func (h Handle) Project() string       { return "" }    // tenancy key (07 §6)
func (h Handle) IsZero() bool          { return h.raw == "" }

// ── The WorkspaceSpec: provision input, declared as DATA ──────────────────────

// WorkspaceSpec is the immutable, fully-resolved request for ONE isolated workspace
// (the configuration pattern). It is DATA: an adapter reads it, it carries no behavior.
// It holds NO live handles and NO secret VALUES — only loggable secrets.References. This
// is the substrate's whole provision vocabulary; the consumer writes ONE spec shape and
// the adapter realizes it on either substrate (distro transparency, 05 §6).
type WorkspaceSpec struct {
	Name             string            // stable, tenancy-scoped logical name; idempotency key for Provision
	Substrate        Substrate         // "" routes via Config.Default
	Image            string            // OCI image ref (the template/devcontainer/agent-runtime/code-server image, 02 §1 Archetype)
	ImagePull        secrets.Reference // OPTIONAL registry pull-secret; resolved server-side at Provision; zero == public image; never the value
	Mounts           []Mount           // file/dir/tmpfs mounts (worktree, read-only clean-room inputs, credential-vehicle tmpfs)
	Resources        Resources         // cpu/memory/storage/pids ceilings (07 §3 isolation; 07 §6 tenancy quota)
	Egress           []EgressRule      // the DECLARED dial-out set; default-deny otherwise (07 §3). Adapter derives NetworkPolicy/firewall. No ingress field exists: dial-out-only is structural.
	Labels           map[string]string // ownership-domain + tenancy tags (Organization/Project, 07 §6); queryable via Selector
	Env              []EnvVar          // NON-secret environment for the workspace; secret env goes via a MountSecret, never here
	ProvisionTimeout time.Duration     // bounds the Ready handshake; 0 == ctx bounds it
}

// Mount is one mount, as data. Source semantics depend on Kind; the adapter maps it to
// a bind mount / volume / configMap / tmpfs.
type Mount struct {
	Kind     MountKind         // Bind | Volume | Tmpfs | Inputs | Secret
	Target   string            // absolute path in the workspace (the default Bind/Inputs target becomes WorkDir)
	Source   string            // host path (Bind), volume name (Volume), "" (Tmpfs/Inputs)
	Ref      secrets.Reference // Kind==Secret: the opaque ref resolved server-side and written to a tmpfs Target (07 §2)
	ReadOnly bool              // the clean-room declared-inputs mount is read-only (07 §4)
}

type MountKind uint8

const (
	MountBind   MountKind = iota // host path -> workspace (local-as-a-cluster dev; the source worktree)
	MountVolume                  // a named persistent volume (CapPersistentVolume)
	MountTmpfs                   // in-memory scratch (credential vehicles land here, never an image layer — 07 §2)
	MountInputs                  // a read-only inputs volume seeded via Files.Put before Run (07 §4 clean room)
	MountSecret                  // a secrets.Reference resolved server-side and written to a tmpfs Target
)

// EgressRule is one declared dial-out destination. The workspace DECLARES what it needs
// (model-provider endpoint, a granted tool's endpoint — derivable by the orchestrator
// from agentsession ToolGrants, 05 §2); the adapter ENFORCES default-deny + these allows
// (07 §3). This is the data F1's NetworkPolicy / the broker consume; this port opens no
// socket and runs no tunnel.
type EgressRule struct {
	Host  string            // FQDN or CIDR the workspace may connect OUT to, e.g. "api.anthropic.com"
	Ports []int             // empty == 443 only
	Note  string            // provenance, e.g. "anthropic api", "grant:Bash(go *) module proxy"
	Ref   secrets.Reference // OPTIONAL mTLS client-material ref for this destination; resolved server-side; never the value
}

// Resources bounds the workspace (07 §3 isolation; 07 §6 quota). Integer milli-units and
// bytes — no float drift across millions of pods (aligned with the CostMicros discipline
// in observability/agentsession). Zero in a field == the adapter/tenancy default (NOT
// unbounded — the multi-tenant adapter substitutes the quota policy's ceiling; unbounded
// only where the manifest declares CapResourceLimits absent).
type Resources struct {
	CPUMilli     int64 // 1000 == one core; the docker-compose `cpus` / k8s cpu request+limit
	MemoryBytes  int64 // the memory limit; an OOMKill surfaces as ConditionOOMKilled
	StorageBytes int64 // ephemeral-storage limit
	PIDs         int64 // fork-bomb ceiling
}

type EnvVar struct{ Name, Value string } // NON-secret only; secrets go via MountSecret / RunSpec.Credential

// ── Workload / Exec ───────────────────────────────────────────────────────────

// RunSpec is the request to run ONE primary workload in a provisioned workspace. The
// agentsession adapter builds this from the harness argv + the credential vehicle; a CI
// executor builds it from the step command; the chat backend from the code-server argv.
type RunSpec struct {
	Command    []string          // argv; empty == the image's default entrypoint
	Env        []EnvVar          // NON-secret workload env; credential env is placed by the adapter via Credential, not here
	WorkDir    string            // "" == the workspace's default mount target
	Credential secrets.Reference // OPAQUE; resolved server-side and injected by the adapter at the injection site; never the value
	Vehicle    CredentialVehicle // how the workload reads it (env on the child / a mounted tmpfs file)
	TTY        bool              // allocate a PTY (interactive sessions)
}

// ExecSpec is the synchronous one-shot exec verb (docker exec / kubectl exec):
// readiness probes, git invocations, a one-shot test command, open-in-shell.
type ExecSpec struct {
	Command []string
	Stdin   io.Reader     // optional; nil == none
	Stdout  io.Writer     // optional; nil == discarded (or buffered into ExecResult, bounded)
	Stderr  io.Writer     // optional; nil == discarded (or buffered into ExecResult, bounded)
	WorkDir string
	TTY     bool          // PTY for open-in-shell; CapExecPTY-gated
	Timeout time.Duration // 0 == ctx bounds it; exceed == DeadlineError
}

// ExecResult is the synchronous result of an Exec.
type ExecResult struct {
	ExitCode int
	Stdout   []byte // bounded, redaction-eligible; large output streams via a Run instead
	Stderr   []byte // bounded, redaction-eligible
	Detail   string // adapter-native exec diagnostics, verbatim
}

// CredentialVehicle mirrors agentsession's seam so the substrate and the harness agree
// on how a credential reaches a child process (07 §2, agentsession §2).
type CredentialVehicle uint8

const (
	VehicleEnv  CredentialVehicle = iota // env var on the CHILD process ONLY, scrubbed of higher-precedence keys
	VehicleFile                          // a short-lived token written to a tmpfs file the workload reads
)

// ── Observation / value types ─────────────────────────────────────────────────

// Substrate selects the adapter. Closed-by-convention but string-typed so a new managed
// adapter (EKS/GKE/AKS/DO ⊂ kubernetes) registers without a code change to this library
// (05 §2: cloud vendors are managed adapters of substrates).
type Substrate string

const (
	SubstrateDocker     Substrate = "docker"     // the daemon
	SubstrateKubernetes Substrate = "kubernetes" // ANY conformant distro (k3d default, kind 2nd target, EKS/GKE/AKS/DO later)
)

// Descriptor is workspace METADATA (no live handle) — what List returns and the
// reconcile loop / drift detector diff (05 §5, 10 §7.1).
type Descriptor struct {
	Handle    Handle
	Name      string
	Substrate Substrate
	State     State
	Labels    map[string]string // the ownership-domain + tenancy tags
	CreatedAt time.Time         // Clock-stamped
}

// Selector filters List by tenancy + labels (cross-tenant impossible: the tenancy keys
// are a required label match enforced by the adapter, 07 §6).
type Selector struct {
	Labels map[string]string // exact-match label set (MUST include the tenancy keys on the multi-tenant cluster)
}

// State is the workspace lifecycle. Closed taxonomy, additive-only (10 §9). Legal
// transitions are enforced by the library, not the adapter: Provisioning → Ready →
// {Degraded → Ready | Evicted} → Gone. A terminal state (Gone) never transitions. The
// adapter-native phase rides Status.Detail verbatim.
type State uint8

const (
	StateProvisioning State = iota // image pulling / namespace+pod creating; Ready handshake not yet confirmed
	StateReady                     // provisioned; mounts attached; egress installed; limits bound — accepts Run/Exec
	StateRunning                   // a primary workload is Running (Run started and live)
	StateDegraded                  // running but a Condition fired (probe failing, memory pressure) — recoverable; Detail carries the native reason
	StateEvicted                   // the substrate reclaimed it out-of-band (node pressure, preemption) — the DRIFT signal (05 §5)
	StateGone                      // terminal: torn down / GC'd / never existed; Open -> NotFoundError
)

// Status is the live observed state + a typed Condition snapshot + a resource snapshot
// (the meter's input, S9; the reconcile-loop + dashboard read).
type Status struct {
	State      State
	Conditions []Condition   // typed, branchable substrate conditions
	Usage      ResourceUsage // observed cpu/memory/storage — folded into UsageRecord by the F1 meter
	Detail     string        // adapter-native phase VERBATIM (CrashLoopBackOff, OOMKilled) for diagnostics; NOT a normalized field
	Since      time.Time     // when State was entered (Clock-stamped)
}

// Condition is one typed, branchable substrate condition (NOT a free-form string — the
// engine/orchestrator branch on it). Closed, additive-only (10 §9).
type Condition uint8

const (
	ConditionReady         Condition = iota
	ConditionImagePulling
	ConditionOOMKilled                 // a workload exceeded MemoryBytes — the runaway-agent signal (02 §2)
	ConditionEvicted                   // node pressure / preemption (the drift surface, 05 §5)
	ConditionUnschedulable             // no node satisfies the resource request (a capacity/quota signal)
	ConditionEgressDenied              // a dial-out to a non-allowlisted host was blocked (07 §3 evidence)
)

// RunStatus is one workload's status (Run.Status transitions).
type RunStatus struct {
	Phase     RunPhase
	ExitCode  int       // valid at terminal
	Condition Condition // ConditionOOMKilled etc. at a Failed/Killed terminal
	Detail    string    // adapter-native exit reason, verbatim
}

type RunPhase uint8

const (
	RunPending   RunPhase = iota
	RunRunning
	RunSucceeded // terminal
	RunFailed    // terminal
	RunKilled    // terminal: aborted via ctx / Teardown / OOM
)

type ResourceUsage struct {
	CPUMilli     int64
	MemoryBytes  int64
	StorageBytes int64
}

// FileMode / FileEntry / LogCursor — narrow value types for the file & log seams.
type FileMode uint32
type FileEntry struct {
	Name  string
	IsDir bool
	Size  int64
	Mode  FileMode
}
type LogCursor uint64

// Resolved is the server-side-resolved secret material handed to an Adapter at Create:
// the library called Deps.Secrets.Resolve for every secrets.Reference in the spec and
// hands the adapter un-printable *secrets.Secret values keyed by where they go. The
// adapter calls Secret.Use at the injection site ONLY; the value never re-enters the
// spec, a Handle, a Status, a log, or an image layer (07 §2). Empty fields == no
// credential for that slot.
type Resolved struct {
	PullSecret *secrets.Secret            // nil if Spec.ImagePull was zero
	Mounts     map[string]*secrets.Secret // MountSecret Target -> resolved material
	Egress     map[string]*secrets.Secret // EgressRule Host    -> resolved mTLS material
	Workload   *secrets.Secret            // RunSpec.Credential -> resolved workload token (nil if zero)
}

// ── CapabilityManifest: where genuine substrate divergence lives (05 §3) ──────

// CapabilityManifest is the adapter's truthful declaration (DATA, not code) of which
// optional capabilities the substrate implements. The engine/UI degrade gracefully (a
// feature needing CapPersistentVolume is disabled on a substrate lacking it, not
// broken — a workspace without enforced egress is FLAGGED, not broken, per C18's
// permanently-visible guarantee badge); the conformance suite verifies truthfulness
// (05 §6). This is the ONE place k3d/kind/docker/EKS divergence is recorded — distro
// transparency is the claim, the manifest is its honest escape hatch.
type CapabilityManifest struct {
	Capabilities map[Capability]CapStatus
	Distro       string // free-form distro identity, e.g. "k3d v5.x / k3s", "kind v0.32", "docker 29.4" — telemetry/UI only
}

type Capability uint8

const (
	CapExecPTY          Capability = iota // interactive PTY exec/run (open-in-shell)
	CapPersistentVolume                   // named persistent volumes (MountVolume) survive restart
	CapBindMount                          // host bind mounts (local-as-a-cluster dev; docker:full, k3d:via hostPath, EKS:absent)
	CapEgressPolicy                       // enforces declared egress / default-deny — DISTRO-DIVERGENT (k8s NetworkPolicy CRDs; docker firewall)
	CapResourceLimits                     // honors Resources (cgroups / k8s requests+limits)
	CapLogStream                          // Run.Logs follow-from-cursor (vs one-shot)
	CapMultiTenant                        // namespace-per-project isolation + quotas (the central cluster, 07 §6)
	CapReattach                           // Provider.Open re-dial survives a control-plane restart
	CapHibernate                          // pause/resume without teardown (policy idle/hibernate, 10 §12) — deferred verb, Q4
)

type CapStatus uint8

const (
	CapAbsent  CapStatus = iota // feature gated off in the UI, not broken (05 §3)
	CapPartial                  // e.g. egress allow-by-host but not by-CIDR; buffered-only Exec where streaming is full
	CapFull
)

// ── Errors (typed, errors.AsType-first, every error carries a Kind) ───────────

type (
	// InvalidSpecError: malformed WorkspaceSpec (no Image, unknown Substrate, bad mount
	// path). Kind=Invalid.
	InvalidSpecError struct{ Field, Reason string }
	// ImageError: unpullable/missing image (bad ref, ImagePull credential denied —
	// carries the secrets.Reference, NEVER the value). Kind=Invalid.
	ImageError struct{ Image string; Ref secrets.Reference }
	// NotFoundError: no such workspace/path in the caller's tenancy (Open/Teardown/
	// Files.Get for an absent workspace or path). Kind=NotFound.
	NotFoundError struct{ Handle Handle; Path string }
	// ConflictError: a non-idempotent name/state collision (a Provision whose Name
	// exists with an INCOMPATIBLE spec). Kind=Conflict.
	ConflictError struct{ Name string }
	// QuotaExceededError: a provision/run that would breach the tenant's bound limits
	// (07 §6) — the central-cluster cross-tenant defense made a typed signal.
	// Kind=Exhausted (retry after reclaim, not immediately).
	QuotaExceededError struct{ Handle Handle; Resource string } // "cpu" | "memory" | "workspaces"
	// IsolationError: a failure to apply the declared isolation/egress guarantees
	// (NetworkPolicy rejected, namespace creation denied) — a HARD, fail-closed failure:
	// a workspace without its declared isolation is NEVER returned Ready (07 §3).
	// Kind=Permission.
	IsolationError struct{ Handle Handle; Detail string }
	// SubstrateUnavailableError: the daemon/apiserver is unreachable or returned a
	// transient fault — the one retryable signal the reconcile loop backs off on.
	// Kind=Unavailable.
	SubstrateUnavailableError struct{ Substrate Substrate; Op string }
	// NotReadyError: a Run/Exec/Files-write called in an illegal State (Exec before
	// Ready, a second Run while Running, a write under a read-only Inputs mount).
	// Kind=Invalid. (The producer's StateError, folded here.)
	NotReadyError struct{ Handle Handle; State State; Op string }
	// DeadlineError: an Exec/provision that exceeded its timeout. Kind=Deadline.
	DeadlineError struct{ Op string }
	// UnsupportedError: a verb needing a Capability the adapter declares absent
	// (MountVolume on a substrate without CapPersistentVolume; PTY exec without
	// CapExecPTY). Kind=Invalid.
	UnsupportedError struct{ Cap Capability }
	// InvalidHandleError: a malformed/zero Handle. Kind=Invalid.
	InvalidHandleError struct{ Raw string }
)

// Each Error() carries the offending handle/field/substrate/ref, NEVER a secret value,
// and each maps to a stable errors.Kind so the transport boundary needs no per-port
// table (errors.md §5, 10 §9). (Method bodies omitted in the draft.)
func (e *InvalidSpecError) Error() string          { return "" }
func (e *ImageError) Error() string                { return "" }
func (e *NotFoundError) Error() string             { return "" }
func (e *ConflictError) Error() string             { return "" }
func (e *QuotaExceededError) Error() string        { return "" }
func (e *IsolationError) Error() string            { return "" }
func (e *SubstrateUnavailableError) Error() string { return "" }
func (e *NotReadyError) Error() string             { return "" }
func (e *DeadlineError) Error() string             { return "" }
func (e *UnsupportedError) Error() string          { return "" }
func (e *InvalidHandleError) Error() string        { return "" }
```

## 3. Fake

```go
// Package workspaceprovidertest is the canonical public fake + the REAL-SUBSTRATE
// conformance harnesses (the testing pattern, 10 §4 / 08 §2). It owns THREE things
// C23 demands as a deliverable, in separate files of ONE package so a consumer imports
// one thing:
//
//  (a) a deterministic in-memory FAKE Adapter (and a one-call FakeProvider) — no daemon,
//      no cluster — so ANY consumer (S2's orchestrator, the F4 agentsession adapter, the
//      engine's clean-room harness, the chat editor backend) unit-tests its logic
//      against the port in microseconds without a substrate;
//
//  (b) the ONE conformance Suite every adapter runs against a REAL substrate (ADR-0016
//      — never a mock); the fake runs it too (the fake ≡ adapter closure, 08 §2); and
//
//  (c) the REAL-SUBSTRATE HARNESSES (the C23 deliverable, owned HERE by ruling Q3):
//      EphemeralContainer (spins one throwaway container on the docker daemon),
//      K3dCluster (the DEFAULT distro) and KindCluster (the SECOND conformance target),
//      each returning a live Adapter bound to its substrate and reaping everything on
//      t.Cleanup — the utilities every consumer's integration tests reuse (C23: "Go
//      tests must spin up real containers and a local kubernetes cluster").
package workspaceprovidertest

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// ── (a) the deterministic in-memory fake ──────────────────────────────────────

// Adapter is a deterministic in-memory workspaceprovider.Adapter. It models the State
// machine for real (so a SUT exercises ordering, idempotency, NotFound-after-Teardown),
// mounts (an in-memory FS), egress (records allowlists for assertion), resource limits
// (records them; can be told to OOMKill a run), and the credential seam (records which
// secrets.References were injected — refs ONLY, never values). Spawns NO process and
// dials NO substrate, so a consumer test runs in microseconds. Configurable manifest for
// graceful-degradation tests. Zero value is a ready, empty Adapter. Safe for concurrent
// use. Deterministic (driven by an injected FakeClock).
type Adapter struct {
	Capabilities workspaceprovider.CapabilityManifest
	// Provisioned is an append-only log of the WorkspaceSpecs Create saw — for "was a
	// workspace with this egress/limits/tenancy-key requested?" assertions.
	Provisioned []workspaceprovider.WorkspaceSpec
	// Destroyed records the Handles torn down (idempotency + leak assertions).
	Destroyed []workspaceprovider.Handle
	// InjectedRefs records every secrets.Reference injected (refs only) — the
	// carries-refs-never-values guarantee, runnable.
	InjectedRefs []secrets.Reference
}

func NewAdapter(caps ...workspaceprovider.Capability) *Adapter { return &Adapter{} }

func (a *Adapter) Create(ctx context.Context, s workspaceprovider.WorkspaceSpec, r workspaceprovider.Resolved) (workspaceprovider.HandleData, error) {
	return workspaceprovider.HandleData{}, nil
}
func (a *Adapter) Dial(ctx context.Context, h workspaceprovider.Handle) (workspaceprovider.HandleData, error) {
	return workspaceprovider.HandleData{}, nil
}
func (a *Adapter) List(ctx context.Context, sel workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error) { return nil, nil }
func (a *Adapter) Destroy(ctx context.Context, h workspaceprovider.Handle) error { return nil }
func (a *Adapter) Manifest() workspaceprovider.CapabilityManifest { return a.Capabilities }

// FailProvisionWith / OOMKillRun / DenyEgressTo force the failure paths a consumer must
// handle (quota, image, unavailable, isolation, OOM, egress-denied) without a real
// substrate — e.g. workspaceprovider.QuotaExceededError{} / IsolationError{}.
func (a *Adapter) FailProvisionWith(err error) *Adapter      { return a }
func (a *Adapter) OOMKillRun(after time.Duration) *Adapter   { return a }
func (a *Adapter) DenyEgressTo(host string) *Adapter         { return a }

// FakeProvider returns a ready-to-use in-memory workspaceprovider.Provider (the
// Substrate wired over the in-memory Adapter + a fake secrets.Provider seeded from seed
// + a fake Clock) for consumer unit tests that just need a working Provider in one call.
func FakeProvider(seed map[string]string) workspaceprovider.Provider { return nil }

// AssertNoSecretMaterial fails t if canary (a seeded credential plaintext) appears in
// ANY recorded Spec/Env/Handle/Status/log — the carries-refs-never-values guarantee,
// runnable (mirrors agentsessiontest.AssertNoSecretInStream / secretstest.AssertNotLeaked).
func (a *Adapter) AssertNoSecretMaterial(t TestingT, canary string) {}

// ── (b) the conformance suite — runs against a REAL substrate (ADR-0016) ──────
// (the exported Suite value lives in §4)

// ── (c) the REAL-SUBSTRATE HARNESSES — the C23 deliverable, owned HERE (Q3) ────

// EphemeralContainer spins ONE throwaway, isolated docker context (a dedicated label
// namespace + network) on the local daemon, returns a live Adapter bound to the REAL
// dockeradapter, and registers Cleanup to reclaim every container/network/volume it
// created. SKIPS (t.Skip) when no docker daemon is reachable, so the suite degrades on a
// machine without docker rather than failing (env-verified: docker 29.4.0, ADR-0016 §4).
func EphemeralContainer(t *testing.T, opts ...HarnessOption) workspaceprovider.Adapter { return nil }

// K3dCluster creates an ephemeral k3d cluster (k3s-in-docker — the DEFAULT local/test
// substrate, ADR-0016 §4), returns an Adapter bound to the REAL kubernetesadapter
// pointed at its kubeconfig, and `k3d cluster delete`s it on Cleanup. The slow cluster
// spin is amortized: a package-level shared cluster with per-test NAMESPACE isolation is
// the default (the cheap unit of teardown); WithPerTest forces a dedicated cluster;
// WithImages pre-pulls images so per-test provision is fast and offline-safe. SKIPS when
// k3d/docker is unavailable.
func K3dCluster(t *testing.T, opts ...HarnessOption) workspaceprovider.Adapter { return nil }

// KindCluster is the SECOND conformance target (kind v0.32.0, ADR-0016 §4): identical
// shape over a different distro. Running RunProviderSuite over BOTH K3dCluster and
// KindCluster is the EMPIRICAL proof of the distro-transparency claim (05 §3/§6) — same
// suite, two distros, both green. SKIPS when kind/docker is unavailable.
func KindCluster(t *testing.T, opts ...HarnessOption) workspaceprovider.Adapter { return nil }

type HarnessOption func(*harnessConfig)

func WithPerTest() HarnessOption             // dedicated cluster per test (slow, hermetic) vs the shared default
func WithImages(refs ...string) HarnessOption // pre-pull images into the cluster (fast, offline-safe)
func KeepOnFailure() HarnessOption           // skip Cleanup when the test failed (debugging)

type harnessConfig struct{ /* unexported */ }

type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}

// fakeDeps re-exports the frozen Clock/Secrets fakes for convenience.
func fakeDeps() workspaceprovider.Deps {
	set := dependencies.Set{} // dependenciestest.Fakes() in practice
	return workspaceprovider.Deps{Clock: set.Clock, Secrets: secretstestProvider()}
}
func secretstestProvider() secrets.Provider { return nil } // secretstest.New(nil)
```

## 4. Conformance suite

The suite proves any `workspaceprovider.Adapter` (real `dockeradapter`/`kubernetesadapter` or the
fake) is substitutable and that the workspace semantics hold. It is authored **once** here and run by
**each** side — the fake's test and **each** adapter's real-substrate test — so substitutability is
*executed*, not asserted, and an adapter cannot weaken it (the cases live with the contract, not the
adapter — 05 §6). It is built on the `testing` pattern's `Suite[S]`/`Factory[S]`/`Harness`/`RunSuite`
construct (testing.md): the factory yields an `Adapter` bound to its substrate; capability-gated cases
**Skip** (not fail) where the substrate's manifest declares a capability absent (05 §3 graceful
degradation), so docker and kubernetes run the **same** suite and a partial adapter looks partial, not
broken. **Conformance runs against REAL substrates, never mocks (ADR-0016 §2).**

```go
// ProviderSuite is THE one Suite (05 §6, ADR-0016), exported per the testing pattern.
// newAdapter builds a fresh Adapter bound to its substrate; the harnesses in §3 supply
// the docker/k3d/kind ones, the fake supplies the in-memory one.
func ProviderSuite() testing.Suite[workspaceprovider.Adapter]

// The four canonical call sites — the proof shape the brief asks for:
//
//   func TestFake_Conforms(t *testing.T)   { run(t, func(ctx, h) { return NewAdapter(), nil }) }
//   func TestDocker_Conforms(t *testing.T) { run(t, adapt(EphemeralContainer(t))) } // REAL daemon
//   func TestK3d_Conforms(t *testing.T)    { run(t, adapt(K3dCluster(t))) }          // REAL cluster, default distro
//   func TestKind_Conforms(t *testing.T)   { run(t, adapt(KindCluster(t))) }         // REAL cluster, 2nd distro
//
// where run/adapt drive testing.RunSuite(r, ProviderSuite(), factory). Same Suite,
// four bindings; the two real-cluster bindings passing IS the distro-transparency proof
// (no mocks — ADR-0016 §2/§4).
```

Properties asserted (against a **real** substrate for the adapter bindings):

- **Provision is all-or-nothing → Ready → Open** returns a non-nil `Workspace` at `StateReady` or
  rolls back leaving no orphaned container/namespace (never a non-nil `Workspace` with a non-nil
  error); `Open(handle)` re-attaches; `List` includes it with the seeded `Labels` (ownership domain,
  05 §5); `ParseHandle(h.String()) == h`.
- **Idempotency:** re-`Provision`ing the same `Name`+compatible spec returns the existing workspace,
  not a `ConflictError`; an incompatible spec yields `ConflictError` (Kind=Conflict).
- **Round-trip statelessness:** `Open(handle)` re-dials a live workspace after the `Provider` is
  reconstructed (orchestrator restart); a torn-down handle yields `NotFoundError` (gated `CapReattach`
  — `Skip` where absent).
- **Run → Status(Running) → terminal** observes the workload's real exit; `Run.Logs` streams its real
  output; **one primary workload** (a second `Run` while `Running` → `NotReadyError`).
- **Exec** runs a real command in the running workspace and returns its real exit code; `Exec` before
  `Ready` → `NotReadyError`; a timeout → `DeadlineError`.
- **File seam:** `Files.Put` then `Files.Get` round-trips; a read-only `MountInputs` rejects writes
  from inside (the clean-room declared-inputs guarantee, 07 §4); `List` enumerates produced artifacts.
- **Teardown is idempotent and reclaiming:** after `Teardown`, `Open` → `NotFoundError`; a second
  `Teardown` → nil; `List` no longer includes it; **no container/namespace/volume leaks** (the
  harness's `Cleanup` re-scan asserts zero orphans — the C23 forced-teardown discipline at the Go
  layer).
- **Isolation is fail-closed; egress is default-deny + declared-allow:** a workspace whose declared
  egress/mounts/limits cannot be applied is never returned Ready (`IsolationError`); a workload dialing
  an undeclared host is blocked and surfaces `ConditionEgressDenied`; a declared `EgressRule` host
  succeeds (gated `CapEgressPolicy` — `Skip`/declared-absence where absent — the distro-divergence
  proof). Dial-out-only is structural: the spec has no ingress field.
- **Resource limits bind:** a workload exceeding `MemoryBytes` is `RunKilled`/`ConditionOOMKilled` with
  the native reason in `Detail`, not a generic failure (the runaway-agent signal; gated
  `CapResourceLimits`).
- **Secret material never leaks:** a `MountSecret`/`ImagePull`/`RunSpec.Credential` ref resolves and the
  material reaches the workspace, but the seeded plaintext appears in **no** `Spec`, `Handle`,
  `Descriptor`, `Status.Detail`, `Run` log, or error string; `ImageError` carries the ref, never the
  value (`AssertNoSecretMaterial`; the 07 §2 guarantee, runnable).
- **Manifest truthfulness:** every `CapFull` capability passes its gated cases on **this** substrate; a
  declared-but-failing capability is a suite failure that blocks release (05 §6).
- **Tenancy isolation:** `List`/`Open` with a different tenancy key never returns this workspace (gated
  `CapMultiTenant`; 07 §6).
- **State normalization & distro transparency:** every adapter reports the normalized `State`/
  `Condition` for the same lifecycle transition; native strings appear only in `Detail`; the identical
  suite passes over docker, k3d, **and** kind — divergence appears ONLY as declared `CapStatus`, never a
  different code path (ADR-0012 "zero special code paths").

## 5. Usage

```go
// ── Composition root: the ONLY place adapters bind; the central/local/BYO switch ─
// "Zero special code paths" (ADR-0012): central, BYO, and local are the SAME Substrate
// over the SAME kubernetes adapter — only the injected client config (kubeconfig) differs.
func substrateFor(posture Posture, sec secrets.Provider, set dependencies.Set) workspaceprovider.Provider {
	prov, _ := workspaceprovider.New(
		workspaceprovider.Config{Default: posture.Default, Namespace: posture.Namespace}, // central: namespace-per-project (07 §6)
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
				workspaceprovider.SubstrateDocker:     dockeradapter.New(dockeradapter.Config{}),                          // the daemon
				workspaceprovider.SubstrateKubernetes: kubernetesadapter.New(kubernetesadapter.Config{Kubeconfig: posture.Kubeconfig}), // central / BYO / k3d / kind
			},
			Secrets: sec,       // server-side resolution of pull-secret/TLS/workload refs at Provision/Run
			Clock:   set.Clock,
		},
	)
	return prov // a *workspaceprovider.Substrate, held as the Provider port by S2's reconcile loop
}

// ── S2 orchestrator: provision an AGENT POD, then hand its PATH to agentsession ──
// (05 §2 boundary: this port owns the pod; agentsession owns the harness in it.)
func (o *Orchestrator) StartAgentSession(ctx context.Context, req SpawnRequest) (*SessionHandle, error) {
	ws, err := o.provider.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      req.WorkspaceName,
		Substrate: req.Substrate,                                  // "kubernetes" (central/BYO) | "docker" (degenerate local)
		Image:     o.agentRuntimeImage,
		Resources: workspaceprovider.Resources{CPUMilli: 1000, MemoryBytes: 2 << 30}, // hard quota (C5, 07 §6)
		Mounts:    []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}}, // the worktree the agent fills
		Egress:    o.egressFor(req.Route, req.Grants),             // orchestrator-owned: model-provider + granted tools only; default-deny (07 §3)
		Labels:    map[string]string{"eden.org": req.OrgID, "eden.project": req.ProjectID}, // tenancy keys (07 §6)
	})
	if err != nil {
		if q := (workspaceprovider.QuotaExceededError{}); errors.AsType(err, &q) { // cross-tenant quota defense (07 §6)
			return nil, errors.Wrap(errors.KindExhausted, "provision agent workspace", err)
		}
		return nil, errors.Wrap(errors.KindUnavailable, "provision agent workspace", err) // reconcile backs off on Unavailable
	}
	// Hand the PATH to agentsession. The ONLY coupling is a string; the harness runs in ws;
	// agentsession.Close will NOT tear ws down — EndSession does (via Teardown).
	session, err := o.agents.Open(ctx, agentsession.Spec{
		Workspace:  ws.Handle().WorkDir(),                          // workspaceprovider's WorkDir → agentsession's CWD (02 §1)
		Routing:    req.Route,
		Grants:     req.Grants,
		Credential: secrets.Ref("anthropic-oauth-token"),           // resolved by agentsession, INSIDE the pod we isolated
	})
	if err != nil {
		_ = o.provider.Teardown(ctx, ws.Handle())                   // roll the pod back on session-open failure
		return nil, err
	}
	// Persist the Handle: the ONLY durable substrate state. On restart, Open(handle) re-attaches
	// (CapReattach) and the orchestrator stays stateless — agentsession's ResumeFrom rests on it.
	return &SessionHandle{Workspace: ws.Handle(), Session: session}, nil
}

// On session end (NOT agentsession.Close — that only reaps the harness process):
func (o *Orchestrator) EndSession(ctx context.Context, h *SessionHandle) error {
	_ = h.Session.Close(ctx)                       // reap the harness process (agentsession, 02 §1)
	return o.provider.Teardown(ctx, h.Workspace)   // reclaim the pod + volumes (workspaceprovider) — idempotent
}

// ── kernel ENGINE: a CLEAN-ROOM exercise environment (07 §4) ─────────────────
func (h *Harness) Exercise(ctx context.Context, run RunRef) (Evidence, error) {
	ws, err := h.provider.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      run.WorkspaceName,
		Image:     h.cleanRoomImage,
		Resources: workspaceprovider.Resources{CPUMilli: 2000, MemoryBytes: 4 << 30, StorageBytes: 8 << 30},
		Mounts:    []workspaceprovider.Mount{{Kind: workspaceprovider.MountInputs, Target: "/inputs", ReadOnly: true}},
		Egress:    nil, // DEFAULT-DENY: the clean room dials out to NOTHING (07 §4)
	})
	if err != nil {
		return Evidence{}, errors.Wrap(errors.KindUnavailable, "provision clean-room", err)
	}
	defer h.provider.Teardown(ctx, ws.Handle())

	// Copy ONLY declared inputs — the read-only mount makes "nothing else" structural
	// (defeats the conftest.py auto-discovery attack, 07 §4).
	for _, in := range run.DeclaredInputs {
		if err := ws.Files().Put(ctx, "/inputs/"+in.Path, in.Reader(), 0o444); err != nil {
			return Evidence{}, errors.Wrap(errors.KindInternal, "seed clean-room input", err)
		}
	}
	// Run the held-out verification suite the implementing agent never saw.
	res, err := ws.Exec(ctx, workspaceprovider.ExecSpec{
		Command: []string{"go", "test", "./_verify/..."}, WorkDir: "/inputs", Timeout: 10 * time.Minute,
	})
	if err != nil {
		var deadline *workspaceprovider.DeadlineError
		if errors.AsType(err, &deadline) { /* a hung suite is a failed verdict, not a crash */ }
		return Evidence{}, errors.Wrap(errors.KindUnavailable, "exercise clean-room", err)
	}
	out, _ := ws.Files().Get(ctx, "/inputs/result.json")
	return h.foldEvidence(res.ExitCode, out), nil // provenance: the workspace fingerprint (07 §4)
}

// ── chat-frontend backend: a remote VS-CODE workspace (C5) ───────────────────
func (s *EditorBackend) OpenEditor(ctx context.Context, projectID, orgID string) (*EditorEndpoint, error) {
	ws, err := s.provider.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Substrate: workspaceprovider.SubstrateKubernetes,
		Image:     s.codeServerImage,
		Resources: workspaceprovider.Resources{CPUMilli: 2000, MemoryBytes: 4 << 30},
		Mounts:    []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/home/coder/project"}},
		Egress:    s.editorEgress(),                  // git remotes + extension marketplace only (07 §3 gates)
		Labels:    map[string]string{"eden.org": orgID, "eden.project": projectID},
	})
	if err != nil {
		return nil, err
	}
	run, err := ws.Run(ctx, workspaceprovider.RunSpec{Command: []string{"code-server", "--bind-addr", "0.0.0.0:8080"}})
	if err != nil {
		_ = s.provider.Teardown(ctx, ws.Handle())
		return nil, err
	}
	go s.streamBootLog(ctx, run) // the dashboard tails the RAW code-server boot log (distinct from any agentsession Event stream)
	return &EditorEndpoint{Workspace: ws.Handle()}, nil
}

// ── a consumer's integration test reuses the C23 real-substrate harness ──────
func TestOrchestrator_ProvisionsOnRealK3d(t *testing.T) {
	prov := workspaceprovidertest.FakeProvider(nil) // unit path; or wire a real K3dCluster(t) adapter for integration
	o := NewOrchestrator(prov)
	if _, err := o.StartAgentSession(context.Background(), req); err != nil { t.Fatal(err) }
	// real-cluster objects are torn down by the harness Cleanup before exit (forced teardown, C23)
}
```

## 6. Design rationale

1. **Two ports, not one 9-method god-interface — split along the real seam.** `Provider` (substrate
   plane: `Provision`/`Open`/`List`/`Teardown`) and `Workspace` (workload plane:
   `Handle`/`Run`/`Exec`/`Files`/`Status`) sit at 4 and 5 methods — at/under the ≤5 ceiling (10 §9) —
   and the split *models the real seam*: S2's reconcile loop holds a `Provider`; the F4 adapter, the
   engine's clean-room harness, and the chat editor backend hold a `Workspace`. `Run` (2) and `Files`
   (3) mirror `agentsession`'s `Stream`/sub-port splits — async stream-shaped vs synchronous
   result-shaped. This is the brief's "interface at most 5 methods, split if needed" applied to the
   natural seams, not arbitrarily. Both drafts split the same way; the reconciled shape is below in §7.

2. **One contract, zero distro forks; divergence lives in the manifest (ADR-0012, 05 §6).** One
   `WorkspaceSpec` shape; the adapter realizes it on docker bind-mounts or k8s volumes, docker net
   rules or `NetworkPolicy`. The central multi-tenant cluster is an ordinary `kubernetes` adapter
   instance with zero special code paths — central/BYO/local are the same `Substrate`, differing only
   in injected `Config`/kubeconfig. Distro transparency is the *claim*, the `CapabilityManifest` is its
   *honest escape hatch* (05 §3), and the one-suite-over-both-adapters-against-real-substrates run is
   its *proof* (05 §6). There is no `if substrate == "kubernetes"` in any consumer.

3. **`workspaceprovidertest` owns the real-substrate harnesses (the ruling the brief demands, Q3).** The
   container/k3d/kind spinners live **with the contract**, not with either adapter, for three
   load-bearing reasons: (a) one consumer imports one package for *both* the in-memory fake *and* a live
   substrate; (b) the conformance `Suite` and the substrate spinners share a home so they cannot drift;
   (c) suites-live-with-the-contract is the 05 §6 invariant that stops an adapter weakening its own
   tests. k3d is the default spinner (aligns the test path with future k3s, ADR-0016 §4); kind is the
   second target so the *same* `ProviderSuite` proves transparency empirically.

4. **Conformance runs against REAL substrates, never mocks (ADR-0016 §2).** The fake exists for
   *consumers'* unit tests; the *contract's* proof is `ProviderSuite` over a real docker daemon and a
   real k3d/kind cluster. Real substrates are where the leaks, the OOM-kills, the egress-policy denials,
   and the teardown-orphans actually happen — a mock would assert the spec back to itself. The
   shared-cluster + per-test-namespace default amortizes the slow cluster spin without sacrificing
   isolation.

5. **The credential seam is honest (07 §2), and mirrors `agentsession` exactly.** A spec carries opaque
   `secrets.Reference`s (pull-secret, workload token, mTLS material); the **library** resolves them
   server-side at `Provision`/`Run` via the injected `secrets.Provider` and hands the **adapter**
   un-printable `*secrets.Secret`s in `Resolved`; the adapter calls `Secret.Use` at the injection site
   and writes them to a `MountTmpfs`/child-env, never an image layer, never the spec, never a `Handle`,
   never a log. The two F-family ports compose without re-litigating the seam.

6. **Errors are typed and Kind-bearing so the transport boundary needs no per-port table.** Every error
   maps to a stable `errors.Kind`, inspected via `errors.AsType`/`errors.KindOf` (errors.md):
   `QuotaExceededError`→`Exhausted`, `SubstrateUnavailableError`→`Unavailable`, `NotFoundError`→
   `NotFound`, `ConflictError`→`Conflict`, `IsolationError`→`Permission`, `DeadlineError`→`Deadline`,
   `Invalid*/NotReady/Unsupported/Image/InvalidHandle`→`Invalid`. The reconcile loop branches on
   `Unavailable` to back off and `Exhausted` to wait-for-reclaim without parsing a substrate string.

7. **Level-based, idempotent primitives — the reconcile loop's vocabulary.** `Provision` is idempotent
   and all-or-nothing (converges whether or not the workspace exists; rolls back on partial failure),
   `Teardown` is idempotent (no-op on gone), `List` returns the *complete* ownership domain (orphan
   detection), `Status` is cheap to poll and is the drift surface. This is exactly what a level-based
   `Reconcile(ctx, key)` (10 §7.1) is built from — the port is the primitive, S2 is the loop, and the
   two stay disjoint.

8. **`New(Config, Deps)` is pure; the `Substrate` is the routing layer.** `Config` carries only the
   default-substrate and namespace knobs; `Deps` injects pre-built adapters keyed by substrate plus
   `Secrets`/`Clock`; the `Substrate` picks the adapter per spec at call time. No daemon dial, no
   apiserver call, no clock read at construction — all substrate I/O is lazy in adapters (10 §2/§4).

9. **`Handle` is a validated, durable, loggable value type — the statelessness backbone.** Like
   `secrets.Reference`, the unexported field forces every `Handle` through the library / `ParseHandle`,
   keeps it comparable (a reconcile-loop map key), tenancy-bearing, and loggable by contract (no
   secret). It is the *only* durable per-workspace state the orchestrator persists; `Provider.Open` +
   `CapReattach` re-dial from it across restarts, which is what `agentsession.Spec.ResumeFrom` rests on.

10. **Isolation is fail-closed; dial-out-only is structural.** A workspace whose declared isolation
    cannot be applied is *never* returned Ready (`IsolationError`, Kind=Permission) — a workspace without
    its isolation is a security failure, not a degraded success (07 §3). Dial-out-only ("pods open no
    listening sockets", 07 §3) is the *absence* of any ingress field on `WorkspaceSpec` — the contract
    cannot request a listener. `ConditionEgressDenied`/`ConditionOOMKilled` are typed, branchable signals.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| Q1 | **F1 family scope** — does this port also cover registry / DNS / object-storage / Postgres-class DB / metrics ingestion (the 05 §2 F1 summary), or only the compute substrate? | Compute-substrate core only (workspaces/workloads/exec/mounts/files/egress/limits); push the rest to **sibling F1 ports** (one concept, one home; an 8-method god-port is the failure mode). | Same: declared **out of scope** for v1; whether they extend this port or get sibling ports (`objectstore`, `database`) is a later-wave decision; the `CapabilityManifest` axis is the additive seam if they land here. | 🧩 **Both agree — scoped to the compute substrate; siblings are separate ports.** v1 `workspaceprovider` owns workspace lifecycle + run/exec/files/egress/limits. Registry/DNS/object-store/DB/metrics and image-building are sibling F1 concerns negotiated separately. If one later proves it belongs *here* it enters additively through the `CapabilityManifest` axis (a declared-absent capability today, a `CapFull` one later) — never a breaking widening. Recorded so the reconciler does not assume this port grows to cover them. |
| Q2 | **Identity type** — a string `WorkspaceID` the adapter maps to a container-id/namespace, or a validated, tenancy-bearing `Handle` value type? | `WorkspaceID string` (opaque, comparable map key); `List`/`Get` route by it. | A validated `Handle` struct (unexported field, `ParseHandle` round-trip) carrying `Substrate()`/`Organization()`/`Project()`/`WorkDir()` — the durable, loggable join key the stateless orchestrator persists and re-dials from. | 🧩 **Took the consumer's `Handle` value type.** The orchestrator's real call site persists identity across restarts and re-dials with it; a bare `string` cannot carry the substrate-routing + tenancy keys the re-dial and cross-tenant defense need without a parallel lookup, and a validated value type (mirroring the frozen `secrets.Reference` decision) keeps it comparable, loggable-by-contract, and shape-checked. `WorkDir()` rides the `Handle` so the `agentsession` coupling is a method call on the durable identity, not a separate field. The producer's "opaque, comparable, routes Open/Teardown" requirements all hold — `Handle` is comparable and routes; it is just richer than a `string`. |
| Q3 | **Re-attach verb** — the producer's `Provider.Get(id)` vs the consumer's `Provider.Open(handle)` for re-dialing an existing workspace. | `Get(ctx, id)` — fetch a handle to an existing workspace by id. | `Open(ctx, handle)` — a pure re-dial that provisions nothing, the substrate-side of orchestrator statelessness, with an explicit `CapReattach` capability. | 🧩 **Took the consumer's `Open` + `CapReattach`.** Same verb, better name and an explicit capability: "open an existing workspace" reads as a re-dial (it provisions nothing), and gating it on `CapReattach` lets a substrate that *cannot* survive a control-plane restart declare so honestly (the manifest is the divergence home, 05 §3) rather than silently failing the re-dial. The producer's `Get` semantics are preserved verbatim; only the name and the capability gate change. |
| Q4 | **Hibernate/pre-warm** — a `Pause`/`Resume` verb on `Provider`, or `Destroy`+re-`Provision` for v1? | No `Pause`/`Resume` verb (it would push `Provider` to 6 methods, over the ceiling); expose `CapHibernate` as a capability but treat idle/hibernate as `policy`'s concern via idempotent `Teardown`+re-`Provision` for v1; defer the verb until `policy` proves the cheaper path is load-bearing. | (Did not request a verb; relies on `Provision`/`Teardown` idempotency.) | 🧩 **No `Pause`/`Resume` verb in v1; `CapHibernate` declared, the verb deferred.** Adding it now blows the 4-method `Provider` past the ceiling for a path no consumer call site exercises yet. v1 idle/hibernate is `policy` driving idempotent `Teardown`+re-`Provision`; `CapHibernate` is declared (absent on most substrates today) so the additive seam exists. When `policy` proves the cheaper pause/resume path is load-bearing, the verb is negotiated then — additively, with the capability already carrying the divergence. |
| Q5 | **`Run`/`Exec` boundary** — is one workload verb enough, or are async-workload (`Run`/`Start`) and sync-command (`Exec`) genuinely distinct? | Distinct: `Start`→`Handle` (async, stream-shaped: logs/wait/signal) + `Exec`→`ExecResult` (sync). | Distinct: `Run`→`Run` (async, status/logs) + `Exec`→`ExecResult` (sync, result-shaped). | 🧩 **Both agree — two verbs, named `Run` (async) and `Exec` (sync).** The async handle is named `Run` (consumer) with a 2-method surface `Status`/`Logs` (consumer), **dropping the producer's separate `Handle{Logs/Wait/Signal}` 3-method port**: `Wait` is `Status` ranged to terminal, and `Signal` (SIGTERM/SIGKILL) is subsumed by `Teardown`'s graceful-drain ladder + ctx-cancellation on the `Run`'s context — no consumer call site signals a workload without tearing the workspace down or cancelling its context, so a third sub-port bought nothing. The producer's `Start` is `Run`; its `Handle` collapses into `Run`+`ctx`. (The durable-identity `Handle` of Q2 is unrelated — that is the workspace identity, not the workload control surface.) |
| Q6 | **Lifecycle taxonomy** — the producer's `Phase{Provisioning/Ready/Running/Degraded/Terminating/Gone}` vs the consumer's `State{Provisioning/Ready/Degraded/Evicted/Gone}` + a typed `Condition` set. | `Phase` enum; native phases ride `Status.Detail` verbatim; no separate condition axis. | `State` enum + a closed, branchable `Condition` set (`OOMKilled`/`Evicted`/`Unschedulable`/`EgressDenied`) the engine/orchestrator branch on, distinct from the lifecycle axis. | 🧩 **Merged: `State` (lifecycle) + `Condition` (branchable substrate signals).** The producer's `PhaseRunning`/`PhaseTerminating` and the consumer's `StateEvicted` both belong: `State` is `Provisioning/Ready/Running/Degraded/Evicted/Gone` (the producer's `Running` and the consumer's `Evicted` both kept; `Terminating` folds into the `Teardown` call's ctx, not a polled state), and `Condition` is the consumer's typed, additive set the runaway-agent + drift surfaces (02 §2, 05 §5) branch on — `OOMKilled` cannot be a generic failure if the budget story is to reconcile against it. Native strings still ride `Status.Detail` verbatim (the producer's load-bearing point). |
| Q7 | **`Files` seam** — the producer left files implicit in `MountSpec`; the consumer added an explicit `Files{Put/Get/List}` port. | Files via `MountSpec` only (bind/volume/configMap/tmpfs); no copy verb. | An explicit `Files` port: `Put` (declared inputs in, clean-room), `Get`/`List` (artifacts out) — a narrow file seam, not a shell. | 🧩 **Took the consumer's explicit `Files` port (3 methods).** The clean-room call site (07 §4) *needs* "copy ONLY declared inputs in, read the produced artifact out" as a first-class, shell-free verb — `MountSpec` alone cannot seed a read-only inputs volume and read a result file back without a shell, and a shell is exactly the reward-hack surface 07 §4 closes. `Mount` keeps the *declarative* mount vocabulary (incl. `MountInputs` read-only); `Files` is the *imperative* seed/collect seam the engine drives. Both belong; neither is redundant. |
| Q8 | **`Adapter` method set** — the producer's `{Provision/Get/List/Destroy/Manifest}` (mirrors `Provider`) vs the consumer's `{Create/Destroy/Dial/Manifest}` + library-owned routing. | Adapter mirrors `Provider` (5 methods) + `Manifest`. | Thinner adapter: `Create`/`Destroy`/`Dial`/`Manifest` (4), the library owns the state machine, status normalization, Handle routing, tenancy stamping, secret-resolution timing. | 🧩 **Took the thin adapter, at 5 methods: `Create`/`Dial`/`List`/`Destroy`/`Manifest`.** The library — not the adapter — owns Handle assignment, idempotency, the ownership-domain labelling, the State machine, status normalization, and secret-resolution timing (so an adapter cannot get idempotency or the credential seam subtly wrong, and a new adapter is reviewable by machine, 05 §6). `List` stays on the adapter (the native-namespace scan the library cannot do generically) so the count lands at 5 (the ceiling, spent). `Create` takes `Resolved` (library-resolved secrets) so the adapter only injects, never resolves — the honest credential seam. |
| Q9 | **Ownership ratification** — the real-substrate Go test harnesses (the C23 deliverable) live in `workspaceprovidertest`, one `ProviderSuite` over the fake + docker daemon + k3d (default) + kind (second target). | Live in `workspaceprovidertest`, maintained by the contract author; one suite, four bindings. | Same: `EphemeralContainer`/`K3dCluster`/`KindCluster` in `workspaceprovidertest` alongside the fake and the one suite; shared-cluster + per-test-namespace default. | 🧩 **Ratified — both sides agree, recorded as the binding ruling.** The C23 real-substrate harnesses live in `workspaceprovidertest` (the `<pattern>test` convention), maintained by the contract author, beside the in-memory fake and the single `ProviderSuite`. One suite runs over four bindings (fake + real docker + real k3d + real kind); the two real-cluster bindings passing is the distro-transparency proof. This is the concrete answer to the brief's "propose ownership and the one-suite-over-both-adapters conformance shape." No consumer hand-rolls cluster-spinning. |
| Q10 | **On `agentsession` (frozen)** — confirm the boundary stays exact and bidirectionally cited: `agentsession.Spec.Workspace` is a path string this port produces; `agentsession.Close` never calls `Teardown`; the egress endpoints `agentsession` "declares" (Route+Grants) are folded by the orchestrator into `WorkspaceSpec.Egress`. | `agentsession.Adapter.Spawn` runs in a workspace this port provisioned via `Open`; `Close` never tears down; `Teardown` is the sole teardown. No `agentsession` change requested. | The coupling is the `Spec.Workspace` *path string* only (no type import either way); the orchestrator reads `Route`/`Grants` and derives egress (`agentsession` needs no `workspaceprovider` import). | 🧩 **Confirmed — no overlap, no `agentsession` change.** The seam is a single path string (`Workspace().WorkDir()` → `agentsession.Spec.Workspace`); neither port imports the other. agentsession.md §1 already states this from its side ("never creates a container… `Close` never tears down the pod"); this contract asserts the matching obligation. Egress-derivation (`Route`+`Grants` → `[]EgressRule`) is **orchestrator-owned**, not substrate-owned and not session-owned — flagged for the orchestrator negotiation (Q11). |
| Q11 | **On the orchestrator contract (to be negotiated, Wave 3A/3B)** — the orchestrator is the primary consumer; it persists `Handle` as the only durable per-workspace state, calls `Open` on restart, and owns the egress-derivation policy. | (Flagged for that negotiation: this port is the level-based primitive; the loop is S2's.) | The orchestrator negotiation must accept `workspaceprovider.Provider` as an injected port and own the `Route`+`Grants` → `[]EgressRule` policy (orchestrator-owned, not substrate-owned). | 🧩 **Flagged forward, not decided here.** The orchestrator negotiation (a later Wave-3A/3B contract) accepts `workspaceprovider.Provider` as an injected port, persists `Handle`, drives the reconcile loop over `Provision`/`Open`/`List`/`Teardown`, and owns egress-derivation. This contract deliberately exposes only the primitives; recorded so the orchestrator negotiation inherits the obligation rather than this port growing a loop. |
| Q12 | **On `secrets`/`errors`/`dependencies`/`testing` (frozen)** — confirm composition with no change, and confirm the real-substrate harnesses sit *beside* the `testing` construct without pulling a substrate dependency into `testing`. | Depends on `secrets.Provider.Resolve` + un-printable `*secrets.Secret`; error set maps onto the existing `Kind` taxonomy with no new `Kind`; suite built on the `testing` construct. Flags that `EphemeralContainer`/`K3dCluster`/`KindCluster` sit beside, not inside, `testing`. | Same composition; the harnesses may depend on `dependenciestest`/`secretstest` (test-only edge) for the fake `Deps`; `IsolationError → KindPermission` flagged for the transport boundary's exhaustive switch. | 🧩 **Aligned to the frozen siblings; no change requested of any.** `secrets.Reference`/`Secret`/`Provider.Resolve` consumed verbatim. Every error maps to an existing `Kind` (no new `Kind`): `QuotaExceededError→KindExhausted`, `SubstrateUnavailableError→KindUnavailable`, `NotFoundError→KindNotFound`, `ConflictError→KindConflict`, `IsolationError→KindPermission`, `DeadlineError→KindDeadline`, the rest →`KindInvalid` — the transport boundary's exhaustive `switch errors.KindOf` covers them (the boundary owns the table, 10 §9). The suite uses `testing.Suite[Adapter]`/`RunSuite`; the real-substrate harnesses (`EphemeralContainer`/`K3dCluster`/`KindCluster`) live in `workspaceprovidertest`, **not** `testing`, so `testing` stays substrate-agnostic — `workspaceprovidertest` owns substrate spin-up and may depend on `dependenciestest`/`secretstest` at the test-only edge. |
| Q14 | **⚠️ POST-FREEZE DRAFT AMENDMENT — credential-injection realization + the OOM-condition surfacing gap on the exec-into-hold Run model (raised in implementation; Mateo ratifies).** Three credential/resource findings surfaced while making the seam REALLY-implemented + really-tested against real substrates (the cardinal rule). **(B6) `MountSecret` injection is now really-implemented on both adapters** (it previously dropped the material into an empty tmpfs/emptyDir): the library resolves the `MountSecret` ref server-side into `Resolved.Mounts[Target]`; the **docker** adapter mounts a genuine tmpfs at the Target's parent and writes the resolved bytes AS the Target with mode `0600` via an in-container `sh -c 'umask 077; cat > "$1"'` exec (docker's `CopyToContainer` cannot write through a tmpfs mount, so the value rides exec STDIN — never the argv/label/log); the **kubernetes** adapter creates an `Opaque` `corev1.Secret` and projects it as a read-only `secret` volume (`defaultMode 0400`) whose single key is mounted AS the Target. Both yield the same observable — reading the Target returns the secret VALUE — proven by the new `caseMountSecret` conformance case on real docker AND real k3d. **(B7) the pull-secret seam is now substitutable across adapters:** the **kubernetes** adapter (which previously ignored `Resolved.PullSecret`) creates a `kubernetes.io/dockerconfigjson` `corev1.Secret` and sets `Pod.Spec.ImagePullSecrets`, matching the docker adapter's `registryAuth`; both present a fixed username (`eden`) so the resolved secret carries only the PASSWORD. Proven against a REAL `registry:2`+htpasswd registry on both substrates (provision succeeds WITH the pull-secret, fails with `ImageError` carrying the ref-never-the-value WITHOUT it). | (n/a — defects surfaced during the implementation against real substrates, not in either original draft.) | (n/a.) | 🧩 **Amended in draft (pending Mateo's ratification).** B6/B7 are now really-implemented + really-tested on real docker and real k3d (no empty-file fakes — the cardinal rule). **B8 — the OOM-CONDITION discriminator on the kubernetes real Run path is an HONEST, documented limitation (not delivered, by design of the exec-into-hold model):** because a `Run` is an exec INTO a long-lived hold pod (so the workload is the exec'd CHILD, not the hold container), the cgroup OOM-kill of the workload attaches the `OOMKilled` *reason* to the child, not to the pod's container status the adapter can read — so the kubernetes real Run path surfaces a memory-bomb as a **SIGKILL exit (137) → `RunPhase=RunKilled`** (the REAL enforcement: the limit binds, the kernel kills the over-memory workload, `Phase=Killed`), but NOT the `ConditionOOMKilled` discriminator. The **docker** adapter DOES deliver `ConditionOOMKilled` on the real Run path (it reads the holding container's cgroup `State.OOMKilled`, which docker sets for any process in the container's cgroup including an exec child). `ConditionOOMKilled` stays in the contract and the fake (the runaway-agent budget signal, 02 §2); `caseResourceLimits` asserts the REAL enforcement (the limit binds; OOM→`RunKilled`/`RunFailed`, never `Succeeded`) on real docker AND real k3d, and asserts the `ConditionOOMKilled` shape only where a substrate genuinely surfaces it (docker). The residual kubernetes OOM-discriminator gap is recorded as **OD-15** (future work: a workload-controller/Job Run model, or a pod-watch that reads the child's cgroup memory.events, would surface the discriminator without the exec-into-hold compromise). | 
| Q13 | **⚠️ POST-FREEZE DRAFT AMENDMENT — `*Substrate` name collision + the exported workload-plane seam (raised in implementation; Mateo ratifies).** The frozen §2 wrote `New(...) (*Substrate, error)` with `type Substrate struct{}` as the concrete Provider, but §2 ALSO declares `type Substrate string` (the substrate-selector). Go cannot declare one identifier as both a struct and a string — the frozen §2 does not compile as written. Separately, §2 left the adapter's workload-plane handle as an UNEXPORTED field on `HandleData`, but the implementation needs an exported port there (the library drives Run/Exec/Files/Probe through it). | (n/a — defect surfaced during the TDD implementation, not in either original draft.) | (n/a.) | 🧩 **Amended in draft (pending Mateo's ratification): (1) the concrete Provider returned by `New` is `*Provisioner`, not `*Substrate` — `type Substrate string` keeps the selector name (it is the public, consumer-facing routing value); the concrete type is renamed since "the thing that provisions" reads truer than "the substrate" anyway, and the collision is otherwise unresolvable. (2) `HandleData.Connection` is an EXPORTED `Connection` port (4 methods: `Run`/`Exec`/`Files`/`Probe`), with `RunDriver` (2 methods) and the `Probe` value type — the WORKLOAD-plane counterpart of the SUBSTRATE-plane `Adapter`, exactly the Provider/Workspace split applied one level down. Both are ADDITIVE to the frozen consumer surface (no change to `Provider`/`Workspace`/`Run`/`Files`/`Adapter`/the error set/the value types); a consumer that holds `Provider`/`Workspace` is unaffected. Recorded here so the rename + the export are a visible, ratifiable amendment rather than a silent divergence between the frozen spec and the landed code (ADR-0016 §1: an overturn/edit is a negotiation, never silent).** Also recorded under this row: the LIBRARY now owns idempotency-by-fingerprint (it stamps `SpecFingerprintLabel` so a same-Name re-Provision is COMPATIBLE→re-dial or INCOMPATIBLE→`ConflictError`), and `CapEgressPolicy` is declared `CapPartial` on docker (genuine `--internal` default-deny for a zero-egress workspace; selective-allow is the Partial gap) and `CapAbsent` on k3d/kind (flannel does not enforce NetworkPolicy) — see OD-14. |
