# Contract draft — orchestrator

> Status: Draft for negotiation — Wave 3A; freezes per the ADR-0016 process · 2026-06-12 · Reconciled from independent producer/consumer drafts (09 §4 step 2). The **basic agent orchestrator** (C23, C14): the central component that manages agent spawn-up. It is **S2's reconcile loop** over `agentsession` (F4) + `workspaceprovider` (S2): resolve an `AgentTemplate` → provision a `Workspace` via `workspaceprovider` → open an `agentsession.Session` in it → track the running set (list/get/stop/resume) → enforce limits (max concurrent, budgets) → emit observability events — as a desired-vs-actual reconcile loop whose contract reads **identically** single-node and multi-node (the brief's load-bearing requirement). It is a **library (S2/S4 seam)**, not an F-family connector: it owns *declarative agent-session lifecycle* and delegates pods to `workspaceprovider`, the agent loop to `agentsession`, credentials to `secrets`, and harness/model choice to `agentconfiguration`. Freezes per the ADR-0016 freeze process; the frozen contract then lands in `libs/go/orchestrator/` and `orchestratortest`, and this draft moves to the attic. Composes with the frozen `secrets.md`/`errors.md`/`observability.md`/`agentsession.md`; demands the concurrently-negotiated `workspaceprovider.md`.

## 1. Scope

`orchestrator` is the port that turns *a request to run an agent* — "start an implementer on this project for the implement phase", "open a chat `AssistantSession` over this project" — into *a tracked, limited, observable running agent session*. It is the **reconcile loop** S2 owns (03 §S2, 02 §1): a declared **desired set** of agents (each pinned to a resolved `AgentTemplate`) reconciled against the **observed actual set** of live `agentsession.Session`s, emitting `observability` events the whole way. At v0 scale it is a **single-node, in-process manager**; the contract reads identically for the multi-node version (the desired/actual split is the seam that survives sharding — §6).

It owns exactly four things (the brief's seven duties fold onto these four):

1. **Template resolution.** An `AgentTemplate` is *data* — the session-scoped sibling of an `Archetype` (02 §2): skills, rules, tool grants, a model/harness route, and a custom sandbox spec. The orchestrator resolves a `TemplateRef` to an immutable `AgentTemplate`, then **folds** it (template = ceiling) plus a per-spawn request (= floor) into the `agentsession.Spec` and the `workspaceprovider` request the lower ports consume. Templates are C13's "core opinionated concepts encapsulating user business data into templates" made concrete at the agent layer. The orchestrator never *executes* a template's contents — it folds it into a downstream artifact, exactly as `Archetype`→monorepo scaffold.
2. **The reconcile spine (desired-vs-actual).** `Spawn` records a *desired* `Agent` at `StatusPending` and returns immediately (it does **not** block on provisioning); the loop provisions the workspace, opens the session, and drives each agent one step toward its desired terminal status. `Stop` records the terminal intent and the loop drains the session + releases the workspace. `Resume` re-attaches a session that outlived its actual record. `Get`/`List` read the reconciled record. The verbs operate on **records** (plain serializable values holding opaque refs), never on in-memory handles — the one decision that makes the single-node contract read identically multi-node (§6, rationale 2).
3. **Limit enforcement (one admission authority).** `MaxConcurrent` per `(Tenant, Template)` class is checked at `Spawn` admission, *before* a workspace is ever provisioned (fail cheap — the metered "cheap and scalable" backpressure, C5/07 §6). Per-session **budget** is *not* double-enforced: the orchestrator folds `AgentTemplate.Limits.Budget` into `agentsession.Spec.Budget` (the single in-session budget authority, agentsession.md Q6) and additionally watches the observed ledger so a runaway agent is stopped even when no consumer is tailing. The template is the ceiling; a spawn may only *tighten*.
4. **Observability.** Every admission/refusal/transition/budget-stop is an `observability.Event` on `PlaneAgent` via a narrow `Telemetry` seam; the per-session `agentsession` token ledger is folded onto the same plane-(b) stream (T6) so FinOps (S9) and limit decisions read one pipe.

It explicitly does **not** own (the consumer must not expect these here):

- **Workspace provisioning mechanism / isolation / egress / the gitrepository clone** — owned by `workspaceprovider` (S2, 02 §1). The orchestrator NAMES the sandbox (the `AgentTemplate.Sandbox` spec — substrate, image, resources, egress) and CALLS the provider; it never talks to a docker daemon or a kube-apiserver, derives no `NetworkPolicy`, and clones no repo. It REQUESTS a workspace and RELEASES it — and `Release` is the **sole** pod-teardown path, since `agentsession.Close` reaps the harness but never the pod (agentsession.md §2/§7).
- **The agent loop / harness invocation / the Event stream** — owned by `agentsession` (F4, 05 §2). The orchestrator OPENS a `Session` and stores its opaque `SessionRef`; the chat surface tails `agentsession.Session.Events` directly off that ref (the orchestrator does **not** proxy the stream and does **not** re-taxonomize events — one Event vocabulary, one `Seq`/replay mechanism survives).
- **Credential storage / minting** — owned by `secrets` + vault (07 §2). A `SpawnRequest` carries an opaque `secrets.Reference`; the orchestrator threads it into `agentsession.Spec.Credential` and never resolves it (resolution is `agentsession.Open`'s server-side job). No secret value ever enters a `SpawnRequest`, an `Agent`, an `ObservabilityEvent`, the desired store, an error, or a log.
- **Template authoring / persistence / versioning** — a governed engine concern (02 §2 `Archetype` provenance). This port consumes a read-only `TemplateStore` seam; it is not the template CRUD surface.
- **Routing economics / model selection** — `agentconfiguration` resolves `RouteKey → Route` (02 §5, C22). The template names a `RouteKey`; the orchestrator carries it and never decides it.
- **Pipeline / phase sequencing** — the 10-phase engine (04) decides *which* template runs *when*; this port spawns and tracks one agent per `Spawn`. Sequencing many is the engine looping `Spawn`/drain/`Stop`.
- **Cross-node scheduling / bin-packing** — at v0 the "node" is this process. The multi-node placement policy is OD-tracked; the contract carries the seam (a swappable `DesiredStore`, a cluster-wide `Probe`) but binds single-node adapters at v0.
- **Usage-record normalization / billing** — S9 folds the ledger the session emits; this port emits, it does not bill.

It cites, never redefines: `agentsession.Session`/`Spec`/`Factory`/`Budget`/`RouteKey`/`ToolGrant`/`HostTool`/`State`/`TokenLedger`/`PermissionRequest`/`Decision` (agentsession.md), `secrets.Reference`/`Provider` (secrets.md), `observability.Provider`/`Event`/`Ledger`/`PlaneAgent` (observability.md), `errors.AsType`/`Kind` (errors.md), `Workspace`/`AssistantSession`/`Archetype`/`TokenBudget`/`Organization`/`Project` (02 §1–2), and the `workspaceprovider` port (negotiated in parallel, wave 3A — cited by the shape this draft *demands* of it, §5 of the contract and the rationale's demands).

## 2. Contract

```go
// Package orchestrator is the Eden basic agent orchestrator (C23, C14): the S2
// reconcile loop that manages agent spawn-up. It resolves an AgentTemplate (the
// session-scoped, data-defined configuration — skills, rules, tool grants, a
// model/harness route, and a custom sandbox spec, 02 §2 Archetype kinship),
// provisions a Workspace via the workspaceprovider port, opens an agentsession.Session
// inside it, tracks the running set (Get/List/Stop/Resume), enforces limits (max
// concurrent, budgets), and emits observability events the whole way.
//
// Module: github.com/gophersys/libs/go/orchestrator  (go 1.26)
//
// SHAPE: a desired-vs-actual reconcile loop. Spawn records a DESIRED agent; the loop
// reconciles it to an ACTUAL live agentsession.Session and drives it to terminal;
// Stop records the terminal intent and the loop reaps actual. At v0 this is a single
// in-process Manager; the contract is IDENTICAL for the multi-node version — the
// desired-state Store and the actual-state Probe are the only seams sharding touches
// (§6). The verbs operate on RECORDS (plain serializable values holding opaque refs),
// never on in-memory handles, which is the one decision that buys multi-node for free.
//
// It does NOT own: workspace provisioning/isolation/egress/clone (workspaceprovider,
// 02 §1 — it NAMES the sandbox and CALLS the provider; Release is the sole pod
// teardown path); the agent loop / Event stream (agentsession F4, 05 §2 — it OPENS a
// Session, stores its opaque ref, and never proxies the stream nor re-taxonomizes
// events); credential minting (secrets + vault, 07 §2 — it threads an opaque
// Reference through, never resolving it); template authoring/persistence (engine
// concern — it consumes a read-only TemplateStore); model selection
// (agentconfiguration); pipeline sequencing (the engine loops Spawn); cross-node
// scheduling (OD; the seam is carried, the policy is not); usage billing (S9 folds
// the ledger).
//
// Concurrency: a Manager is safe for concurrent use. Spawn/Get/List/Stop/Resume/Watch
// may be called concurrently; the reconcile loop runs on its own goroutine (after
// Start) and serializes per-Agent transitions internally. Close is idempotent.
package orchestrator

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider" // the frozen S2 workspace seam (wave 3A); consumed, not redefined
)

// ─────────────────────────────────────────────────────────────────────────────
// 1. The AgentTemplate entity — DATA, session-scoped, kin to Archetype (02 §2)
// ─────────────────────────────────────────────────────────────────────────────

// AgentTemplate is the precise, versioned, data-only configuration ONE agent session
// is spawned from (C13/C23: "custom configuration — skills, rules, tool grants,
// model/harness binding — plus a custom sandbox spec"). It is the SESSION-SCOPED
// sibling of an Archetype (02 §2): an Archetype is a project-scoped, grafted,
// versioned technology-stack module; an AgentTemplate is the versioned, pluggable
// recipe for one agent loop. Both are DATA with provenance, neither is hand-edited at
// the use site, both are IMMUTABLE once published (editing is publishing a new
// version — a governed act), and neither is interpreted here: the orchestrator FOLDS
// a template into an agentsession.Spec + a workspaceprovider request and never executes
// its contents.
//
// It carries exactly the five axes the brief names — skills, rules, tool grants,
// model/harness binding, and a custom sandbox spec — plus identity/provenance and the
// default limits a launch runs under. Nothing here is a live handle; nothing here is a
// secret VALUE (only a loggable secrets.Reference).
type AgentTemplate struct {
	Ref         TemplateRef // identity: Name + Version (pins the immutable published recipe; provenance)
	Description string      // operator-facing summary; never a secret

	// — Capability surface the agent is equipped with (data the harness is given) —
	Skills []SkillRef               // named skill modules to mount (agentconfiguration resolves to harness-native files)
	Rules  []RuleRef                // named rule/system-prompt fragments (standing instructions; hermetic, never a secret)
	Grants []agentsession.ToolGrant // the standing allowlist AS DATA (07 §3) — folded verbatim into agentsession.Spec.Grants
	Hosts  []agentsession.HostTool  // Eden-provided callback tools (read-scoped project-data tools for an AssistantSession)

	// — Model/harness binding (orchestrator carries it; agentconfiguration decides it) —
	Routing agentsession.RouteKey // selects harness+model per phase/role (agentsession §2.7, 02 §5); orchestrator is TOLD, never decides

	// — The custom sandbox spec (the workspaceprovider demand, declared as data) —
	Sandbox SandboxSpec // substrate + resource envelope + egress the workspace must satisfy

	// — Default limits this template launches under (a Spawn may only TIGHTEN, never loosen) —
	Limits Limits // max-concurrent class ceiling + per-session token budget defaults (02 §2 TokenBudget)

	Labels map[string]string // free-form selectors for fleet/rollout grouping (C17); non-secret
}

// TemplateRef pins an immutable published template by Name + Version. Comparable,
// loggable, usable as a map key (mirrors the secrets.Reference discipline).
type TemplateRef struct {
	Name    string // stable slug, e.g. "product-designer", "implementer-go", "assistant"
	Version string // semver of the published template; "" is the invalid zero ref
}

// IsZero reports the invalid zero ref (empty Name or Version).
func (r TemplateRef) IsZero() bool { return r.Name == "" || r.Version == "" }

// String returns "name@version" (loggable).
func (r TemplateRef) String() string

// SkillRef / RuleRef are opaque, versioned names of capability modules the
// agentconfiguration/TemplateStore resolves into harness-native artifacts. The
// orchestrator carries them; it does not parse, fetch, or execute their contents.
type (
	SkillRef struct{ Name, Version string }
	RuleRef  struct{ Name, Version string }
)

// SandboxSpec is the custom sandbox the template demands — the orchestrator's REQUEST
// to workspaceprovider, declared as data (restated here so a template is
// self-contained). The orchestrator NEVER enforces isolation or touches a container;
// it states the requirement and workspaceprovider satisfies it (07 §3). Egress
// endpoints are DECLARED here and ENFORCED by the provider deriving a NetworkPolicy
// from EgressAllow + the session Grants (declared one side, enforced the other — the
// same split agentsession holds).
type SandboxSpec struct {
	Substrate    Substrate         // kubernetes | docker (02 §1 Platform; ADR-0012); selects mechanism only (P6)
	Image        string            // the agent runtime image (harness preinstalled); pinned by digest in production
	Resources    ResourceEnvelope  // CPU/memory/ephemeral-storage the substrate enforces
	EgressAllow  []string          // explicit egress endpoints beyond model-provider + granted tools (default-deny, 07 §3)
	Env          map[string]string // non-secret child-process env (NEVER a credential — that is the secrets seam)
	WorkdirRepo  RepoMount         // optional repo to clone into the workspace (gitrepository's concern; passed through)
}

// Substrate is the template-author's F1 adapter declaration (ADR-0012: kubernetes is
// the default user-workload substrate; which cluster is the orthogonal ClusterRef,
// resolved at Spawn). orchestrator COMPILES it into workspaceprovider.WorkspaceSpec's
// substrate string ("kubernetes" | "docker"); "anything from k3s to EKS works" is the
// workspaceprovider adapter's job, not a per-cloud branch here (02 §1 "cloud vendors are
// managed adapters of substrates").
type Substrate uint8

const (
	SubstrateKubernetes Substrate = iota // the default → workspaceprovider "kubernetes"; k3d/kind/EKS/GKE/… via the provider adapter
	SubstrateDocker                      // platform self-hosting + degenerate local → workspaceprovider "docker" (ADR-0012)
)

type ResourceEnvelope struct {
	CPUMillis    int64 // request==limit for determinism in v0
	MemoryMiB    int64
	EphemeralMiB int64
}

// RepoMount declares a repository to be present in the workspace at spawn. Opaque to
// orchestrator: it is handed to workspaceprovider (which owns the gitrepository
// clone). The zero value means "empty workspace".
type RepoMount struct {
	URL  string            // clone URL (mirror/eden-authority/byo per ADR-0013); resolved by gitrepository
	Ref  string            // branch/tag/sha; "" == default branch
	Auth secrets.Reference // OPAQUE clone credential; resolved server-side, never the value
}

// Limits bounds a template's launches. MaxConcurrent is a CLASS ceiling shared by all
// agents of a (Tenant, Template) pair (the "max concurrent" the brief names); Budget
// is the per-session token ceiling (02 §2 TokenBudget) the orchestrator folds into
// agentsession.Spec.Budget AND watches via the observed ledger (one budget authority,
// agentsession.md Q6).
type Limits struct {
	MaxConcurrent int                 // 0 == use Config.DefaultMaxConcurrent
	Budget        agentsession.Budget // per-session cost/turns/wall ceiling
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. The Manager port — the surface a consumer (S1 control plane, S4 engine, the
//    chat backend) holds. Exactly 5 methods (the 10 §9 ceiling).
// ─────────────────────────────────────────────────────────────────────────────

// Manager manages agent spawn-up: it records DESIRED state and the reconcile loop
// drives ACTUAL toward it. Every verb is a record mutation or a record read — NONE
// blocks on provisioning or on the agent loop (that happens asynchronously in
// reconcile), which is exactly what makes the single-node contract read identically
// multi-node (rationale 2). New returns the concrete *Pool (return-concrete); callers
// hold this interface (accept-interface). Its zero value is unusable.
type Manager interface {
	// Spawn records the DESIRED intent to run one agent from a template and returns the
	// assigned Agent at StatusPending IMMEDIATELY — it does NOT wait for the workspace
	// or the session (those reconcile asynchronously; observe via Get/Watch). It
	// validates the request against limits BEFORE admitting it (fail cheap, before any
	// pod): a wrapped LimitError (errors.AsType, errors.KindExhausted) if the (Tenant,
	// Template) MaxConcurrent ceiling is met, TemplateNotFoundError for an unknown ref,
	// or InvalidRequestError for a malformed request or a widening override. The
	// returned Agent.ID is the stable handle for every later verb.
	Spawn(ctx context.Context, request SpawnRequest) (Agent, error)

	// Get returns the current Agent record (desired + last-observed actual, reconciled),
	// or a wrapped NotFoundError. Used by the chat backend to obtain the SessionRef to
	// tail and by the engine to poll readiness.
	Get(ctx context.Context, id AgentID) (Agent, error)

	// List returns the Agents matching a filter (by tenant, template, status, label) —
	// the running-set view the dashboard and the engine's scheduler read. Paginated via
	// the filter's Cursor/Limit; a point-in-time snapshot, not a subscription.
	List(ctx context.Context, filter Filter) (Page, error)

	// Stop records the DESIRED terminal intent: the reconcile loop aborts the in-flight
	// turn, Closes the agentsession.Session (which reaps the harness but NEVER tears
	// down the pod — agentsession §2), and RELEASES the workspace back to
	// workspaceprovider (the pod teardown THIS port owns end to end). Idempotent:
	// stopping an already-terminal or already-stopping agent is a no-op success. by
	// stamps the audit identity (07 §7). It returns when the intent is RECORDED, not
	// when teardown completes (observe the terminal Status via Get/Watch).
	Stop(ctx context.Context, id AgentID, by string) error

	// Resume records the DESIRED intent to re-attach a stopped/disconnected agent to
	// its harness-native session (agentsession.Spec.ResumeFrom + CapResume) in a
	// freshly-provisioned-or-surviving workspace — the "resume" the brief names, and the
	// path a backend restart / chat reconnect / old-Run reload takes. UnsupportedError
	// if the bound adapter declares CapResume absent, ConflictError if the agent is not
	// in a resumable Status, NotFoundError if unknown. Reconcile drives the actual
	// re-attach; observe via Get/Watch.
	Resume(ctx context.Context, id AgentID, by string) error
}

// Watcher is the PUSH-observe seam, split off the 5-method Manager (10 §9): a consumer
// that needs live transitions (the dashboard's running-set, the engine waiting for
// StatusRunning) subscribes instead of polling Get. The stream carries Agent-RECORD
// transitions, NOT the agent's own Event stream (that is agentsession.Session.Events,
// tailed directly off Agent.Session). The concrete *Pool implements it. One method.
type Watcher interface {
	// Watch streams AgentEvent transitions for agents matching filter, from now forward.
	// The first emission per matching agent is its current state (snapshot-then-tail), so
	// a fresh subscriber needs no separate List. Closing ctx ends THIS subscription only.
	// Pull-based: a slow consumer slows its own read, never the loop.
	Watch(ctx context.Context, filter Filter) (AgentStream, error)
}

// AgentStream is a one-shot, ordered transition view for ONE Watch subscriber (mirrors
// agentsession.Stream — same ergonomics, different payload).
type AgentStream interface {
	Next(ctx context.Context) (AgentEvent, bool) // ok=false at end (ctx done / Manager closed)
	Err() error                                  // non-nil on fault
}

// AgentEvent is one Agent-record transition (NOT an agentsession.Event). It is the
// orchestration-plane observability the dashboard renders as the running-set chrome.
type AgentEvent struct {
	AgentID  AgentID
	From, To Status
	At       time.Time
	Reason   string // human-readable cause ("workspace provisioned", "budget exceeded"); never a secret
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. The reconcile loop — desired-vs-actual, identical single-node/multi-node
// ─────────────────────────────────────────────────────────────────────────────

// Reconciler is the desired-vs-actual engine BEHIND the Manager verbs — the
// "reconcile-loop shape" the brief asks for (generalized from 05 §5), made a
// first-class, hand-drivable port so the SAME logic runs (a) tick-driven in-process at
// v0 and (b) as a multi-node controller later, with no surface change. The Pool runs
// it on a loop (after Start); it is exposed so a test (or a multi-node leader) drives a
// SINGLE deterministic pass. Two methods.
type Reconciler interface {
	// Reconcile performs ONE pass: read DESIRED records (DesiredStore) and OBSERVED
	// actuals (Probe), compute the diff, and drive each agent one step toward its
	// desired Status — provision a workspace + Open a session for a Pending agent,
	// Close + Release for a Stopping one, re-attach for a Resuming one, mark Failed on a
	// provisioning/spawn/auth fault. It is IDEMPOTENT and CONVERGENT: repeated passes
	// with unchanged desired state are a no-op once actual == desired. It performs AT
	// MOST ONE transition per agent per pass (so a pass is bounded and the loop stays
	// responsive). A single agent's failure never fails the pass (it is recorded on that
	// agent). Returns the per-agent outcomes for observability, not control flow.
	Reconcile(ctx context.Context, ports ReconcilePorts) (ReconcileReport, error)

	// Reap garbage-collects terminal agents past their retention window: releases any
	// lingering workspace lease, finalizes the ledger, and (per DesiredStore policy)
	// archives the record. Separate from Reconcile so retention runs on its own cadence.
	// Idempotent.
	Reap(ctx context.Context, before time.Time) (ReapReport, error)
}

// ReconcilePorts is the set of side-effecting ports a pass drives. Passed per-call (not
// stored) so a multi-node leader can scope a pass to its shard and a test can inject
// fakes per pass without reconstructing the Pool.
type ReconcilePorts struct {
	Workspaces workspaceprovider.Provider // provision/teardown the sandbox (the frozen S2 seam, §5)
	Sessions   agentsession.Factory       // open/resume the agent session in the provisioned workspace
	Probe      Probe                      // observe ACTUAL state (in-process map at v0; cluster query multi-node)
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Records, status, requests
// ─────────────────────────────────────────────────────────────────────────────

// AgentID is the stable, comparable, loggable handle for one orchestrated agent. It
// equals the agentsession SessionID once the session is open, so a consumer needs no
// separate join key.
type AgentID string

// Agent is the reconciled record: the DESIRED intent (Template, Tenant, Limits) plus
// the last-OBSERVED actual (Status, the live workspace + session refs, the running
// ledger). A plain value (copyable, zero-safe) holding NO live handles — only the
// frozen workspaceprovider.Handle + an opaque SessionRef a consumer resolves through
// the owning port. This is what lets the record live in a Postgres row unchanged at
// multi-node (§6).
type Agent struct {
	ID       AgentID     // stable handle (== agentsession SessionID once running)
	Tenant   Tenancy     // tenancy keys — present from day 1 (07 §6); every record carries them
	Template TemplateRef // the desired template (immutable pin)
	RunID    string      // correlation: the engine Run (02 §2) this session serves; "" for a bare chat session
	Status   Status      // last-observed actual lifecycle status
	Limits   Limits      // effective limits (template defaults, possibly tightened by the request)

	Workspace workspaceprovider.Handle  // the provisioned workspace handle (zero until reconciled); the Teardown key — workspaceprovider owns its lifecycle
	Session   SessionRef                // the open agentsession (zero until reconciled); resolve via agentsession to tail Events
	Ledger    agentsession.TokenLedger  // last-observed token/cost aggregate (folded from the session's EventUsage)

	By        string    // who spawned it (audit identity, 07 §7)
	CreatedAt time.Time
	UpdatedAt time.Time
	Detail    string // last transition detail (StatusFailed: a REDACTED reason; never a credential)
}

// Tenancy is the org/project key every agent carries (07 §6). It scopes admission
// (MaxConcurrent is per (Tenant, Template)), observability, and the DesiredStore key.
type Tenancy struct {
	OrganizationID string
	ProjectID      string
}

// SessionRef is the opaque, loggable agentsession session id a consumer passes to
// agentsession to tail Events — the chat surface opens Events(ctx, FromSeq) off THIS,
// NOT off orchestrator, so the running-set view links to the live transcript without
// orchestrator proxying the stream. SessionRef is also the harness-native re-attach
// handle Resume round-trips into agentsession.Spec.ResumeFrom. (The workspace handle is
// workspaceprovider.Handle, stored as Agent.Workspace — the frozen S2 type, not an
// orchestrator-owned WorkspaceRef; §5/Q8.)
type SessionRef string

// Status is the closed, additive-only (10 §9) agent lifecycle — the ORCHESTRATION plane
// (distinct from agentsession.State, the INNER agent-loop state). The reconcile loop
// drives transitions; legal edges are enforced by the library:
// Pending→Provisioning→Running→{Stopping→Stopped | Failed}; Running→Suspended→Resuming
// →Running; any non-terminal →Stopping (a Stop) or →Failed (a fault). Terminal: Stopped,
// Failed. Status rides AgentEvent and the observability stream.
type Status uint8

const (
	StatusPending      Status = iota // desired recorded; not yet reconciled (no workspace yet)
	StatusProvisioning               // workspaceprovider is bringing up the sandbox
	StatusRunning                    // session Open; the agent loop is live (maps to any non-terminal agentsession.State)
	StatusSuspended                  // session dropped/disconnected but re-attachable (CapResume); desired still "running"
	StatusResuming                   // reconcile is re-attaching (Spec.ResumeFrom)
	StatusStopping                   // a Stop was recorded; reconcile is aborting+closing+releasing
	StatusStopped                    // TERMINAL: gracefully stopped; workspace released, ledger finalized
	StatusFailed                     // TERMINAL: provisioning/spawn/auth/budget fault; Detail carries the redacted reason
)

// Terminal reports whether s is a terminal status (no further transition).
func (s Status) Terminal() bool { return s == StatusStopped || s == StatusFailed }

// SpawnRequest is the immutable, fully-resolved input for one Spawn (the configuration
// discipline: parsed at the edge, frozen). It names the template and supplies the
// per-spawn bindings the template cannot carry (tenancy, the resolved credential ref,
// audit identity, run correlation, optional tightening, the permission decider). It
// holds NO secret value and NO live handle.
type SpawnRequest struct {
	Tenant     Tenancy           // tenancy keys (07 §6); required (admission + observability + store scope)
	Template   TemplateRef       // the immutable template to spawn from; required
	Credential secrets.Reference // OPAQUE; flows into agentsession.Spec.Credential, resolved server-side at Open (07 §2)
	By         string            // audit identity of the spawner (07 §7)
	RunID      string            // the engine Run this session serves; "" for a bare chat session
	Cluster    ClusterRef        // which cluster the workspace is provisioned on (ADR-0012); zero == Config.DefaultCluster

	// OnPermission is the policy decider threaded into agentsession.Spec.OnPermission.
	// When set (the engine: deny-default clean-room policy) permission requests resolve
	// synchronously; when nil (the chat) they surface as events for an out-of-band human
	// Session.Resolve (agentsession.md Q2). The orchestrator does not decide; it threads
	// the consumer's choice through.
	OnPermission func(agentsession.PermissionRequest) agentsession.Decision

	// Optional per-spawn overrides — may only TIGHTEN the template (a smaller budget, a
	// narrower grant subset, extra system hints). An attempt to widen is an
	// InvalidRequestError (the template is the ceiling, the request the floor).
	BudgetOverride *agentsession.Budget // nil == template default
	SystemHints    string               // extra hermetic system-prompt augmentation; never a secret
	Labels         map[string]string    // per-spawn labels merged over the template's
}

// ClusterRef names the cluster a workspace is provisioned on (ADR-0012). Opaque to this
// port; the workspaceprovider routes it to an F1 adapter instance (central multi-tenant
// | BYO | local k3d). Zero value == Config.DefaultCluster.
type ClusterRef struct{ ID string } // "" == default

// Filter selects Agents for List/Watch. Empty fields match all; a non-empty field
// narrows. Tenant is ALWAYS applied by the caller's authorization scope upstream
// (07 §5 — authorization is the gateway's job, not this port's).
type Filter struct {
	Tenant     Tenancy     // zero == all tenancies (admin/dashboard); set == one org/project
	Template   TemplateRef // zero == any; Name-only matches all versions
	Statuses   []Status    // nil == any
	OnlyActive bool        // true == exclude terminal statuses (the "running agents" dashboard view)
	Labels     map[string]string
	Cursor     string // opaque pagination cursor ("" == first page)
	Limit      int    // 0 == the Manager's default page size
}

// Page is one List result page.
type Page struct {
	Agents []Agent
	Next   string // opaque cursor for the next page; "" == last page
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. The workspaceprovider seam — CONSUMED, not redefined (one concept, one home).
//    The S2 workspace port froze concurrently in workspaceprovider.md (wave 3A); it
//    already models THIS orchestrator as its consumer. orchestrator's Deps.Workspaces
//    is a workspaceprovider.Provider verbatim — it does NOT mint a parallel
//    WorkspaceProvider/Workspace/WorkspaceRef type (Q8). The three frozen verbs
//    orchestrator binds to:
//      • Provision(WorkspaceSpec) (Workspace, error) — on a Pending agent. orchestrator
//        COMPILES SandboxSpec + Tenant + Cluster into a workspaceprovider.WorkspaceSpec
//        (tenancy rides Labels/Name; SandboxSpec.EgressAllow → []EgressRule; substrate
//        + image + resources map 1:1). Provision is all-or-nothing and idempotent on
//        Name within a tenancy (the level-based reconcile contract), so a re-Provision
//        in a retried pass re-adopts rather than duplicates.
//      • Teardown(Handle) — on EVERY terminal transition (Stopped/Failed) and on a
//        session-open failure. It is the SOLE pod-reaper, since agentsession.Close reaps
//        the harness but NEVER the pod (agentsession §2). Idempotent (Stop is).
//      • Open(Handle) (Workspace, error) — the re-dial after a Pool restart / node
//        recycle. The Handle is the ONLY durable substrate state orchestrator keeps
//        (persisted as Agent.Workspace, a plain serializable value, §4), so Open is
//        what makes the manager stateless across restarts — the workspace half of the
//        Probe/restart-correctness thesis (rationale 2) and of Resume.
//
//    The harness CWD is ws.Handle().WorkDir() → agentsession.Spec.Workspace (the only
//    coupling is a string). orchestrator never calls Workspace.Run/Exec/Files itself —
//    the harness is launched by the agentsession adapter's Spawn inside the provisioned
//    pod (05 §2 boundary); orchestrator owns the pod LIFECYCLE (Provision/Teardown/Open),
//    not what runs in it. The full frozen workspaceprovider.Provider names more verbs
//    (List, and the Workspace's Run/Exec/Files/Status); this is the subset reconcile
//    binds to — the authority on the seam's shape is workspaceprovider.md.
// ─────────────────────────────────────────────────────────────────────────────

// Probe observes ACTUAL state — the multi-node seam. At v0 it reads the Pool's
// in-process map; multi-node it queries the cluster (pods alive? sessions live?). It is
// READ-ONLY (observe, never mutate) so the reconcile diff has a truthful "actual"
// independent of the desired record — the property that makes reconcile correct after a
// Pool restart (rebuild actual from the cluster, not from memory). One method.
type Probe interface {
	// Observe returns the actual status of the agents in ids (workspace alive? session
	// live + its last State/ledger?), so Reconcile diffs against desired. An id with no
	// live actual returns Pending-or-terminal per what the world shows. NEVER mutates.
	Observe(ctx context.Context, ids []AgentID) (map[AgentID]Actual, error)
}

// Actual is one agent's observed world-state (the right half of the reconcile diff).
type Actual struct {
	WorkspaceLive bool
	SessionLive   bool
	SessionState  agentsession.State       // last-observed inner agent-loop state
	Ledger        agentsession.TokenLedger // last-observed usage (for budget enforcement)
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. The constructor spine (10 §4) — PURE
// ─────────────────────────────────────────────────────────────────────────────

// New is the pure constructor spine: no I/O, no clock read, no env read, no
// provisioning, no goroutine started. It validates Config + Deps and returns the
// concrete *Pool. The reconcile loop starts only at Pool.Start (so New stays pure and a
// test drives Reconcile by hand). Returns a wrapped ConfigError (errors.AsType) for an
// invalid Config or a nil required Dep.
func New(configuration Config, dependencies Deps) (*Pool, error)

// Config is the immutable, fully-resolved input. It holds NO ports and NO secrets —
// only scalar policy knobs the routing/limits logic needs, frozen at the edge.
type Config struct {
	DefaultMaxConcurrent int           // class ceiling when a template/request sets 0; 0 here == unbounded (discouraged in production)
	DefaultCluster       ClusterRef    // the cluster a zero-Cluster SpawnRequest resolves to (ADR-0012 hosted-default; local-k3d for dogfooding)
	ReconcileInterval    time.Duration // the loop tick when run via Start; 0 == a sane default
	RetentionWindow      time.Duration // how long terminal Agents are kept before Reap archives them
	ProvisionTimeout     time.Duration // max wait for workspaceprovider.Provider.Provision before marking the agent Failed
}

// Deps is the injected hexagon (accept interfaces; New constructs none). The durable
// DESIRED record and cross-cutting ports live here; the side-effecting reconcile ports
// (workspaceprovider.Provider, agentsession.Factory, Probe) MAY be supplied here as
// defaults for Start's loop and are overridden per-pass via ReconcilePorts (§3), so a multi-node
// leader can scope them per shard. A single-node app supplies them once.
type Deps struct {
	Desired   DesiredStore     // durable desired-state records (in-memory v0; Postgres multi-node) — the ONE swap for multi-node
	Templates TemplateStore    // resolves a TemplateRef to its immutable AgentTemplate (read-only)
	Secrets   secrets.Provider // the seam the credential ref is carried THROUGH; agentsession.Open resolves it server-side
	Telemetry Telemetry        // emits the orchestration-plane observability Events (transitions, limit hits, ledger ticks)
	Clock     Clock            // injected time source so New stays pure and reconcile is deterministic

	// Reconcile-time defaults for Start's loop; a per-pass ReconcilePorts overrides them.
	Workspaces workspaceprovider.Provider // the frozen S2 seam (docker/k3d v0; kubernetes later) — owns pods/isolation/egress/clone
	Sessions   agentsession.Factory
	Probe      Probe
}

// DesiredStore is the durable record of WHAT SHOULD RUN — the single port whose adapter
// swap (in-memory ⇄ Postgres) takes orchestrator from single-node to multi-node with NO
// surface change (rationale 2). The reconcile loop is its only writer of actual-status;
// consumers write desired-intent through the Manager verbs. Records are plain values (no
// live handles), so they serialize to a row, and Resume survives a node recycle.
type DesiredStore interface {
	// Put records or replaces an Agent (the desired intent + last-observed actual).
	Put(ctx context.Context, agent Agent) error
	// Get returns one Agent record (NotFoundError if absent).
	Get(ctx context.Context, id AgentID) (Agent, error)
	// List returns records matching filter (the running-set + reconcile input).
	List(ctx context.Context, filter Filter) (Page, error)
}

// TemplateStore resolves an immutable TemplateRef to its AgentTemplate. Read-only from
// orchestrator's view (publishing/versioning templates is a governed act upstream, like
// Archetype publishing — 02 §2). One method.
type TemplateStore interface {
	// Resolve returns the immutable published AgentTemplate for ref, or a wrapped
	// TemplateNotFoundError (errors.KindNotFound) for an unknown ref/version.
	Resolve(ctx context.Context, ref TemplateRef) (AgentTemplate, error)
}

// Telemetry is the narrow observability seam orchestrator emits on (a structural subset
// of observability.Provider so orchestrator depends on the interface it USES, not the
// whole 5-method Provider — accept-interfaces, 10 §9). The composition root passes an
// observability.Provider, which satisfies this. One method.
type Telemetry interface {
	Emit(ctx context.Context, event ObservabilityEvent)
}

// ObservabilityEvent is the orchestration-plane event orchestrator emits per transition.
// It is a thin, typed envelope the composition root maps onto an observability.Event on
// PlaneAgent (orchestrator stays a leaf-ish library and does not import observability's
// Event shape — the mapping lives at the seam, mirroring how secrets.TelemetryValue
// closes the observability seam structurally).
type ObservabilityEvent struct {
	AgentID AgentID
	Tenant  Tenancy
	Kind    ObservabilityKind
	From    Status
	To      Status
	Ledger  agentsession.TokenLedger // populated on ObsLedgerTick / terminal kinds
	Detail  string                   // redacted; never a credential
}

type ObservabilityKind uint8

const (
	ObsSpawnAdmitted  ObservabilityKind = iota // a Spawn passed limits and recorded desired intent
	ObsLimitRejected                           // a Spawn was rejected by MaxConcurrent (the cost-visibility signal, S9/C5)
	ObsTransition                              // a reconcile Status transition (From→To)
	ObsLedgerTick                              // a folded EventUsage tick (FinOps stream, S9)
	ObsBudgetExceeded                          // the per-session budget ceiling forced a Stop (02 §2)
	ObsReconcileError                          // a per-agent reconcile fault (recorded, non-fatal to the pass)
)

// Clock is the minimal injected time port (mirrors observability.Clock /
// agentsession.Clock). Read at reconcile/emit time, never in New.
type Clock interface{ Now() time.Time }

// Pool is the concrete Manager + Watcher + Reconciler returned by New (named for the
// pool of tracked agents, mirroring agentsession.Pool). It holds the desired-state
// seam, runs the reconcile loop (after Start), enforces limits, folds ledgers, and
// emits observability Events. Safe for concurrent use; zero value unusable.
type Pool struct{ /* unexported */ }

func (p *Pool) Spawn(ctx context.Context, request SpawnRequest) (Agent, error)
func (p *Pool) Get(ctx context.Context, id AgentID) (Agent, error)
func (p *Pool) List(ctx context.Context, filter Filter) (Page, error)
func (p *Pool) Stop(ctx context.Context, id AgentID, by string) error
func (p *Pool) Resume(ctx context.Context, id AgentID, by string) error
func (p *Pool) Watch(ctx context.Context, filter Filter) (AgentStream, error)
func (p *Pool) Reconcile(ctx context.Context, ports ReconcilePorts) (ReconcileReport, error)
func (p *Pool) Reap(ctx context.Context, before time.Time) (ReapReport, error)

// Start runs the reconcile loop on its own goroutine at Config.ReconcileInterval, using
// the Deps-supplied reconcile ports, until ctx is cancelled or Close. It is the ONE
// impure entry (it starts a goroutine and reads the Clock); New stays pure. Optional: a
// single-node app calls Start; a test calls Reconcile by hand.
func (p *Pool) Start(ctx context.Context) error

// Close stops the loop, records a Stopping intent for every non-terminal agent it owns
// (best-effort graceful drain bounded by ctx), and releases resources. Idempotent. It
// does NOT itself tear down pods — it records the intent the final reconcile pass acts
// on. Separate from the Manager interface (lifecycle of the manager, not of an agent).
func (p *Pool) Close(ctx context.Context) error

// ─────────────────────────────────────────────────────────────────────────────
// 7. Reports & errors (typed, errors.AsType-first, aligned with errors.md)
// ─────────────────────────────────────────────────────────────────────────────

// ReconcileReport / ReapReport summarize a pass for observability (NOT control flow).
type ReconcileReport struct {
	Observed     int
	Transitioned int
	Failed       int
	Outcomes     []AgentEvent // the per-agent transitions this pass produced
}
type ReapReport struct{ Reaped int }

// The error taxonomy — typed structs inspected via errors.AsType (errors.md), each
// carrying the offending id/ref, never a secret value. The Manager/Pool returns them
// wrapped with the right errors.Kind so the transport boundary maps once (10 §9).
type (
	TemplateNotFoundError struct{ Ref TemplateRef }                // KindNotFound
	NotFoundError         struct{ ID AgentID }                     // KindNotFound (unknown agent)
	LimitError            struct{ Tenant Tenancy; Template TemplateRef; Max, Current int } // KindExhausted (MaxConcurrent met)
	InvalidRequestError   struct{ Reason string }                  // KindInvalid (malformed / a widening override)
	ConflictError         struct{ ID AgentID; Status Status }      // KindConflict (Resume on a non-resumable status)
	UnsupportedError      struct{ ID AgentID; Capability string }  // KindInvalid (Resume but CapResume absent)
	ProvisionError        struct{ Tenant Tenancy; Cluster ClusterRef; Message string } // KindUnavailable (often retryable)
	ConfigError           struct{ Reason string }                  // KindInvalid (bad Config / nil required Dep)
)

func (e TemplateNotFoundError) Error() string
func (e NotFoundError) Error() string
func (e LimitError) Error() string
func (e InvalidRequestError) Error() string
func (e ConflictError) Error() string
func (e UnsupportedError) Error() string
func (e ProvisionError) Error() string
func (e ConfigError) Error() string
```

## 3. Fake

```go
// Package orchestratortest provides the canonical in-memory fakes + conformance suite
// so consumers (S1 control plane, S4 engine, the chat backend) test the spawn-up
// reconcile loop — admission limits, the desired/actual split, Stop reaping, Resume
// replay, the credential seam — WITHOUT a real cluster or a real claude/omp process,
// and so any future Pool/Probe adapter proves substitutability against the same
// properties (the testing pattern, 10 §4 / 08 §2). The fakes are DETERMINISTIC
// (injected clock, no goroutines unless asked) so a test drives reconcile by hand and
// asserts exact transitions.
package orchestratortest

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// DesiredStore is an in-memory orchestrator.DesiredStore (the v0 binding, reusable as a
// test double). Deterministic; safe for concurrent use.
type DesiredStore struct{ /* unexported: map + mutex */ }

func NewDesiredStore() *DesiredStore { return &DesiredStore{} }
func (s *DesiredStore) Put(ctx context.Context, a orchestrator.Agent) error { return nil }
func (s *DesiredStore) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	return orchestrator.Agent{}, nil
}
func (s *DesiredStore) List(ctx context.Context, f orchestrator.Filter) (orchestrator.Page, error) {
	return orchestrator.Page{}, nil
}

// TemplateStore is an in-memory orchestrator.TemplateStore seeded from a map.
type TemplateStore struct{ /* unexported */ }

func NewTemplateStore(seed ...orchestrator.AgentTemplate) *TemplateStore { return &TemplateStore{} }
func (s *TemplateStore) Resolve(ctx context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	return orchestrator.AgentTemplate{}, nil
}

// Workspaces is the scripted workspaceprovider.Provider the suite drives — the
// orchestrator fake REUSES workspaceprovidertest (one home for the workspace fake), so
// a test asserts "a workspace was Provisioned for the spawn (with the right
// WorkspaceSpec compiled from SandboxSpec+Tenant+Cluster) and TORN DOWN on every
// terminal transition" — the leak the brief's lifecycle guard requires. Its
// FailProvisionWith forces a quota/transient fault. orchestratortest does not mint a
// parallel workspace fake (Q8).
//
//	import "github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
//	ws := workspaceprovidertest.New()  // wired into orchestratortest.New via WithWorkspaces

// Probe is a scriptable orchestrator.Probe: a test sets the observed Actual per agent,
// so reconcile's diff is exercised against a controlled "world" (workspace died?
// session went AwaitingPermission? ledger crossed budget?).
type Probe struct{ /* unexported: map[AgentID]Actual */ }

func NewProbe() *Probe { return &Probe{} }
func (p *Probe) Set(id orchestrator.AgentID, actual orchestrator.Actual) *Probe { return p }
func (p *Probe) Observe(ctx context.Context, ids []orchestrator.AgentID) (map[orchestrator.AgentID]orchestrator.Actual, error) {
	return nil, nil
}

// Telemetry captures emitted ObservabilityEvents for transition/limit/ledger assertions
// (the observability obligation, runnable).
type Telemetry struct{ Events []orchestrator.ObservabilityEvent }

func (t *Telemetry) Emit(ctx context.Context, e orchestrator.ObservabilityEvent) {}

// Clock is a manual clock (mirrors observability/agentsession test clocks).
type Clock struct{ /* unexported */ }

func NewClock() *Clock                    { return &Clock{} }
func (c *Clock) Now() time.Time           { return time.Time{} }
func (c *Clock) Advance(d time.Duration)  {}

// Manager is a deterministic in-process orchestrator.Manager: a real orchestrator.New
// over the fakes above plus an agentsessiontest scripted Adapter wired into an
// agentsession.Pool, so it exercises the REAL reconcile logic — not a degenerate stub.
// WithScript sets the agentsession.Event sequence a launched session emits so a test
// drives ready/usage/terminal deterministically.
type Manager struct{ /* wraps orchestrator.New over fakes */ }

func New(options ...Option) *Manager { return &Manager{} }

type Option func(*config)
type config struct{ /* unexported */ }

// WithTemplate seeds one resolvable AgentTemplate.
func WithTemplate(t orchestrator.AgentTemplate) Option { return nil }

// WithScript sets the agentsession.Event sequence the session for templateName emits.
func WithScript(templateName string, script ...agentsession.Event) Option { return nil }

// WithMaxConcurrent sets the per-(Tenant,Template) admission ceiling (to test LimitError).
func WithMaxConcurrent(n int) Option { return nil }

// WithWorkspaces wires the scripted workspaceprovider fake (workspaceprovidertest) the
// reconcile loop provisions through, so the lifecycle (Provision on Pending, Teardown on
// terminal) is exercised against the REAL frozen S2 seam fake, not a re-implementation.
func WithWorkspaces(p workspaceprovider.Provider) Option { return nil }

// The Manager satisfies orchestrator.Manager + Watcher + Reconciler.
func (m *Manager) Spawn(ctx context.Context, r orchestrator.SpawnRequest) (orchestrator.Agent, error) {
	return orchestrator.Agent{}, nil
}
func (m *Manager) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	return orchestrator.Agent{}, nil
}
func (m *Manager) List(ctx context.Context, f orchestrator.Filter) (orchestrator.Page, error) {
	return orchestrator.Page{}, nil
}
func (m *Manager) Stop(ctx context.Context, id orchestrator.AgentID, by string) error   { return nil }
func (m *Manager) Resume(ctx context.Context, id orchestrator.AgentID, by string) error { return nil }

// Reconcile drives a single deterministic pass by hand (no goroutine), so a test asserts
// exact transitions; Advance steps the manual Clock for retention/timeout assertions.
func (m *Manager) Reconcile(ctx context.Context) (orchestrator.ReconcileReport, error) {
	return orchestrator.ReconcileReport{}, nil
}
func (m *Manager) Advance(d time.Duration) {}

// AssertNoOrphans fails t if any provisioned workspace was not Released by the end of the
// test (the forced-CRUD / leak guarantee made runnable — mirrors the Playwright
// destroy-through-the-UI discipline, C23).
func (m *Manager) AssertNoOrphans(t TestingT) {}

// AssertNoSecretInRecord fails t if canary appears in any Agent record's logged form, an
// ObservabilityEvent, or an error string (the credential-seam guarantee, runnable —
// mirrors agentsessiontest.AssertNoSecretInStream).
func (m *Manager) AssertNoSecretInRecord(t TestingT, canary string) {}

type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}
```

## 4. Conformance suite

The suite proves any `orchestrator.Manager`/`Reconciler` (the v0 `*Pool` or a future
multi-node build) is substitutable and that the lifecycle/limit/credential semantics
hold. It lives in `orchestratortest` per the testing pattern (10 §4, 08 §2); the
real-cluster arm (k3d default / kind second target — ADR-0016) runs in release pipelines
once `workspaceprovider` lands.

```go
// RunManagerSuite asserts the port contract against a freshly-constructed Manager wired
// with the supplied fakes (or a real adapter set). newManager returns a Manager plus the
// scripted Harness a test drives a pass against.
func RunManagerSuite(t *testing.T, newManager func() (orchestrator.Manager, Harness))

// Harness gives the suite the scripted dependencies it drives a pass against. Workspaces
// is the frozen-seam fake (workspaceprovidertest), not an orchestrator-owned double (Q8).
type Harness struct {
	Reconcile  func(context.Context) (orchestrator.ReconcileReport, error) // one deterministic pass
	Workspaces *workspaceprovidertest.Adapter
	Probe      *Probe
	Telemetry  *Telemetry
	Clock      *Clock
}
```

Properties asserted:

- **Spawn records desired, does not block** — `Spawn` returns `StatusPending` immediately and provisions NO workspace; the workspace/session appear only after a `Reconcile` pass (the async, multi-node-shaped contract).
- **Reconcile is convergent + idempotent** — one pass takes a Pending agent Provisioning→Running (workspace `Provision`ed, session `Open`ed); a second pass with unchanged desired is a no-op; at most one transition per agent per pass.
- **Lifecycle legality** — only the §4 status edges occur; terminal statuses never transition; an illegal Resume (non-resumable status) returns `ConflictError`; Resume with `CapResume` absent returns `UnsupportedError`.
- **Limit enforcement** — the `(Tenant, Template)` `MaxConcurrent` ceiling rejects an over-limit `Spawn` with `LimitError`/`KindExhausted` (carrying `Max`+`Current`) *before* provisioning and emits `ObsLimitRejected`; a `Stop` frees a slot; a tightening override is admitted, a widening override is `InvalidRequestError`.
- **Workspace lifecycle — no leak** — every terminal transition (Stopped or Failed) calls `workspaceprovider.Provider.Teardown` exactly once; `agentsession.Close` is called *before* `Teardown` (drain-then-reap) and is never expected to tear down the pod (boundary held); a provisioning failure marks the agent `Failed` and still tears down any partial workspace; `AssertNoOrphans` holds at end of test.
- **Budget authority** — when the observed `Actual.Ledger` crosses `Limits.Budget.MaxCostMicros`, reconcile drives a Stop, the terminal record carries the budget reason, and `ObsBudgetExceeded` is emitted; the orchestrator does NOT double-enforce per turn (one authority, agentsession.md Q6 — it folds `Budget` into `Spec.Budget` and watches the ledger).
- **Restart correctness** — rebuilding the Pool and reconciling against a `Probe` that reports live actuals re-adopts running agents (actual rebuilt from the world, not from memory) — the property that makes the single-node contract honest at multi-node; `Resume` after a dropped actual returns a record tailing the durable transcript.
- **Stream pass-through, no re-taxonomy** — the orchestrator never proxies the agentsession stream; a consumer tails `Agent.Session` directly off the `SessionRef`; the orchestrator's OWN events ride `Telemetry` only.
- **Observability completeness** — every transition emits exactly one `ObsTransition`; `ObsLedgerTick`s fold the session's `EventUsage`; terminal kinds carry the finalized ledger.
- **Credential seam** — the opaque `secrets.Reference` flows from `SpawnRequest` into `agentsession.Spec.Credential` and is never resolved here; it never enters an `Agent` record's logged form, an `ObservabilityEvent`, the `DesiredStore`, or an error string (`AssertNoSecretInRecord` runnable).
- **Tenancy isolation** — `List`/`Watch` with a `Tenant` filter never returns another project's agents; admission counts are per-tenancy.
- **Watch = snapshot-then-tail** — a fresh `Watch` subscriber sees current state first then transitions, gap-free; a slow subscriber never stalls the loop.

## 5. Usage

```go
// ── composition root: wire orchestrator above the frozen seams (single-node v0) ──
// The ONLY place the lower ports + the cluster default bind, and the only stage switch.
func wireOrchestrator(stage environment.Stage, sessions agentsession.Factory, wsp workspaceprovider.Provider,
	templates orchestrator.TemplateStore, store orchestrator.DesiredStore, obs observability.Provider) *orchestrator.Pool {

	cfg := orchestrator.Config{ // dogfooding default (ADR-0012/0016)
		DefaultCluster:   orchestrator.ClusterRef{ID: "local-k3d"},
		ReconcileInterval: 2 * time.Second,
		RetentionWindow:  24 * time.Hour,
		ProvisionTimeout: 90 * time.Second,
	}
	if stage == environment.Production {
		cfg.DefaultCluster = orchestrator.ClusterRef{ID: "eden-central"} // hosted-default multi-tenant (ADR-0012)
		cfg.DefaultMaxConcurrent = 8                                     // metered quota (07 §6, C5)
	}
	pool, _ := orchestrator.New(cfg, orchestrator.Deps{
		Desired:    store,                          // in-memory v0 (orchestratortest.NewDesiredStore); Postgres multi-node — NO surface change
		Templates:  templates,                      // resolves TemplateRef → AgentTemplate (published, immutable)
		Secrets:    obs2vault(stage),               // carried to agentsession.Open, resolved server-side (07 §2)
		Telemetry:  obs,                            // observability.Provider satisfies the narrow Telemetry seam
		Clock:      realClock{},
		Workspaces: wsp,                            // the frozen S2 seam (docker/k3d v0; managed kubernetes later) — owns pods/isolation/clone
		Sessions:   sessions,                       // the agentsession.Factory (claude-code adapter, ADR-0008)
		Probe:      inProcessProbe,                 // v0 reads the live map; multi-node queries the cluster
	})
	return pool // a *orchestrator.Pool, held as orchestrator.Manager downstream
}

// ── S4 kernel engine: spawn an implementer for a phase Run, observe Running, fold ──
// The engine resolves WHICH template (04 §5 policy); orchestrator spawns it. One Spawn
// per agent; the engine loops it across a pipeline.
func (e *Engine) runPhase(ctx context.Context, orch orchestrator.Manager, p phase.Spec) (phase.Evidence, error) {
	agent, err := orch.Spawn(ctx, orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: p.OrgID(), ProjectID: p.ProjectID()},
		Template:   orchestrator.TemplateRef{Name: "implementer-go", Version: p.TemplateVersion()}, // skills+rules+grants+sandbox, all data
		Credential: secrets.Ref("anthropic-oauth-token"),                                           // OPAQUE; setup-token path (C22)
		By:         e.actor(ctx),                                                                    // audit identity (07 §7)
		RunID:      p.RunID(),
		// A clean-room deny-default permission policy is threaded straight through — it
		// becomes agentsession.Spec.OnPermission (one round-trip, two deciders, agentsession Q2).
		OnPermission: func(req agentsession.PermissionRequest) agentsession.Decision {
			if p.Policy().Allows(req.Tool, req.Input) {
				return agentsession.Decision{Allow: true, By: "policy:clean-room"}
			}
			return agentsession.Decision{Allow: false, By: "policy:clean-room"}
		},
	})
	if err != nil {
		var limit orchestrator.LimitError
		if errors.AsType(err, &limit) {
			// the metered backpressure: too many concurrent agents for this (tenant, template) (C5/S9).
			return phase.Evidence{}, fmt.Errorf("agent capacity (%d/%d): %w", limit.Current, limit.Max, err)
		}
		return phase.Evidence{}, fmt.Errorf("spawn implementer: %w", err)
	}
	// Spawn returned immediately at StatusPending. The engine OWNS the session's end:
	// Stop reaps the workspace (the pod lifecycle orchestrator owns end to end, unlike
	// agentsession.Close — 02 §1).
	defer orch.Stop(ctx, agent.ID, e.actor(ctx))

	// Wait for desired→actual (orchestrator did NOT block Spawn on provisioning), then
	// tail the SAME agentsession handle the chat would — off the SessionRef, NOT through
	// orchestrator (no stream proxy). The chat surface and the engine fold the identical
	// stream (agentsession.md §5).
	running, err := waitRunning(ctx, orch, agent.ID) // polls Get until Status==Running or terminal
	if err != nil {
		return phase.Evidence{}, err
	}
	sess := e.agents.OpenByRef(ctx, running.Session) // resolve the SessionRef → live agentsession.Session
	if _, err := sess.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: p.Task()}); err != nil {
		return phase.Evidence{}, fmt.Errorf("prompt: %w", err)
	}
	ledger := agentsession.NewLedgerFold()
	stream := sess.Events(ctx, agentsession.FromSeq(0))
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			break
		}
		p.TranscriptSink().Append(ev)
		ledger.Fold(ev)
	}
	if err := stream.Err(); err != nil {
		return phase.Evidence{}, fmt.Errorf("drain session: %w", err)
	}
	return phase.Evidence{Artifact: running.Workspace.WorkDir(), Ledger: ledger.Finish(), Outcome: ledger.Outcome()}, nil
}

// ── chat-service backend: open an interactive AssistantSession, list/stop ────────
// The SvelteKit server holds the Manager; the browser holds nothing but the AgentID and
// tails events over SSE (the credential boundary is server-side, C22).
func (s *ChatBackend) startAssistant(ctx context.Context, orgID, projectID, userID string) (orchestrator.AgentID, error) {
	agent, err := s.orch.Spawn(ctx, orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: orgID, ProjectID: projectID},
		Template:   orchestrator.TemplateRef{Name: "assistant", Version: "current"}, // read-scoped, Claude Code + Fable 5 (C22)
		Credential: secrets.Ref("anthropic-oauth-token"),
		By:         userID,
		// OnPermission NIL ⇒ permission requests surface as events for the human to
		// Resolve out-of-band (the chat's approve/deny card — agentsession Q2).
	})
	if err != nil {
		var limit orchestrator.LimitError
		if errors.AsType(err, &limit) {
			return "", fmt.Errorf("you have %d agents running (limit %d): %w", limit.Current, limit.Max, err) // 429 to the UI
		}
		return "", err
	}
	return agent.ID, nil // the browser gets the id; once Running, SSE tails agent.Session via agentsession
}

// The dashboard's "running agents" view (C10/C11): the actual set, scoped to a project.
func (s *ChatBackend) listAgents(ctx context.Context, orgID, projectID string) (orchestrator.Page, error) {
	return s.orch.List(ctx, orchestrator.Filter{
		Tenant:     orchestrator.Tenancy{OrganizationID: orgID, ProjectID: projectID},
		OnlyActive: true, // exclude terminal — the live agents only
	})
}

// The chat's "stop" button: the user reaps their own session (destroy-through-the-UI,
// the forced-CRUD discipline C23). Stop owns the FULL teardown — session close AND
// workspace release — unlike agentsession.Close which never touches the pod (02 §1).
func (s *ChatBackend) stopAgent(ctx context.Context, id orchestrator.AgentID, userID string) error {
	return s.orch.Stop(ctx, id, userID)
}

// ── the reconcile loop drives desired→actual (started once; or driven by hand in tests) ──
//   for each desired Agent:
//     Pending      → Workspaces.Provision(toWorkspaceSpec(template.Sandbox, tenant, cluster)) → StatusProvisioning
//     Provisioning → Sessions.Open(foldTemplate(template, request, ws))                       → StatusRunning
//     Running      → Probe.Observe: budget crossed? → Stop; session live? keep
//     Stopping     → session.Close(ctx) + Workspaces.Teardown(agent.Workspace)               → StatusStopped
//     Resuming     → Sessions.Open(Spec.ResumeFrom)                                           → StatusRunning
// toWorkspaceSpec compiles SandboxSpec+Tenant+Cluster → workspaceprovider.WorkspaceSpec
// (tenancy rides Labels/Name; egress → []EgressRule). Teardown is the SOLE pod-reaper.
// Each step emits one ObservabilityEvent; one transition per agent per pass.
```

The template→Spec fold (the heart of `Spawn`+reconcile, shown for the seam it closes):

```go
// foldTemplate composes the immutable AgentTemplate + the per-spawn SpawnRequest into
// the frozen agentsession.Spec — the one place orchestration meets the F4 session
// contract. The template is the ceiling; the request only tightens.
func foldTemplate(t orchestrator.AgentTemplate, r orchestrator.SpawnRequest, ws workspaceprovider.Workspace) agentsession.Spec {
	return agentsession.Spec{
		Workspace:    ws.Handle().WorkDir(),        // the provisioned dir → agentsession CWD (the only coupling is a string; provider owns the lifecycle)
		Routing:      t.Routing,                    // harness+model selector (agentconfiguration decides; we carry)
		Grants:       t.Grants,                     // standing allowlist as data (07 §3)
		HostTools:    t.Hosts,                      // read-scoped project-data callback tools (AssistantSession)
		Credential:   r.Credential,                 // OPAQUE ref; agentsession.Open resolves it server-side
		Budget:       effectiveBudget(t.Limits, r), // template default, tightened by r.BudgetOverride (never widened)
		SystemHints:  t.systemHints() + r.SystemHints,
		OnPermission: r.OnPermission,               // nil ⇒ chat human resolves out-of-band; set ⇒ engine deny-default policy
	}
}
```

## 6. Design rationale

1. **Orchestrator is a manager *above* the seams, not a fourth substrate.** It owns exactly one new concept — **declarative desired-vs-actual agent-session lifecycle** — and delegates everything else to the seams it composes: pods/isolation/egress/clone to `workspaceprovider`, the agent loop + transcript + token ledger to `agentsession` (05 §2), credentials to `secrets`/vault (07 §2), harness/model choice to `agentconfiguration`. This is "one concept, one home" (README cohesion): every other entity is cited, never redefined. The brief's seven duties (resolve template → provision → open session → track → enforce limits → emit events → reconcile) map onto exactly the four owned things in §1, nothing more.

2. **The single-node contract reads identically multi-node because the verbs operate on *records*, never on in-memory handles.** Every `Agent` is a plain serializable value holding a `workspaceprovider.Handle` + an opaque `SessionRef` (handles into the owning ports), not live objects. Desired state lives behind one port (`DesiredStore`); observed actual behind another (`Probe`). v0 binds in-memory adapters; multi-node binds Postgres + a cluster query — **zero surface change**. This is the one load-bearing decision the brief demands ("a contract that reads identically for the multi-node version"): the reconciled form refuses a `map[AgentID]*liveSession` on the manager, because that map is exactly what does not survive a process boundary. Reconcile rebuilds actual from `Probe` (the world), so a manager restart re-adopts running agents instead of orphaning them — and `Resume` (a node recycle, a chat reconnect, an old-Run reload) is a pure read of the durable record plus a `FromSeq` replay off the agentsession transcript.

3. **Reconcile is a first-class, hand-drivable port, generalized from 05 §5.** `Reconciler.Reconcile(ctx, ports)` does one bounded, idempotent, convergent pass — read desired, observe actual, drive each agent one step. Exposing it (rather than burying it in a goroutine) makes the loop deterministically testable (agentsession-style scripted passes) and gives a multi-node leader a per-shard pass for free. `Start` is the only impure entry (goroutine + clock); `New` stays pure (10 §4). This mirrors how 05 §5 makes drift a reconcile loop and how IaC substrates make reconcile the primary topology — the orchestrator is that pattern applied to session lifecycle.

4. **`AgentTemplate` is data, session-scoped, and precisely the Archetype's sibling (02 §2).** An Archetype is project-scoped, grafted, versioned stack data; an `AgentTemplate` is single-session-scoped, spawned-from, versioned agent-recipe data. The kinship is structural: both are **immutable once published**, both are **never executed here** (folded into a downstream artifact — Archetype→monorepo scaffold, Template→`agentsession.Spec`), both are **pinned by a versioned ref**. The five axes the brief names (skills, rules, tool grants, model/harness binding, custom sandbox) are exactly the five capability fields; `Grants`/`Hosts`/`Routing` are the *frozen* `agentsession` types verbatim (no parallel grant or routing model — one home), and `SandboxSpec` is the orchestrator's request to `workspaceprovider`. This is C13's "core opinionated concepts encapsulating user business data into templates" at the agent layer.

5. **Five methods on `Manager`, the rest split (10 §9).** The brief's lifecycle verbs are exactly `Spawn`/`Get`/`List`/`Stop`/`Resume` = 5 — and every one has a real call site in §5. Push observation (`Watch`) splits to `Watcher`; reconcile splits to `Reconciler`; the actual-state read splits to `Probe`; the desired record to `DesiredStore`; template resolution to `TemplateStore`; the workspace seam to the frozen `workspaceprovider.Provider`; observability to the narrow `Telemetry`. Every interface sits at or under the ceiling. `Close`/`Start` (lifecycle of the *manager*, not of an agent) live on the concrete `*Pool`, off the port, so a consumer holding `Manager` never confuses "stop an agent" with "shut down the orchestrator." `Spawn` does not block on provisioning — it admits desired intent and returns `StatusPending` — which is what keeps it a record verb and the contract async-shaped.

6. **Limits and budgets are enforced where they belong, with one authority each.** `MaxConcurrent` is a `(Tenant, Template)` class ceiling checked at `Spawn` admission, *before any pod* (the cost-visibility gate, S9/C5) — failing closed with `LimitError`/`KindExhausted` (carrying `Max`+`Current` so the UI shows "5 of 8 running") and an `ObsLimitRejected` event. The per-session token budget is folded into `agentsession.Spec.Budget` (the harness courtesy cap) AND watched by reconcile against the observed `Actual.Ledger` (the authoritative stop) — exactly agentsession.md Q6's "one budget authority, expressed as a terminal outcome," lifted to the orchestration plane so a runaway agent is stopped even if no consumer is tailing it. The template is the ceiling; a `SpawnRequest` may only tighten — a widening override is an `InvalidRequestError`.

7. **The agentsession stream is re-exported by reference, never proxied; one event taxonomy survives.** `Agent.Session` is an opaque `SessionRef` a consumer resolves through `agentsession` to obtain the *same* `Session` the chat tails and the engine folds — so there is **one** event taxonomy and **one** `Seq`/replay mechanism (agentsession.md's load-bearing invariant untouched). The orchestrator's own `ObservabilityEvent` is strictly its spawn/stop/limit transitions on `PlaneAgent`, a thin typed envelope the composition root maps onto an `observability.Event` — orchestrator does not import the observability `Event` shape, mirroring how `secrets.TelemetryValue` closes that seam structurally. This is why `Telemetry` is a one-method view, not the full 5-method `Provider`.

8. **Credentials and tenancy obey the frozen contracts by construction.** The `SpawnRequest` carries an opaque `secrets.Reference`; the orchestrator threads it into `agentsession.Spec.Credential` and *never resolves it* (resolution is `agentsession.Open`'s server-side job, 07 §2) — so no secret value ever enters a `SpawnRequest`, an `Agent`, an `ObservabilityEvent`, the `DesiredStore`, a log, or an error (`AssertNoSecretInRecord` runnable, mirroring `agentsessiontest.AssertNoSecretInStream`). Every record carries a `Tenancy` (07 §6 "all data rows carry tenancy keys"); admission, `List`/`Watch`, observability, and the store key are all tenancy-scoped, so cross-tenant isolation (threat #6) is structural, not bolted on. Errors are typed structs inspected via `errors.AsType`, each carrying the offending id/ref and a `KindOf`-mappable classification, never a value.

9. **`SandboxSpec` names the substrate, not the cloud (C15/ADR-0012).** The template declares `Substrate{kubernetes|docker}` + image + resources + egress; *which cluster* is the orthogonal `ClusterRef` (hosted-central | BYO | local-k3d), resolved at `Spawn` and compiled into the `workspaceprovider.WorkspaceSpec`. "Anything from k3s to EKS works" is the `workspaceprovider` adapter's job (05 §3 conformance), not a per-cloud branch here — exactly the F1 posture (02 §1). Egress endpoints are *declared* here (`SandboxSpec.EgressAllow`) and *enforced* by the provider deriving the `NetworkPolicy`/firewall from the compiled `[]EgressRule` + the session `Grants` (07 §3) — declared one side, enforced the other, the same split agentsession holds.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| Q1 | **Port name + record name** — the held interface is `Orchestrator` carrying an `Agent` record, or `Manager` carrying a `Handle`? | `Orchestrator` interface; the tracked record is `Agent`; concrete `*Manager`. | `Manager` interface; the tracked record is `Handle`; concrete `*SingleNodeManager`. | 🧩 **`Manager` interface, `Agent` record, concrete `*Pool`.** The package is already named `orchestrator` (the role); an `Orchestrator` interface inside it stutters, and the consumer's two real backend call sites (`engine`, `chat`) hold a thing they call `Manager`. The record is `Agent` (the producer's name): the brief asks to "define the `AgentTemplate` entity precisely," and `Agent` is the natural runtime instance of an `AgentTemplate` — `Handle` reads as a transport detail. The concrete type is `*Pool` (mirroring `agentsession.Pool`, the sibling it composes), not the consumer's `*SingleNodeManager` (which leaks the v0 topology into a name the multi-node build must keep) nor the producer's `*Manager` (collides with the chosen interface name). Return-concrete `*Pool`, accept-interface `Manager` (10 §9). |
| Q2 | **Spawn verb name** — `Spawn` or `Launch`? | `Spawn` (records desired, returns `StatusPending`). | `Launch` (admits desired, returns `PhasePending`). | 🧩 **`Spawn`.** The brief's own words are "manages agent **spawn-up**" and C23 names "agent **start**/stop/resume"; `Spawn` is the corpus term and pairs with `agentsession.Adapter.Spawn` (the process launch one layer down). `Launch` was a synonym with no extra meaning. Semantics are identical (both async, both return Pending) — only the token is pinned. |
| Q3 | **Does the record carry a live `agentsession.Session`, or an opaque `SessionRef`?** | Opaque `SessionRef` (a record is a plain serializable value; resolve via the owning port). | A live `Handle.Session agentsession.Session` (so the chat/engine tail it directly off the record). | 🧩 **Opaque `SessionRef`; resolve via `agentsession`.** This is the contract's load-bearing decision (rationale 2): a record holding a live `Session` cannot survive a Postgres row or a process boundary, so the multi-node-identical requirement the brief demands *forces* the producer's form. The consumer's real need — tail the stream without orchestrator proxying it — is fully met: the chat/engine resolve `Agent.Session` (the `SessionRef`) through `agentsession` and tail the *same* `Session` (shown in §5's `OpenByRef`). The consumer's anti-proxy intent (one event taxonomy, no re-stream) is honored *better* by a ref than by embedding the handle, because the orchestrator never even holds the live object on the hot path. |
| Q4 | **Is `Reconciler` a public, hand-drivable port, or buried in the concrete and exercised only via the fake's `Advance`?** | Public `Reconciler{Reconcile, Reap}` — the brief's "reconcile-loop shape" made first-class; a multi-node leader and a test both drive a single pass. | Implicit: the loop is internal to `*SingleNodeManager`; tests step it via `orchestratortest.Manager.Advance`. | 🧩 **Public `Reconciler`.** The brief explicitly asks for "the reconcile-loop shape (desired vs actual) … whose contract reads identically for the multi-node version." A *buried* loop cannot read identically multi-node — the multi-node leader needs a per-shard `Reconcile(ports)` entry, and a deterministic test needs to assert exact transitions per pass (the consumer's `Advance` is a weaker version of the same need). Exposing it costs nothing (it sits under the 5-method ceiling as a 2-method port) and is the mechanism that makes "single-node and multi-node read identically" *true* rather than asserted. `Start`/`Close` (the goroutine driver) stay on `*Pool`, off the port. |
| Q5 | **Is there a `Watch` push-observe verb?** | Yes — split into `Watcher{Watch}` (the dashboard's live running-set; the engine waiting for `StatusRunning`). | No — observation is `List` (snapshot) + the `observability` stream; no `Watch`. | 🧩 **Kept `Watcher`, split off the 5-method `Manager`.** The dashboard's "running agents" view (C10/C11, "observe production systems") is a real live-update call site, and the engine polling `Get` for readiness is wasteful where a push exists. But it does NOT belong on the core `Manager` (it would be a 6th method) and it must NOT carry the agent's own `agentsession.Event` stream (that is tailed off the `SessionRef`) — so `Watch` carries only `AgentEvent` record transitions and lives on a separate `Watcher` the same `*Pool` implements. The consumer's "just poll `List`" remains valid for simple callers; `Watch` is the efficient path, not a required one. |
| Q6 | **Status granularity** — an 8-value `Status` (Pending/Provisioning/Running/Suspended/Resuming/Stopping/Stopped/Failed), or a 5-value `Phase` (Pending/Provisioning/Running/Stopping/Terminal)? | 8-value `Status` (explicit Suspended/Resuming for the re-attach path; Stopped vs Failed split). | 5-value `Phase` (collapses Suspended/Resuming and folds Stopped/Failed into one `PhaseTerminal`). | 🧩 **8-value `Status` (additive-only).** The brief names "list/get/**stop/resume**" as first-class, and `Resume` needs an observable `Suspended`→`Resuming`→`Running` path the 5-value enum cannot express. Splitting `Stopped` (graceful) from `Failed` (fault, with a redacted `Detail`) is the difference the dashboard renders and the engine branches on (a budget/auth failure is not a clean stop). The enum is closed and additive-only (10 §9), so the consumer's coarser view is a trivial projection (`Suspended`/`Resuming`→"running"; `Stopped`/`Failed`→"terminal") it can compute client-side — the reverse is lossy. Richer-but-projectable wins. |
| Q7 | **`MaxConcurrent` scope** — per `(Tenant, Template)` class, or per-project AND per-organization? | Per `(Tenant, Template)` (a template-class ceiling). | Per-project AND per-organization (two tenancy-level ceilings, no template axis). | 🧩 **Per `(Tenant, Template)` at v0, where `Tenant` = org+project.** The template axis is load-bearing: a project may want 16 cheap reviewers but only 2 expensive implementers concurrently, which a tenancy-only ceiling cannot express. `Tenant` is `Tenancy{Organization, Project}`, so the consumer's project-scope is the dominant key already. The consumer's **per-Tenant *total*** ceiling (independent of template) and **per-organization** ceiling are real for the hosted multi-tenant cluster (07 §6 quota) but are **additive** — a future `TenantPolicy` the `DesiredStore` consults at admission — and are left out of v0 to avoid speculative generality. This is the one open item flagged for Mateo (Q9 below). |
| Q8 | **The workspace seam shape** — does orchestrator mint its own 2-method `WorkspaceProvider`/`Workspace`/`WorkspaceRef`, or consume the frozen `workspaceprovider`? Both drafts independently sketched a workspace port (producer: `Request`/`Release` over a `SandboxSpec`+`WorkspaceRef`; consumer: `Provision`/`Teardown` over a `ProvisionRequest`+id). | `Request(SandboxSpec) (Workspace, error)` + `Release(WorkspaceRef)`; orchestrator owns the `Workspace`/`WorkspaceRef` types. | `Provision(ProvisionRequest{Tenancy, Cluster, Sandbox}) (Workspace, error)` + `Teardown(id)`; orchestrator owns the narrow view. | 🧩 **Neither — CONSUME the frozen `workspaceprovider.Provider` verbatim (one concept, one home).** `workspaceprovider.md` froze concurrently in wave 3A and **already models this orchestrator as its consumer** (its §5 shows `o.provider.Provision(...)` → `ws.Handle().WorkDir()` → `agentsession.Spec.Workspace`, and `Teardown(ws.Handle())` on session end). So orchestrator does NOT mint a parallel `WorkspaceProvider`/`Workspace`/`WorkspaceRef`: `Deps.Workspaces` is a `workspaceprovider.Provider`; `Agent.Workspace` is a `workspaceprovider.Handle` (the durable substrate state, a serializable value — exactly rationale 2). The frozen verbs orchestrator binds to are **`Provision(WorkspaceSpec)`** (orchestrator compiles `SandboxSpec`+`Tenant`+`Cluster` → `WorkspaceSpec`: tenancy rides `Labels`/`Name`, `EgressAllow` → `[]EgressRule` — both drafts' "tenancy/cluster must ride the request" non-negotiable is satisfied), **`Teardown(Handle)`** the sole pod-reaper (producer's `Release` intent and consumer's `Teardown` verb converge on the frozen `Teardown`), and **`Open(Handle)`** the post-restart re-dial — which turns out to be the workspace half of orchestrator's Probe/restart-correctness/Resume thesis for free (the producer draft demanded restart-rebuild; the frozen seam already provides `Open`). The frozen `Provision` already returns `QuotaExceededError`(Exhausted)/`SubstrateUnavailableError`(Unavailable), so orchestrator's reconcile keeps a Pending agent on Exhausted/Unavailable within `ProvisionTimeout` and marks Failed otherwise — wrapping the provider cause in `ProvisionError`. Both independent drafts are subsumed; the real-substrate (k3d default / kind 2nd target, ADR-0016) test helpers live in `workspaceprovidertest`, where that contract placed them, and orchestratortest reuses them. |
| Q9 | **Per-Tenant total quota (the hosted-tier ceiling)** — does the frozen contract need a per-Organization/per-Tenant total `MaxConcurrent` *now*, or is the `(Tenant, Template)` ceiling enough for v0? | Out of v0 (avoid speculative generality); the obvious next limit, additive via a `TenantPolicy`. | Wants per-organization + per-project ceilings present from day 1 (the metering obligation, 07 §6). | 🧩 **Flagged for Mateo — recorded, not silently resolved.** v0 ships the `(Tenant, Template)` ceiling only. The hosted central cluster is multi-tenant from v1 (ADR-0012, 07 §6) and metering/quota is a live obligation, so a **per-Tenant total** ceiling (independent of template) is the likely-next limit. It is purely additive — a `TenantPolicy{MaxConcurrent}` the `DesiredStore` consults at admission, emitting the same `ObsLimitRejected` signal — so freezing without it is safe (no surface breaks when it lands). **Ruling deferred to Mateo:** if hosted-tier quota lands early, add `TenantPolicy` to the frozen `Deps` now; otherwise v0 ships the template-class ceiling and the org/project total is a wave-3B amendment. |
| Q10 | **cross-contract reconciliation, post-draft** — both drafts named the frozen siblings; confirm alignment. | Named `agentsession.{Factory,Spec,Budget,RouteKey,ToolGrant,HostTool,State,TokenLedger,PermissionRequest,Decision}`, `secrets.Reference/Provider`, a narrow `observability` `Telemetry` subset, `errors.AsType`+typed structs. | Named the same set plus `agentsession.HostTool` on the template and `OnPermission` threaded through `SpawnRequest`. | 🧩 **Aligned to the frozen siblings as written.** Credentials use `secrets.Reference` (loggable) + `secrets.Provider` exactly as `secrets.md` froze them — carried, never resolved here. The template's `Grants`/`Hosts`/`Routing`/`Budget` and the request's `OnPermission` are the frozen `agentsession` types verbatim, so `foldTemplate` (§5) is a struct-copy with no translation layer; `SessionRef` is the `agentsession` session id `Spec.ResumeFrom` consumes (Resume round-trips it — confirmed against agentsession.md Q1's `Spec.ResumeFrom` + `CapResume`). Observability rides a narrow `Telemetry{Emit}` (a structural subset of `observability.Provider`) and a typed `ObservabilityEvent` the composition root maps onto a `PlaneAgent` `observability.Event` — orchestrator does not import the observability `Event` shape, mirroring `secrets.TelemetryValue` (secrets.md Q9). Errors are typed structs inspected via `errors.AsType` per `errors.md`, each carrying the offending id/ref, never a value. **One confirmation owed by agentsession (non-blocking):** the harness-native re-attach handle stored as `Agent.Session`/`SessionRef` is the same string `agentsession.Spec.ResumeFrom` consumes; the frozen contract reads as yes. |
