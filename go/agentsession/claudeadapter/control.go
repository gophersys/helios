package claudeadapter

import (
	"encoding/json"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
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
// sdkMcpServers is a JSON OBJECT keyed by server name (the Claude Agent SDK contract), NOT a
// JSON array of names. Each value is the in-process SDK server descriptor ({type:"sdk", name})
// so claude knows the server runs in-process and routes its tools over mcp_message rather than
// spawning a subprocess. Advertising an ARRAY makes claude (2.1.x) complete the MCP
// `initialize` + `notifications/initialized` then STALL before `tools/list` — the whole turn
// never processes (admittedSeq frozen at ready, zero message/tool events). This was the
// eden_commit_transition host-tool stall; reproduced live (array=stall, object=runs clean even
// under the full supervisor shape: hooks + --permission-prompt-tool stdio + a large allowlist).
func initializeFrame(requestID string, servers []string) ([]byte, error) {
	request := map[string]any{"subtype": "initialize"}
	if len(servers) > 0 {
		advertised := make(map[string]any, len(servers))
		for _, name := range servers {
			advertised[name] = map[string]any{"type": "sdk", "name": name}
		}
		request["sdkMcpServers"] = advertised
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

// permissionAnswerPrefix tags the internal permission-answer frame. It MUST equal the
// library's agentsession.permissionAnswer prefix (the one home for the frame shape); the
// constant is duplicated here only because it is unexported in the library — a black-box
// test (TestPermissionAnswerPrefix_MatchesLibrary) pins them equal so a drift fails the gate.
const permissionAnswerPrefix = "eden:permission:"

// rationaleSeparator MUST equal the library's agentsession.rationaleSeparator (the 0x1f unit
// separator). It delimits the OPTIONAL audit Rationale the library appends to the answer
// frame; it is unexported in the library, so a black-box test pins them equal (drift fails).
const rationaleSeparator = "\x1f"

// parsePermissionAnswer decodes the internal eden:permission frame. ok=false for any text that
// is not a permission answer (a genuine Steer interjection), so Send falls through to the
// ordinary user-turn path for those. The frame is id:verdict:by[\x1frationale]; by may itself
// contain ':' (a "policy:name" identity), so only the first two ':' separators are structural,
// and the OPTIONAL audit rationale rides after a 0x1f separator that By can never contain (a
// frame without it parses byte-identically to the pre-ratification id:verdict:by).
func parsePermissionAnswer(text string) (parsedPermissionAnswer, bool) {
	if !strings.HasPrefix(text, permissionAnswerPrefix) {
		return parsedPermissionAnswer{}, false
	}
	rest := strings.TrimPrefix(text, permissionAnswerPrefix)
	requestID, afterID, ok := strings.Cut(rest, ":")
	if !ok {
		return parsedPermissionAnswer{}, false
	}
	verdict, byAndRationale, ok := strings.Cut(afterID, ":")
	if !ok {
		return parsedPermissionAnswer{}, false
	}
	if verdict != "allow" && verdict != "deny" {
		return parsedPermissionAnswer{}, false
	}
	// Split the optional audit rationale off the By identity (the 0x1f separator never
	// appears in a By, so this is unambiguous; absent separator -> the whole tail is By).
	by, rationale, _ := strings.Cut(byAndRationale, rationaleSeparator)
	return parsedPermissionAnswer{requestID: requestID, allow: verdict == "allow", by: by, rationale: rationale}, true
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
