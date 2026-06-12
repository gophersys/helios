// Package ledger parses the stream-json transcript emitted by a headless
// Claude Code session and folds it into a token/cost ledger.
//
// The parser is deliberately forward-compatible: every line is first decoded
// into a loosely-typed Event whose unknown fields survive, and only the event
// types we understand are interpreted. An event type we have never seen does
// not break parsing — it is counted and ignored. This matters because the
// observed stream already carries types beyond the documented set (for example
// rate_limit_event), and the real codingharness must not crash when Claude Code
// adds more.
package ledger

import (
	"encoding/json"
)

// Event is one decoded line of the stream-json transcript. Only the fields the
// ledger interprets are named; everything else is preserved verbatim in Raw so
// nothing is lost and unknown shapes do not fail decoding.
type Event struct {
	Type    string          `json:"type"`
	Subtype string          `json:"subtype"`
	Message json.RawMessage `json:"message"`

	// Result-event fields (present only when Type == "result").
	IsError          *bool           `json:"is_error"`
	NumTurns         *int            `json:"num_turns"`
	DurationMillis   *int64          `json:"duration_ms"`
	TotalCostUSD     *float64        `json:"total_cost_usd"`
	ResultText       string          `json:"result"`
	StopReason       string          `json:"stop_reason"`
	Usage            *Usage          `json:"usage"`
	PermissionDenied json.RawMessage `json:"permission_denials"`

	Raw json.RawMessage `json:"-"`
}

// Usage is the token accounting shared by per-message assistant events and the
// aggregate result event. Cache fields are first-class because cache economics
// dominate the real cost of an agent loop.
type Usage struct {
	InputTokens              int `json:"input_tokens"`
	OutputTokens             int `json:"output_tokens"`
	CacheReadInputTokens     int `json:"cache_read_input_tokens"`
	CacheCreationInputTokens int `json:"cache_creation_input_tokens"`
}

// assistantMessage is the inner message envelope on assistant/user events.
type assistantMessage struct {
	Model   string `json:"model"`
	Usage   *Usage `json:"usage"`
	Content []struct {
		Type string `json:"type"`
		Name string `json:"name"`
	} `json:"content"`
}

// Decode parses a single transcript line into an Event, retaining the raw bytes.
// A line that is not valid JSON is reported via the returned error; the caller
// decides whether to skip or fail.
func Decode(line []byte) (Event, error) {
	var event Event
	if err := json.Unmarshal(line, &event); err != nil {
		return Event{Raw: append([]byte(nil), line...)}, err
	}
	event.Raw = append([]byte(nil), line...)
	return event, nil
}

// Ledger is the folded summary of a session. It is the spike's return value:
// the one-line JSON the kernel's real harness will eventually carry on every Run.
type Ledger struct {
	Succeeded    bool   `json:"succeeded"`
	StopReason   string `json:"stop_reason,omitempty"`
	ResultText   string `json:"result_text"`
	Turns        int    `json:"turns"`
	ToolUses     int    `json:"tool_uses"`
	EventCount   int    `json:"event_count"`
	UnknownTypes int    `json:"unknown_event_types"`

	InputTokens         int `json:"input_tokens"`
	OutputTokens        int `json:"output_tokens"`
	CacheReadTokens     int `json:"cache_read_tokens"`
	CacheCreationTokens int `json:"cache_creation_tokens"`

	TotalCostUSD  float64        `json:"total_cost_usd"`
	WallMillis    int64          `json:"wall_ms"`
	SessionMillis int64          `json:"session_reported_ms,omitempty"`
	ToolUseByName map[string]int `json:"tool_use_by_name"`
}

// knownTypes are the event types the fold interprets. Anything else is counted
// as an unknown type but never causes a failure.
var knownTypes = map[string]bool{
	"system":    true,
	"assistant": true,
	"user":      true,
	"result":    true,
}

// Folder accumulates events into a Ledger. Token totals are taken from the
// authoritative aggregate carried on the result event; tool uses and the
// known/unknown type split are derived by walking every assistant message.
type Folder struct {
	ledger    Ledger
	sawResult bool
}

// NewFolder returns a fold ready to consume events.
func NewFolder() *Folder {
	return &Folder{ledger: Ledger{ToolUseByName: map[string]int{}}}
}

// Add folds one event into the running ledger.
func (folder *Folder) Add(event Event) {
	folder.ledger.EventCount++
	if !knownTypes[event.Type] {
		folder.ledger.UnknownTypes++
		return
	}

	switch event.Type {
	case "assistant":
		folder.foldAssistant(event)
	case "result":
		folder.foldResult(event)
	}
}

func (folder *Folder) foldAssistant(event Event) {
	if len(event.Message) == 0 {
		return
	}
	var message assistantMessage
	if err := json.Unmarshal(event.Message, &message); err != nil {
		return
	}
	for _, block := range message.Content {
		if block.Type == "tool_use" {
			folder.ledger.ToolUses++
			name := block.Name
			if name == "" {
				name = "unknown"
			}
			folder.ledger.ToolUseByName[name]++
		}
	}
}

func (folder *Folder) foldResult(event Event) {
	folder.sawResult = true
	if event.NumTurns != nil {
		folder.ledger.Turns = *event.NumTurns
	}
	if event.DurationMillis != nil {
		folder.ledger.SessionMillis = *event.DurationMillis
	}
	if event.TotalCostUSD != nil {
		folder.ledger.TotalCostUSD = *event.TotalCostUSD
	}
	folder.ledger.ResultText = event.ResultText
	folder.ledger.StopReason = event.StopReason
	// A result event reports success unless is_error is true and the subtype is
	// not "success". The subtype carries the failure class (error_max_turns,
	// error_during_execution, ...).
	folder.ledger.Succeeded = event.Subtype == "success" && (event.IsError == nil || !*event.IsError)
	if event.Usage != nil {
		folder.ledger.InputTokens = event.Usage.InputTokens
		folder.ledger.OutputTokens = event.Usage.OutputTokens
		folder.ledger.CacheReadTokens = event.Usage.CacheReadInputTokens
		folder.ledger.CacheCreationTokens = event.Usage.CacheCreationInputTokens
	}
}

// Finish stamps the measured wall time and returns the folded ledger. If no
// result event was ever seen the session is treated as failed regardless of
// what else streamed, which is the safe default for a headless run.
func (folder *Folder) Finish(wallMillis int64) Ledger {
	folder.ledger.WallMillis = wallMillis
	if !folder.sawResult {
		folder.ledger.Succeeded = false
		if folder.ledger.StopReason == "" {
			folder.ledger.StopReason = "no_result_event"
		}
	}
	return folder.ledger
}
