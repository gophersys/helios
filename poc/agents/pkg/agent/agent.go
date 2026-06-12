package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// Agent is the core orchestrator for managing an OMP agent instance.
type Agent struct {
	ID       string
	Config   AgentConfig

	rpc      *RPCClient
	rpcCancel context.CancelFunc
	sm       *StateMachine
	metrics  *MetricsBus
	tracker  *TokenTracker
	configM  *ConfigManager

	mu         sync.Mutex
	startedAt  time.Time
	finishedAt time.Time
	events     []AgentEventLog

	currentModel ModelInfo

	bridgeCallback func(ctx context.Context, question string) (string, error)
}

// NewAgent creates a new agent with the given configuration.
func NewAgent(id string, config AgentConfig) *Agent {
	configM := NewConfigManager(config)

	a := &Agent{
		ID:       id,
		Config:   config,
		configM:  configM,
		metrics:  NewMetricsBus(id, 10000),
	}

	a.sm = NewStateMachine(func(from, to AgentState) {
		a.metrics.Emit(Metric{
			Type:      MetricStateTransition,
			Timestamp: time.Now(),
			StateFrom: string(from),
			StateTo:   string(to),
			Labels:    map[string]string{"agent_id": id},
		})
	})

	return a
}

// Start initializes the agent: spawns OMP, configures model, and transitions to Ready.
func (a *Agent) Start(ctx context.Context) error {
	a.mu.Lock()
	if a.sm.Current() != StateCreated {
		a.mu.Unlock()
		return fmt.Errorf("agent %s already started (state: %s)", a.ID, a.sm.Current())
	}
	a.sm.MustTransition(StateInitializing)
	a.mu.Unlock()

	a.startedAt = time.Now()

	// Determine OMP path — resolve "omp" via PATH to prevent arbitrary binary exec
	ompPath := a.Config.OMPPath
	if ompPath == "" {
		ompPath = "omp"
	}
	// Resolve "omp" to its absolute path and only allow that binary
	resolvedPath := ompPath
	if !strings.Contains(ompPath, "/") {
		if p, err := exec.LookPath(ompPath); err == nil {
			resolvedPath = p
		}
	}
	// Verify the resolved path points to an "omp" binary
	base := filepath.Base(resolvedPath)
	if base != "omp" && base != "omp.exe" {
		return fmt.Errorf("invalid OMP binary: %q (must be 'omp')", ompPath)
	}

	rpcCtx, rpcCancel := context.WithCancel(context.Background())
	rpc, err := NewRPCClient(rpcCtx, a.ID, resolvedPath)
	if err != nil {
		rpcCancel()
		a.mu.Lock()
		a.sm.MustTransition(StateFailed)
		a.finishedAt = time.Now()
		a.mu.Unlock()
		return fmt.Errorf("spawn omp: %w", err)
	}
	a.rpcCancel = rpcCancel
	a.rpc = rpc


	// Set up event subscription
	eventCh := a.rpc.Subscribe()
	go a.handleEvents(eventCh)

	// Configure the agent via RPC
	if err := a.configureRPC(ctx); err != nil {
		a.rpc.Close()
		a.mu.Lock()
		a.sm.MustTransition(StateFailed)
		a.finishedAt = time.Now()
		a.mu.Unlock()
		return fmt.Errorf("configure rpc: %w", err)
	}

	// Get initial state to extract model info
	state, err := a.rpc.GetState(ctx)
	if err == nil && state != nil {
		a.extractModelInfo(state)
	}

	a.mu.Lock()
	a.sm.MustTransition(StateReady)
	a.mu.Unlock()

	a.metrics.Emit(Metric{
		Type:      MetricEvent,
		Timestamp: time.Now(),
		EventType: "agent_ready",
		AgentID:   a.ID,
		Labels:    map[string]string{"model": a.Config.Model},
	})

	return nil
}

// Prompt sends a prompt and waits for completion. Events are streamed to metrics bus.
func (a *Agent) Prompt(ctx context.Context, message string) error {
	a.mu.Lock()
	if a.sm.Current() != StateReady && a.sm.Current() != StateRunning {
		state := a.sm.Current()
		a.mu.Unlock()
		return fmt.Errorf("cannot prompt in state: %s", state)
	}
	a.sm.MustTransition(StateRunning)
	a.mu.Unlock()

	a.metrics.Emit(Metric{
		Type:      MetricEvent,
		Timestamp: time.Now(),
		EventType: "prompt_sent",
		AgentID:   a.ID,
		Payload:   mustMarshal(map[string]string{"message": truncate(message, 200)}),
	})

	_, err := a.rpc.Prompt(ctx, message)
	if err != nil {
		a.mu.Lock()
		a.sm.MustTransition(StateFailed)
		a.finishedAt = time.Now()
		a.mu.Unlock()
		return fmt.Errorf("prompt: %w", err)
	}

	return nil
}

// Abort cancels the current agent turn. No-op if agent hasn't started.
func (a *Agent) Abort(ctx context.Context) error {
	if a.rpc == nil {
		return fmt.Errorf("agent not started")
	}
	_, err := a.rpc.Abort(ctx)
	if err != nil {
		return err
	}
	a.mu.Lock()
	a.sm.MustTransition(StateCancelled)
	a.finishedAt = time.Now()
	a.mu.Unlock()
	return nil
}

// GetState returns the full OMP agent state.
func (a *Agent) GetState(ctx context.Context) (map[string]interface{}, error) {
	return a.rpc.GetState(ctx)
}

// TokenUsage returns current token usage snapshot.
func (a *Agent) TokenUsage() TokenUsage {
	if a.tracker != nil {
		return a.tracker.Snapshot()
	}
	return TokenUsage{}
}

// Metrics returns the metrics bus for subscribing/exporting.
func (a *Agent) Metrics() *MetricsBus {
	return a.metrics
}

// State returns the current lifecycle state.
func (a *Agent) State() AgentState {
	return a.sm.Current()
}

// Events returns a copy of all recorded agent events.
func (a *Agent) Events() []AgentEventLog {
	a.mu.Lock()
	defer a.mu.Unlock()
	events := make([]AgentEventLog, len(a.events))
	copy(events, a.events)
	return events
}

// Uptime returns how long the agent has been running.
func (a *Agent) Uptime() time.Duration {
	return time.Since(a.startedAt)
}

// SetBridgeCallback sets the callback used by the supervisor-worker bridge.
func (a *Agent) SetBridgeCallback(cb func(ctx context.Context, question string) (string, error)) {
	a.bridgeCallback = cb
}

// GetRPCClient returns the underlying RPC client (for advanced use).
func (a *Agent) GetRPCClient() *RPCClient {
	return a.rpc
}

// Shutdown cleanly terminates the agent.
func (a *Agent) Shutdown(ctx context.Context) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.sm.IsTerminal() {
		return nil
	}

	if a.rpc != nil {
		if a.sm.Current() == StateRunning {
			abortCtx, abortCancel := context.WithTimeout(context.Background(), 5*time.Second)
			a.rpc.Abort(abortCtx)
			abortCancel()
		}
		a.rpc.Close()
	}
	if a.rpcCancel != nil {
		a.rpcCancel()
	}
	a.sm.Transition(StateCancelled)
	a.finishedAt = time.Now()
	a.metrics.Close()

	return nil
}

// GenerateReport creates a comprehensive run report.
func (a *Agent) GenerateReport() *AgentRunReport {
	report := &AgentRunReport{
		AgentID:   a.ID,
		Config:    a.Config,
		StartedAt: a.startedAt,
		EndedAt:   a.finishedAt,
		State:     a.sm.Current(),
		Metrics:   a.metrics.Snapshot(),
		Events:    a.Events(),
	}
	if !a.finishedAt.IsZero() {
		report.Duration = a.finishedAt.Sub(a.startedAt)
	}
	if a.tracker != nil {
		report.TokenUsage = a.tracker.Snapshot()
	}
	return report
}

// ──────────────────────────────────────────────
//  Private methods
// ──────────────────────────────────────────────

func (a *Agent) configureRPC(ctx context.Context) error {
	// Set thinking level
	if a.Config.ThinkingLevel != "" {
		if _, err := a.rpc.SetThinkingLevel(ctx, a.Config.ThinkingLevel); err != nil {
			return fmt.Errorf("set thinking level: %w", err)
		}
		time.Sleep(50 * time.Millisecond)
	}

	// Set auto-compaction
	_, err := a.rpc.SetAutoCompaction(ctx, a.Config.AutoCompaction)
	if err != nil {
		return fmt.Errorf("set auto compaction: %w", err)
	}

	return nil
}

func (a *Agent) extractModelInfo(state map[string]interface{}) {
	if state == nil {
		return
	}
	if modelRaw, ok := state["model"].(map[string]interface{}); ok {
		if id, ok := modelRaw["id"].(string); ok {
			a.currentModel.ID = id
		}
		if name, ok := modelRaw["name"].(string); ok {
			a.currentModel.Name = name
		}
		if provider, ok := modelRaw["provider"].(string); ok {
			a.currentModel.Provider = provider
		}
		if baseURL, ok := modelRaw["baseUrl"].(string); ok {
			a.currentModel.BaseURL = baseURL
		}
		if cw, ok := modelRaw["contextWindow"].(float64); ok {
			a.currentModel.ContextWindow = int64(cw)
		}
		if mt, ok := modelRaw["maxTokens"].(float64); ok {
			a.currentModel.MaxTokens = int64(mt)
		}
		if costRaw, ok := modelRaw["cost"].(map[string]interface{}); ok {
			if input, ok := costRaw["input"].(float64); ok {
				a.currentModel.Cost.Input = input
			}
			if output, ok := costRaw["output"].(float64); ok {
				a.currentModel.Cost.Output = output
			}
			if cr, ok := costRaw["cacheRead"].(float64); ok {
				a.currentModel.Cost.CacheRead = cr
			}
			if cw, ok := costRaw["cacheWrite"].(float64); ok {
				a.currentModel.Cost.CacheWrite = cw
			}
		}

		a.tracker = NewTokenTracker(a.currentModel)
	}
}

func (a *Agent) handleEvents(eventCh chan RpcFrame) {
	for frame := range eventCh {
		a.mu.Lock()
		a.events = append(a.events, AgentEventLog{
			Timestamp: time.Now(),
			Type:      AgentEventType(frame.Type),
			RawFrame:  mustMarshal(frame),
		})
		a.mu.Unlock()

		// Emit metrics for significant events
		switch frame.Type {
		case string(EventAgentStart):
			a.metrics.Emit(Metric{
				Type:      MetricEvent,
				Timestamp: time.Now(),
				EventType: string(EventAgentStart),
				AgentID:   a.ID,
			})
			if a.tracker != nil {
				a.tracker.IncrementTurn()
			}

		case string(EventAgentEnd):
			// Emit token usage as a cost metric
			if a.tracker != nil {
				snap := a.tracker.Snapshot()
				a.metrics.Emit(Metric{
					Type:          MetricCost,
					Timestamp:     time.Now(),
					InputTokens:   snap.InputTokens,
					OutputTokens:  snap.OutputTokens,
					CostUSD:       snap.CostUSD,
					TurnCount:     snap.TurnCount,
					ToolCallCount: snap.ToolCallCount,
					FileSystemOps: snap.FileSystemOps,
					AgentID:       a.ID,
					ModelID:       a.currentModel.ID,
				})
			}
			a.metrics.Emit(Metric{
				Type:      MetricEvent,
				Timestamp: time.Now(),
				EventType: string(EventAgentEnd),
				AgentID:   a.ID,
			})
			a.mu.Lock()
			if a.sm.Current() == StateRunning {
				a.sm.Transition(StateReady)
			}
			a.mu.Unlock()
		case string(EventToolExecStart):
			a.metrics.Emit(Metric{
				Type:      MetricToolCall,
				Timestamp: time.Now(),
				ToolName:  frame.ToolName,
				AgentID:   a.ID,
			})
			if a.tracker != nil {
				a.tracker.IncrementToolCall()
			}

		case string(EventToolExecEnd):
			// Could track duration here
		}
	}
}

func mustMarshal(v interface{}) json.RawMessage {
	data, err := json.Marshal(v)
	if err != nil {
		panic("mustMarshal: " + err.Error())
	}
	return data
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}