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
// (contract §6). The verbs operate on RECORDS (plain serializable values holding
// opaque refs), never on in-memory handles, which is the one decision that buys
// multi-node for free.
//
// It does NOT own: workspace provisioning/isolation/egress/clone (workspaceprovider,
// 02 §1 — it NAMES the sandbox and CALLS the provider; Release/Teardown is the sole
// pod teardown path); the agent loop / Event stream (agentsession F4, 05 §2 — it
// OPENS a Session, stores its opaque ref, and never proxies the stream nor
// re-taxonomizes events); credential minting (secrets + vault, 07 §2 — it threads an
// opaque Reference through, never resolving it); template authoring/persistence
// (engine concern — it consumes a read-only TemplateStore); model selection
// (agentconfiguration); pipeline sequencing (the engine loops Spawn); cross-node
// scheduling (OD; the seam is carried, the policy is not); usage billing (S9 folds
// the ledger).
//
// Concurrency: a Pool is safe for concurrent use. Spawn/Get/List/Stop/Resume/Watch
// may be called concurrently; the reconcile loop runs on its own goroutine (after
// Start) and serializes per-Agent transitions internally. Close is idempotent.
package orchestrator

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// ─────────────────────────────────────────────────────────────────────────────.
// 1. The AgentTemplate entity — DATA, session-scoped, kin to Archetype (02 §2)
// ─────────────────────────────────────────────────────────────────────────────.

// AgentTemplate is the precise, versioned, data-only configuration ONE agent session
// is spawned from (C13/C23: skills, rules, tool grants, model/harness binding, plus a
// custom sandbox spec). It is the SESSION-SCOPED sibling of an Archetype (02 §2): both
// are DATA with provenance, neither hand-edited at the use site, both IMMUTABLE once
// published, and neither interpreted here — the orchestrator FOLDS a template into an
// agentsession.Spec + a workspaceprovider request and never executes its contents.
//
// It carries the five axes the brief names — skills, rules, tool grants, model/harness
// binding, and a custom sandbox spec — plus identity/provenance and the default limits
// a launch runs under. Nothing here is a live handle; nothing here is a secret VALUE
// (only a loggable secrets.Reference).
type AgentTemplate struct {
	Ref         TemplateRef // identity: Name + Version (pins the immutable published recipe; provenance)
	Description string      // operator-facing summary; never a secret

	// — Capability surface the agent is equipped with (data the harness is given) —
	Skills []SkillRef               // named skill modules to mount (agentconfiguration resolves to harness-native files)
	Rules  []RuleRef                // named rule/system-prompt fragments (standing instructions; hermetic, never a secret)
	Grants []agentsession.ToolGrant // the standing allowlist AS DATA (07 §3) — folded verbatim into agentsession.Spec.Grants
	Hosts  []agentsession.HostTool  // Eden-provided callback tools (read-scoped project-data tools for an AssistantSession)

	// — Model/harness binding (orchestrator carries it; agentconfiguration decides it) —
	Routing agentsession.RouteKey // selects harness+model per phase/role; orchestrator is TOLD, never decides

	// — The custom sandbox spec (the workspaceprovider demand, declared as data) —
	Sandbox SandboxSpec // substrate + resource envelope + egress the workspace must satisfy

	// — Default limits this template launches under (a Spawn may only TIGHTEN, never loosen) —
	Limits Limits // max-concurrent class ceiling + per-session token budget defaults (02 §2 TokenBudget)

	// SystemHints is the template's standing system-prompt augmentation, folded ahead
	// of any per-spawn SystemHints (hermetic; never a secret).
	SystemHints string

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
func (r TemplateRef) String() string {
	if r.IsZero() {
		return "<invalid-template-ref>"
	}
	return r.Name + "@" + r.Version
}

// SkillRef is an opaque, versioned name of a skill module the
// agentconfiguration/TemplateStore resolves into harness-native artifacts. The
// orchestrator carries it; it does not parse, fetch, or execute its contents.
type SkillRef struct{ Name, Version string }

// RuleRef is an opaque, versioned name of a rule/system-prompt fragment the
// agentconfiguration/TemplateStore resolves into harness-native artifacts. The
// orchestrator carries it; it does not parse, fetch, or execute its contents.
type RuleRef struct{ Name, Version string }

// SandboxSpec is the custom sandbox the template demands — the orchestrator's REQUEST
// to workspaceprovider, declared as data. The orchestrator NEVER enforces isolation or
// touches a container; it states the requirement and workspaceprovider satisfies it
// (07 §3). Egress endpoints are DECLARED here and ENFORCED by the provider deriving a
// NetworkPolicy from EgressAllow + the session Grants.
type SandboxSpec struct {
	Substrate   Substrate         // kubernetes | docker (02 §1 Platform; ADR-0012); selects mechanism only
	Image       string            // the agent runtime image (harness preinstalled); pinned by digest in production
	Resources   ResourceEnvelope  // CPU/memory/ephemeral-storage the substrate enforces
	EgressAllow []string          // explicit egress endpoints beyond model-provider + granted tools (default-deny, 07 §3)
	Env         map[string]string // non-secret child-process env (NEVER a credential — that is the secrets seam)
	WorkdirRepo RepoMount         // optional repo to clone into the workspace (gitrepository's concern; passed through)

	// Entrypoint is the WORKLOAD-POD command (ADR-0022 §4, OD-15-a): when non-empty the
	// workspace's MAIN process IS the workload (the agent-runtime sidecar as PID-1), so the
	// supervised pod's lifecycle natively IS the session's — the orchestrator Probes the
	// provider's supervised Status rather than raw heartbeats. It folds verbatim into
	// workspaceprovider.WorkspaceSpec.Entrypoint. Empty == a classic Ready-then-Run workspace
	// (the existing behavior — additive, spec-selected). The orchestrator never interprets it.
	Entrypoint []string
}

// Substrate is the template-author's F1 adapter declaration (ADR-0012: kubernetes is
// the default user-workload substrate; which cluster is the orthogonal ClusterRef,
// resolved at Spawn). orchestrator COMPILES it into workspaceprovider.WorkspaceSpec's
// substrate string ("kubernetes" | "docker").
type Substrate uint8

// The v0 substrates. A managed kubernetes (EKS/GKE/AKS) is the same kubernetes adapter
// pointed at a different cluster config, not a new Substrate value.
const (
	SubstrateKubernetes Substrate = iota // the default → workspaceprovider "kubernetes"
	SubstrateDocker                      // platform self-hosting + degenerate local → workspaceprovider "docker"
)

// ResourceEnvelope bounds a sandbox's CPU/memory/ephemeral-storage. request==limit for
// determinism in v0.
type ResourceEnvelope struct {
	CPUMillis    int64
	MemoryMiB    int64
	EphemeralMiB int64
}

// RepoMount declares a repository to be present in the workspace at spawn. Opaque to
// orchestrator: it is handed to workspaceprovider (which owns the gitrepository clone).
// The zero value means "empty workspace".
type RepoMount struct {
	URL        string            // clone URL (mirror/eden-authority/byo per ADR-0013); resolved by gitrepository
	Ref        string            // branch/tag/sha; "" == default branch
	Credential secrets.Reference // OPAQUE clone credential; resolved server-side, never the value
}

// Limits bounds a template's launches. MaxConcurrent is a CLASS ceiling shared by all
// agents of a (Tenant, Template) pair; Budget is the per-session token ceiling the
// orchestrator folds into agentsession.Spec.Budget AND watches via the observed ledger
// (one budget authority, agentsession.md Q6).
type Limits struct {
	MaxConcurrent int                 // 0 == use Config.DefaultMaxConcurrent
	Budget        agentsession.Budget // per-session cost/turns/wall ceiling
}

// ─────────────────────────────────────────────────────────────────────────────.
// 2. Records, status, requests
// ─────────────────────────────────────────────────────────────────────────────.

// AgentID is the stable, comparable, loggable handle for one orchestrated agent. It
// equals the agentsession SessionID once the session is open, so a consumer needs no
// separate join key.
type AgentID string

// Tenancy is the org/project key every agent carries (07 §6). It scopes admission
// (MaxConcurrent is per (Tenant, Template)), observability, and the DesiredStore key.
type Tenancy struct {
	OrganizationID string
	ProjectID      string
}

// IsZero reports the empty tenancy (both keys empty).
func (t Tenancy) IsZero() bool { return t.OrganizationID == "" && t.ProjectID == "" }

// SessionRef is the opaque, loggable agentsession session id a consumer passes to
// agentsession to tail Events — the chat surface opens Events(ctx, FromSeq) off THIS,
// NOT off orchestrator, so the running-set view links to the live transcript without
// orchestrator proxying the stream. SessionRef is also the harness-native re-attach
// handle Resume round-trips into agentsession.Spec.ResumeFrom.
type SessionRef string

// Status is the closed, additive-only (10 §9) agent lifecycle — the ORCHESTRATION plane
// (distinct from agentsession.State, the INNER agent-loop state). The reconcile loop
// drives transitions; legal edges are enforced by the library:
// Pending→Provisioning→Running→{Stopping→Stopped | Failed}; Running→Suspended→Resuming
// →Running; any non-terminal →Stopping (a Stop) or →Failed (a fault). Terminal:
// Stopped, Failed.
type Status uint8

// The agent lifecycle statuses. Append-only (10 §9): never reordered or renamed.
const (
	StatusPending      Status = iota // desired recorded; not yet reconciled (no workspace yet)
	StatusProvisioning               // workspaceprovider is bringing up the sandbox
	StatusRunning                    // session Open; the agent loop is live (any non-terminal agentsession.State)
	StatusSuspended                  // session dropped/disconnected but re-attachable (CapResume); desired still "running"
	StatusResuming                   // reconcile is re-attaching (Spec.ResumeFrom)
	StatusStopping                   // a Stop was recorded; reconcile is aborting+closing+releasing
	StatusStopped                    // TERMINAL: gracefully stopped; workspace released, ledger finalized
	StatusFailed                     // TERMINAL: provisioning/spawn/auth/budget fault; Detail carries the redacted reason
)

// statusTokens holds the stable lower-kebab token for each Status, indexed by value.
var statusTokens = [...]string{
	StatusPending:      "pending",
	StatusProvisioning: "provisioning",
	StatusRunning:      "running",
	StatusSuspended:    "suspended",
	StatusResuming:     "resuming",
	StatusStopping:     "stopping",
	StatusStopped:      "stopped",
	StatusFailed:       "failed",
}

// String returns the stable lower-kebab token (e.g. "provisioning"). Total: returns
// "pending" for any out-of-range value.
func (s Status) String() string {
	if int(s) < len(statusTokens) {
		return statusTokens[s]
	}
	return statusTokens[StatusPending]
}

// Terminal reports whether s is a terminal status (no further transition).
func (s Status) Terminal() bool { return s == StatusStopped || s == StatusFailed }

// Agent is the reconciled record: the DESIRED intent (Template, Tenant, Limits) plus
// the last-OBSERVED actual (Status, the live workspace + session refs, the running
// ledger). A plain value (copyable, zero-safe) holding NO live handles — only the
// frozen workspaceprovider.Handle + an opaque SessionRef a consumer resolves through
// the owning port. This is what lets the record live in a Postgres row unchanged at
// multi-node (contract §6).
type Agent struct {
	ID       AgentID     // stable handle (== agentsession SessionID once running)
	Tenant   Tenancy     // tenancy keys — present from day 1 (07 §6); every record carries them
	Template TemplateRef // the desired template (immutable pin)
	RunID    string      // correlation: the engine Run (02 §2) this session serves; "" for a bare chat session
	Desired  Desired     // the desired terminal status the loop drives toward (Running or Stopped)
	Status   Status      // last-observed actual lifecycle status
	Limits   Limits      // effective limits (template defaults, possibly tightened by the request)
	Cluster  ClusterRef  // the cluster the workspace is provisioned on (resolved at Spawn)

	Workspace workspaceprovider.Handle // the provisioned workspace handle (zero until reconciled); the Teardown key
	Session   SessionRef               // the open agentsession (zero until reconciled); resolve via agentsession to tail Events
	Ledger    agentsession.TokenLedger // last-observed token/cost aggregate (folded from the session's EventUsage)

	By        string // who spawned/stopped it (audit identity, 07 §7)
	CreatedAt time.Time
	UpdatedAt time.Time
	Detail    string // last transition detail (StatusFailed: a REDACTED reason; never a credential)
}

// Desired is the closed set of terminal intents the reconcile loop drives an Agent
// toward. Spawn records DesiredRunning; Stop records DesiredStopped. It is separate
// from Status (the observed actual) — the diff between Desired and Status is what each
// reconcile pass closes by one step.
type Desired uint8

// The desired terminal intents.
const (
	DesiredRunning Desired = iota // the agent should be live (Spawn / Resume)
	DesiredStopped                // the agent should be torn down (Stop / Close)
)

// String renders the desired intent for logs (loggable; never a secret).
func (d Desired) String() string {
	if d == DesiredStopped {
		return "stopped"
	}
	return "running"
}

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

// IsZero reports the empty cluster ref (the Config.DefaultCluster sentinel).
func (c ClusterRef) IsZero() bool { return c.ID == "" }

// Filter selects Agents for List/Watch. Empty fields match all; a non-empty field
// narrows. Tenant is ALWAYS applied by the caller's authorization scope upstream (07 §5
// — authorization is the gateway's job, not this port's).
type Filter struct {
	Tenant     Tenancy           // zero == all tenancies (admin/dashboard); set == one org/project
	Template   TemplateRef       // zero == any; Name-only matches all versions
	Statuses   []Status          // nil == any
	OnlyActive bool              // true == exclude terminal statuses (the "running agents" dashboard view)
	Labels     map[string]string // exact-match label set
	Cursor     string            // opaque pagination cursor ("" == first page)
	Limit      int               // 0 == the Manager's default page size
}

// Page is one List result page.
type Page struct {
	Agents []Agent
	Next   string // opaque cursor for the next page; "" == last page
}

// Actual is one agent's observed world-state (the right half of the reconcile diff).
type Actual struct {
	WorkspaceLive bool
	SessionLive   bool
	SessionState  agentsession.State       // last-observed inner agent-loop state
	Ledger        agentsession.TokenLedger // last-observed usage (for budget enforcement)
}
