package agent

import (
	"encoding/json"
	"fmt"
	"math"
	"sync"
	"time"
)

// TokenTracker tracks token usage and cost across an agent run.
type TokenTracker struct {
	mu       sync.Mutex
	usage    TokenUsage
	model    ModelInfo
	started  time.Time
}

// NewTokenTracker creates a new tracker with the given model cost info.
func NewTokenTracker(model ModelInfo) *TokenTracker {
	return &TokenTracker{
		model:   model,
		started: time.Now(),
	}
}

// RecordUsage records a chunk of token usage. Negative values are treated as zero.
func (tt *TokenTracker) RecordUsage(input, output int64) {
	tt.mu.Lock()
	defer tt.mu.Unlock()

	if input < 0 {
		input = 0
	}
	if output < 0 {
		output = 0
	}

	tt.usage.InputTokens += input
	tt.usage.OutputTokens += output
	inputCost := float64(input) / 1_000_000 * tt.model.Cost.Input
	outputCost := float64(output) / 1_000_000 * tt.model.Cost.Output
	tt.usage.CostUSD += inputCost + outputCost
	tt.usage.LastUpdated = time.Now()
	tt.usage.ModelID = tt.model.ID
}
func (tt *TokenTracker) RecordCacheUsage(read, write int64) {
	tt.mu.Lock()
	defer tt.mu.Unlock()

	tt.usage.CacheReadTokens += read
	tt.usage.CacheWriteTokens += write

	cacheCost := float64(read) / 1_000_000 * tt.model.Cost.CacheRead
	cacheWriteCost := float64(write) / 1_000_000 * tt.model.Cost.CacheWrite
	tt.usage.CostUSD += cacheCost + cacheWriteCost
	tt.usage.LastUpdated = time.Now()
}

// IncrementTurn increments the turn counter.
func (tt *TokenTracker) IncrementTurn() {
	tt.mu.Lock()
	tt.usage.TurnCount++
	tt.mu.Unlock()
}

// IncrementToolCall increments the tool call counter.
func (tt *TokenTracker) IncrementToolCall() {
	tt.mu.Lock()
	tt.usage.ToolCallCount++
	tt.mu.Unlock()
}

// IncrementFSOp increments the filesystem operation counter.
func (tt *TokenTracker) IncrementFSOp() {
	tt.mu.Lock()
	tt.usage.FileSystemOps++
	tt.mu.Unlock()
}

// Snapshot returns a copy of current usage.
func (tt *TokenTracker) Snapshot() TokenUsage {
	tt.mu.Lock()
	defer tt.mu.Unlock()
	u := tt.usage
	u.RunDuration = time.Since(tt.started)
	return u
}

// TotalCost returns the accumulated cost in USD.
func (tt *TokenTracker) TotalCost() float64 {
	return tt.Snapshot().CostUSD
}

// Summary returns a human-readable cost summary.
func (tt *TokenTracker) Summary() string {
	u := tt.Snapshot()
	return fmt.Sprintf("Model: %s | Tokens: %d in / %d out | Turns: %d | Tools: %d | FS: %d | Cost: $%.6f | Duration: %s",
		u.ModelID,
		u.InputTokens, u.OutputTokens,
		u.TurnCount, u.ToolCallCount, u.FileSystemOps,
		u.CostUSD, time.Since(tt.started).Round(time.Millisecond),
	)
}

// EstimateCostForTokens estimates cost for a given number of tokens.
func EstimateCostForTokens(model ModelInfo, inputTokens, outputTokens int64) float64 {
	inputCost := float64(inputTokens) / 1_000_000 * model.Cost.Input
	outputCost := float64(outputTokens) / 1_000_000 * model.Cost.Output
	return math.Round((inputCost+outputCost)*1_000_000) / 1_000_000
}

// ParseTokenUsageFromState attempts to extract token usage from OMP get_state response.
func ParseTokenUsageFromState(data map[string]interface{}) map[string]int64 {
	result := make(map[string]int64)
	if data == nil {
		return result
	}

	// The state might have token usage under "contextUsage"
	if ctxUsage, ok := data["contextUsage"].(map[string]interface{}); ok {
		if tokens, ok := ctxUsage["tokens"].(float64); ok {
			result["context_tokens"] = int64(tokens)
		}
	}

	return result
}

// MarshalJSON implements json.Marshaler for human-readable output.
func (tt *TokenTracker) MarshalJSON() ([]byte, error) {
	u := tt.Snapshot()
	return json.Marshal(map[string]interface{}{
		"model_id":          u.ModelID,
		"input_tokens":      u.InputTokens,
		"output_tokens":     u.OutputTokens,
		"cache_read_tokens": u.CacheReadTokens,
		"cache_write_tokens": u.CacheWriteTokens,
		"cost_usd":          u.CostUSD,
		"turn_count":        u.TurnCount,
		"tool_call_count":   u.ToolCallCount,
		"filesystem_ops":    u.FileSystemOps,
		"run_duration":      time.Since(tt.started).String(),
		"summary":           tt.Summary(),
	})
}
