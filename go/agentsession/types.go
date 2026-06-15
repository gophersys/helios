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
// machine, Seq ordering, grant->audit linkage, and credential-injection shape; an
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
	"time"
)

// State is the session lifecycle (grounded in poc/agents state.go, generalized).
// Closed taxonomy, additive-only (10 §9). The legal transitions are enforced by
// the library, not the adapter: Initializing->Ready->{Running<->AwaitingInput |
// AwaitingPermission}->{Completed | Failed | Aborted}. A terminal state
// (Completed/Failed/Aborted) never transitions. The State rides the stream as the
// SessionState event payload (the chat's connection/idle/working/terminal chrome).
type State uint8

// The session lifecycle states. Append-only (10 §9): never reordered or renamed.
const (
	StateInitializing       State = iota // process spawning + auth handshake not yet confirmed
	StateReady                           // harness handshake confirmed (init/ready event seen); accepts the first Prompt
	StateRunning                         // a turn is in flight (model thinking / tools running)
	StateAwaitingInput                   // turn complete, awaiting the next Prompt (interactive) or done (batch)
	StateAwaitingPermission              // blocked on an out-of-grant request; awaiting Resolve (permission round-trip)
	StateCompleted                       // graceful terminal: a turn reached a clean result; ledger finalized, process reaped
	StateFailed                          // terminal: spawn/auth/transport failure or unrecoverable harness error
	StateAborted                         // terminal: an Abort took the session to a stop
)

// stateTokens holds the stable lower-kebab token for each State, indexed by value.
var stateTokens = [...]string{
	StateInitializing:       "initializing",
	StateReady:              "ready",
	StateRunning:            "running",
	StateAwaitingInput:      "awaiting-input",
	StateAwaitingPermission: "awaiting-permission",
	StateCompleted:          "completed",
	StateFailed:             "failed",
	StateAborted:            "aborted",
}

// String returns the stable lower-kebab token (e.g. "awaiting-input"). Total:
// returns "initializing" for any out-of-range value.
func (s State) String() string {
	if int(s) < len(stateTokens) {
		return stateTokens[s]
	}
	return stateTokens[StateInitializing]
}

// IsTerminal reports whether s is a terminal state (Completed/Failed/Aborted),
// which never transitions.
func (s State) IsTerminal() bool {
	return s == StateCompleted || s == StateFailed || s == StateAborted
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

// CommandKind is the turn-taking control axis. Append-only (10 §9).
type CommandKind uint8

// The turn-taking commands.
const (
	CommandPrompt CommandKind = iota // start a turn (valid when Ready/AwaitingInput)
	CommandSteer                     // interject into a running turn (CapSteer)
	CommandAbort                     // cancel the in-flight turn (always valid until terminal)
)

// Decision answers a PermissionRequest. The decider is the caller (human or
// policy); the By stamp is the audit identity (07 §7): a user id or "policy:<name>".
// In the ratified permission model (founder, 2026-06-15) a Decision may also be
// returned by the PermissionAdvisor port, in which case By is "advisor:<name>" and
// Rationale carries the audit-logged reasoning.
type Decision struct {
	Allow bool
	// Remember widens the standing grant for THIS session only — never persisted to
	// the credential profile (that is a governed act, not a chat click); scope is the
	// exact tool+pattern the agent asked for ("allow Bash(go test ./...)", not "allow
	// Bash"). RETAINED for the frozen surface; the canonical widening trigger is now
	// Scope == ScopeSession (a ScopeSession allow implies Remember). A true Remember is
	// honored identically (session widening) for back-compat.
	Remember bool
	By       string // identity stamp for audit ("user:<id>" | "policy:<name>" | "advisor:<name>")

	// Scope bounds how long an allow holds. ScopeOnce (the zero value) authorizes THIS
	// request only — the same tool is re-asked next time. ScopeSession dynamically
	// widens THIS running session's in-memory grant set so the exact tool is NOT
	// re-asked for the remainder of the session (NEVER persisted to the config-as-code
	// grants — that is a governed act, not a chat click). Scope is meaningful only on an
	// allow; a deny is always terminal-for-this-request regardless of Scope.
	Scope DecisionScope

	// Rationale is the audit-logged reasoning behind the decision. The PermissionAdvisor
	// MUST populate it (the advisor's verdict is only as trustworthy as its audited
	// reasoning); a human/policy decision MAY leave it empty. It is bounded, redacted
	// text — NEVER a secret value (it rides EventPermissionResolved and the transcript).
	Rationale string
}

// DecisionScope bounds how long a permission allow holds within a session. Append-only
// (10 §9): never reordered or renamed. The zero value (ScopeOnce) is the safe default —
// a Decision built without naming a Scope authorizes one request only.
type DecisionScope uint8

// The decision scopes.
const (
	ScopeOnce    DecisionScope = iota // authorize THIS request only; the same tool is re-asked next time (the safe default)
	ScopeSession                      // widen this running session's in-memory grant set so the exact tool is not re-asked this session (never persisted)
)

// decisionScopeTokens holds the stable lower-kebab token for each DecisionScope.
var decisionScopeTokens = [...]string{
	ScopeOnce:    "once",
	ScopeSession: "session",
}

// String returns the stable lower-kebab token (e.g. "session"). Total: returns "once"
// for any out-of-range value.
func (s DecisionScope) String() string {
	if int(s) < len(decisionScopeTokens) {
		return decisionScopeTokens[s]
	}
	return decisionScopeTokens[ScopeOnce]
}

// Ack is the sequence number a control/resolve was admitted at, so a UI can
// correlate the resulting events when they arrive on the stream.
type Ack struct{ Seq uint64 }

// EventKind is the NORMALIZED taxonomy every harness maps onto (the EVENT TAXONOMY
// table in the contract). It is the stable, closed, additive-only (10 §9)
// classification the engine and chat surface branch on WITHOUT parsing
// harness-native strings. Grounded in the union of the OMP AgentEventType set
// (poc/agents types.go) and the Claude stream-json types (poc/codingharness
// ledger.go).
type EventKind uint8

// The normalized event taxonomy. Append-only (10 §9): never reordered or renamed.
const (
	EventSessionState       EventKind = iota // a State transition (connection/idle/working/terminal chrome)
	EventMessageStart                        // an assistant message began (Role, turn)
	EventThinkingDelta                       // a reasoning/thinking fragment (foldable; redaction-eligible)
	EventTextDelta                           // a streamed assistant text fragment (token-by-token render)
	EventMessageEnd                          // the assistant message completed
	EventToolStart                           // a tool invocation began: name, args summary, the GRANT it ran under
	EventToolUpdate                          // a tool's partial/streamed result (OMP partial-result streaming)
	EventToolEnd                             // a tool invocation finished: outcome, duration, redacted result digest
	EventPermissionRequest                   // the harness wants a tool OUTSIDE the standing grant — the human/policy gate
	EventPermissionResolved                  // the request was decided (Allow/Deny + By) — the audit + UI-notification record
	EventUsage                               // a token-usage + cost tick (UsageMeter) with model attribution — ALL FOUR token kinds
	EventResult                              // TERMINAL: a turn reached a clean result; carries the authoritative TokenLedger
	EventFailed                              // TERMINAL: an error moved the session to StateFailed; carries the ledger + typed reason
	EventAborted                             // TERMINAL: an Abort took the session to a stop; carries the ledger + By
	EventExtension                           // a harness event with no normalized kind — preserved VERBATIM, NEVER dropped
	EventThinkingProgress                    // a pre-message reasoning HEARTBEAT (no content yet): a running estimated thinking-token count, for a live "thinking…" status indicator
)

// eventKindTokens holds the stable lower-kebab token for each EventKind, indexed
// by value.
var eventKindTokens = [...]string{
	EventSessionState:       "session-state",
	EventMessageStart:       "message-start",
	EventThinkingDelta:      "thinking-delta",
	EventTextDelta:          "text-delta",
	EventMessageEnd:         "message-end",
	EventToolStart:          "tool-start",
	EventToolUpdate:         "tool-update",
	EventToolEnd:            "tool-end",
	EventPermissionRequest:  "permission-request",
	EventPermissionResolved: "permission-resolved",
	EventUsage:              "usage",
	EventResult:             "result",
	EventFailed:             "failed",
	EventAborted:            "aborted",
	EventExtension:          "extension",
	EventThinkingProgress:   "thinking-progress",
}

// String returns the stable lower-kebab token (e.g. "tool-start"). Total: returns
// "extension" for any out-of-range value.
func (k EventKind) String() string {
	if int(k) < len(eventKindTokens) {
		return eventKindTokens[k]
	}
	return eventKindTokens[EventExtension]
}

// Event is one immutable, ordered record on the stream — a plain value (copyable,
// zero-safe). SessionID + TurnID + Seq give total ordering and correlation; Kind is
// the stable axis; exactly one typed Payload pointer is populated per Kind (a tagged
// union by convention; nil otherwise); Extension carries the opaque per-harness
// remainder so a harness that emits richer data than Eden normalizes loses NOTHING.
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
	Message    *MessagePayload    // EventMessageStart/ThinkingDelta/TextDelta/MessageEnd/ThinkingProgress (Tokens)
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

// IsTerminal reports whether this Event ends the session (exactly one terminal
// event per session: Result, Failed, or Aborted).
//
//nolint:gocritic // contract §2: Event is a plain copyable value record; its predicates take a value receiver (the frozen surface).
func (e Event) IsTerminal() bool {
	return e.Kind == EventResult || e.Kind == EventFailed || e.Kind == EventAborted
}

// StatePayload carries an EventSessionState transition.
type StatePayload struct {
	From, To State
}

// MessagePayload carries a streamed assistant fragment or a thinking fragment.
// Delta is the INCREMENTAL text (not the cumulative message). Thinking is its own
// Kind so the UI can fold it and retention/redaction can treat reasoning distinctly.
type MessagePayload struct {
	Role  string // "assistant" | "system"
	Delta string // the incremental fragment
	// Tokens is the running ESTIMATED reasoning-token count carried by EventThinkingProgress
	// (a pre-message heartbeat). Zero for every message/thinking/text delta. It is an estimate
	// for a live "thinking…" status indicator, NOT a billed usage figure (that is EventUsage).
	Tokens int
}

// ToolPayload carries a tool invocation's start (EventToolStart), partial
// (EventToolUpdate), or end (EventToolEnd). GrantID ties the call back to the
// allowlist entry that permitted it — the audit chain 07 §3 requires. Args/result
// summaries are redacted, bounded — never raw secret-bearing data.
type ToolPayload struct {
	CallID        string        // correlates Start<->Update<->End
	Name          string        // tool name, e.g. "Write", "Bash", a host-tool name
	GrantID       string        // the ToolGrant that authorized this call (audit linkage)
	ArgsSummary   string        // EventToolStart: redacted, bounded summary of arguments
	PartialDigest string        // EventToolUpdate: redacted, bounded streamed fragment
	Outcome       ToolOutcome   // EventToolEnd only
	ResultDigest  string        // EventToolEnd only: redacted, bounded result summary
	Duration      time.Duration // EventToolEnd only
	IsHostTool    bool          // true when this is an Eden-provided host tool (callback), not a harness-native tool
}

// ToolOutcome classifies an EventToolEnd. Append-only (10 §9).
type ToolOutcome uint8

// The tool-end outcomes.
const (
	ToolOutcomeOK     ToolOutcome = iota // the tool ran to completion
	ToolOutcomeError                     // the tool reported an error
	ToolOutcomeDenied                    // the permission gate rejected it
)

// PermissionPayload is the permission round-trip record: EventPermissionRequest
// when the harness wants a capability OUTSIDE the standing grant, and
// EventPermissionResolved when it is decided. The request BLOCKS the harness
// (StateAwaitingPermission) until resolved; the decision is supplied either by
// Spec.OnPermission (policy, synchronous) or by an out-of-band Session.Resolve
// (human, asynchronous across HTTP requests).
type PermissionPayload struct {
	RequestID string
	Tool      string
	Reason    string        // why the harness wants it
	Decision  GrantDecision // EventPermissionResolved: what was decided
	By        string        // EventPermissionResolved: the deciding identity (user id or "policy:<name>")
}

// GrantDecision is the resolution state of a permission request. Append-only.
type GrantDecision uint8

// The permission-resolution states.
const (
	GrantPending GrantDecision = iota // awaiting policy/human (the request, pre-resolution)
	GrantAllowed                      // the request was allowed
	GrantDenied                       // the request was denied
)

// UsageMeter is a token-usage + cost tick with model attribution — the live meter
// (per EventUsage) AND the running prefix of the terminal TokenLedger. It carries
// ALL FOUR token kinds confirmed present in BOTH harnesses: input, output,
// cache-read, cache-creation/write — cache economics dominate real agent-loop cost,
// so collapsing them makes FinOps (S9) and the ADR-0008 routing comparison wrong.
// Cost is integer micro-units (no float drift — aligned with
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
// carries the AUTHORITATIVE TokenLedger (the poc/codingharness total_cost_usd
// ground truth) so the engine's evidence envelope and the chat's final meter
// reconcile.
type TerminalPayload struct {
	Outcome    TurnOutcome
	Ledger     TokenLedger
	ResultText string      // EventResult: the final assistant text (batch: the artifact-adjacent result)
	StopReason string      // harness stop reason, surfaced verbatim for diagnostics
	Reason     ErrorReason // EventFailed: the branchable classification
	Detail     string      // EventFailed: a redacted message; never a credential
	By         string      // EventAborted: who aborted (user id or "policy:<name>")
}

// TurnOutcome classifies a terminal Event. Append-only (10 §9).
type TurnOutcome uint8

// The terminal turn outcomes.
const (
	TurnCompleted      TurnOutcome = iota // a clean result
	TurnAborted                           // an Abort stopped the session
	TurnFailed                            // an unrecoverable error
	TurnMaxTurns                          // the harness turn cap was reached
	TurnBudgetExceeded                    // the TokenBudget cost-aware abort (02 §2) — chat meter shows "stopped: budget"
)

// TokenLedger is the authoritative aggregate on a terminal Event — the UsageMeter
// fields plus the run-shaped correlation/accounting the engine folds into the Run's
// evidence and the FinOps UsageRecord. It is the poc/codingharness ledger,
// verbatim-shaped, promoted into the library.
type TokenLedger struct {
	UsageMeter     // the four token kinds + cost + model/harness attribution (cumulative)
	Turns          int32
	ToolUses       int32
	WallTime       time.Duration
	ToolUsesByName map[string]int32 // per-tool counts, for the routing/cost breakdown
}

// ErrorReason is the stable, branchable error classification (the engine retries on
// ReasonRateLimit, aborts on ReasonAuth). Closed, additive-only (10 §9).
type ErrorReason uint8

// The error reasons surfaced on EventFailed.
const (
	ReasonUnknown      ErrorReason = iota // unclassified
	ReasonAuth                            // bad/expired token (07 §2 path) — INCLUDES the silent-bad-token trap
	ReasonRateLimit                       // provider throttling (the rate_limit_event lesson)
	ReasonBudget                          // TokenBudget ceiling hit (02 §2, 04 §6)
	ReasonMaxTurns                        // harness turn cap reached
	ReasonTransport                       // stdio/RPC framing or process death
	ReasonHarnessError                    // an error the harness reported about its own loop
)
