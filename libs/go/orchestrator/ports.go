package orchestrator

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// ─────────────────────────────────────────────────────────────────────────────.
// The Manager port — the surface a consumer (S1 control plane, S4 engine, the chat
// backend) holds. Exactly 5 methods (the 10 §9 ceiling).
// ─────────────────────────────────────────────────────────────────────────────.

// Manager manages agent spawn-up: it records DESIRED state and the reconcile loop
// drives ACTUAL toward it. Every verb is a record mutation or a record read — NONE
// blocks on provisioning or on the agent loop (that happens asynchronously in
// reconcile), which is exactly what makes the single-node contract read identically
// multi-node. New returns the concrete *Pool (return-concrete); callers hold this
// interface (accept-interface). Its zero value is unusable.
type Manager interface {
	// Spawn records the DESIRED intent to run one agent from a template and returns the
	// assigned Agent at StatusPending IMMEDIATELY — it does NOT wait for the workspace
	// or the session (those reconcile asynchronously; observe via Get/Watch). It
	// validates the request against limits BEFORE admitting it (fail cheap, before any
	// pod): a wrapped LimitError (errors.AsType, errors.KindExhausted) if the (Tenant,
	// Template) MaxConcurrent ceiling is met, TemplateNotFoundError for an unknown ref,
	// or InvalidRequestError for a malformed request or a widening override.
	Spawn(ctx context.Context, request SpawnRequest) (Agent, error)

	// Get returns the current Agent record (desired + last-observed actual, reconciled),
	// or a wrapped NotFoundError.
	Get(ctx context.Context, id AgentID) (Agent, error)

	// List returns the Agents matching a filter (by tenant, template, status, label) —
	// the running-set view the dashboard and the engine's scheduler read. A point-in-time
	// snapshot, not a subscription.
	List(ctx context.Context, filter Filter) (Page, error)

	// Stop records the DESIRED terminal intent: the reconcile loop aborts the in-flight
	// turn, Closes the agentsession.Session (which reaps the harness but NEVER tears down
	// the pod — agentsession §2), and RELEASES the workspace back to workspaceprovider
	// (the pod teardown THIS port owns end to end). Idempotent. by stamps the audit
	// identity (07 §7). It returns when the intent is RECORDED, not when teardown
	// completes (observe the terminal Status via Get/Watch).
	Stop(ctx context.Context, id AgentID, by string) error

	// Resume records the DESIRED intent to re-attach a stopped/disconnected agent to its
	// harness-native session (agentsession.Spec.ResumeFrom + CapResume). UnsupportedError
	// if the bound adapter declares CapResume absent, ConflictError if the agent is not in
	// a resumable Status, NotFoundError if unknown. Reconcile drives the actual re-attach.
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

// Reconciler is the desired-vs-actual engine BEHIND the Manager verbs — the
// reconcile-loop shape made a first-class, hand-drivable port so the SAME logic runs
// (a) tick-driven in-process at v0 and (b) as a multi-node controller later, with no
// surface change. The Pool runs it on a loop (after Start); it is exposed so a test
// (or a multi-node leader) drives a SINGLE deterministic pass. Two methods.
type Reconciler interface {
	// Reconcile performs ONE pass: read DESIRED records (DesiredStore) and OBSERVED
	// actuals (Probe), compute the diff, and drive each agent one step toward its desired
	// Status — provision a workspace + Open a session for a Pending agent, Close + Release
	// for a Stopping one, re-attach for a Resuming one, mark Failed on a fault. It is
	// IDEMPOTENT and CONVERGENT: repeated passes with unchanged desired state are a no-op
	// once actual == desired. It performs AT MOST ONE transition per agent per pass. A
	// single agent's failure never fails the pass (it is recorded on that agent). Returns
	// the per-agent outcomes for observability, not control flow.
	Reconcile(ctx context.Context, ports ReconcilePorts) (ReconcileReport, error)

	// Reap garbage-collects terminal agents past their retention window: releases any
	// lingering workspace lease and (per DesiredStore policy) archives the record.
	// Separate from Reconcile so retention runs on its own cadence. Idempotent.
	Reap(ctx context.Context, before time.Time) (ReapReport, error)
}

// ReconcilePorts is the set of side-effecting ports a pass drives. Passed per-call (not
// stored) so a multi-node leader can scope a pass to its shard and a test can inject
// fakes per pass without reconstructing the Pool.
type ReconcilePorts struct {
	Workspaces workspaceprovider.Provider // provision/teardown the sandbox (the frozen S2 seam)
	Sessions   agentsession.Factory       // open/resume the agent session in the provisioned workspace
	Probe      Probe                      // observe ACTUAL state (in-process map at v0; cluster query multi-node)
}

// Probe observes ACTUAL state — the multi-node seam. At v0 it reads the Pool's
// in-process map; multi-node it queries the cluster. It is READ-ONLY (observe, never
// mutate) so the reconcile diff has a truthful "actual" independent of the desired
// record — the property that makes reconcile correct after a Pool restart. One method.
type Probe interface {
	// Observe returns the actual status of the agents in ids (workspace alive? session
	// live + its last State/ledger?), so Reconcile diffs against desired. An id with no
	// live actual is absent from the result. NEVER mutates.
	Observe(ctx context.Context, ids []AgentID) (map[AgentID]Actual, error)
}

// DesiredStore is the durable record of WHAT SHOULD RUN — the single port whose adapter
// swap (in-memory ⇄ Postgres) takes orchestrator from single-node to multi-node with NO
// surface change. The reconcile loop is its only writer of actual-status; consumers
// write desired-intent through the Manager verbs. Records are plain values (no live
// handles), so they serialize to a row, and Resume survives a node recycle.
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
// observability.Provider, which a thin shim satisfies. One method.
type Telemetry interface {
	Emit(ctx context.Context, event ObservabilityEvent)
}

// ObservabilityEvent is the orchestration-plane event orchestrator emits per
// transition. It is a thin, typed envelope the composition root maps onto an
// observability.Event on PlaneAgent (orchestrator stays a leaf-ish library and does not
// import observability's Event shape — the mapping lives at the seam, mirroring how
// secrets.TelemetryValue closes the observability seam structurally).
type ObservabilityEvent struct {
	AgentID AgentID
	Tenant  Tenancy
	Kind    ObservabilityKind
	From    Status
	To      Status
	Ledger  agentsession.TokenLedger // populated on ObsLedgerTick / terminal kinds
	Detail  string                   // redacted; never a credential
}

// ObservabilityKind is the orchestration-plane event class. Append-only (10 §9).
type ObservabilityKind uint8

// The orchestration-plane event kinds.
const (
	ObsSpawnAdmitted  ObservabilityKind = iota // a Spawn passed limits and recorded desired intent
	ObsLimitRejected                           // a Spawn was rejected by MaxConcurrent (the cost-visibility signal, S9/C5)
	ObsTransition                              // a reconcile Status transition (From→To)
	ObsLedgerTick                              // a folded EventUsage tick (FinOps stream, S9)
	ObsBudgetExceeded                          // the per-session budget ceiling forced a Stop (02 §2)
	ObsReconcileError                          // a per-agent reconcile fault (recorded, non-fatal to the pass)
)

// obsKindTokens holds the stable lower-kebab token for each ObservabilityKind.
var obsKindTokens = [...]string{
	ObsSpawnAdmitted:  "spawn-admitted",
	ObsLimitRejected:  "limit-rejected",
	ObsTransition:     "transition",
	ObsLedgerTick:     "ledger-tick",
	ObsBudgetExceeded: "budget-exceeded",
	ObsReconcileError: "reconcile-error",
}

// String returns the stable lower-kebab token (e.g. "limit-rejected"). Total: returns
// "spawn-admitted" for any out-of-range value.
func (k ObservabilityKind) String() string {
	if int(k) < len(obsKindTokens) {
		return obsKindTokens[k]
	}
	return obsKindTokens[ObsSpawnAdmitted]
}

// Clock is the minimal injected time port (mirrors observability.Clock /
// agentsession.Clock). Read at reconcile/emit time, never in New.
type Clock interface{ Now() time.Time }

// ReconcileReport summarizes a reconcile pass for observability (NOT control flow).
type ReconcileReport struct {
	Observed     int
	Transitioned int
	Failed       int
	Outcomes     []AgentEvent // the per-agent transitions this pass produced
}

// ReapReport summarizes a reap pass.
type ReapReport struct{ Reaped int }
