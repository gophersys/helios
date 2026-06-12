package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
)

// HostToolManager manages the host tools registered with the OMP process.
type HostToolManager struct {
	agent   *Agent
	tools   map[string]HostToolDefinition
	handlers map[string]func(ctx context.Context, args json.RawMessage) (interface{}, error)
}

// NewHostToolManager creates a new host tool manager for the given agent.
func NewHostToolManager(agent *Agent) *HostToolManager {
	htm := &HostToolManager{
		agent:    agent,
		tools:    make(map[string]HostToolDefinition),
		handlers: make(map[string]func(ctx context.Context, args json.RawMessage) (interface{}, error)),
	}

	// Install the generic handler on the RPC client
	if agent.rpc != nil {
		agent.rpc.SetHostToolHandler(htm.handleToolCall)
	}

	return htm
}

// RegisterTool registers a host tool that the agent can call.
func (htm *HostToolManager) RegisterTool(def HostToolDefinition, handler func(ctx context.Context, args json.RawMessage) (interface{}, error)) error {
	if def.Name == "" {
		return fmt.Errorf("tool name cannot be empty")
	}
	if handler == nil {
		return fmt.Errorf("tool handler cannot be nil")
	}

	htm.tools[def.Name] = def
	htm.handlers[def.Name] = handler

	return nil
}

// SyncTools sends the current tool set to the OMP process.
func (htm *HostToolManager) SyncTools(ctx context.Context) error {
	if htm.agent.rpc == nil {
		return fmt.Errorf("RPC client not available")
	}

	tools := make([]HostToolDefinition, 0, len(htm.tools))
	for _, def := range htm.tools {
		tools = append(tools, def)
	}

	toolsJSON, err := json.Marshal(tools)
	if err != nil {
		return fmt.Errorf("marshal tools: %w", err)
	}

	_, err = htm.agent.rpc.Send(ctx, RpcCommand{
		Type:  "set_host_tools",
		Tools: toolsJSON,
	})
	return err
}

// GetTool returns a registered tool definition.
func (htm *HostToolManager) GetTool(name string) (HostToolDefinition, bool) {
	def, ok := htm.tools[name]
	return def, ok
}

// ListTools returns all registered tool definitions.
func (htm *HostToolManager) ListTools() []HostToolDefinition {
	result := make([]HostToolDefinition, 0, len(htm.tools))
	for _, def := range htm.tools {
		result = append(result, def)
	}
	return result
}

func (htm *HostToolManager) handleToolCall(ctx context.Context, req RpcHostToolRequest) (interface{}, error) {
	handler, ok := htm.handlers[req.ToolName]
	if !ok {
		return map[string]interface{}{
			"isError": true,
			"content": []map[string]interface{}{
				{"type": "text", "text": fmt.Sprintf("Unknown host tool: %s", req.ToolName)},
			},
		}, nil
	}

	// Create a context with timeout
	toolCtx, cancel := context.WithTimeout(ctx, 5*time.Minute)
	defer cancel()

	return handler(toolCtx, req.Arguments)
}

// ──────────────────────────────────────────────
//  Pre-built tools
// ──────────────────────────────────────────────

// NewConsultSupervisorTool creates the standard "consult_supervisor" tool
// that workers use to ask the supervisor questions.
func NewConsultSupervisorTool() HostToolDefinition {
	return HostToolDefinition{
		Name:        "consult_supervisor",
		Label:       "Consult Supervisor",
		Description: "Ask the supervisor agent for guidance, advice, or answers to questions you cannot resolve. Use this when you need help, clarification, or a second opinion.",
		Parameters: HostToolParam{
			Type: "object",
			Properties: map[string]HostToolProperty{
				"question": {
					Type:        "string",
					Description: "The question to ask the supervisor agent. Be specific and provide context.",
				},
			},
			Required: []string{"question"},
		},
	}
}

// NewFileSystemReadTool creates a tool for reading files that bypasses OMP's built-in read.
func NewFileSystemReadTool(basePath string) (HostToolDefinition, func(ctx context.Context, args json.RawMessage) (interface{}, error)) {
	def := HostToolDefinition{
		Name:        "sandbox_read",
		Label:       "Sandbox Read",
		Description: "Read files from the sandboxed filesystem",
		Parameters: HostToolParam{
			Type: "object",
			Properties: map[string]HostToolProperty{
				"path": {
					Type:        "string",
					Description: "Path to the file to read",
				},
			},
			Required: []string{"path"},
		},
	}

	handler := func(ctx context.Context, args json.RawMessage) (interface{}, error) {
		var params struct {
			Path string `json:"path"`
		}
		if err := json.Unmarshal(args, &params); err != nil {
			return nil, fmt.Errorf("invalid arguments: %w", err)
		}
		if params.Path == "" {
			return nil, fmt.Errorf("path is required")
		}

		// Use the read function from the OMP tool surface via the RPC client
		return map[string]interface{}{
			"content": []map[string]interface{}{
				{"type": "text", "text": fmt.Sprintf("Would read: %s (sandbox path: %s)", params.Path, basePath)},
			},
		}, nil
	}

	return def, handler
}