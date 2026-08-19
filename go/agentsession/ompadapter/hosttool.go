package ompadapter

import (
	"context"
	"encoding/json"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
)

// hostToolRouter services the host-tool half of the rpc channel: it renders the Spec's
// HostTools for set_host_tools, routes each host_tool_call into the matching in-process
// Handler, and answers with host_tool_result. It owns no transport — the conn hands it the
// frame writer — and it correlates on the RPC frame `id`, never on the model's toolCallId.
type hostToolRouter struct {
	tools map[string]agentsession.HostTool
	order []string              // registration order, so set_host_tools is deterministic
	send  func(frame any) error // the conn's serialized stdin writer

	mu      sync.Mutex
	pending map[string]context.CancelFunc
	closed  bool
}

// newHostToolRouter indexes the HostTools by name. An empty set yields a router that advertises
// nothing, so no set_host_tools frame is written at all.
func newHostToolRouter(tools []agentsession.HostTool, send func(frame any) error) *hostToolRouter {
	router := &hostToolRouter{
		tools:   make(map[string]agentsession.HostTool, len(tools)),
		order:   make([]string, 0, len(tools)),
		send:    send,
		pending: make(map[string]context.CancelFunc),
	}
	for _, tool := range tools {
		if _, duplicate := router.tools[tool.Name]; duplicate {
			continue
		}
		router.tools[tool.Name] = tool
		router.order = append(router.order, tool.Name)
	}
	return router
}

// definitions renders the RpcHostToolDefinition list for set_host_tools. name, description and
// parameters are the fields omp's definition declares; a tool with no Schema advertises the
// empty object schema so `parameters` is never absent.
func (r *hostToolRouter) definitions() []map[string]any {
	out := make([]map[string]any, 0, len(r.order))
	for _, name := range r.order {
		tool := r.tools[name]
		parameters := any(map[string]any{"type": "object"})
		if len(tool.Schema) > 0 {
			parameters = json.RawMessage(tool.Schema)
		}
		out = append(out, map[string]any{
			"name":        tool.Name,
			"description": tool.Description,
			"parameters":  parameters,
		})
	}
	return out
}

// call routes one host_tool_call into its Handler and answers it. The Handler runs on its own
// goroutine so a slow tool cannot stall the frame pump — which is also what keeps a
// host_tool_cancel for the very call in flight readable while it runs.
//
// id is the RPC correlation id the answer MUST echo: host-tools.ts resolves the pending call
// with #pendingCalls.get(frame.id), so an answer keyed on the model's toolCallId matches
// nothing and is silently discarded, leaving the model waiting for a tool that already ran.
func (r *hostToolRouter) call(id, toolName string, arguments json.RawMessage) {
	tool, found := r.tools[toolName]
	if !found {
		r.answer(hostToolResult(id, "unknown host tool: "+toolName, true))
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	if !r.register(id, cancel) {
		cancel()
		return
	}
	go func() {
		defer r.settle(id)
		result, err := tool.Handler(ctx, arguments)
		if ctx.Err() != nil {
			// Canceled locally (a host_tool_cancel, or the session closing): omp is no longer
			// waiting on this id, so there is nothing to answer.
			return
		}
		if err != nil {
			// isError rejects the pending call with the concatenated text parts, so the model sees
			// a failed tool rather than a broken transport. The Handler's own error text is NOT
			// forwarded: it is not guaranteed to be free of what the tool was handed.
			r.answer(hostToolResult(id, "host tool failed: "+toolName, true))
			return
		}
		r.answer(hostToolResult(id, string(result), false))
	}()
}

// cancel drops a pending call locally. The bridge emits host_tool_cancel and rejects on its own
// side without waiting for the host to acknowledge (q4 §5), so no frame is written back.
func (r *hostToolRouter) cancel(targetID string) {
	r.mu.Lock()
	stop, found := r.pending[targetID]
	delete(r.pending, targetID)
	r.mu.Unlock()
	if found {
		stop()
	}
}

// closeAll cancels every call still in flight when the session closes. It mirrors omp's own
// side of the stdin EOF, where the bridge rejects every pending call with its sticky
// #closedError.
func (r *hostToolRouter) closeAll() {
	r.mu.Lock()
	pending := r.pending
	r.pending = make(map[string]context.CancelFunc)
	r.closed = true
	r.mu.Unlock()
	for _, stop := range pending {
		stop()
	}
}

// register records a call in flight, reporting false once the session is closed (no new call is
// admitted after the EOF).
func (r *hostToolRouter) register(id string, stop context.CancelFunc) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return false
	}
	r.pending[id] = stop
	return true
}

// settle releases a finished call's cancellation, whether it was answered or canceled.
func (r *hostToolRouter) settle(id string) {
	r.mu.Lock()
	stop, found := r.pending[id]
	delete(r.pending, id)
	r.mu.Unlock()
	if found {
		stop()
	}
}

// answer writes a host_tool_result frame. A transport that cannot take it has already ended the
// session; the model's own wait is omp's to end, not this adapter's to report on.
func (r *hostToolRouter) answer(frame map[string]any) {
	_ = r.send(frame) //nolint:errcheck // best-effort answer; a failed write means the session is already gone, which the pump surfaces as the end of the stream.
}

// hostToolResult renders the RpcHostToolResult frame. result.content is a JSON ARRAY — the ONLY
// structural requirement omp enforces (isRpcHostToolResult accepts the frame only when
// Array.isArray(result.content) holds), and a bare string result is not an error but a frame
// dropped on the floor.
func hostToolResult(id, text string, isError bool) map[string]any {
	frame := map[string]any{
		"type": "host_tool_result",
		"id":   id,
		"result": map[string]any{
			"content": []map[string]any{{"type": "text", "text": text}},
		},
	}
	if isError {
		frame["isError"] = true
	}
	return frame
}
