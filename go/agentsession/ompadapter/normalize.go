// Package ompadapter is the REAL Oh My Pi (omp) harness adapter for the agentsession F4
// port (ADR-0008): it spawns ONE long-lived `omp --mode rpc` CLI subprocess per session,
// threads the OpenRouter provider key (an opaque secrets.Reference resolved server-side) onto
// the CHILD process env under OPENROUTER_API_KEY ONLY (never Eden's env, never a log), and
// NORMALIZES omp's frame stream into the Eden Event taxonomy. The wiring (arg/env
// construction, json parsing) is unit-tested with fixtures captured from a live omp run and
// against the stub subprocess under `-tags integration`. The LIVE omp turn is proven in the
// harness/acceptance lane only — agentsession/omp_turn_harness_test.go under
// `//go:build harness` (run via `ctl.sh harness`), FAIL-NOT-SKIP by that lane's contract.
// This package carries no live arm and no skip (Mateo's ruling, 2026-08-26; task #24 tracks
// the omp 17.2.5 rpc deadlock).
//
// Mode choice: rpc, not json. `--mode json` is a clean ONE-WAY stream, but it is also ONE
// PROCESS PER TURN — a session that exits after its turn cannot serve a second Prompt, cannot
// hold set_host_tools, and cannot take an injected turn. `--mode rpc` keeps one process alive
// across every turn: NDJSON commands on stdin, frames on stdout, readiness announced by omp's
// own `ready` frame. Its bidirectional traffic is answered rather than avoided (rpc.go):
// the fire-and-forget widget requests are ignored, and the dialogs — which carry no timeout
// and therefore wait forever — are answered on arrival. Never `--mode rpc-ui`: that mode
// installs the tool UI context (main.ts:1570) and is the plane a tool can block on.
package ompadapter

import (
	"encoding/json"

	"github.com/gophersys/libs/go/agentsession"
)

// harnessName is the Eden adapter key for this harness.
const harnessName = "omp"

// frame is the outer omp json envelope every line shares. Unknown top-level `type`s are
// preserved verbatim as EventExtension (never dropped, never fatal — forward-compat).
type frame struct {
	Type string `json:"type"`

	// startup metadata; the readiness signal is the rpc `ready` frame, handled in rpc.go.
	ID string `json:"id"`

	// message_start / message_end / turn_end / agent_end carry a message snapshot.
	Message *ompMessage `json:"message"`

	// message_update carries the streaming delta envelope.
	AssistantMessageEvent *assistantEvent `json:"assistantMessageEvent"`

	// tool_execution_start / tool_execution_end (the top-level, clean tool signal).
	ToolCallID string          `json:"toolCallId"`
	ToolName   string          `json:"toolName"`
	Args       json.RawMessage `json:"args"`
	Intent     string          `json:"intent"`
	Result     json.RawMessage `json:"result"`
	IsError    *bool           `json:"isError"`

	// agent_end carries the full message list (the terminal aggregate); the last assistant
	// message is the authoritative result.
	Messages []ompMessage `json:"messages"`
}

// ompMessage is an omp message snapshot (user echo or assistant). The assistant variant
// carries the model attribution, the four-token usage+cost, and a stopReason that flips a
// terminal between result and failed.
type ompMessage struct {
	Role        string         `json:"role"`
	Content     []contentBlock `json:"content"`
	Model       string         `json:"model"`
	Provider    string         `json:"provider"`
	Usage       *ompUsage      `json:"usage"`
	StopReason  string         `json:"stopReason"`
	ErrorStatus int            `json:"errorStatus"`
	Duration    int64          `json:"duration"`
}

// contentBlock is one structural block in an omp message (text / thinking).
type contentBlock struct {
	Type     string `json:"type"`
	Text     string `json:"text"`
	Thinking string `json:"thinking"`
}

// assistantEvent is the message_update streaming delta. `type` is the stream phase
// (thinking_start/thinking_delta/thinking_end, text_start/text_delta/text_end,
// toolcall_start/toolcall_delta/toolcall_end); `delta` carries the incremental fragment.
type assistantEvent struct {
	Type     string `json:"type"`
	Delta    string `json:"delta"`
	Content  string `json:"content"`
	ToolCall *struct {
		ID        string          `json:"id"`
		Name      string          `json:"name"`
		Arguments json.RawMessage `json:"arguments"`
	} `json:"toolCall"`
}

// ompUsage is the four-token accounting omp reports on every assistant usage block plus the
// cost split (USD floats). totalTokens/reasoningTokens are derived; cost.total is the
// authoritative spend the ledger converts to micro-units.
type ompUsage struct {
	Input      int64   `json:"input"`
	Output     int64   `json:"output"`
	CacheRead  int64   `json:"cacheRead"`
	CacheWrite int64   `json:"cacheWrite"`
	Cost       ompCost `json:"cost"`
}

// ompCost is the USD cost split omp reports inside usage.
type ompCost struct {
	Total float64 `json:"total"`
}

// normalizer maps omp json frames onto the Eden Event taxonomy. It is the adapter's only
// knowledge of the vendor wire format (05 §1) and is pure: it allocates Events from bytes,
// performs NO I/O, and stamps no Seq (the library owns Seq). It threads model attribution
// across frames exactly as a live session does, and remembers the latest assistant snapshot
// so agent_end can emit the authoritative terminal even though that frame's own messages
// list is the source of truth.
type normalizer struct {
	model   string // model attribution learned from the first assistant frame
	digest  digester
	lastMsg *ompMessage // the most recent assistant snapshot (for the terminal aggregate)
}

// newNormalizer builds a normalizer with a bounded-digest redactor.
func newNormalizer() *normalizer { return &normalizer{digest: defaultDigester} }

// normalize maps one omp json line to zero or more Events. A line that does not parse, or
// whose type Eden does not model, becomes an EventExtension carrying the raw bytes verbatim —
// never dropped, never fatal. The returned events are pre-Seq; the library stamps Seq.
func (n *normalizer) normalize(line []byte) []agentsession.Event {
	var f frame
	if err := json.Unmarshal(line, &f); err != nil {
		return []agentsession.Event{extension(line)}
	}
	switch f.Type {
	case "session", "agent_start", "turn_start":
		// Lifecycle chrome / startup metadata, preserved as Extension so nothing is dropped.
		// (`session` belongs to the retired one-process-per-turn print mode, which announced one
		// per PROCESS; an rpc session announces none.)
		return []agentsession.Event{extension(line)}
	case "ready", "response", "notice", "available_commands_update",
		"extension_ui_request", "host_tool_call", "host_tool_cancel":
		// The rpc CONTROL plane. rpc.go acts on these (readiness + protocol negotiation, the
		// host-tool round trip, the dialog answer); the taxonomy has no distinct kind for a
		// control frame, so each is ALSO surfaced verbatim as Extension — known and preserved,
		// rather than silently consumed by the layer that serviced it.
		return []agentsession.Event{extension(line)}
	case "message_start":
		return n.messageStart(&f, line)
	case "message_update":
		return n.messageUpdate(&f, line)
	case "message_end":
		return n.messageEnd(&f, line)
	case "tool_execution_start":
		return []agentsession.Event{n.toolStart(&f)}
	case "tool_execution_end":
		return []agentsession.Event{n.toolEnd(&f)}
	case "turn_end":
		return n.turnEnd(&f, line)
	case "agent_end":
		return []agentsession.Event{n.agentEnd(&f, line)}
	default:
		return []agentsession.Event{extension(line)}
	}
}

// messageStart maps a message_start frame. The user-role echo is dropped (it is Eden's own
// prompt reflected back); the assistant variant opens an assistant message and learns the
// model attribution.
func (n *normalizer) messageStart(f *frame, line []byte) []agentsession.Event {
	if f.Message == nil {
		return []agentsession.Event{extension(line)}
	}
	if f.Message.Role == "user" {
		return nil
	}
	if f.Message.Model != "" {
		n.model = f.Message.Model
	}
	n.lastMsg = f.Message
	return []agentsession.Event{{
		Kind:    agentsession.EventMessageStart,
		Message: &agentsession.MessagePayload{Role: roleOr(f.Message.Role, "assistant")},
	}}
}

// messageUpdate maps a message_update frame's streaming delta to the matching delta Kind.
// thinking_delta -> EventThinkingDelta, text_delta -> EventTextDelta, toolcall_delta ->
// EventToolUpdate (the partial-result stream). The *_start/*_end phases carry no incremental
// payload Eden models distinctly, so they survive as Extension (the occurrence is preserved,
// never dropped).
func (n *normalizer) messageUpdate(f *frame, line []byte) []agentsession.Event {
	ev := f.AssistantMessageEvent
	if ev == nil {
		return []agentsession.Event{extension(line)}
	}
	switch ev.Type {
	case "thinking_delta":
		return []agentsession.Event{{
			Kind:    agentsession.EventThinkingDelta,
			Message: &agentsession.MessagePayload{Role: "assistant", Delta: ev.Delta},
		}}
	case "text_delta":
		return []agentsession.Event{{
			Kind:    agentsession.EventTextDelta,
			Message: &agentsession.MessagePayload{Role: "assistant", Delta: ev.Delta},
		}}
	case "toolcall_delta":
		return []agentsession.Event{{
			Kind: agentsession.EventToolUpdate,
			Tool: &agentsession.ToolPayload{PartialDigest: n.digest([]byte(ev.Delta))},
		}}
	default:
		// thinking_start/thinking_end/text_start/text_end/toolcall_start/toolcall_end: keep the
		// raw phase as Extension so the reasoning/tool track boundaries survive losslessly.
		return []agentsession.Event{extension(line)}
	}
}

// messageEnd maps a message_end frame. The user echo is dropped; the assistant variant emits
// EventMessageEnd plus a per-message usage tick (the running delta meter — the authoritative
// cumulative totals ride the terminal).
func (n *normalizer) messageEnd(f *frame, line []byte) []agentsession.Event {
	if f.Message == nil {
		return []agentsession.Event{extension(line)}
	}
	if f.Message.Role == "user" {
		return nil
	}
	n.lastMsg = f.Message
	events := []agentsession.Event{{Kind: agentsession.EventMessageEnd}}
	if f.Message.Usage != nil {
		events = append(events, n.usageTick(f.Message.Usage))
	}
	return events
}

// toolStart maps a top-level tool_execution_start to EventToolStart. The args summary is
// digested (bounded + redacted), never the raw arguments.
func (n *normalizer) toolStart(f *frame) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventToolStart,
		Tool: &agentsession.ToolPayload{
			CallID:      f.ToolCallID,
			Name:        f.ToolName,
			ArgsSummary: n.digest(f.Args),
		},
	}
}

// toolEnd maps a top-level tool_execution_end to EventToolEnd, correlated by ToolCallID. The
// result is digested (bounded + redacted), never the raw content; isError flips the outcome.
func (n *normalizer) toolEnd(f *frame) agentsession.Event {
	outcome := agentsession.ToolOutcomeOK
	if f.IsError != nil && *f.IsError {
		outcome = agentsession.ToolOutcomeError
	}
	return agentsession.Event{
		Kind: agentsession.EventToolEnd,
		Tool: &agentsession.ToolPayload{
			CallID:       f.ToolCallID,
			Name:         f.ToolName,
			Outcome:      outcome,
			ResultDigest: n.digest(f.Result),
		},
	}
}

// turnEnd maps a turn_end frame to a per-turn usage tick (delta). The frame's own message
// snapshot is remembered so agent_end can finalize even if it carries no messages list.
func (n *normalizer) turnEnd(f *frame, line []byte) []agentsession.Event {
	if f.Message == nil {
		return []agentsession.Event{extension(line)}
	}
	n.lastMsg = f.Message
	if f.Message.Usage == nil {
		return nil
	}
	return []agentsession.Event{n.usageTick(f.Message.Usage)}
}

// agentEnd maps the agent_end frame to EventTurnEnd or the session-terminal EventFailed,
// carrying the authoritative four-token TokenLedger built from the final assistant message. A
// stopReason of "error" (with the upstream HTTP errorStatus) yields a classified EventFailed;
// otherwise a TURN boundary with the final assistant text.
//
// A clean agent_end ends the TURN, not the session: one rpc process serves every turn, so the
// conn — and the session on it — stay alive for the next Prompt, which rides a stdin frame.
func (n *normalizer) agentEnd(f *frame, line []byte) agentsession.Event {
	final := n.finalAssistant(f)
	if final == nil {
		// No assistant message ever materialized: surface the terminal frame verbatim rather
		// than fabricating a result.
		return extension(line)
	}
	if final.Model != "" {
		n.model = final.Model
	}
	ledger := n.ledger(final)
	if final.StopReason == "error" {
		return agentsession.Event{
			Kind: agentsession.EventFailed,
			Terminal: &agentsession.TerminalPayload{
				Outcome:    agentsession.TurnFailed,
				Ledger:     ledger,
				Reason:     reasonFromErrorStatus(final.ErrorStatus),
				Detail:     statusDetail(final.ErrorStatus),
				StopReason: final.StopReason,
			},
		}
	}
	return agentsession.Event{
		Kind: agentsession.EventTurnEnd,
		Terminal: &agentsession.TerminalPayload{
			Outcome:    agentsession.TurnCompleted,
			Ledger:     ledger,
			ResultText: assistantText(final),
			StopReason: final.StopReason,
		},
	}
}

// finalAssistant resolves the authoritative final assistant message for the terminal: the
// last assistant entry in agent_end's messages list when present, else the most recent
// assistant snapshot threaded across the stream.
func (n *normalizer) finalAssistant(f *frame) *ompMessage {
	for i := len(f.Messages) - 1; i >= 0; i-- {
		if f.Messages[i].Role == "assistant" {
			return &f.Messages[i]
		}
	}
	return n.lastMsg
}

// ledger builds the authoritative cumulative TokenLedger from the final assistant message's
// four-token usage and USD cost. CostMicros is converted with no float drift; an absent
// usage block leaves the -1 "unreported" cost sentinel.
func (n *normalizer) ledger(msg *ompMessage) agentsession.TokenLedger {
	ledger := agentsession.TokenLedger{
		UsageMeter: agentsession.UsageMeter{
			Model: n.model, Harness: harnessName, CostMicros: -1, Cumulative: true,
		},
		Turns: 1,
	}
	if msg.Usage != nil {
		ledger.InputTokens = msg.Usage.Input
		ledger.OutputTokens = msg.Usage.Output
		ledger.CacheReadTokens = msg.Usage.CacheRead
		ledger.CacheCreationTokens = msg.Usage.CacheWrite
		ledger.CostMicros = usdToMicros(msg.Usage.Cost.Total)
	}
	if msg.Duration > 0 {
		ledger.WallTime = millisToDuration(msg.Duration)
	}
	return ledger
}

// usageTick builds a per-message/per-turn (delta) EventUsage from an omp usage block. The
// terminal carries the authoritative cumulative totals; these ticks are the running deltas
// the live meter renders, attributed to the model with the USD cost converted to micros.
func (n *normalizer) usageTick(u *ompUsage) agentsession.Event {
	meter := &agentsession.UsageMeter{
		Model: n.model, Harness: harnessName,
		InputTokens:         u.Input,
		OutputTokens:        u.Output,
		CacheReadTokens:     u.CacheRead,
		CacheCreationTokens: u.CacheWrite,
		CostMicros:          usdToMicros(u.Cost.Total),
		Cumulative:          false,
	}
	return agentsession.Event{Kind: agentsession.EventUsage, Usage: meter}
}

// assistantText concatenates the text blocks of an assistant message into the final result
// text (thinking blocks are excluded — reasoning is its own track).
func assistantText(msg *ompMessage) string {
	var text string
	for i := range msg.Content {
		if msg.Content[i].Type == "text" {
			text += msg.Content[i].Text
		}
	}
	return text
}

// extension wraps a raw line as a verbatim EventExtension (forward-compat).
func extension(line []byte) agentsession.Event {
	raw := make([]byte, len(line))
	copy(raw, line)
	return agentsession.Event{Kind: agentsession.EventExtension, Extension: raw}
}

// roleOr returns role or a fallback when empty.
func roleOr(role, fallback string) string {
	if role == "" {
		return fallback
	}
	return role
}
