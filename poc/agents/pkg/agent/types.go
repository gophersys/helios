// Package agent implements a Go runtime for OMP (Oh My Pi) coding agents
// via the RPC stdio protocol. It provides lifecycle management, metrics,
// supervisor-worker bridging, and HTTP API surfaces for embedding.
package agent

import (
	"encoding/json"
	"time"
)

// ──────────────────────────────────────────────
//  Agent lifecycle states
// ──────────────────────────────────────────────

type AgentState string

const (
	StateCreated      AgentState = "created"
	StateInitializing AgentState = "initializing"
	StateReady        AgentState = "ready"
	StateRunning      AgentState = "running"
	StatePaused       AgentState = "paused"
	StateCompleted    AgentState = "completed"
	StateFailed       AgentState = "failed"
	StateCancelled    AgentState = "cancelled"
)

// ──────────────────────────────────────────────
//  OMP RPC protocol: inbound frames (stdin)
// ──────────────────────────────────────────────

type RpcCommand struct {
	ID      string          `json:"id,omitempty"`
	Type    string          `json:"type"`
	Message string          `json:"message,omitempty"`
	Phases  json.RawMessage `json:"phases,omitempty"`
	Tools   json.RawMessage `json:"tools,omitempty"`
	Mode    string          `json:"mode,omitempty"`
	Enabled *bool           `json:"enabled,omitempty"`
	Level   string          `json:"level,omitempty"`
	// Additional fields passed through
	Provider string `json:"provider,omitempty"`
	ModelID  string `json:"modelId,omitempty"`
	Name     string `json:"name,omitempty"`
}

// ──────────────────────────────────────────────
//  OMP RPC protocol: outbound frames (stdout)
// ──────────────────────────────────────────────

type RpcFrame struct {
	Type string `json:"type"`

	// Response fields
	ID      string          `json:"id,omitempty"`
	Command string          `json:"command,omitempty"`
	Success *bool           `json:"success,omitempty"`
	Error   string          `json:"error,omitempty"`
	Data    json.RawMessage `json:"data,omitempty"`

	// Agent event fields
	AgentEventType string          `json:"agent_event_type,omitempty"`
	MessageEvent   json.RawMessage `json:"assistantMessageEvent,omitempty"`
	Message        json.RawMessage `json:"message,omitempty"`

	// Tool events
	ToolName       string `json:"toolName,omitempty"`
	ToolCallID     string `json:"toolCallId,omitempty"`

	// Extension UI
	Method  string `json:"method,omitempty"`
	Title   string `json:"title,omitempty"`

	// Host tool protocol
	ToolCall      json.RawMessage `json:"toolCall,omitempty"`
	Arguments     json.RawMessage `json:"arguments,omitempty"`
	PartialResult json.RawMessage `json:"partialResult,omitempty"`
	Result        json.RawMessage `json:"result,omitempty"`
	TargetID      string          `json:"targetId,omitempty"`
}

// ──────────────────────────────────────────────
//  AgentSessionEvent subset we care about
// ──────────────────────────────────────────────

type AgentEventType string

const (
	EventAgentStart           AgentEventType = "agent_start"
	EventAgentEnd             AgentEventType = "agent_end"
	EventTurnStart            AgentEventType = "turn_start"
	EventTurnEnd              AgentEventType = "turn_end"
	EventMessageUpdate        AgentEventType = "message_update"
	EventMessageStart         AgentEventType = "message_start"
	EventMessageEnd           AgentEventType = "message_end"
	EventToolExecStart        AgentEventType = "tool_execution_start"
	EventToolExecUpdate       AgentEventType = "tool_execution_update"
	EventToolExecEnd          AgentEventType = "tool_execution_end"
	EventAutoCompactStart     AgentEventType = "auto_compaction_start"
	EventAutoCompactEnd       AgentEventType = "auto_compaction_end"
	EventAutoRetryStart       AgentEventType = "auto_retry_start"
	EventAutoRetryEnd         AgentEventType = "auto_retry_end"
	EventTTSRTriggered        AgentEventType = "ttsr_triggered"
	EventTodoReminder         AgentEventType = "todo_reminder"
	EventTodoAutoClear        AgentEventType = "todo_auto_clear"
	EventHostToolCall         AgentEventType = "host_tool_call"
	EventHostToolCancel       AgentEventType = "host_tool_cancel"
	EventExtUIRequest         AgentEventType = "extension_ui_request"
	EventExtError             AgentEventType = "extension_error"
)

// ──────────────────────────────────────────────
//  Metrics & Telemetry
// ──────────────────────────────────────────────

type MetricType string

const (
	MetricLLM             MetricType = "llm"
	MetricToolCall        MetricType = "tool_call"
	MetricToolResult      MetricType = "tool_result"
	MetricFileSystem      MetricType = "filesystem"
	MetricEvent           MetricType = "agent_event"
	MetricStateTransition MetricType = "state_transition"
	MetricCost            MetricType = "cost"
	MetricError           MetricType = "error"
)

type Metric struct {
	ID        string            `json:"id"`
	AgentID   string            `json:"agent_id"`
	Type      MetricType        `json:"type"`
	Timestamp time.Time         `json:"timestamp"`
	Duration  time.Duration     `json:"duration_ns,omitempty"`
	Labels    map[string]string `json:"labels,omitempty"`
	Payload   json.RawMessage   `json:"payload,omitempty"`
	// Convenience fields
	ToolName      string  `json:"tool_name,omitempty"`
	ModelID       string  `json:"model_id,omitempty"`
	InputTokens   int64   `json:"input_tokens"`
	OutputTokens  int64   `json:"output_tokens"`
	CostUSD       float64 `json:"cost_usd"`
	// Lifecycle counters
	TurnCount     int64 `json:"turn_count"`
	ToolCallCount int64 `json:"tool_call_count"`
	FileSystemOps int64 `json:"filesystem_ops"`
	FSPath        string  `json:"fs_path,omitempty"`
	FSOperation   string  `json:"fs_operation,omitempty"`
	FSBytes       int64   `json:"fs_bytes,omitempty"`
	EventType     string  `json:"event_type,omitempty"`
	StateFrom     string  `json:"state_from,omitempty"`
	StateTo       string  `json:"state_to,omitempty"`
	ErrorMessage  string  `json:"error_message,omitempty"`
}

// ──────────────────────────────────────────────
//  Model cost configuration
// ──────────────────────────────────────────────

type ModelCost struct {
	Input      float64 `json:"input"`
	Output     float64 `json:"output"`
	CacheRead  float64 `json:"cacheRead"`
	CacheWrite float64 `json:"cacheWrite"`
}

type ModelInfo struct {
	ID            string    `json:"id"`
	Name          string    `json:"name"`
	Provider      string    `json:"provider"`
	BaseURL       string    `json:"baseUrl"`
	ContextWindow int64     `json:"contextWindow"`
	MaxTokens     int64     `json:"maxTokens"`
	Cost          ModelCost `json:"cost"`
}

// ──────────────────────────────────────────────
//  Token & usage tracking
// ──────────────────────────────────────────────

type TokenUsage struct {
	InputTokens          int64   `json:"input_tokens"`
	OutputTokens         int64   `json:"output_tokens"`
	CacheReadTokens      int64   `json:"cache_read_tokens"`
	CacheWriteTokens     int64   `json:"cache_write_tokens"`
	CostUSD              float64 `json:"cost_usd"`
	ModelID              string  `json:"model_id"`
	TurnCount            int64   `json:"turn_count"`
	ToolCallCount        int64   `json:"tool_call_count"`
	FileSystemOps        int64   `json:"filesystem_ops"`
	RunDuration          time.Duration `json:"run_duration_ns"`
	LastUpdated          time.Time `json:"last_updated"`
}

func (t *TokenUsage) Add(other TokenUsage) {
	t.InputTokens += other.InputTokens
	t.OutputTokens += other.OutputTokens
	t.CacheReadTokens += other.CacheReadTokens
	t.CacheWriteTokens += other.CacheWriteTokens
	t.CostUSD += other.CostUSD
	t.TurnCount += other.TurnCount
	t.ToolCallCount += other.ToolCallCount
	t.FileSystemOps += other.FileSystemOps
	t.LastUpdated = time.Now()
}

// ──────────────────────────────────────────────
//  Configuration
// ──────────────────────────────────────────────

type AgentConfig struct {
	// OMP binary path
	OMPPath string `json:"omp_path" yaml:"omp_path"`

	// Model to use (e.g. "openrouter/deepseek/deepseek-v4-flash")
	Model string `json:"model" yaml:"model"`

	// Thinking level: off|minimal|low|medium|high
	ThinkingLevel string `json:"thinking_level" yaml:"thinking_level"`

	// Session persistence
	SessionDir string `json:"session_dir" yaml:"session_dir"`
	InMemory   bool   `json:"in_memory" yaml:"in_memory"`

	// Max run time
	MaxRunTime time.Duration `json:"max_run_time" yaml:"max_run_time"`

	// Auto-compaction and retry
	AutoCompaction bool `json:"auto_compaction" yaml:"auto_compaction"`
	AutoRetry      bool `json:"auto_retry" yaml:"auto_retry"`

	// Steering mode
	SteeringMode string `json:"steering_mode" yaml:"steering_mode"` // all | one-at-a-time

	// Labels for the agent
	Labels map[string]string `json:"labels,omitempty" yaml:"labels,omitempty"`

	// Agent directory override
	AgentDir string `json:"agent_dir,omitempty" yaml:"agent_dir,omitempty"`
}

func DefaultConfig() AgentConfig {
	return AgentConfig{
		OMPPath:        "omp",
		Model:          "openrouter/deepseek/deepseek-v4-flash",
		ThinkingLevel:  "high",
		InMemory:       false,
		MaxRunTime:     15 * time.Minute,
		AutoCompaction: true,
		AutoRetry:      true,
		SteeringMode:   "one-at-a-time",
		Labels:         make(map[string]string),
	}
}

// ──────────────────────────────────────────────
//  Host tool definition
// ──────────────────────────────────────────────

type HostToolParam struct {
	Type       string                     `json:"type"`
	Properties map[string]HostToolProperty `json:"properties,omitempty"`
	Required   []string                   `json:"required,omitempty"`
}

type HostToolProperty struct {
	Type        string `json:"type"`
	Description string `json:"description,omitempty"`
}

type HostToolDefinition struct {
	Name        string        `json:"name"`
	Label       string        `json:"label,omitempty"`
	Description string        `json:"description"`
	Parameters  HostToolParam `json:"parameters"`
}

type RpcHostToolRequest struct {
	Type       string          `json:"type"` // host_tool_call | host_tool_cancel
	ID         string          `json:"id"`
	ToolCallID string          `json:"toolCallId,omitempty"`
	ToolName   string          `json:"toolName,omitempty"`
	Arguments  json.RawMessage `json:"arguments,omitempty"`
	TargetID   string          `json:"targetId,omitempty"` // for cancel
}

// ──────────────────────────────────────────────
//  Report format (post-analysis)
// ──────────────────────────────────────────────

type AgentRunReport struct {
	AgentID    string          `json:"agent_id"`
	Config     AgentConfig     `json:"config"`
	StartedAt  time.Time       `json:"started_at"`
	EndedAt    time.Time       `json:"ended_at"`
	Duration   time.Duration   `json:"duration_ns"`
	State      AgentState      `json:"final_state"`
	TokenUsage TokenUsage      `json:"token_usage"`
	Metrics    []Metric        `json:"metrics"`
	Events     []AgentEventLog `json:"events"`
	Error      string          `json:"error,omitempty"`
}

type AgentEventLog struct {
	Timestamp   time.Time            `json:"timestamp"`
	Type        AgentEventType       `json:"type"`
	RawFrame    json.RawMessage      `json:"raw_frame,omitempty"`
	Annotations map[string]string    `json:"annotations,omitempty"`
}
