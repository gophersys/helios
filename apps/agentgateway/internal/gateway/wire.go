package gateway

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
)

// This file is the wire contract: the JSON request/response DTOs the SvelteKit UI
// exchanges, and the per-kind SSE event projection. Everything here is a redaction-safe
// projection of the library types — no credential value has a path into any field (the
// agentsession Event taxonomy is redaction-eligible by construction, and the gateway never
// holds a resolved secret).

// ── REST request DTOs ────────────────────────────────────────────────────────.

// createSessionRequest is the body of POST /sessions: the per-spawn bindings the chat
// surface supplies. The credential is NOT here — it rides the gateway's configured
// secrets.Reference, resolved server-side at Open (REQ-0021). RunID correlates the engine
// Run; Prompt, when non-empty, is sent as the first turn so the chat starts working.
type createSessionRequest struct {
	OrganizationID  string            `json:"organizationId"`
	ProjectID       string            `json:"projectId"`
	TemplateName    string            `json:"templateName"`
	TemplateVersion string            `json:"templateVersion"`
	RunID           string            `json:"runId,omitempty"`
	By              string            `json:"by,omitempty"`
	Labels          map[string]string `json:"labels,omitempty"`
	Prompt          string            `json:"prompt,omitempty"`

	// Product is the OPTIONAL ProductConfig the create-flow wizard proposed (POST /product/propose)
	// and the user then edited. When present, the gateway normalizes it and folds it into the
	// agent's initial-context preamble prepended to Prompt, so the build agent opens with the full
	// product spec in view (a "session" IS a PRODUCT Eden builds). Per-dimension backend honoring is
	// incremental, but the spec is carried + visible. Absent == the existing harness+prompt path,
	// unchanged.
	Product *ProductConfig `json:"product,omitempty"`
}

// controlRequest is the body of POST /sessions/{id}/control: the prompt/steer/abort verb
// that takes effect mid-stream (REQ-0020 controls). Text is the message for prompt/steer;
// empty for abort.
type controlRequest struct {
	Command string `json:"command"` // "prompt" | "steer" | "abort"
	Text    string `json:"text,omitempty"`
}

// resolveRequest is the body of POST /sessions/{id}/permissions/{requestId}: the human's
// answer to a pending out-of-grant EventPermissionRequest (ADR-0025). The RequestID is the
// PATH wildcard, NOT a body field — the body carries only the decision. Verdict is the
// allow/deny verb; Scope bounds an allow to this request only ("once") or the running
// session ("session", never persisted); By is the OPTIONAL principal that gets stamped
// "human:<by>" on the audited Decision (defaulting to "human:anonymous"). This is a Resolve,
// NOT a control Command — it calls the session's distinct Resolve method.
type resolveRequest struct {
	Verdict string `json:"verdict"`         // "allow" | "deny"
	Scope   string `json:"scope,omitempty"` // "once" (default) | "session"
	By      string `json:"by,omitempty"`    // the deciding principal; stamped "human:<by>" for audit
}

// ── REST response DTOs ───────────────────────────────────────────────────────.

// agentView is the JSON projection of an orchestrator.Agent for the session-list and the
// get-one record (REQ-0022 list, REQ-0020 record). It carries the lifecycle status, the
// tenancy, and the live token/cost ledger — NEVER a credential.
type agentView struct {
	ID        string     `json:"id"`
	Org       string     `json:"organizationId"`
	Project   string     `json:"projectId"`
	Template  string     `json:"template"`
	RunID     string     `json:"runId,omitempty"`
	Status    string     `json:"status"`
	Desired   string     `json:"desired"`
	By        string     `json:"by,omitempty"`
	Detail    string     `json:"detail,omitempty"`
	CreatedAt time.Time  `json:"createdAt"`
	UpdatedAt time.Time  `json:"updatedAt"`
	Ledger    ledgerView `json:"ledger"`
	// CanResume is the record-plane (orchestrator) Resume allowance: true only when the agent's
	// lifecycle Status is re-attachable (Suspended/Stopped). The UI seeds the Resume control's
	// enablement from this on attach so a live session never offers a Resume the record plane rejects
	// (the turn-taking allowances ride the SSE stateView instead).
	CanResume bool `json:"canResume"`
}

// listResponse is the body of GET /sessions: a page of agents plus the opaque next cursor
// (REQ-0022 paginated session-list).
type listResponse struct {
	Sessions []agentView `json:"sessions"`
	Next     string      `json:"next,omitempty"`
}

// createResponse is the body of POST /sessions: the assigned AgentID the client uses for
// every subsequent route (the SSE stream, the control channel, the transcript).
type createResponse struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

// controlResponse is the body of POST /sessions/{id}/control: the Seq the control was
// admitted at, so the UI correlates the resulting events on the stream (Ack).
type controlResponse struct {
	AdmittedSeq uint64 `json:"admittedSeq"`
}

// resolveResponse is the body of POST /sessions/{id}/permissions/{requestId}: the Seq the
// resulting EventPermissionResolved was admitted at, so the UI correlates the resolution on
// the stream (the same Ack shape the control verbs return).
type resolveResponse struct {
	AdmittedSeq uint64 `json:"admittedSeq"`
}

// transcriptResponse is the body of GET /sessions/{id}/transcript: the persisted Run's
// full event list, replayed from the durable transcript and queryable AFTER the session
// ends (REQ-0020 persisted Run, REQ-0023 reconstruct from persisted events).
type transcriptResponse struct {
	ID       string      `json:"id"`
	Events   []eventView `json:"events"`
	HeadSeq  uint64      `json:"headSeq"`
	Complete bool        `json:"complete"` // true == the terminal event is present
}

// workspaceResponse is the body of GET /sessions/{id}/workspace: the REAL files the agent
// actually produced under its workspace directory — the ground-truth view beyond the
// tool-derived artifact list the UI assembles from the event stream. Paths are RELATIVE to
// the workspace root, sorted, and capped; no field can carry a credential (a path, a size,
// and a mtime are all that escape).
type workspaceResponse struct {
	Files []workspaceFileView `json:"files"`
}

// workspaceFileView is one file under the workspace root: its slash-separated path RELATIVE
// to the root (never absolute, never escaping the root), its size in bytes, and its
// modification time as a Unix second so the UI renders without parsing a timestamp.
type workspaceFileView struct {
	Path         string `json:"path"`
	Size         int64  `json:"size"`
	ModifiedUnix int64  `json:"modifiedUnix"`
}

// workspaceFileContent is the body of GET /sessions/{id}/workspace/file?path= — the content of one
// workspace file the UI viewer renders. Kind is "text" (Text holds the UTF-8 content) or "binary"
// (Text empty); Truncated marks a read clipped at the size cap. No field can hold a credential
// (.git + dotfiles are refused by the handler).
type workspaceFileContent struct {
	Path      string `json:"path"`
	Text      string `json:"text"`
	Kind      string `json:"kind"`
	Truncated bool   `json:"truncated"`
}

// ── the SSE event projection (REQ-0024) ──────────────────────────────────────.

// eventView is the JSON `data:` payload of one SSE frame — a redaction-safe projection of
// an agentsession.Event. The SSE frame's `event:` field carries the kind token and `id:`
// carries the monotonic Seq (REQ-0023), so the UI dispatches on the event type and tracks
// its cursor without parsing the body. Exactly the populated sub-payload for the kind is
// non-nil (a tagged union by convention), so each of the nine REQ-0024 event types renders
// individually.
type eventView struct {
	SessionID  string          `json:"sessionId"`
	Seq        uint64          `json:"seq"`
	Kind       string          `json:"kind"`
	Turn       int             `json:"turn,omitempty"`
	TurnID     string          `json:"turnId,omitempty"`
	Time       time.Time       `json:"time"`
	State      *stateView      `json:"state,omitempty"`
	Message    *messageView    `json:"message,omitempty"`
	Tool       *toolView       `json:"tool,omitempty"`
	Permission *permissionView `json:"permission,omitempty"`
	Usage      *usageView      `json:"usage,omitempty"`
	Terminal   *terminalView   `json:"terminal,omitempty"`
	Extension  []byte          `json:"extension,omitempty"`
}

// stateView projects a session-state transition (the chat's connection/idle/working chrome) AND the
// turn-taking control allowances for the NEW state — the one-home (state × command) legality
// (agentsession.LegalControls), projected so the UI derives every control's enablement from this set
// instead of re-encoding the matrix. A control absent from Allowed must be disabled, so an illegal
// action (e.g. Steer in awaiting-permission) is never offerable. CanResolve is the second axis (a
// permission allow/deny is legal iff a request is pending — i.e. the AwaitingPermission state).
type stateView struct {
	From       string   `json:"from"`
	To         string   `json:"to"`
	Allowed    []string `json:"allowed"`
	CanResolve bool     `json:"canResolve"`
}

// allowedControlTokens renders agentsession.LegalControls(state) as the lower-kebab wire tokens
// (prompt|steer|abort) the UI keys its controls off — citing the agentsession home, never a re-spelled
// gateway matrix. Always a non-nil slice so the JSON is an array (a terminal state → []).
func allowedControlTokens(state agentsession.State) []string {
	legal := agentsession.LegalControls(state)
	tokens := make([]string, 0, len(legal))
	for _, kind := range legal {
		tokens = append(tokens, kind.String())
	}
	return tokens
}

// messageView projects a message-start / thinking-delta / text-delta / message-end fragment,
// or a thinking-progress heartbeat (Tokens = the running estimated reasoning-token count).
type messageView struct {
	Role  string `json:"role,omitempty"`
	Delta string `json:"delta,omitempty"`
	// Tokens is the running estimated reasoning-token count on a thinking-progress event (the
	// live "thinking…" status), zero/omitted on every message/thinking/text delta.
	Tokens int `json:"tokens,omitempty"`
}

// toolView projects a tool start / update / end (REQ-0024 tool activity). The grant linkage
// and redacted digests carry the audit chain; never a raw secret-bearing argument.
type toolView struct {
	CallID        string `json:"callId,omitempty"`
	Name          string `json:"name,omitempty"`
	GrantID       string `json:"grantId,omitempty"`
	ArgsSummary   string `json:"argsSummary,omitempty"`
	PartialDigest string `json:"partialDigest,omitempty"`
	Outcome       string `json:"outcome,omitempty"`
	ResultDigest  string `json:"resultDigest,omitempty"`
	DurationMs    int64  `json:"durationMs,omitempty"`
	IsHostTool    bool   `json:"isHostTool,omitempty"`
}

// permissionView projects a permission request / resolved record (the human/policy gate).
type permissionView struct {
	RequestID string `json:"requestId"`
	Tool      string `json:"tool,omitempty"`
	Reason    string `json:"reason,omitempty"`
	Decision  string `json:"decision,omitempty"`
	By        string `json:"by,omitempty"`
}

// usageView projects a token/cost tick — ALL FOUR token kinds + per-model attribution, live
// (REQ-0024 token/cost meter). Cost is integer micro-units (no float drift).
type usageView struct {
	Model               string `json:"model,omitempty"`
	Harness             string `json:"harness,omitempty"`
	InputTokens         int64  `json:"inputTokens"`
	OutputTokens        int64  `json:"outputTokens"`
	CacheReadTokens     int64  `json:"cacheReadTokens"`
	CacheCreationTokens int64  `json:"cacheCreationTokens"`
	CostMicros          int64  `json:"costMicros"`
	Cumulative          bool   `json:"cumulative"`
}

// ledgerView projects the authoritative terminal TokenLedger (the final meter the UI
// reconciles against).
type ledgerView struct {
	usageView
	Turns          int32            `json:"turns"`
	ToolUses       int32            `json:"toolUses"`
	WallTimeMs     int64            `json:"wallTimeMs"`
	ToolUsesByName map[string]int32 `json:"toolUsesByName,omitempty"`
}

// terminalView projects a terminal event (result / failed / aborted) and its authoritative
// ledger. The failure Detail is redacted (never a credential) by the library contract.
type terminalView struct {
	Outcome    string     `json:"outcome"`
	ResultText string     `json:"resultText,omitempty"`
	StopReason string     `json:"stopReason,omitempty"`
	Reason     string     `json:"reason,omitempty"`
	Detail     string     `json:"detail,omitempty"`
	By         string     `json:"by,omitempty"`
	Ledger     ledgerView `json:"ledger"`
}

// ── projection functions ─────────────────────────────────────────────────────.

// toAgentView projects an orchestrator.Agent onto the wire DTO (no credential field
// exists on the projection, so a leak is impossible by construction).
//
//nolint:gocritic // Agent is the contract's copyable record; the projector reads it by value.
func toAgentView(agent orchestrator.Agent) agentView {
	return agentView{
		ID:        string(agent.ID),
		Org:       agent.Tenant.OrganizationID,
		Project:   agent.Tenant.ProjectID,
		Template:  agent.Template.String(),
		RunID:     agent.RunID,
		Status:    agent.Status.String(),
		Desired:   agent.Desired.String(),
		By:        agent.By,
		Detail:    agent.Detail,
		CreatedAt: agent.CreatedAt,
		UpdatedAt: agent.UpdatedAt,
		Ledger:    toLedgerView(agent.Ledger),
		CanResume: agent.Status == orchestrator.StatusSuspended || agent.Status == orchestrator.StatusStopped,
	}
}

// toEventView projects an agentsession.Event onto the SSE `data:` DTO, populating exactly
// the sub-payload for the kind. It is the single normalization point between the library
// taxonomy and the wire (one concept, one home).
//
//nolint:gocritic // Event is the contract's copyable value record; the projector reads it by value.
func toEventView(event agentsession.Event) eventView {
	view := eventView{
		SessionID: event.SessionID,
		Seq:       event.Seq,
		Kind:      event.Kind.String(),
		Turn:      event.Turn,
		TurnID:    event.TurnID,
		Time:      event.Time,
		Extension: event.Extension,
	}
	if event.State != nil {
		view.State = &stateView{
			From:       event.State.From.String(),
			To:         event.State.To.String(),
			Allowed:    allowedControlTokens(event.State.To),
			CanResolve: event.State.To == agentsession.StateAwaitingPermission,
		}
	}
	if event.Message != nil {
		view.Message = &messageView{Role: event.Message.Role, Delta: event.Message.Delta, Tokens: event.Message.Tokens}
	}
	if event.Tool != nil {
		view.Tool = toToolView(event.Tool)
	}
	if event.Permission != nil {
		view.Permission = &permissionView{
			RequestID: event.Permission.RequestID,
			Tool:      event.Permission.Tool,
			Reason:    event.Permission.Reason,
			Decision:  grantDecisionToken(event.Permission.Decision),
			By:        event.Permission.By,
		}
	}
	if event.Usage != nil {
		view.Usage = toUsageView(*event.Usage)
	}
	if event.Terminal != nil {
		view.Terminal = toTerminalView(event.Terminal)
	}
	return view
}

// toToolView projects a ToolPayload, rendering the outcome token only for an end event.
func toToolView(tool *agentsession.ToolPayload) *toolView {
	return &toolView{
		CallID:        tool.CallID,
		Name:          tool.Name,
		GrantID:       tool.GrantID,
		ArgsSummary:   tool.ArgsSummary,
		PartialDigest: tool.PartialDigest,
		Outcome:       toolOutcomeToken(tool.Outcome),
		ResultDigest:  tool.ResultDigest,
		DurationMs:    tool.Duration.Milliseconds(),
		IsHostTool:    tool.IsHostTool,
	}
}

// toUsageView projects a UsageMeter (all four token kinds + attribution).
//
//nolint:gocritic // UsageMeter is the contract's copyable value record; the projector reads it by value.
func toUsageView(meter agentsession.UsageMeter) *usageView {
	return &usageView{
		Model:               meter.Model,
		Harness:             meter.Harness,
		InputTokens:         meter.InputTokens,
		OutputTokens:        meter.OutputTokens,
		CacheReadTokens:     meter.CacheReadTokens,
		CacheCreationTokens: meter.CacheCreationTokens,
		CostMicros:          meter.CostMicros,
		Cumulative:          meter.Cumulative,
	}
}

// toLedgerView projects the authoritative TokenLedger.
//
//nolint:gocritic // TokenLedger is the contract's copyable value record; the projector reads it by value.
func toLedgerView(ledger agentsession.TokenLedger) ledgerView {
	return ledgerView{
		usageView:      *toUsageView(ledger.UsageMeter),
		Turns:          ledger.Turns,
		ToolUses:       ledger.ToolUses,
		WallTimeMs:     ledger.WallTime.Milliseconds(),
		ToolUsesByName: ledger.ToolUsesByName,
	}
}

// toTerminalView projects a TerminalPayload + its ledger.
func toTerminalView(terminal *agentsession.TerminalPayload) *terminalView {
	return &terminalView{
		Outcome:    turnOutcomeToken(terminal.Outcome),
		ResultText: terminal.ResultText,
		StopReason: terminal.StopReason,
		Reason:     errorReasonToken(terminal.Reason),
		Detail:     terminal.Detail,
		By:         terminal.By,
		Ledger:     toLedgerView(terminal.Ledger),
	}
}
