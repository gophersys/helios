package claudeadapter

import (
	"encoding/json"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/errors"
)

// hostToolServerName is the SDK-MCP server name Eden advertises to claude at the initialize
// handshake. Eden-provided host tools surface to the model as mcp__<server>__<Name>, so the
// model calls e.g. mcp__eden__lookup; the conn routes the matching mcp_message back into the
// HostTool.Handler. One server holds the whole Spec.HostTools set.
const hostToolServerName = "eden"

// controlResponseFrame renders a control_response line answering a control_request correlated
// by request id. response is the verb-specific body (a PermissionResult for can_use_tool, or
// {"mcp_response": <JSON-RPC>} for an mcp_message). It is the out-of-band answer the host
// writes on stdin — NOT a {"type":"user"} conversation turn (the bug this replaces).
func controlResponseFrame(requestID string, response any) ([]byte, error) {
	payload := map[string]any{
		"type": "control_response",
		"response": map[string]any{
			"subtype":    "success",
			"request_id": requestID,
			"response":   response,
		},
	}
	line, err := json.Marshal(payload)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "claudeadapter: marshal control_response", err)
	}
	return append(line, '\n'), nil
}

// initializeFrame renders the host's initialize control_request. When servers is non-empty it
// advertises them as sdkMcpServers, so claude drives the in-process host tools over
// mcp_message control_requests (tools/list + tools/call). With no host tools it is a bare
// handshake. requestID correlates claude's control_response ack.
//
// sdkMcpServers is a JSON ARRAY of bare server NAMES (the CLI's Zod schema is
// `sdkMcpServers: array(string)`; the CLI itself synthesizes the {type:"sdk", name} descriptor
// for each). It is NOT an object/map and NOT an array of objects — either of those fails the
// schema, so the CLI drops the server and reports it "not connected" (the model then cannot call
// mcp__<server>__<tool>). The array merely ADVERTISES; the host must then SERVE the CLI-initiated
// MCP JSON-RPC handshake over mcp_message control_requests (initialize → notifications/initialized
// → tools/list → tools/call), each answered in the matching control_response — see
// hostToolRouter.route. Failing to answer ANY step (notably notifications/initialized) blocks the
// CLI's client.connect() (the host-tool round-trip never starts). Verified via the Claude Agent
// SDK control-protocol source (claude 2.1.x).
func initializeFrame(requestID string, servers []string) ([]byte, error) {
	request := map[string]any{"subtype": "initialize"}
	if len(servers) > 0 {
		request["sdkMcpServers"] = servers
	}
	payload := map[string]any{
		"type":       "control_request",
		"request_id": requestID,
		"request":    request,
	}
	line, err := json.Marshal(payload)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "claudeadapter: marshal initialize", err)
	}
	return append(line, '\n'), nil
}

// permissionResult builds the PermissionResult body for a can_use_tool control_response. An
// allow MUST carry updatedInput (claude rejects an allow that omits a valid object with a
// ZodError) — it defaults to the original input the ask carried (echoed via the normalizer's
// stash). A deny carries the human/policy message so the model sees why it was refused.
func permissionResult(allow bool, message string, originalInput json.RawMessage) map[string]any {
	if !allow {
		return map[string]any{"behavior": "deny", "message": message}
	}
	result := map[string]any{"behavior": "allow"}
	if len(originalInput) > 0 {
		result["updatedInput"] = json.RawMessage(originalInput)
	} else {
		// The ask carried no input (or it was already consumed): default to an empty object so
		// the allow still satisfies the updatedInput schema rather than failing validation.
		result["updatedInput"] = map[string]any{}
	}
	return result
}

// parsedPermissionAnswer is the decoded internal eden:permission:<id>:<verdict>:<by> frame the
// library's forwardDecision sends as CommandSteer text. The adapter TRANSLATES it to the
// can_use_tool control_response on the wire; the internal frame stays the normalized
// representation (one home for the decision shape, the library's), so the agentsession seam
// is unchanged.
type parsedPermissionAnswer struct {
	requestID string
	allow     bool
	by        string
	rationale string // the OPTIONAL audit Rationale appended after the 0x1f separator (empty when absent)
}

// parsePermissionAnswer decodes the internal eden:permission frame through the grammar's ONE
// HOME (agentsession/internal/controlframe). ok=false for any text that is not a permission
// answer (a genuine Steer interjection), so Send falls through to the ordinary user-turn path
// for those.
func parsePermissionAnswer(text string) (parsedPermissionAnswer, bool) {
	requestID, allow, by, rationale, ok := controlframe.DecodePermission(text)
	if !ok {
		return parsedPermissionAnswer{}, false
	}
	return parsedPermissionAnswer{requestID: requestID, allow: allow, by: by, rationale: rationale}, true
}

// denyMessage renders the operator-safe deny message sent to the model on a refused tool. It
// names the deciding identity and, when present, the audit rationale (the founder model's
// advisor reasoning) so the model learns WHY — but carries no secret (by is a user id or
// "policy:<name>"; rationale is bounded, redacted text).
func denyMessage(by, rationale string) string {
	msg := "denied by Eden permission policy"
	if by != "" {
		msg += " (" + by + ")"
	}
	if rationale != "" {
		msg += ": " + rationale
	}
	return msg
}

// hostToolNames projects the SDK-MCP server set Eden advertises. It is a single server
// (hostToolServerName) holding the whole HostTools set, or empty when there are none.
func hostToolNames(tools []agentsession.HostTool) []string {
	if len(tools) == 0 {
		return nil
	}
	return []string{hostToolServerName}
}
