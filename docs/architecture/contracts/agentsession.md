# Contract — agentsession

> Status: Frozen (ADR-0016) · 2026-06-13 · Reconciled from independent producer/consumer drafts
> (09 §4 step 2) and frozen with the library built: the exported surface is mechanically recorded
> at `libs/go/agentsession/.apibaseline` (the freeze made mechanical, ADR-0020) and the claude/omp
> adapters + the ADR-0020 8-dimension test taxonomy are green. The **F4 connector family's session
> interface** — the agent abstraction layer (C22, ADR-0008). This is a **connector contract**
> (05 §2 family F4: the `execute(spec, context, tools, schema) → artifact + transcript + token
> ledger` verb made interactive and resumable), **not** a 10 §4 library pattern. A breaking change
> to the surface requires a contract revision (ADR-0016 §1) + re-recording the `.apibaseline` —
> the cardinal sin otherwise (10 §9).

## 1. Scope

`agentsession` is the port that turns *a harness process* — a headless `claude` CLI (ADR-0008), an
`omp --mode rpc` subprocess, a future `codex` loop — into *a controllable, instrumented Eden
session*: **one agent loop, in one sandbox (07 §3), over one Workspace (02 §1)**. It is **one
contract with no mode fork** — a `Session` is the primitive; the engine's batch
`execute(spec, context, tools, schema)` (05 §2) is a thin fold over `Open → Prompt → drain to
terminal → close`, and the chat surface (C22) is the same `Session` opened, streamed, steered, and
reconnected. The asymmetry (chat exercises deltas/steer/replay/multi-client; batch never does)
proves the surface is minimal, not bifurcated. It owns exactly four things:

1. **Lifecycle** — open a session, drive it (`Prompt` / `Steer` / `Abort`), observe its state.
2. **The event stream** — one normalized, ordered, forward-compatible `Event` taxonomy that is the
   **instrumentation contract** (the EVENT TAXONOMY of §2): every message delta, thinking block,
   tool start/end, permission request, token-usage tick, error, and lifecycle transition a harness
   emits, normalized into Eden's vocabulary, with an opaque per-harness `Extension` payload so
   nothing is lost — plus **monotonic per-session sequence numbers** that make `Last-Event-ID`
   reconnect, fresh-tab replay, and the engine's `FromSeq(0)` fold the *same* mechanism.
3. **The tool-grant model** — the allowlist (as data) and the capability manifest a session is
   launched with, plus the seam for **host tools** (Eden-provided tools the agent calls back into —
   the read-scoped project-data tools of an `AssistantSession`), and the **permission round-trip**
   (the agent asks → a `PermissionRequest` event → a human via chat or a policy via engine
   `Resolve`s it).
4. **Configurability** — which harness + model serves each invocation, resolved upstream by
   `agentconfiguration` and handed in frozen (C22's "right agent for the right phase").

It explicitly does **not** own (the consumer must not expect these here):

- **Pod / workspace provisioning and lifecycle** — owned by **S2's orchestrator over the
  `workspaceprovider` port** (02 §1 Workspace boundary; 05 §2). This contract assumes a workspace
  already exists and a harness can be spawned in it; it **never creates a container** and `Close`
  **never tears down the pod**.
- **Isolation mechanism** — pod sandboxing, dial-out-only, default-deny egress are **assumed, not
  implemented** here (07 §3; see §6). The contract *declares the egress endpoints a session needs*
  (so F1's `NetworkPolicy` can be derived from the `Route` + `Grants`) but enforces none, opens no
  socket, and manages no pod.
- **Credential storage / minting** — owned by the `secrets` port + vault (07 §2). This contract
  carries an **opaque `secrets.Reference`**, resolved server-side at `Open`; the *injection seam*
  into the harness process is defined in §2 (the EVENT TAXONOMY's sibling, the credential-flow
  diagram) but the raw value never enters this library's logs, the `Spec`, or any `Event`.
- **Transcript persistence policy & retention** — the `Transcript` is a first-class stored object
  (02 §2 / P9) and the durable replay log this contract's resumability rests on, but *where* and
  *how long* it is stored is the engine's / 07 §2 retention concern. This port **emits** the event
  stream and **names** its replay semantics; it does not persist it.
- **UI concerns** — rendering, layout, the Ableton-grade chat surface (C11/C22) consume the `Event`
  stream; no view model, no markdown, no diff-rendering leaks into this contract.
- **Usage-record normalization / billing** — the per-`Event` `UsageMeter` and the terminal
  `TokenLedger` ride the stream; folding them into `UsageRecord`/FinOps (S9) and `TokenBudget`
  enforcement (02 §2, 04 §6) is the engine's job over `observability.Ledger` (T6). This port emits;
  it does not bill.

It cites, never redefines: `Run` / `Transcript` / `AssistantSession` / `Workspace` (02 §1–2),
`Secret` / `Reference` (07 §2, secrets.md), the observability `Event` and T6 `Ledger`
(observability.md), and the `agents.yaml` projection (`agentconfiguration`, 02 §5).

## 2. Contract

```go
// Package agentsession is the Eden F4 session port: the agent abstraction layer
// (C22, ADR-0008). It turns a harness process — headless claude, omp --mode rpc,
// codex later — into ONE controllable, instrumented, resumable Eden session: one
// agent loop, one sandbox (07 §3), one Workspace (02 §1). It normalizes a
// harness-native stream (Claude stream-json / OMP RPC frames) into a monotonic
// Event sequence (the instrumentation contract), exposes turn-taking + steer +
// abort, a human/policy permission round-trip, and from-seq replay for
// multi-client reconnect. The engine's batch execute(spec, context, tools, schema)
// (05 §2) is a thin fold over this primitive — no mode fork in the type.
//
// It does NOT own: pod/workspace provisioning (S2 over workspaceprovider, 02 §1 —
// Close never tears down a pod); isolation mechanism (assumed per 07 §3, never
// implemented here); credential storage/minting (secrets port + vault, 07 §2 —
// this carries an opaque Reference and resolves it server-side at Open);
// transcript persistence/retention (it produces the sequence; persistence is the
// transcript/observability seam); UI; or UsageRecord/billing.
//
// Module: github.com/gophersys/libs/go/agentsession  (go 1.26)
//
// The library owns the Event vocabulary, the Session contract, the lifecycle state
// machine, Seq ordering, grant→audit linkage, and credential-injection shape; an
// Adapter (claudeadapter, ompadapter, codexadapter) implements only the lower
// Harness seam (the only place a vendor harness is spawned or its wire format
// parsed, 05 §1). A declared CapabilityManifest capability that fails the
// conformance suite blocks adapter release (05 §3/§6).
//
// Concurrency: a Session is safe for concurrent use. Events(ctx, from) may be
// called concurrently by MANY consumers (multi-client fan-out); each is an
// independent, seq-ordered, gap-free view. Control verbs (Prompt/Steer/Abort) and
// Resolve may be called concurrently with reading and are serialized internally
// onto the harness transport. Close is idempotent.
package agentsession

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/secrets"
)

// ── Lifecycle: states ────────────────────────────────────────────────────────

// State is the session lifecycle (grounded in poc/agents state.go, generalized).
// Closed taxonomy, additive-only (10 §9). The legal transitions are enforced by
// the library, not the adapter: Initializing→Ready→{Running↔AwaitingInput |
// AwaitingPermission}→{Completed | Failed | Aborted}. A terminal state
// (Completed/Failed/Aborted) never transitions. The State rides the stream as the
// SessionState event payload (the chat's connection/idle/working/terminal chrome).
type State uint8

const (
	StateInitializing      State = iota // process spawning + auth handshake not yet confirmed
	StateReady                          // harness handshake confirmed (init/ready event seen); accepts the first Prompt
	StateRunning                        // a turn is in flight (model thinking / tools running)
	StateAwaitingInput                  // turn complete, awaiting the next Prompt (interactive) or done (batch)
	StateAwaitingPermission             // blocked on an out-of-grant request; awaiting Resolve (§2 permission round-trip)
	StateCompleted                      // graceful terminal: a turn reached a clean result; ledger finalized, process reaped
	StateFailed                         // terminal: spawn/auth/transport failure or unrecoverable harness error
	StateAborted                        // terminal: an Abort took the session to a stop
)

// ── The Session port + its Stream ────────────────────────────────────────────

// Session is the controllable, instrumented agent session — the single port a
// consumer holds, obtained from Factory.Open. Exactly 4 methods (the 10 §9
// ceiling, well under it). Both the chat (live render) and the engine (fold to
// evidence) drive exactly these. Its zero value is unusable.
type Session interface {
	// Events returns the normalized event stream from the given cursor. FromSeq(0)
	// replays the whole session from the durable transcript, then attaches to the
	// live tail with no gap and no dup (transcript replay on reload, for free). A
	// reconnecting consumer passes its last-seen Seq+1. MULTIPLE concurrent calls
	// are MULTIPLE viewers of one session (fan-out: the chat tab, a second browser,
	// the dashboard observer) — all see identical Seq-ordered events. Closing ctx
	// drops THIS subscriber only; it neither stalls other viewers nor the agent
	// (backpressure: §2 "Resumability & fan-out").
	Events(ctx context.Context, from Cursor) Stream

	// Control issues a turn-taking command. Prompt is valid only when
	// Ready/AwaitingInput (in batch, called once with the spec task; in chat, once
	// per message); Steer interjects guidance into a Running turn without aborting
	// it (the "course-correct mid-run" affordance — degrades per CapSteer); Abort
	// cancels the in-flight turn and is valid until terminal. It returns the Seq the
	// control was ADMITTED at (so a UI correlates the resulting events) — NOT the
	// agent's reply, which streams back on Events. Returns a wrapped StateError
	// (errors.AsType) if out of phase, or UnsupportedError if the adapter declares
	// the verb's Capability absent.
	Control(ctx context.Context, command Command) (Ack, error)

	// Resolve answers a pending PermissionRequest (the agent asked to use a
	// capability outside its standing Grants). The DECIDER is the caller: a human
	// click (chat A5) or a policy function (engine). Idempotent on RequestID; first
	// decision wins under multi-client races (UnknownPermissionError if already
	// resolved/expired). Returns the Seq of the resulting PermissionResolved event.
	// When Spec.OnPermission is set, the library calls it and the consumer never
	// calls Resolve directly; when it is nil, requests surface as events for an
	// out-of-band Resolve (the chat's asynchronous human round-trip).
	Resolve(ctx context.Context, requestID string, decision Decision) (Ack, error)

	// Close releases the session handle: stop accepting input, signal the harness to
	// stop, drain the in-flight turn (bounded by ctx), emit the terminal Event, then
	// reap the process (the poc/agents abort→close-stdin→wait→kill graceful ladder).
	// It does NOT tear down the pod (that is workspaceprovider's job, 02 §1).
	// Idempotent. After Close, every live Events tail drains and closes.
	Close(ctx context.Context) error
}

// Stream is a one-shot, ordered, gap-free, dup-free event view for ONE consumer.
// The engine ranges over a channel adapter (Chan); the SSE route awaits each event
// (Next) — both are ergonomic faces of the same pull-based stream.
type Stream interface {
	// Next blocks for the next event; ok=false at end-of-stream (terminal reached,
	// ctx cancelled, or fault). Events arrive strictly Seq-ordered with no holes
	// from `from`. Pull-based: the consumer's read rate IS the backpressure (a slow
	// chat tab slows its own read; it does not stall other viewers or the agent).
	Next(ctx context.Context) (Event, bool)

	// Err reports a fault that ended the stream early (pod death mid-run, decode
	// fault). nil at a clean terminal end. The engine treats non-nil as a failed
	// phase; the chat shows a banner and may reconnect from its last Seq.
	Err() error
}

// Cursor is the resume position: FromSeq(0) is full replay from the start of the
// session; FromSeq(n) reads [n+1 .. head] from the durable transcript then tails.
type Cursor uint64

// FromSeq constructs a Cursor at the given sequence number.
func FromSeq(seq uint64) Cursor { return Cursor(seq) }

// Command is one turn-taking control (the normalized form sent to the adapter).
type Command struct {
	Kind CommandKind
	Text string // Prompt/Steer message; empty for Abort
}

type CommandKind uint8

const (
	CommandPrompt CommandKind = iota // start a turn (valid when Ready/AwaitingInput)
	CommandSteer                     // interject into a running turn (CapSteer)
	CommandAbort                     // cancel the in-flight turn (always valid until terminal)
)

// Decision answers a PermissionRequest. The decider is the caller (human or
// policy); the By stamp is the audit identity (07 §7): a user id or "policy:<name>".
type Decision struct {
	Allow    bool
	Remember bool   // widens the standing grant for THIS session only — never persisted to the
	                // credential profile (that is a governed act, not a chat click); scope is the
	                // exact tool+pattern the agent asked for ("allow Bash(go test ./...)", not "allow Bash")
	By       string // identity stamp for audit
}

// Ack is the sequence number a control/resolve was admitted at, so a UI can
// correlate the resulting events when they arrive on the stream.
type Ack struct{ Seq uint64 }

// ── The Event stream: the instrumentation contract & EVENT TAXONOMY ──────────

// EventKind is the NORMALIZED taxonomy every harness maps onto (the EVENT TAXONOMY
// table below). It is the stable, closed, additive-only (10 §9) classification the
// engine and chat surface branch on WITHOUT parsing harness-native strings.
// Grounded in the union of the OMP AgentEventType set (poc/agents types.go) and the
// Claude stream-json types (poc/codingharness ledger.go) — the two maximally-
// different harnesses ADR-0008 requires the contract be authored against from day 1.
type EventKind uint8

const (
	EventSessionState       EventKind = iota // a State transition (the connection/idle/working/terminal chrome)
	EventMessageStart                        // an assistant message began (Role, turn)
	EventThinkingDelta                       // a reasoning/thinking fragment (separately classified so the UI can fold it; redaction-eligible)
	EventTextDelta                           // a streamed assistant text fragment (token-by-token render)
	EventMessageEnd                          // the assistant message completed
	EventToolStart                           // a tool invocation began: name, args summary, the GRANT under which it ran
	EventToolUpdate                          // a tool's partial/streamed result (OMP partial-result streaming)
	EventToolEnd                             // a tool invocation finished: outcome, duration, (redacted) result digest
	EventPermissionRequest                   // the harness wants a tool OUTSIDE the standing grant — the human/policy gate
	EventPermissionResolved                  // the request was decided (Allow/Deny + By) — the audit + UI-notification record
	EventUsage                               // a token-usage + cost tick (UsageMeter) with model attribution — ALL FOUR token kinds
	EventResult                              // TERMINAL: a turn reached a clean result; carries the authoritative TokenLedger
	EventFailed                              // TERMINAL: an error moved the session to StateFailed; carries the ledger + typed reason
	EventAborted                             // TERMINAL: an Abort took the session to a stop; carries the ledger + By
	EventExtension                           // a harness event with no normalized kind — preserved VERBATIM, NEVER dropped (forward-compat)
)

// Event is one immutable, ordered record on the stream — a plain value (copyable,
// zero-safe). SessionID + TurnID + Seq give total ordering and correlation; Kind is
// the stable axis; exactly one typed Payload pointer is populated per Kind (a tagged
// union by convention; nil otherwise); Extension carries the opaque per-harness
// remainder so a harness that emits richer data than Eden normalizes loses NOTHING
// (the rate_limit_event lesson from poc/codingharness — unknown types must survive).
type Event struct {
	SessionID string
	TurnID    string
	Seq       uint64    // monotonic per session; assigned at durable transcript append (Seq == transcript offset)
	Turn      int       // turn ordinal (batch: 0; chat: increments per message)
	Time      time.Time // adapter-stamped at emit (the harness clock); zero == library stamps via injected Clock
	Kind      EventKind

	// Exactly one is populated per Kind (nil otherwise). Pointers so a zero Event is
	// valid and an unknown Kind (Extension) carries no normalized payload.
	State      *StatePayload      // EventSessionState
	Message    *MessagePayload    // EventMessageStart/ThinkingDelta/TextDelta/MessageEnd
	Tool       *ToolPayload       // EventToolStart/ToolUpdate/ToolEnd
	Permission *PermissionPayload // EventPermissionRequest/PermissionResolved
	Usage      *UsageMeter        // EventUsage (the running prefix of the terminal ledger)
	Terminal   *TerminalPayload   // EventResult/Failed/Aborted (carries the authoritative TokenLedger)

	// Extension is the opaque escape hatch: the raw harness frame (or the part Eden
	// did not normalize) as bytes. ALWAYS present for EventExtension; MAY ride
	// alongside any normalized Kind to carry harness-specific extras. The transcript
	// stores it verbatim; the engine's LedgerFold counts unknown kinds but never
	// fails on them; the UI ignores what it doesn't understand. Redaction-eligible.
	Extension []byte
}

// Terminal reports whether this Event ends the session (exactly one terminal event
// per session: Result, Failed, or Aborted).
func (e Event) Terminal() bool {
	return e.Kind == EventResult || e.Kind == EventFailed || e.Kind == EventAborted
}

type StatePayload struct {
	From, To State
}

// MessagePayload carries a streamed assistant fragment or a thinking fragment.
// Delta is the INCREMENTAL text (not the cumulative message). Thinking is its own
// Kind so the UI can fold it and retention/redaction can treat reasoning distinctly.
type MessagePayload struct {
	Role  string // "assistant" | "system"
	Delta string // the incremental fragment
}

// ToolPayload carries a tool invocation's start (EventToolStart), partial
// (EventToolUpdate), or end (EventToolEnd). GrantID ties the call back to the
// allowlist entry that permitted it — the audit chain 07 §3 requires ("tool grants
// recorded per Run"). Args/result summaries are redacted, bounded — never raw
// secret-bearing data (the full result rides the redacted transcript, not the digest).
type ToolPayload struct {
	CallID       string        // correlates Start↔Update↔End
	Name         string        // tool name, e.g. "Write", "Bash", a host-tool name
	GrantID      string        // the ToolGrant that authorized this call (audit linkage)
	ArgsSummary  string        // EventToolStart: redacted, bounded summary of arguments
	PartialDigest string       // EventToolUpdate: redacted, bounded streamed fragment
	Outcome      ToolOutcome   // EventToolEnd only
	ResultDigest string        // EventToolEnd only: redacted, bounded result summary
	Duration     time.Duration // EventToolEnd only
	IsHostTool   bool          // true when this is an Eden-provided host tool (callback), not a harness-native tool
}

type ToolOutcome uint8

const (
	ToolOutcomeOK ToolOutcome = iota
	ToolOutcomeError
	ToolOutcomeDenied // the permission gate rejected it
)

// PermissionPayload is the permission round-trip record: EventPermissionRequest
// when the harness wants a capability OUTSIDE the standing grant (the Claude-app
// "allow this tool?" surface; OMP's host_tool_call gate), and EventPermissionResolved
// when it is decided. The request BLOCKS the harness (StateAwaitingPermission) until
// resolved; the decision is supplied either by Spec.OnPermission (policy, synchronous)
// or by an out-of-band Session.Resolve (human, asynchronous across HTTP requests).
type PermissionPayload struct {
	RequestID string
	Tool      string
	Reason    string        // why the harness wants it
	Decision  GrantDecision // EventPermissionResolved: what was decided
	By        string        // EventPermissionResolved: the deciding identity (user id or "policy:<name>")
}

type GrantDecision uint8

const (
	GrantPending GrantDecision = iota // awaiting policy/human (the request, pre-resolution)
	GrantAllowed
	GrantDenied
)

// UsageMeter is a token-usage + cost tick with model attribution — the live meter
// (per EventUsage) AND the running prefix of the terminal TokenLedger. It carries
// ALL FOUR token kinds confirmed present in BOTH harnesses (poc/codingharness
// ledger.go Usage; poc/agents TokenUsage): input, output, cache-read,
// cache-creation/write — cache economics dominate real agent-loop cost, so
// collapsing them makes FinOps (S9) and the ADR-0008 routing comparison wrong. Cost
// is integer micro-units (no float drift across millions of calls — aligned with
// observability.Ledger.CostMicros). Model + Harness attribute the spend so routing
// economics (ADR-0008) are MEASURED, not argued.
type UsageMeter struct {
	Model               string // the model that produced this tick, e.g. "claude-fable-5", "deepseek-v4-flash"
	Harness             string // "claude-code" | "omp" | "codex"
	InputTokens         int64
	OutputTokens        int64
	CacheReadTokens     int64 // cache-hit input tokens (cheap)
	CacheCreationTokens int64 // cache-write input tokens (the 4th kind — distinct cost)
	CostMicros          int64 // provider spend, micro-units of account currency; -1 == harness did not report cost
	Cumulative          bool  // true == session-to-date totals (Claude result event); false == this-turn delta
}

// TerminalPayload bounds the session: exactly one terminal Event carries it. It
// carries the AUTHORITATIVE TokenLedger (the poc/codingharness total_cost_usd ground
// truth) so the engine's evidence envelope and the chat's final meter reconcile.
type TerminalPayload struct {
	Outcome    TurnOutcome
	Ledger     TokenLedger
	ResultText string      // EventResult: the final assistant text (batch: the artifact-adjacent result)
	StopReason string      // harness stop reason, surfaced verbatim for diagnostics
	Reason     ErrorReason // EventFailed: the branchable classification
	Detail     string      // EventFailed: a redacted message; never a credential
	By         string      // EventAborted: who aborted (user id or "policy:<name>")
}

type TurnOutcome uint8

const (
	TurnCompleted TurnOutcome = iota
	TurnAborted
	TurnFailed
	TurnMaxTurns
	TurnBudgetExceeded // the TokenBudget cost-aware abort (02 §2) — a distinct outcome the chat meter shows as "stopped: budget"
)

// TokenLedger is the authoritative aggregate on a terminal Event — the UsageMeter
// fields plus the run-shaped correlation/accounting the engine folds into the
// Run's evidence and the FinOps UsageRecord. It is the poc/codingharness ledger,
// verbatim-shaped, promoted into the library (the LedgerFold the engine uses).
type TokenLedger struct {
	UsageMeter                          // the four token kinds + cost + model/harness attribution (cumulative)
	Turns         int32
	ToolUses      int32
	WallTime      time.Duration
	ToolUsesByName map[string]int32 // per-tool counts, for the routing/cost breakdown
}

// ErrorReason is the stable, branchable error classification (the engine retries on
// ReasonRateLimit, aborts on ReasonAuth). Closed, additive-only (10 §9).
type ErrorReason uint8

const (
	ReasonUnknown      ErrorReason = iota
	ReasonAuth                     // bad/expired token (07 §2 path) — INCLUDES the silent-bad-token trap (§6)
	ReasonRateLimit                // provider throttling (the rate_limit_event lesson)
	ReasonBudget                   // TokenBudget ceiling hit (02 §2, 04 §6)
	ReasonMaxTurns                 // harness turn cap reached
	ReasonTransport                // stdio/RPC framing or process death
	ReasonHarnessError             // an error the harness reported about its own loop
)

// ── The constructor spine (10 §4) — PURE ─────────────────────────────────────

// Factory opens sessions. It is the port the engine/chat-backend holds; New returns
// the concrete *Pool (return-concrete, accept-interface). Open binds a harness
// Adapter (selected by Spec.Routing) to a workspace and returns a live Session. The
// Factory does NOT provision the workspace (that arrived via S2); it spawns the
// harness process inside it.
type Factory interface {
	// Open binds the credential (resolves the opaque Reference server-side, mints a
	// scoped token), invokes the harness in the already-provisioned pod, and returns
	// a live Session at Seq 0 once the handshake is confirmed (StateReady) — or an
	// error. ResumeFrom, when non-empty, re-attaches an existing harness session
	// instead of spawning fresh. Errors: AuthError (no usable credential — the
	// silent-bad-token trap is converted to this, not trusted as success — the
	// setup-token precondition, C22); SpawnError (binary missing / pod not ready);
	// wrapped %w cause otherwise.
	Open(ctx context.Context, spec Spec) (Session, error)
}

// Spec is the immutable, fully-resolved input for ONE session (the configuration
// pattern: parsed at the edge, frozen). It holds NO live handles and NO secret
// values — only a loggable secrets.Reference.
type Spec struct {
	Workspace    string            // the already-provisioned workspace dir (S2 owns its lifecycle); the harness CWD (02 §1)
	Routing      RouteKey          // selects harness+model via agentconfiguration (§2.7); routable per phase
	Grants       []ToolGrant       // the allowlist AS DATA — standing capability the session launches with (07 §3)
	HostTools    []HostTool        // Eden-provided callback tools (read-scoped project-data tools for AssistantSession)
	Credential   secrets.Reference // OPAQUE; resolved server-side at Open, injected per the credential-flow diagram — never the value
	Budget       Budget            // soft ceilings surfaced to the harness + hard ceilings the engine enforces by Abort
	ResumeFrom   string            // harness-native session id to re-attach (empty == fresh)
	SystemHints  string            // optional system-prompt augmentation (hermetic-context seam; never a secret)

	// OnPermission is the policy decider for out-of-grant requests (the engine's
	// clean-room auto-resolver). When non-nil it is called synchronously and the
	// consumer never calls Session.Resolve. When NIL (the chat), requests surface as
	// EventPermissionRequest events for an out-of-band human Resolve. nil with no
	// Resolve ever arriving leaves the request pending until ctx/Close — so a batch
	// session MUST set it. Default-deny is the safe policy (a deny ends the turn with
	// a recorded denial in the transcript — evidence of what was refused).
	OnPermission func(PermissionRequest) Decision
}

// PermissionRequest is the policy decider's input (a non-pointer projection of
// PermissionPayload's request side, so OnPermission has no stream dependency).
type PermissionRequest struct {
	RequestID string
	Tool      string
	Input     []byte // the args the harness wants to run with (redaction is the adapter's job before this)
	Reason    string
}

// RouteKey is the opaque key agentconfiguration resolves to a concrete (harness,
// model) pair per phase/role (§2.7, 02 §5 agents.yaml). The session port does NOT
// decide which harness/model — it is told. This is C22's "right agent for the right
// phase" selector, kept out of this contract's policy.
type RouteKey struct {
	Phase string // "product-design", "implement", "review", ... | "" for interactive
	Role  string // "assistant" | "implementer" | "reviewer" | ...
}

// ToolGrant is one allowlist entry AS DATA (not code): a capability the session may
// exercise without a permission prompt. Pattern mirrors Claude --allowedTools
// ("Write", "Bash(go *)") and OMP SyncTools. The engine derives the egress endpoints
// a granted tool needs (§6) from the grant set.
type ToolGrant struct {
	ID       string   // stable id for audit linkage (ToolPayload.GrantID)
	Tool     string   // tool name, e.g. "Write", "Read", "Bash"
	Scopes   []string // sub-scoping, e.g. ["go *", "ls *"] for Bash; nil == whole tool
	ReadOnly bool     // marks a read-scoped grant (AssistantSession: project-data tools, NO write paths — 07 §3)
}

// HostTool is an Eden-provided tool the agent calls BACK into (the OMP host-tool
// channel: host_tool_call → handler → host_tool_result, with partial-result
// streaming surfaced as EventToolUpdate). For AssistantSession these are the
// read-scoped project-data tools (runs, dashboards, FinOps, drift events — 02 §1)
// with NO write paths and NO credential access (07 §3). The handler runs in-process,
// server-side.
type HostTool struct {
	Name        string
	Description string
	Schema      []byte // JSON-schema of parameters (opaque to this lib; passed to the harness)
	Handler     func(ctx context.Context, args []byte) (result []byte, err error)
}

// Budget carries the soft ceilings surfaced to the harness AND the hard ceilings the
// engine enforces by aborting. The harness-native cap (Claude --max-budget-usd) is
// best-effort; the AUTHORITATIVE enforcement is the engine watching EventUsage
// against TokenBudget (02 §2) and calling Abort/Close — the harness cap is a
// courtesy, not the guarantee, and there is exactly ONE budget authority (the engine).
type Budget struct {
	MaxCostMicros int64         // 0 == unbounded here (engine still enforces TokenBudget)
	MaxTurns      int32         // 0 == harness default
	MaxWall       time.Duration // 0 == ctx bounds it
}

// Config is the immutable spine input for the Factory. It holds the routing table;
// it reads NO env, NO clock, NO secret (10 §4).
type Config struct {
	// Routing is the resolved agentconfiguration projection: RouteKey → Route. Built
	// at the edge by the agentconfiguration library (02 §5); frozen here.
	Routing map[RouteKey]Route
}

// Route is a resolved (harness, model) binding for a RouteKey.
type Route struct {
	Harness string // adapter key: "claude-code" | "omp" | "codex"
	Model   string // model id passed to the harness
}

// Deps is the injected hexagon. New constructs no ports.
type Deps struct {
	// Adapters maps a harness key to its Adapter (the lower Harness seam). At least
	// one is required. The claude-code adapter is the v1 entry (ADR-0008); omp is the
	// committed second (proves the abstraction with a maximally-different harness).
	Adapters map[string]Adapter

	// Secrets resolves the opaque Credential reference to a short-lived Secret at
	// OPEN time, server-side, so the value reaches the harness process per the
	// credential-flow diagram and NEVER enters this library's logs, the Spec, or any
	// Event (07 §2).
	Secrets secrets.Provider

	// Transcript is the durable replay log Seq is assigned against (Seq == transcript
	// offset) and from which FromSeq(n) replays. The library APPENDS to it and reads
	// it for replay; retention/redaction policy lives behind this seam (07 §2).
	Transcript Transcript

	// Clock stamps Event.Time when an adapter supplies none; keeps New pure and the
	// fake deterministic (mirrors observability.Clock).
	Clock Clock
}

// Transcript is the durable, append-only replay log seam (the 02 §2 / P9 object,
// behind a port so persistence/retention is the consumer's concern, not this
// library's). The library assigns Seq at Append and replays via ReadFrom.
type Transcript interface {
	// Append durably stores one Event and returns the Seq it was assigned (the
	// transcript offset). Called once per Event before fan-out, so every viewer sees
	// identical Seq numbers.
	Append(ctx context.Context, event Event) (seq uint64, err error)

	// ReadFrom returns the stored events [from+1 .. head] for replay — available
	// AFTER a session terminates too (reload an old Run's chat), so replay reads the
	// stored transcript, not a live ring buffer.
	ReadFrom(ctx context.Context, sessionID string, from Cursor) (Stream, error)
}

type Clock interface{ Now() time.Time }

// New is the pure constructor spine: no I/O, no clock read, no env read, no process
// spawn. It validates Config + Deps and returns the concrete *Pool. The first
// process spawn happens only at Pool.Open.
func New(configuration Config, dependencies Deps) (*Pool, error) { return nil, nil }

// Pool is the concrete Factory returned by New: it routes each Open to the Adapter
// named by the resolved Route, manages spawned sessions, assigns Seq against the
// Transcript, fans out to viewers, and reaps sessions on Close. Safe for concurrent
// use. Zero value unusable.
type Pool struct{ /* unexported */ }

func (p *Pool) Open(ctx context.Context, spec Spec) (Session, error) { return nil, nil }

// ── The lower seam: Adapter (the ONLY place a harness CLI/SDK is invoked) ─────

// Adapter is the per-harness implementation seam — the only place a vendor harness
// is spawned or its wire format parsed (05 §1). It is THIN: the library owns the
// lifecycle state machine, Seq ordering, grant→audit linkage, budget watching,
// fan-out, and credential-injection shape; the adapter owns ONLY (a) spawning the
// process and (b) translating its native frames ↔ the normalized Event/Control
// vocabulary.
type Adapter interface {
	// Spawn launches the harness process in spec.Workspace with the resolved Route,
	// the credential already injected (the library called Secrets.Resolve and hands
	// the adapter an InjectedCredential — the adapter places it where its harness
	// reads it: an env var, an apiKeyHelper, a configuration file in a tmpfs). It returns a
	// HarnessConn — the bidirectional, normalized stream + control sink.
	Spawn(ctx context.Context, spec Spec, route Route, cred InjectedCredential) (HarnessConn, error)

	// Manifest declares which optional capabilities this adapter implements. The
	// library degrades gracefully (05 §3) and the conformance suite verifies the
	// manifest is truthful (a declared capability that fails its suite blocks release,
	// 05 §6).
	Manifest() CapabilityManifest
}

// HarnessConn is the adapter's normalized connection: it EMITS normalized Events
// (already mapping native → Event) and ACCEPTS normalized Control. The library wraps
// it as the Session, adding the state machine, Seq, transcript append, fan-out,
// grant linkage, and budget watching. Exactly 3 methods.
type HarnessConn interface {
	Events() <-chan Event                      // already-normalized; pre-Seq, pre-fan-out (the library stamps Seq)
	Send(ctx context.Context, c Command) error // Prompt/Steer/Abort as a normalized control frame
	Close(ctx context.Context) error           // the graceful abort→stdin-close→wait→kill ladder
}

// InjectedCredential is the resolved-but-still-protected credential handed to the
// adapter at Spawn. The Secret is resolved server-side from the opaque Reference and
// is un-printable (secrets.Secret); the adapter is told HOW its harness wants it
// (EnvName, or a HelperScript path) and uses Secret.Use to place it — the value
// never enters the Spec, an Event, a log, or an image layer (the credential-flow
// diagram below).
type InjectedCredential struct {
	Secret  *secrets.Secret // un-printable; the adapter calls .Use(fn) at the injection site only
	Vehicle CredentialVehicle
	EnvName string // for VehicleEnv: e.g. "CLAUDE_CODE_OAUTH_TOKEN"
}

type CredentialVehicle uint8

const (
	VehicleEnv    CredentialVehicle = iota // env var on the CHILD process ONLY (not Eden's env), scrubbed of higher-precedence keys
	VehicleHelper                          // apiKeyHelper script that fetches a short-lived token on demand (the 07 §2 ideal)
)

// CapabilityManifest is the adapter's declaration (05 §3). DATA, not code.
type CapabilityManifest struct {
	Capabilities map[Capability]CapStatus
}

type Capability uint8

const (
	CapSteer            Capability = iota // mid-turn steering (Claude Code SDK streaming-input vs OMP SteeringMode vs codex none)
	CapResume                             // re-attach by harness-native session id (Claude --resume; omp session dir)
	CapThinkingEvents                     // emits separate thinking deltas
	CapHostTools                          // supports the host-tool callback channel
	CapNativeBudget                       // honors a harness-native budget cap (Claude --max-budget-usd)
	CapPermissionPrompt                   // supports the out-of-grant permission round-trip
	CapPartialToolResults                 // streams EventToolUpdate (OMP partial results)
)

type CapStatus uint8

const (
	CapAbsent  CapStatus = iota // feature gated off in the UI, not broken (05 §3)
	CapPartial                  // e.g. Steer "queue for next turn" rather than true mid-turn
	CapFull
)

// ── Errors (typed, errors.AsType-first, aligned with errors.md) ──────────────

type (
	// UnsupportedError is returned by a control verb whose Capability the adapter
	// declares absent (Steer/Resume on a harness that cannot). The UI consulted the
	// manifest first; this is the belt-and-suspenders runtime guard.
	UnsupportedError struct{ Cap Capability }
	// SpawnError reports a failed process launch (binary missing, workspace gone, pod
	// not ready).
	SpawnError struct{ Harness string }
	// AuthError reports a credential failure AT OPEN — including the silent-bad-token
	// trap (§6): the library requires an init/ready event and converts its ABSENCE
	// into an AuthError rather than trusting the harness exit code. It is the
	// Unauthenticated outcome the chat renders as the setup-token card (C22).
	AuthError struct{ Reference secrets.Reference } // carries the ref, NEVER the value
	// StateError reports a control verb called in an illegal State (e.g. Prompt while
	// Running, Abort on a terminal session).
	StateError struct {
		From State
		Op   string
	}
	// UnknownPermissionError reports a Resolve for a RequestID that is already
	// resolved, expired, or never existed (multi-client races resolve to "first
	// decision wins").
	UnknownPermissionError struct{ RequestID string }
)

func (e UnsupportedError) Error() string       { return "" }
func (e SpawnError) Error() string             { return "" }
func (e AuthError) Error() string              { return "" }
func (e StateError) Error() string             { return "" }
func (e UnknownPermissionError) Error() string { return "" }
```

### EVENT TAXONOMY (the instrumentation contract Mateo asked for, C22)

The normalized `EventKind` set every harness maps onto — the **union normalized** from the two
maximally-different harnesses ADR-0008 names (OMP's `agent/turn/message/tool/permission/...` and
Claude's `system/assistant/user/result/rate_limit_event`). The engine and chat surface branch on
this axis without parsing harness-native strings; `EventExtension` + the per-event `Extension []byte`
carry anything Eden has not normalized **losslessly to the transcript** (the `rate_limit_event`
surprise, measured in `poc/codingharness`, proves harnesses emit types Eden hasn't normalized).

| Event kind | Payload fields | Emitted when | claude-code | omp | codex |
|---|---|---|---|---|---|
| `EventSessionState` | `StatePayload{From, To}` | a lifecycle `State` transition (init→ready→running→…→terminal) | full | full | full |
| `EventMessageStart` | `MessagePayload{Role}` + `Turn` | an assistant message begins | full | full | full |
| `EventThinkingDelta` | `MessagePayload{Delta}` (redaction-eligible) | a reasoning/thinking fragment (foldable; treated distinctly by retention) | full (CapThinkingEvents) | full | partial |
| `EventTextDelta` | `MessagePayload{Delta}` | a streamed assistant text fragment (token-by-token render) | full | full | full |
| `EventMessageEnd` | — (`Turn`) | the assistant message completes | full | full | full |
| `EventToolStart` | `ToolPayload{CallID, Name, GrantID, ArgsSummary, IsHostTool}` | a tool invocation begins | full | full | full |
| `EventToolUpdate` | `ToolPayload{CallID, PartialDigest}` | a tool's partial/streamed result | absent | full (CapPartialToolResults) | absent |
| `EventToolEnd` | `ToolPayload{CallID, Outcome, ResultDigest, Duration}` | a tool invocation finishes | full | full | full |
| `EventPermissionRequest` | `PermissionPayload{RequestID, Tool, Reason}` | the harness wants a tool OUTSIDE the standing grant | full (CapPermissionPrompt) | full | partial |
| `EventPermissionResolved` | `PermissionPayload{RequestID, Decision, By}` | the request was decided (human or policy) | full | full | partial |
| `EventUsage` | `UsageMeter{Model, Harness, 4×tokens, CostMicros, Cumulative}` | a token-usage + cost tick | full (cumulative on `result`) | full (per-tick) | partial |
| `EventResult` | `TerminalPayload{Outcome:Completed, Ledger, ResultText, StopReason}` | TERMINAL: a turn reached a clean result | full | full | full |
| `EventFailed` | `TerminalPayload{Outcome:Failed, Ledger, Reason, Detail}` | TERMINAL: an unrecoverable harness/auth/transport error | full | full | full |
| `EventAborted` | `TerminalPayload{Outcome:Aborted, Ledger, By}` | TERMINAL: an `Abort` stopped the session | full | full | full |
| `EventExtension` | — (`Extension []byte` only) | a harness frame with no normalized kind — preserved VERBATIM, NEVER dropped | full | full | full |

### Credential flow (the seam, designed honestly — 07 §2)

The `Spec` carries an **opaque `secrets.Reference`** — loggable, value-less. The value never enters
the `Spec`, an `Event`, a log, or an image layer; it crosses into the child harness process **only**
at the injection site, confined by `Secret.Use(fn)`. `VehicleEnv` places the value on the *child*
process environment only — never Eden's env — and the adapter **scrubs higher-precedence keys**
(`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`) first, or a stray key silently wins (the precedence
trap, verified in the spike). `VehicleHelper` is the **07 §2 ideal**: an `apiKeyHelper` script the
harness calls on a 401, fetching a *short-lived* token from the vault per use, over the year-long
static `setup-token`.

```
 setup-token (once, server-side, C22)
        │  produces an OAuth/setup token stored in the vault as a secrets.Secret (07 §2, un-printable)
        ▼
 vault ──── bound as ──▶ secrets.Reference  ──(loggable; lives in the Spec & configuration)──┐
        ▲                                                                                    │
        │                                                                                    ▼
        │  Factory.Open: Deps.Secrets.Resolve(ref) ── server-side ──▶ *secrets.Secret ──▶ InjectedCredential
        │  (mints/fetches the short-lived scoped token; AuthError on failure — carries the ref, never the value)
        │                                                                                    │
        │                                                                                    ▼
        │   Adapter.Spawn(..., cred): Secret.Use(fn) at the injection site ──▶ child harness pod
        └──── VehicleHelper: apiKeyHelper fetches a fresh short-lived token from the vault per 401 ◀──┘
              VehicleEnv: child-process env ONLY (CLAUDE_CODE_OAUTH_TOKEN), higher-precedence keys scrubbed

 Never crosses this boundary: the raw value in the Spec / any Event / a log / a transcript / an image layer.
```

### Resumability & fan-out (the semantics the producer must guarantee)

- **Sequence numbers.** Per-session monotonic `uint64`, assigned at the point the event is durably
  appended to the `Transcript` (the replay log), so **`Seq == transcript offset`** — no separate
  counter to drift. The library assigns `Seq` before fan-out, so every viewer sees identical
  numbers. This is the one fact that makes `Last-Event-ID` reconnect, fresh-tab replay, and the
  engine's `FromSeq(0)` fold the *same* mechanism.
- **Replay then tail.** `Events(ctx, FromSeq(n))` reads `[n+1 .. head]` from the durable transcript,
  then attaches to the live tail with no gap and no dup at the seam (a small in-flight buffer bridges
  "last durable" → "now live"). A fresh tab (`FromSeq(0)`) gets the full transcript replay for free.
  Replay is available **after** a session terminates too (reload an old Run's chat) — `ReadFrom`
  reads the stored transcript, not a live ring buffer.
- **Backpressure.** The `Stream` is **pull-based** end to end. A slow consumer slows *its own* read;
  it must NOT stall the agent or other viewers. The donor `poc/agents` RPC `Subscribe` *drops* frames
  for a slow subscriber — **wrong for us**, because a dropped event breaks gap-free replay. Resolution
  (the §7 Q1 ruling): a live-tail subscriber that overflows its in-flight buffer is **converted to a
  `FromSeq` replay reader** off the durable transcript (catch up by re-reading, never by skipping).
- **Multi-client / fan-out.** N concurrent `Events` calls on one Session = N viewers (chat tab,
  second tab, dashboard observer). All see the same `Seq`-ordered stream. Any viewer may
  `Control`/`Resolve` (subject to its grant — a read-scoped `AssistantSession` viewer cannot
  prompt/resolve; 07 §3), and the effect appears as new events on *every* viewer's stream.
  First-decision-wins for permission races (`UnknownPermissionError` for the losers).

## 3. Fake

```go
// Package agentsessiontest is the canonical public fake (the testing pattern,
// 10 §4 / 08 §2). It is a SCRIPTED harness Adapter: a test feeds it a sequence of
// Events to emit and asserts over the Commands it received, so the kernel (engine,
// chat backend) tests lifecycle, ordering, Seq-replay, grant-linkage, budget-abort,
// the permission round-trip, and the credential seam WITHOUT spawning a real
// claude/omp process. An in-memory Transcript is provided so Seq/replay are real.
package agentsessiontest

import (
	"context"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
)

// Adapter is a scripted agentsession.Adapter. Script is the Event sequence the next
// Spawned session will emit (in order); Received records every Command the SUT sent.
// It honors the lifecycle state machine so a test exercises real ordering, not a
// degenerate stub.
type Adapter struct {
	Script      []agentsession.Event
	Capabilities agentsession.CapabilityManifest // configurable, to test graceful degradation
	// Received is appended on every Command the SUT sends (Prompt/Steer/Abort).
	Received []agentsession.Command
	// InjectedRefs records which secrets.Reference each Spawn was asked to inject —
	// refs ONLY, never values — for "was the credential injected, and never the value
	// leaked?" assertions (the credential-flow guarantee, runnable).
	InjectedRefs []secrets.Reference
}

func New(script ...agentsession.Event) *Adapter { return &Adapter{Script: script} }

func (a *Adapter) Spawn(ctx context.Context, spec agentsession.Spec, route agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	return nil, nil
}
func (a *Adapter) Manifest() agentsession.CapabilityManifest { return a.Capabilities }

// FailSpawnWith forces the next Spawn to return err (e.g. agentsession.AuthError) —
// for the silent-bad-token / spawn-failure paths.
func (a *Adapter) FailSpawnWith(err error) *Adapter { return a }

// Transcript is an in-memory agentsession.Transcript so Seq assignment and
// FromSeq replay are exercised for real (not stubbed) in kernel tests.
type Transcript struct{ /* unexported: append-only slice + mutex */ }

func NewTranscript() *Transcript { return &Transcript{} }

func (t *Transcript) Append(ctx context.Context, e agentsession.Event) (uint64, error) { return 0, nil }
func (t *Transcript) ReadFrom(ctx context.Context, sessionID string, from agentsession.Cursor) (agentsession.Stream, error) {
	return nil, nil
}

// AssertNoSecretInStream fails if canary appears in ANY emitted Event (Extension,
// summaries, Detail) — the redaction-by-construction guarantee, runnable.
func (a *Adapter) AssertNoSecretInStream(t TestingT, canary string) {}

type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}
```

## 4. Conformance suite

The suite proves any `agentsession.Adapter` (real `claudeadapter`/`ompadapter` or the fake) is
substitutable and that the `Session` semantics hold. It lives in `agentsessiontest` per the testing
pattern (10 §4, 08 §2). A real adapter runs it against a recorded/replayed harness stream (08 §2);
the live-sandbox arm runs it against a real `claude`/`omp` in a pod in release pipelines (05 §6).

```go
// Run drives any agentsession.Adapter through the substitutability properties.
func Run(t *testing.T, newAdapter func() agentsession.Adapter)
```

Properties asserted:

- **Lifecycle legality** — only the §2 transitions occur; a control verb in an illegal `State`
  returns `StateError`; `Close` is idempotent and does NOT tear down the pod; terminal states never
  transition; every live `Events` tail closes exactly once, after the terminal Event.
- **Ordering & correlation** — `Seq` is strictly monotonic per session and equals the transcript
  offset; every Event carries the correct `SessionID`/`TurnID`/`Turn`; `EventToolUpdate`/`ToolEnd`
  correlate to their `EventToolStart` by `CallID`.
- **Replay = tail, gap-free, dup-free** — `Events(ctx, FromSeq(n))` yields `[n+1 .. head]` then the
  live tail with no gap and no dup at the seam; `FromSeq(0)` replays the whole session; replay holds
  AFTER the session terminates (old-Run reload).
- **Multi-client fan-out** — N concurrent `Events` calls see identical `Seq`-ordered streams; a slow
  subscriber neither stalls the agent nor other viewers (it is demoted to a `FromSeq` replay reader,
  never dropping events).
- **Forward compatibility** — an unrecognized harness frame surfaces as `EventExtension` with the raw
  bytes in `Extension`, is **never dropped and never fatal** (the `rate_limit_event` property), and a
  `LedgerFold` over the stream counts it without failing.
- **All four token kinds + attribution** — `EventUsage`/`TerminalPayload.Ledger` populate
  input/output/cache-read/cache-creation, `Model`+`Harness`, and `CostMicros` (or `-1` when
  unreported); `Cumulative` is truthful so the per-turn deltas reconcile against the terminal totals.
- **Grant linkage** — every `EventToolStart` carries a `GrantID` matching a `Spec.Grants[].ID`; an
  out-of-grant tool raises `EventPermissionRequest`.
- **Permission round-trip, two deciders** — with `Spec.OnPermission` set, a request is resolved
  synchronously by policy and a default-deny ends the call `ToolOutcomeDenied`; with `OnPermission`
  nil, the request surfaces as `EventPermissionRequest` and an out-of-band `Resolve` unblocks it;
  `Resolve` is idempotent on `RequestID` (first decision wins; losers get `UnknownPermissionError`).
- **Capability honesty** — a verb whose `Capability` the manifest declares `CapAbsent` returns
  `UnsupportedError`; a declared-`CapFull` capability actually works; a `CapPartial` Steer is
  observably "queue for next turn" not mid-turn (a lying manifest fails the suite — 05 §6).
- **Credential seam holds** — `Spawn` receives an `InjectedCredential` whose `Secret` is un-printable;
  the `secrets.Reference` is never in the `Spec`-as-logged, any `Event`, or any error string;
  `AuthError` carries the ref, never the value; **the absence of an init/ready event is converted to
  `AuthError`** (the silent-bad-token defense), not trusted as success.
- **Budget abort, one authority** — when `EventUsage` cumulative cost crosses `Budget.MaxCostMicros`,
  the library issues `Abort` and the terminal Event carries `TurnBudgetExceeded` (the harness-native
  cap is not relied upon; there is exactly one budget authority).
- **Secret-safety by construction** — `AssertNoSecretInStream(canary)` holds across every Event; tool
  arg/result digests are bounded and redacted.

## 5. Usage

```go
// ── kernel engine: a BATCH phase execution (a Run, 02 §2) — execute is a fold ─
// execute(spec, context, tools, schema) → (artifact, transcript, ledger) (05 §2)
// is literally this function: Open → Prompt → drain to terminal → fold evidence.
func runPhase(ctx context.Context, agents agentsession.Factory, p phase.Spec) (phase.Evidence, error) {
	session, err := agents.Open(ctx, agentsession.Spec{
		Workspace:  p.WorktreePath,                                  // the clean-room worktree S2 provisioned (07 §4); we only run in it
		Routing:    agentsession.RouteKey{Phase: p.Name(), Role: "implementer"},
		Grants:     p.ToolGrants(),                                  // allowlist as data: Write, Read, Bash(go *) (07 §3)
		Credential: secrets.Ref("anthropic-oauth-token"),           // OPAQUE; resolved server-side at Open
		Budget:     agentsession.Budget{MaxCostMicros: p.Budget().Micros}, // hard ceiling + cost-aware abort (02 §2)
		// Batch wants a quiet, policy-driven permission decider, not a human. This is
		// the SAME round-trip the chat resolves with a click; the engine supplies a
		// function. A deny ends the turn with a recorded denial in the transcript.
		OnPermission: func(req agentsession.PermissionRequest) agentsession.Decision {
			if p.Policy().Allows(req.Tool, req.Input) {
				return agentsession.Decision{Allow: true, By: "policy:clean-room"}
			}
			return agentsession.Decision{Allow: false, By: "policy:clean-room"} // no escape hatch outside declared grants
		},
	})
	if err != nil {
		var authErr agentsession.AuthError
		if errors.AsType(err, &authErr) { /* the silent-bad-token trap, surfaced — Unauthenticated → setup-token */ }
		return phase.Evidence{}, fmt.Errorf("open session: %w", err)
	}
	defer session.Close(ctx)

	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: p.Task()}); err != nil {
		return phase.Evidence{}, fmt.Errorf("prompt: %w", err)
	}

	// Drain the SAME normalized stream the chat tails — but only FOLD it, don't
	// render it. FromSeq(0) ⇒ the fold is the complete transcript. One in-process
	// consumer: no fan-out, no reconnect — the asymmetry that proves the surface minimal.
	ledger := agentsession.NewLedgerFold() // the poc/codingharness fold, promoted (forward-compatible: unknown kinds counted, never fatal)
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			break
		}
		p.TranscriptSink().Append(ev) // first-class Run artifact, redacted on capture (02 §2, P9)
		ledger.Fold(ev)
		if ev.Kind == agentsession.EventUsage {
			// The event stream IS the instrumentation: fold usage into the T6 ledger.
			obs.Emit(ctx, observability.LedgerEvent(clock.Now(), observability.Ledger{
				RunID: p.RunID(), PhaseID: p.Name(),
				Model: ev.Usage.Model, Harness: ev.Usage.Harness,
				TokensIn: ev.Usage.InputTokens, TokensOut: ev.Usage.OutputTokens,
				CacheHits: ev.Usage.CacheReadTokens, CostMicros: ev.Usage.CostMicros,
			}))
		}
	}
	if err := stream.Err(); err != nil { // a stream fault (pod died mid-run) is a real failure
		return phase.Evidence{}, fmt.Errorf("drain session: %w", err)
	}
	return phase.Evidence{
		Artifact:   p.WorktreePath,                 // the worktree diff
		Transcript: p.TranscriptSink().Ref(),       // evidence-envelope provenance (07 §4)
		Ledger:     ledger.Finish(),                // authoritative total_cost_usd — the routing-economics measurement
		Outcome:    ledger.Outcome(),               // succeeded/stopReason from the terminal Event
	}, nil
}

// ── chat-surface backend: an INTERACTIVE AssistantSession (02 §1, C22) ────────
// The SvelteKit server holds the session handle (the browser never does — the
// credential boundary is server-side). The SSE route maps Last-Event-ID → FromSeq.
func (s *ChatBackend) openSession(ctx context.Context, ws string) (agentsession.Session, error) {
	return s.agents.Open(ctx, agentsession.Spec{
		Workspace:  ws,
		Routing:    agentsession.RouteKey{Role: "assistant"},   // Claude Code + Fable 5 (C22)
		HostTools:  s.projectDataTools(),                       // read-scoped: runs, dashboards, FinOps, drift (07 §3)
		Credential: secrets.Ref("anthropic-oauth-token"),       // same opaque ref; setup-token path (C22)
		// OnPermission NIL ⇒ requests surface as EventPermissionRequest for the human
		// to Resolve out-of-band (the chat's approve/deny card, A5). The human decides
		// across HTTP requests, so the decision cannot be a synchronous callback.
	})
}

// The SSE route resumes by sequence number; a POST sibling resolves a permission.
func (s *ChatBackend) streamEvents(ctx context.Context, sess agentsession.Session, lastEventID uint64, w SSEWriter) error {
	stream := sess.Events(ctx, agentsession.FromSeq(lastEventID)) // Last-Event-ID → exact next event; fresh tab (0) = full replay
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			return stream.Err()
		}
		w.Send(ev.Seq, ev.Kind, ev) // `id:` = the resume cursor; the UI renders deltas, the tool rail, the meter, permission cards
		if ev.Terminal() {
			return nil
		}
	}
}

func (s *ChatBackend) approve(ctx context.Context, sess agentsession.Session, requestID string, allow bool, userID string) error {
	_, err := sess.Resolve(ctx, requestID, agentsession.Decision{Allow: allow, By: userID}) // the human click; first-decision-wins
	var unknown agentsession.UnknownPermissionError
	if errors.AsType(err, &unknown) { /* already resolved by another viewer → 409 */ }
	return err
}
```

## 6. Design rationale

1. **One contract, no mode fork (one primitive, two consumers).** Both drafts converge here from
   opposite directions: the producer's "one contract, two policies — not two contracts" and the
   consumer's "`execute` is a thin fold over a `Session`." The reconciled form keeps the *one*
   `Session` and *one* `Event` taxonomy both demand, but **drops the producer's `Mode` field**: the
   batch/interactive difference is which features a consumer *exercises* (chat uses deltas, steer,
   replay, multi-client, the live meter and the human permission round-trip; batch uses none of
   them), not a structural switch. The asymmetry is additive — every chat-only feature is a no-op
   for batch — so it proves the surface minimal rather than bifurcated. `execute(spec, context,
   tools, schema)` (05 §2) is `Open → Prompt → drain → fold`, shown in §5.
2. **`Seq == transcript offset` is the load-bearing invariant.** Binding the resume cursor to the
   durable transcript offset (not a volatile in-memory counter) makes `Last-Event-ID` reconnect,
   fresh-tab replay, and the engine's `FromSeq(0)` fold the *same* read. The `Transcript` (02 §2,
   P9) is therefore not a side-effect — it is the backbone resumability rests on, injected as a
   `Deps` port so persistence/retention stays the consumer's concern (07 §2).
3. **The event stream is the instrumentation contract.** Ordered by `Seq`, correlated by
   `SessionID`/`TurnID`. The EVENT TAXONOMY is the union normalized from the two harnesses ADR-0008
   names. `EventExtension` + the per-event `Extension []byte` are **non-negotiable** (both drafts):
   the `rate_limit_event` surprise (measured) proves harnesses emit types Eden has not normalized;
   the contract carries them losslessly to the transcript and ignores them in the engine rather than
   drop or crash. Thinking is its own Kind so the UI folds it and retention treats reasoning
   distinctly.
4. **Four token kinds, integer micro-units, model+harness attribution per tick.** Cache economics
   dominate real agent-loop cost; collapsing cache-read and cache-creation makes FinOps (S9) and the
   ADR-0008 routing comparison wrong. `CostMicros`, not `float64` (aligned with
   `observability.Ledger.CostMicros`). The live `UsageMeter` is the running prefix of the
   authoritative terminal `TokenLedger`; this port emits, it does not bill.
5. **The permission round-trip is one verb, two deciders.** `EventPermissionRequest` →
   `Session.Resolve` (out-of-band) OR `Spec.OnPermission` (in-line policy) unifies the human-click
   approval (chat, C22) and the policy auto-resolver (engine clean-room). The producer's pre-declared
   `PermissionPolicy{Default, Ask}` could not serve the chat: a human deciding *across HTTP requests*
   is not a synchronous callback inside the stream. The consumer's `Resolve` verb + nil-`OnPermission`
   path is taken; the engine's synchronous policy survives as `OnPermission` (see §7 Q2). Every tool
   call carries its `GrantID` so the per-Run audit (07 §3) is mechanical; `AssistantSession`s get
   `ReadOnly` grants and project-data `HostTool`s only.
6. **Credentials confined to a seam, designed honestly.** Only an opaque `secrets.Reference` rides
   the `Spec`; the value is resolved server-side at `Open`, confined to `Secret.Use(fn)` at the
   injection site, and crosses into the *child* process env (scrubbed of higher-precedence keys) or
   an `apiKeyHelper`-fetched short-lived token (the 07 §2 ideal) — never the `Spec`, an `Event`, a
   log, a transcript, or an image layer (the credential-flow diagram). The init/ready event — not the
   harness exit code — is the success signal; its absence converts to `AuthError` (the silent-bad-token
   trap, measured). `AuthError` is the `Unauthenticated` outcome the chat renders as the setup-token
   card (C22, REQ-0021).
7. **Isolation is assumed, never implemented; pod lifecycle is S2's.** Pod sandboxing, dial-out-only,
   default-deny egress are 07 §3 / F1 / S2 obligations. This contract opens no socket, manages no pod,
   and `Close` **never tears down the pod** (02 §1 Workspace boundary) — its only contribution is
   *declaring the egress endpoints a session's `Route` + `Grants` need* so F1 can derive the
   `NetworkPolicy`.
8. **`agentconfiguration` decides harness+model; this port is told.** `RouteKey → Route` arrives
   frozen in `Config`. The session port never grows model-selection or routing-economics policy —
   that is upstream (C22's "right agent for the right phase").
9. **Interfaces under the 5-method ceiling, split where needed (10 §9).** `Session` is 4 methods
   (`Events`/`Control`/`Resolve`/`Close`) — the producer's 7-method `Session`
   (Prompt/Steer/Abort/Resume/Close/Events/State) is collapsed: the three turn verbs fold into
   `Control(Command)` (the consumer's real call sites issue one POST shape), `State` rides the stream
   as `EventSessionState` (no separate accessor — the chat reads it off the same stream it already
   tails), and `Resume` becomes `Spec.ResumeFrom` (re-attach is spawn-shaped — see §7 Q1). `Stream`
   (2), `HarnessConn` (3), `Adapter` (2), `Transcript` (2), `Factory` (1) all sit under the ceiling.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| Q1 | **`Resume`/reconnect shape** — a `Session.Resume` verb, a `Provider.Open{ResumeFrom}` spawn, or seq-based `Events(FromSeq)` reconnect? Both producer drafts the verb tentatively; the consumer pins seq-replay. | Lean `Provider.Open{ResumeFrom}` (re-attach is spawn-shaped); keep `Session.Resume` only if in-place reconnect after a transport blip is needed. | No `Resume` verb at all: reconnect is `Events(ctx, FromSeq(n))` over the durable transcript; harness-native re-attach is `Spec.ResumeFrom`. | 🧩 **Split into TWO distinct concerns, neither a `Session` method.** (a) *Consumer reconnect* (a dropped SSE socket, a fresh tab, an old-Run reload) is `Events(ctx, FromSeq(n))` — pure replay-then-tail off the transcript, no harness involvement. (b) *Harness re-attach* (Claude `--resume`, omp session dir, surviving a pod recycle) is `Spec.ResumeFrom` + `CapResume`. The producer's `Session.Resume` verb is **dropped**: it conflated the two, and keeping `Session` at 4 methods needs the cut. Every real call site (the SSE route, the engine fold) uses `FromSeq`; none needs an in-place `Resume` RPC. |
| Q2 | **Permission decision** — a pre-declared `PermissionPolicy{Default, Ask}`, or a `Resolve` verb + an `OnPermission` callback? | Policy + an `Ask` hook returning `GrantPending` for the human-deciding case — avoid a blocking RPC inside the stream. | `Resolve` (out-of-band verb) for the human + `OnPermission` (policy fn) for the engine — the chat human decides *across HTTP requests*, not in a callback. | 🧩 **Took the consumer's `Resolve` + `OnPermission`; dropped the producer's `Ask`.** The chat's real call site (A5 `POST …/permissions/[requestId]`) proves it: a human clicking approve in a *later* HTTP request cannot be a synchronous `Ask` closure held open inside the stream. So the request **blocks the harness** (`StateAwaitingPermission`) and emits `EventPermissionRequest`; resolution is either an out-of-band `Session.Resolve` (human, asynchronous, idempotent, first-decision-wins across viewers) or a synchronous `Spec.OnPermission` (engine policy). The producer's two cases both survive — `OnPermission` *is* the policy `Default`/`Ask`, just hoisted to the `Spec` — but the human path is a real verb, not a held-open callback. `GrantPending` survives as the pre-resolution `Decision` state on the request event. |
| Q3 | **Mode field** — is `Mode{Batch, Interactive}` a structural `Spec` field? | Yes — `Mode` selects the default permission policy and whether the session auto-closes after the first terminal turn; "one contract, two policies." | No `Mode` — `execute` is a fold over `Session`; the batch/interactive difference is which features the consumer exercises, all additive. | 🧩 **Dropped `Mode`.** The two policy effects the producer attached to `Mode` decompose cleanly without a structural fork: (a) the default permission policy is just whether `Spec.OnPermission` is set (engine: set, deny-default; chat: nil, human-resolved); (b) "auto-close after the first terminal turn" is the *batch consumer's* drain-loop choosing to `Close` on `Terminal()` (§5) — the library need not encode it. Keeping `Mode` would invite per-mode branching inside the library the consumer's call sites prove unnecessary. The producer's load-bearing claim — *one `Event` taxonomy, not two contracts* — is fully honored; only the redundant knob is cut. |
| Q4 | **`Session` method shape** — 7 verbs (Prompt/Steer/Abort/Resume/Close/Events/State) or a collapsed surface? | Seven (Events is the data channel, not a control verb, so "5 + Events + State"). | Four: `Events`/`Control`/`Resolve`/`Close`. | 🧩 **Took the consumer's 4-method `Session`** (10 §9 ceiling is a hard rule, not a soft target). The three turn verbs fold into `Control(Command{Kind})` — the consumer's POST routes already send one `{kind, text}` shape, so the split bought nothing; `State()` is removed because state rides the stream as `EventSessionState` (the chat reads it off the stream it already tails — a second accessor is a second source of truth); `Resume` is gone per Q1. `Steer`/`Abort` semantics are preserved as `CommandSteer`/`CommandAbort`, with `Steer` degrading per `CapSteer`. |
| Q5 | **Backpressure / slow subscriber** — drop frames (donor `poc/agents` `Subscribe`) or guarantee gap-free? | (Implicit: single-consumer `Events() <-chan Event`, no fan-out contract.) | Gap-free is required for replay; "overflow ⇒ demote to a `FromSeq` replay reader," never skip. | 🧩 **Took the consumer's gap-free guarantee with catch-up-by-replay.** The donor's frame-drop is correct for a CPU-telemetry fan-out but **wrong here**: a dropped event breaks the `Seq`-replay invariant the whole resumability story rests on. A slow live-tail subscriber that overflows its in-flight buffer is converted to a `FromSeq` reader off the durable transcript — it catches up by re-reading, never by skipping — and one slow viewer never stalls the agent or other viewers (pull-based `Stream`). This is a conformance property (§4). The producer's single-consumer `Events() <-chan Event` becomes the *adapter-internal* `HarnessConn.Events()`; the public `Session.Events` is the multi-client, replayable form. |
| Q6 | **Budget enforcement authority** — the library watches `EventUsage` and aborts, or the engine does? | Library offers best-effort `Budget` abort; authoritative `TokenBudget` (02 §2) is the engine's — avoid two authorities. | (Implicit via `Spec.Budget`: hard ceiling + cost-aware abort, expecting a terminal `budget_exhausted`.) | 🧩 **One authority, expressed as a terminal outcome.** The library watches `EventUsage` against `Budget.MaxCostMicros` and issues `Abort` (so a runaway harness is stopped even if the engine's own watch lags), but the *authoritative* `TokenBudget` (02 §2) remains the engine's — the two never disagree because the library's abort is strictly tighter-or-equal and both terminate the same session. The budget stop surfaces as a `TurnBudgetExceeded` terminal outcome (the consumer's `budget_exhausted` wish, as a distinct `TurnOutcome` so the chat meter shows "stopped: budget" rather than a crash — consumer Q5). |
| Q7 | **`Steer` across harnesses** — a steering-mode enum, or `CapSteer` {absent/partial/full}? | `CapSteer` {absent/partial/full} + graceful degrade; resist a steering-mode enum until a second steering harness proves the shape. | Capability-manifest candidate: declare `steer: full|partial|absent`, degrade the UI; claude-code may be "queue for next turn" (partial) vs true mid-turn (omp). | 🧩 **`CapSteer` {Absent, Partial, Full}; no steering-mode enum.** Both sides agree. `CapPartial` carries exactly the consumer's "queue for next turn" semantics (claude-code headless) vs `CapFull` true mid-turn (omp `SteeringMode`); the conformance suite asserts a `CapPartial` Steer is observably queued, not mid-turn (§4). A steering-mode enum is resisted until a second mid-turn-steering harness proves its shape — premature generality otherwise. |
| Q8 | **Structured message content** — blocks (text/code/tool-use/image) or flat `Delta string`? | Flat deltas + `EventThinking`/`EventTool*` Kinds already separate the structural axes; push back on a block model unless the UI proves a concrete need. | (Flat `text_delta`/`thinking_delta` in the SSE shapes; tool activity is its own event class.) | 🧩 **Flat deltas (both sides agree).** The structural axes are already separated by Kind (`EventThinkingDelta` / `EventTextDelta` / `EventToolStart`/`Update`/`End`), so a block content-model would import the harness's content schema into the contract for no consumer-proven gain. Revisited additively if the Ableton-grade UI (C11/C22) proves a concrete need for, e.g., inline image blocks. |
| Q9 | **Per-event redaction boundary** — do `tool_start.input`/`tool_end.output` (which can carry file contents or command output) inherit the `Secret`-construction redaction, or need a declared redaction pass? | (Implicit: `ArgsSummary`/`ResultDigest` are "redacted, bounded summary … never raw secret-bearing args.") | Open question: confirm events inherit the transcript's redact-by-construction (07 §2), or a declared pass before an event reaches the stream. | 🧩 **Adapter redacts before emit; the contract carries only bounded digests.** Tool I/O is a real leak surface, so `ToolPayload` carries `ArgsSummary`/`PartialDigest`/`ResultDigest` — **redacted, bounded** by the adapter at the normalization boundary — never raw args or full output (the full result rides the *redacted transcript*, 07 §2). `Event.Extension` is likewise redaction-eligible. The `secrets.Secret` type keeps credentials off the stream by construction; the *adapter* owns redacting non-secret-typed sensitive payloads (command output, file contents) before an `Event` is emitted, and `AssertNoSecretInStream` (§3) + the secret-safety conformance property (§4) make it runnable. |
| Q10 | **Cursor durability window** — is the full transcript always `FromSeq`-replayable (needed for old-Run reload), or is there a live-window limit beyond which replay needs a different path? | (Implicit: "the transcript stores it verbatim.") | Needs full replayability for old-Run reload; else the chat needs a separate history fetch. | 🧩 **Full replayability is the contract; `Transcript.ReadFrom` serves it.** `FromSeq(n)` reads the durable transcript via `Deps.Transcript.ReadFrom`, which is available **after** the session terminates — so the single `Events(FromSeq)` path serves live tail, mid-session reconnect, and old-Run reload alike (no separate history endpoint). The transcript's *retention* (how long it is kept) is the 07 §2 / engine concern behind the `Transcript` seam, not this port's; once retention expires a session is simply no longer openable, which is an engine-level 404, not a session-level gap. |
| Q11 | **Multi-turn engine phases** — engine loops `Control(prompt)`, or a `phases`-style batch command? | (Implicit: `Prompt` once with the spec task; auto-close after the terminal turn.) | v1 phases are single-shot; multi-turn is the engine looping `Control(prompt)` unless the producer wants a batch `phases` command. | 🧩 **Engine loops `Control(CommandPrompt)`; no batch `phases` command.** Keeping it consumer-driven (one `Control(prompt)` per turn) avoids importing the donor OMP `RpcCommand.Phases` shape into the contract before a real multi-turn phase proves it. v1 phases are single-shot (matches the `poc/codingharness` spike); a multi-turn phase loops `Prompt` against the same `Session`. Additive later if a batch-phases affordance proves load-bearing. |
| Q12 | **cross-contract reconciliation, post-draft** — the producer named `observability.Ledger`/`CostMicros` and `secrets.Reference`/`Secret`; the consumer named a `SecretReference` and a `LedgerFold`. Confirm alignment to the frozen-shape siblings. | n/a | n/a | 🧩 **Aligned to the sibling contracts as written.** Credentials use `secrets.Reference` (loggable) + `secrets.Secret` (un-printable, `Use(fn)`-only) exactly as `secrets.md` froze them — the consumer's `SecretReference` is renamed to `secrets.Reference`. The four-token + `CostMicros` (integer micro-units) `UsageMeter`/`TokenLedger` shape matches `observability.Ledger` (T6) so the engine folds one into the other without a translation layer (§5). Errors are typed structs inspected via `errors.AsType` per `errors.md` (`AuthError`/`SpawnError`/`StateError`/`UnsupportedError`/`UnknownPermissionError`), each carrying the offending ref/cap/state, never a value. |
