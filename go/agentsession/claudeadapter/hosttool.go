package claudeadapter

import (
	"context"
	"encoding/json"

	"github.com/gophersys/libs/go/agentsession"
)

// mcpProtocolVersion is the MCP handshake version the host server reports when claude's
// initialize carries none. The server otherwise ECHOES the client's requested protocolVersion
// (MCP version negotiation: a server that answers a 2025-11-25 client with an older version
// is treated as incompatible and the in-process handshake stalls — observed live).
const mcpProtocolVersion = "2025-11-25"

// initializeParams is the params of claude's MCP initialize: its requested protocol version,
// echoed back so version negotiation succeeds.
type initializeParams struct {
	ProtocolVersion string `json:"protocolVersion"`
}

// jsonrpcMessage is the JSON-RPC 2.0 envelope claude drives the host tools over (inside an
// mcp_message control_request). id is absent on notifications; method selects the verb.
type jsonrpcMessage struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
}

// toolsCallParams is the params of a tools/call: the tool name and its arguments, routed into
// the matching HostTool.Handler.
type toolsCallParams struct {
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

// hostToolRouter services the host-tool half of the control channel: it answers claude's
// mcp_message JSON-RPC (initialize/tools/list/tools/call) by routing into the registered
// HostTools. It owns NO transport — it returns the JSON-RPC result to write back; the conn
// wraps it as {"mcp_response": ...} in a control_response. Handler results stream nothing
// here (partial results are surfaced as EventToolUpdate by the conn separately).
type hostToolRouter struct {
	tools  map[string]agentsession.HostTool
	digest digester
}

// newHostToolRouter indexes the HostTools by name. An empty set yields a router that answers
// tools/list with nothing (no host tools advertised).
func newHostToolRouter(tools []agentsession.HostTool) *hostToolRouter {
	index := make(map[string]agentsession.HostTool, len(tools))
	for _, tool := range tools {
		index[tool.Name] = tool
	}
	return &hostToolRouter{tools: index, digest: defaultDigester}
}

// route services one mcp_message JSON-RPC and returns the JSON-RPC response to write back as
// the mcp_response, plus any normalized Events to fan out (an EventToolUpdate carrying the
// host-tool result digest on a tools/call). ok=false means the message is a notification with
// no response (e.g. notifications/initialized) — the conn writes nothing back.
func (r *hostToolRouter) route(ctx context.Context, raw json.RawMessage) (response any, events []agentsession.Event, ok bool) {
	var message jsonrpcMessage
	if err := json.Unmarshal(raw, &message); err != nil {
		return nil, nil, false
	}
	switch message.Method {
	case "initialize":
		return r.result(message.ID, map[string]any{
			"protocolVersion": negotiatedVersion(message.Params),
			"capabilities":    map[string]any{"tools": map[string]any{}},
			"serverInfo":      map[string]any{"name": hostToolServerName, "version": "1.0.0"},
		}), nil, true
	case "tools/list":
		return r.result(message.ID, map[string]any{"tools": r.descriptors()}), nil, true
	case "tools/call":
		return r.call(ctx, &message)
	default:
		// notifications/* and any unmodeled method carry no id and expect no response.
		return nil, nil, false
	}
}

// call routes a tools/call into the matching HostTool.Handler and renders the JSON-RPC result.
// A missing tool or a Handler error becomes an isError tool result (the model sees the failure
// rather than the transport breaking). The result digest rides an EventToolUpdate so the host
// tool's outcome is observable on the stream.
func (r *hostToolRouter) call(ctx context.Context, message *jsonrpcMessage) (any, []agentsession.Event, bool) {
	var params toolsCallParams
	if err := json.Unmarshal(message.Params, &params); err != nil {
		return r.errorResult(message.ID, "invalid tools/call params"), nil, true
	}
	tool, found := r.tools[params.Name]
	if !found {
		return r.errorResult(message.ID, "unknown host tool: "+params.Name), nil, true
	}
	result, err := tool.Handler(ctx, params.Arguments)
	if err != nil {
		return r.errorResult(message.ID, "host tool failed"), nil, true
	}
	event := agentsession.Event{
		Kind: agentsession.EventToolUpdate,
		Tool: &agentsession.ToolPayload{
			Name:          params.Name,
			PartialDigest: r.digest(result),
			IsHostTool:    true,
		},
	}
	return r.result(message.ID, map[string]any{
		"content": []map[string]any{{"type": "text", "text": string(result)}},
	}), []agentsession.Event{event}, true
}

// descriptors renders the HostTool schema list for tools/list. Each tool's Schema is its
// JSON-schema inputSchema, opaque to this lib (passed through to the harness).
func (r *hostToolRouter) descriptors() []map[string]any {
	out := make([]map[string]any, 0, len(r.tools))
	for _, tool := range r.tools {
		descriptor := map[string]any{"name": tool.Name, "description": tool.Description}
		if len(tool.Schema) > 0 {
			descriptor["inputSchema"] = json.RawMessage(tool.Schema)
		} else {
			descriptor["inputSchema"] = map[string]any{"type": "object"}
		}
		out = append(out, descriptor)
	}
	return out
}

// result builds a JSON-RPC success envelope.
func (r *hostToolRouter) result(id json.RawMessage, result any) map[string]any {
	return map[string]any{"jsonrpc": "2.0", "id": rawOrNull(id), "result": result}
}

// errorResult builds a JSON-RPC tool-result carrying isError, so the model sees a host-tool
// failure as a tool error rather than a broken transport.
func (r *hostToolRouter) errorResult(id json.RawMessage, message string) map[string]any {
	return r.result(id, map[string]any{
		"content": []map[string]any{{"type": "text", "text": message}},
		"isError": true,
	})
}

// negotiatedVersion echoes the MCP protocol version the client (claude) requested in its
// initialize, falling back to the default when none is present. Echoing the client's version
// is the MCP negotiation contract; answering with a different version stalls the handshake.
func negotiatedVersion(params json.RawMessage) string {
	var p initializeParams
	if err := json.Unmarshal(params, &p); err == nil && p.ProtocolVersion != "" {
		return p.ProtocolVersion
	}
	return mcpProtocolVersion
}

// rawOrNull returns the raw id, or JSON null when absent, so the envelope always carries a
// valid id field.
func rawOrNull(id json.RawMessage) json.RawMessage {
	if len(id) == 0 {
		return json.RawMessage("null")
	}
	return id
}
