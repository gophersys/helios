// Package claudeadapter is the REAL claude-code harness adapter for the agentsession
// F4 port (ADR-0008): it spawns the headless `claude` CLI subprocess, threads the
// setup-token credential as an opaque secrets.Reference resolved server-side and placed
// on the CHILD process env only (never Eden's env, never a log), and NORMALIZES the
// CLI's stream-json output into the Eden Event taxonomy. The wiring (arg/env
// construction, stream-json parsing) is unit-tested with sample fixtures; the LIVE
// authenticated run is GATED on a real setup-token and is NOT executed in any test.
package claudeadapter

import (
	"encoding/json"

	"github.com/gophersys/libs/go/agentsession"
)

// harnessName is the Eden adapter key for this harness.
const harnessName = "claude-code"

// streamLine is the outer stream-json envelope every Claude Code CLI line shares (the
// shape measured in poc/codingharness/internal/ledger). Unknown `type`s are preserved
// verbatim as EventExtension (the rate_limit_event lesson — never dropped, never fatal).
type streamLine struct {
	Type    string          `json:"type"`
	Subtype string          `json:"subtype"`
	Message json.RawMessage `json:"message"`

	// result-line fields (the authoritative terminal aggregate).
	IsError        *bool    `json:"is_error"`
	NumTurns       *int     `json:"num_turns"`
	DurationMillis *int64   `json:"duration_ms"`
	TotalCostUSD   *float64 `json:"total_cost_usd"`
	ResultText     string   `json:"result"`
	StopReason     string   `json:"stop_reason"`
	Usage          *usage   `json:"usage"`
}

// usage is the four-token accounting shared by per-message assistant events and the
// terminal result (the cache-creation/cache-read split is load-bearing for FinOps).
type usage struct {
	InputTokens              int `json:"input_tokens"`
	OutputTokens             int `json:"output_tokens"`
	CacheReadInputTokens     int `json:"cache_read_input_tokens"`
	CacheCreationInputTokens int `json:"cache_creation_input_tokens"`
}

// assistantMessage is the inner envelope on assistant/user lines.
type assistantMessage struct {
	Model      string         `json:"model"`
	Role       string         `json:"role"`
	StopReason string         `json:"stop_reason"`
	Usage      *usage         `json:"usage"`
	Content    []contentBlock `json:"content"`
}

// contentBlock is one structural block in an assistant message (text / thinking /
// tool_use) or a user message (tool_result).
type contentBlock struct {
	Type      string          `json:"type"`
	Text      string          `json:"text"`
	Thinking  string          `json:"thinking"`
	ID        string          `json:"id"`
	Name      string          `json:"name"`
	Input     json.RawMessage `json:"input"`
	ToolUseID string          `json:"tool_use_id"`
	Content   json.RawMessage `json:"content"`
	IsError   *bool           `json:"is_error"`
}

// normalizer maps Claude Code stream-json lines onto the Eden Event taxonomy. It is the
// adapter's only knowledge of the vendor wire format (05 §1) and is pure: it allocates
// Events from bytes, performs NO I/O, and stamps no Seq (the library owns Seq). It is
// unit-tested against real fixture lines.
type normalizer struct {
	model  string // the model attribution (learned from the first assistant/init line)
	digest digester
}

// newNormalizer builds a normalizer with a bounded-digest redactor.
func newNormalizer() *normalizer { return &normalizer{digest: defaultDigester} }

// normalize maps one stream-json line to zero or more Events. A line that does not
// parse, or whose type Eden does not model, becomes an EventExtension carrying the raw
// bytes verbatim — never dropped, never fatal (forward-compat). The returned events are
// pre-Seq; the library stamps Seq and fans them out.
func (n *normalizer) normalize(line []byte) []agentsession.Event {
	var envelope streamLine
	if err := json.Unmarshal(line, &envelope); err != nil {
		return []agentsession.Event{extension(line)}
	}
	switch envelope.Type {
	case "system":
		return n.system(&envelope, line)
	case "assistant":
		return n.assistant(&envelope, line)
	case "user":
		return n.user(&envelope)
	case "result":
		return []agentsession.Event{n.result(&envelope)}
	default:
		// An unmodeled type (e.g. rate_limit_event) survives verbatim.
		return []agentsession.Event{extension(line)}
	}
}

// system maps the init line to the Ready handshake transition (the success signal the
// library requires — its absence is the silent-bad-token trap). Non-init system lines
// are preserved as Extension.
func (n *normalizer) system(envelope *streamLine, line []byte) []agentsession.Event {
	if envelope.Subtype != "init" {
		return []agentsession.Event{extension(line)}
	}
	return []agentsession.Event{{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}}
}

// assistant maps an assistant line to message-start + per-block deltas + tool starts +
// an optional usage tick. Text and thinking blocks become their distinct delta Kinds;
// tool_use blocks become EventToolStart (the args summary is redacted/bounded). The
// per-message usage rides as a delta EventUsage tick.
func (n *normalizer) assistant(envelope *streamLine, line []byte) []agentsession.Event {
	var message assistantMessage
	if len(envelope.Message) == 0 || json.Unmarshal(envelope.Message, &message) != nil {
		return []agentsession.Event{extension(line)}
	}
	if message.Model != "" {
		n.model = message.Model
	}
	events := []agentsession.Event{{
		Kind:    agentsession.EventMessageStart,
		Message: &agentsession.MessagePayload{Role: roleOr(message.Role, "assistant")},
	}}
	for i := range message.Content {
		if event, ok := n.block(&message.Content[i]); ok {
			events = append(events, event)
		}
	}
	if message.Usage != nil {
		events = append(events, n.usageTick(message.Usage))
	}
	events = append(events, agentsession.Event{Kind: agentsession.EventMessageEnd})
	return events
}

// block maps one assistant content block to an Event (text/thinking delta or tool
// start). ok=false for an empty/ignorable block.
func (n *normalizer) block(block *contentBlock) (agentsession.Event, bool) {
	switch block.Type {
	case "text":
		if block.Text == "" {
			return agentsession.Event{}, false
		}
		return agentsession.Event{
			Kind:    agentsession.EventTextDelta,
			Message: &agentsession.MessagePayload{Role: "assistant", Delta: block.Text},
		}, true
	case "thinking":
		// A thinking block is emitted even when its text is empty/redacted (the CLI emits
		// signed-but-empty reasoning blocks): the UI folds the reasoning track, and a
		// retention policy treats thinking distinctly — so the OCCURRENCE matters, not just
		// the bytes. The delta carries whatever reasoning text was present.
		return agentsession.Event{
			Kind:    agentsession.EventThinkingDelta,
			Message: &agentsession.MessagePayload{Role: "assistant", Delta: block.Thinking},
		}, true
	case "tool_use":
		return agentsession.Event{
			Kind: agentsession.EventToolStart,
			Tool: &agentsession.ToolPayload{
				CallID:      block.ID,
				Name:        block.Name,
				ArgsSummary: n.digest(block.Input),
			},
		}, true
	default:
		return agentsession.Event{}, false
	}
}

// user maps a user line (a tool_result echo) to EventToolEnd, correlated by ToolUseID.
// The result is digested (bounded + redacted), never the raw content.
func (n *normalizer) user(envelope *streamLine) []agentsession.Event {
	var message assistantMessage
	if len(envelope.Message) == 0 || json.Unmarshal(envelope.Message, &message) != nil {
		return nil
	}
	var events []agentsession.Event
	for i := range message.Content {
		block := &message.Content[i]
		if block.Type != "tool_result" {
			continue
		}
		outcome := agentsession.ToolOutcomeOK
		if block.IsError != nil && *block.IsError {
			outcome = agentsession.ToolOutcomeError
		}
		events = append(events, agentsession.Event{
			Kind: agentsession.EventToolEnd,
			Tool: &agentsession.ToolPayload{
				CallID:       block.ToolUseID,
				Outcome:      outcome,
				ResultDigest: n.digest(block.Content),
			},
		})
	}
	return events
}

// result maps the terminal result line to EventResult (success) or EventFailed (error),
// carrying the authoritative four-token TokenLedger. CostMicros is converted from the
// reported USD with no float drift (round to the nearest micro-unit).
func (n *normalizer) result(envelope *streamLine) agentsession.Event {
	ledger := agentsession.TokenLedger{
		UsageMeter: agentsession.UsageMeter{
			Model: n.model, Harness: harnessName, CostMicros: -1, Cumulative: true,
		},
	}
	if envelope.Usage != nil {
		ledger.InputTokens = int64(envelope.Usage.InputTokens)
		ledger.OutputTokens = int64(envelope.Usage.OutputTokens)
		ledger.CacheReadTokens = int64(envelope.Usage.CacheReadInputTokens)
		ledger.CacheCreationTokens = int64(envelope.Usage.CacheCreationInputTokens)
	}
	if envelope.TotalCostUSD != nil {
		ledger.CostMicros = usdToMicros(*envelope.TotalCostUSD)
	}
	if envelope.NumTurns != nil {
		ledger.Turns = int32(*envelope.NumTurns)
	}
	if envelope.DurationMillis != nil {
		ledger.WallTime = millisToDuration(*envelope.DurationMillis)
	}

	failed := (envelope.IsError != nil && *envelope.IsError) || envelope.Subtype != "success"
	if failed {
		return agentsession.Event{
			Kind: agentsession.EventFailed,
			Terminal: &agentsession.TerminalPayload{
				Outcome:    agentsession.TurnFailed,
				Ledger:     ledger,
				Reason:     reasonFromSubtype(envelope.Subtype),
				Detail:     subtypeDetail(envelope.Subtype),
				StopReason: envelope.StopReason,
			},
		}
	}
	return agentsession.Event{
		Kind: agentsession.EventResult,
		Terminal: &agentsession.TerminalPayload{
			Outcome:    agentsession.TurnCompleted,
			Ledger:     ledger,
			ResultText: envelope.ResultText,
			StopReason: envelope.StopReason,
		},
	}
}

// usageTick builds a per-message (delta) EventUsage from an assistant usage block. The
// terminal result carries the authoritative cumulative totals; these per-message ticks
// are the running deltas the live meter renders. Cost is unreported per-message (-1); it
// arrives on the result line as total_cost_usd.
func (n *normalizer) usageTick(u *usage) agentsession.Event {
	meter := &agentsession.UsageMeter{
		Model: n.model, Harness: harnessName,
		InputTokens:         int64(u.InputTokens),
		OutputTokens:        int64(u.OutputTokens),
		CacheReadTokens:     int64(u.CacheReadInputTokens),
		CacheCreationTokens: int64(u.CacheCreationInputTokens),
		CostMicros:          -1,
		Cumulative:          false,
	}
	return agentsession.Event{Kind: agentsession.EventUsage, Usage: meter}
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
