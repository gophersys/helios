package claudeadapter_test

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// capturedCanUseToolFrame is a REAL can_use_tool control_request line captured from claude
// v2.1.177 driven under -p --input-format stream-json --output-format stream-json
// --permission-mode default --permission-prompt-tool stdio when the model called an
// out-of-grant Bash tool (curl > file). It is the exact wire shape the normalizer must map.
const capturedCanUseToolFrame = `{"type":"control_request","request_id":"req-77","request":{"subtype":"can_use_tool","tool_name":"Bash","display_name":"Bash","input":{"command":"curl -s https://example.com -o /tmp/out.txt","description":"Fetch and save"},"decision_reason":{"type":"other","reason":"command could not be statically validated as safe"},"tool_use_id":"toolu_01abc"}}`

// TestNormalize_ControlRequest_CanUseTool is the fast, non-vacuous proof of the permission
// parser: the captured can_use_tool control_request normalizes to ONE EventPermissionRequest
// carrying the request id, the tool name, and the redacted decision reason — NOT an opaque
// EventExtension (the bug). The raw input is held off-stream (for the updatedInput echo), so
// it must NOT appear on the emitted Event's payload.
func TestNormalize_ControlRequest_CanUseTool(t *testing.T) {
	t.Parallel()
	events := claudeadapter.NormalizeLineForTest([]byte(capturedCanUseToolFrame))

	if len(events) != 1 {
		t.Fatalf("can_use_tool must normalize to exactly one event, got %d: %+v", len(events), events)
	}
	ev := events[0]
	if ev.Kind != agentsession.EventPermissionRequest {
		t.Fatalf("can_use_tool must map to EventPermissionRequest, got %v (the opaque-Extension bug)", ev.Kind)
	}
	if ev.Kind == agentsession.EventExtension {
		t.Fatal("can_use_tool must NOT fall through to EventExtension")
	}
	if ev.Permission == nil {
		t.Fatal("EventPermissionRequest carried no PermissionPayload")
	}
	if ev.Permission.RequestID != "req-77" {
		t.Errorf("RequestID = %q, want req-77", ev.Permission.RequestID)
	}
	if ev.Permission.Tool != "Bash" {
		t.Errorf("Tool = %q, want Bash", ev.Permission.Tool)
	}
	if ev.Permission.Reason == "" || !strings.Contains(ev.Permission.Reason, "statically validated") {
		t.Errorf("Reason did not carry the decision_reason text: %q", ev.Permission.Reason)
	}
	// The raw command (the input) is held off-stream; it must not leak onto the Event.
	if strings.Contains(ev.Permission.Reason, "curl") {
		t.Errorf("the tool input must not leak onto the Event payload; Reason=%q", ev.Permission.Reason)
	}
}

// TestNormalize_ControlRequest_WeakenToConfirm is the weaken-to-confirm half: it proves the
// test is non-vacuous by feeding a control_request whose subtype is NOT can_use_tool (an
// initialize ack). That MUST NOT emit a permission event — it is serviced on the control path.
// If the normalizer naively mapped every control_request to a permission event, this fails.
func TestNormalize_ControlRequest_WeakenToConfirm(t *testing.T) {
	t.Parallel()
	initAck := `{"type":"control_request","request_id":"x","request":{"subtype":"initialize","sdkMcpServers":["eden"]}}`
	events := claudeadapter.NormalizeLineForTest([]byte(initAck))
	for i := range events {
		if events[i].Kind == agentsession.EventPermissionRequest {
			t.Fatalf("a non-can_use_tool control_request must not become an EventPermissionRequest")
		}
	}
}

// TestNormalize_CanUseTool_SkillScoped proves the Skill/SlashCommand wrapper is scoped with the
// INVOKED sub-command name so the library's scoped-grant machinery can gate WHICH skill. A bare
// "Skill" matches no scoped grant and always escalates (the supervisor's /propose-questionnaire
// was default-denied as an unscoped "Skill"); the normalizer folds input.skill into the tool
// string as "Skill(propose-questionnaire)" (the same scope-in-parens shape as "Bash(go test)").
func TestNormalize_CanUseTool_SkillScoped(t *testing.T) {
	t.Parallel()
	frame := `{"type":"control_request","request_id":"req-skill","request":{"subtype":"can_use_tool","tool_name":"Skill","input":{"skill":"propose-questionnaire","args":"generate it"},"tool_use_id":"toolu_skill"}}`
	events := claudeadapter.NormalizeLineForTest([]byte(frame))
	if len(events) != 1 || events[0].Permission == nil {
		t.Fatalf("Skill can_use_tool must map to one EventPermissionRequest, got %+v", events)
	}
	if got := events[0].Permission.Tool; got != "Skill(propose-questionnaire)" {
		t.Fatalf("Skill tool must be scoped with the invoked skill name; Tool = %q, want Skill(propose-questionnaire)", got)
	}
	// A SlashCommand input carries the raw "/name args" line; the leading /token's name is folded.
	slash := `{"type":"control_request","request_id":"req-slash","request":{"subtype":"can_use_tool","tool_name":"SlashCommand","input":{"command":"/record-answer {\"question\":\"01-x\"}"},"tool_use_id":"toolu_slash"}}`
	sevents := claudeadapter.NormalizeLineForTest([]byte(slash))
	if len(sevents) != 1 || sevents[0].Permission == nil {
		t.Fatalf("SlashCommand can_use_tool must map to one EventPermissionRequest, got %+v", sevents)
	}
	if got := sevents[0].Permission.Tool; got != "SlashCommand(record-answer)" {
		t.Fatalf("SlashCommand tool must be scoped with the command name; Tool = %q, want SlashCommand(record-answer)", got)
	}
	// A non-wrapper tool (Bash) is returned unchanged — the fold is wrapper-only, non-vacuous.
	bare := claudeadapter.NormalizeLineForTest([]byte(capturedCanUseToolFrame))
	if len(bare) != 1 || bare[0].Permission == nil || bare[0].Permission.Tool != "Bash" {
		t.Fatalf("a non-wrapper tool must be unchanged; got %+v", bare)
	}
}

// TestInitializeFrame_SdkMcpServersIsArrayOfNames pins the host-tool advertise shape: the
// initialize control_request must advertise sdkMcpServers as a JSON ARRAY of bare server NAMES
// (the CLI's `array(string)` Zod schema; the CLI synthesizes the {type:"sdk",name} descriptor
// itself). It must NOT be an object/map — the object form fails the schema, the CLI drops the
// server, and the model is told "not connected". The object-is-gone check is the non-vacuous
// regression (an earlier mis-fix emitted the object form).
func TestInitializeFrame_SdkMcpServersIsArrayOfNames(t *testing.T) {
	t.Parallel()
	frame, err := claudeadapter.InitializeFrameForTest([]agentsession.HostTool{{Name: "eden_commit_transition"}})
	if err != nil {
		t.Fatalf("InitializeFrameForTest: %v", err)
	}
	var decoded struct {
		Request struct {
			Subtype       string          `json:"subtype"`
			SdkMcpServers json.RawMessage `json:"sdkMcpServers"`
		} `json:"request"`
	}
	if err := json.Unmarshal(frame, &decoded); err != nil {
		t.Fatalf("unmarshal initialize frame: %v (%s)", err, frame)
	}
	if decoded.Request.Subtype != "initialize" {
		t.Fatalf("subtype = %q, want initialize", decoded.Request.Subtype)
	}
	// Non-vacuous regression: the object form (the not-connected mis-fix) must be GONE.
	if len(decoded.Request.SdkMcpServers) > 0 && decoded.Request.SdkMcpServers[0] == '{' {
		t.Fatalf("sdkMcpServers is a JSON object (fails the CLI schema → server dropped): %s", decoded.Request.SdkMcpServers)
	}
	var names []string
	if err := json.Unmarshal(decoded.Request.SdkMcpServers, &names); err != nil {
		t.Fatalf("sdkMcpServers must be a JSON array of names: %v (%s)", err, decoded.Request.SdkMcpServers)
	}
	if len(names) != 1 || names[0] != "eden" {
		t.Fatalf("sdkMcpServers = %v, want [eden]", names)
	}
}

// TestHostToolRouter_AnswersNotificationsInitialized pins the round-trip fix: an mcp_message the
// CLI tunnels for a JSON-RPC NOTIFICATION (notifications/initialized — no id) MUST still be
// answered (ok=true) with an mcp_response, or the CLI's client.connect() blocks and the host-tool
// round-trip never starts. The router previously returned ok=false for the default case (no
// control_response written) — the "MCP server not connected" stall. Non-vacuous: the empty-result
// answer must be a valid jsonrpc result envelope.
func TestHostToolRouter_AnswersNotificationsInitialized(t *testing.T) {
	t.Parallel()
	tools := []agentsession.HostTool{{Name: "eden_commit_transition"}}
	resp, _, ok := claudeadapter.HostToolRouteForTest(tools, []byte(`{"jsonrpc":"2.0","method":"notifications/initialized"}`))
	if !ok {
		t.Fatalf("notifications/initialized must be answered (ok=true) or client.connect() blocks")
	}
	raw, err := json.Marshal(resp)
	if err != nil {
		t.Fatalf("marshal notification response: %v", err)
	}
	var env struct {
		JSONRPC string          `json:"jsonrpc"`
		Result  json.RawMessage `json:"result"`
	}
	if err := json.Unmarshal(raw, &env); err != nil || env.JSONRPC != "2.0" || env.Result == nil {
		t.Fatalf("notification answer must be a jsonrpc result envelope: %s", raw)
	}
}

// TestHostToolRouter_InitializeAdvertisesToolsCapability pins that the host's MCP initialize
// answer declares capabilities.tools — which is what makes the CLI proceed to tools/list (it
// gates on `if (capabilities?.tools)`). Without it the server connects but no tools are listed.
func TestHostToolRouter_InitializeAdvertisesToolsCapability(t *testing.T) {
	t.Parallel()
	tools := []agentsession.HostTool{{Name: "eden_commit_transition"}}
	resp, _, ok := claudeadapter.HostToolRouteForTest(tools, []byte(`{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}`))
	if !ok {
		t.Fatalf("initialize must be answered")
	}
	raw, _ := json.Marshal(resp) //nolint:errcheck // test marshal of a known map.
	if !strings.Contains(string(raw), `"capabilities"`) || !strings.Contains(string(raw), `"tools"`) {
		t.Fatalf("initialize answer must declare capabilities.tools (gates the CLI's tools/list): %s", raw)
	}
}

// TestInitializeFrame_NoHostToolsIsBareHandshake pins the chat path: with no host tools the
// initialize frame carries NO sdkMcpServers key (a bare handshake) — so the chat/permission
// paths are byte-unaffected by the host-tool advertisement.
func TestInitializeFrame_NoHostToolsIsBareHandshake(t *testing.T) {
	t.Parallel()
	frame, err := claudeadapter.InitializeFrameForTest(nil)
	if err != nil {
		t.Fatalf("InitializeFrameForTest(nil): %v", err)
	}
	if strings.Contains(string(frame), "sdkMcpServers") {
		t.Fatalf("a no-host-tools initialize must omit sdkMcpServers: %s", frame)
	}
}

// TestControlRequest_NotOpaqueExtension pins the regression directly: the SAME captured
// can_use_tool frame, if the control_request case were absent, would fall to the normalizer's
// default arm and become an EventExtension. Assert it does NOT.
func TestControlRequest_NotOpaqueExtension(t *testing.T) {
	t.Parallel()
	events := claudeadapter.NormalizeLineForTest([]byte(capturedCanUseToolFrame))
	for i := range events {
		if events[i].Kind == agentsession.EventExtension {
			t.Fatalf("can_use_tool leaked as an opaque Extension (the pre-fix bug)")
		}
	}
}

// TestPermissionDecisionFrame_Allow proves the ALLOW translation: the resolved decision becomes
// a control_response (NOT a {"type":"user"} turn), subtype success, correlated by request id,
// carrying behavior=allow and the ORIGINAL input echoed as updatedInput (claude rejects an
// allow that omits a valid updatedInput with a ZodError — verified live).
func TestPermissionDecisionFrame_Allow(t *testing.T) {
	t.Parallel()
	originalInput := []byte(`{"command":"curl -s https://example.com -o /tmp/out.txt"}`)
	frame, err := claudeadapter.PermissionDecisionFrameForTest("req-77", true, "user-42", originalInput)
	if err != nil {
		t.Fatalf("build allow frame: %v", err)
	}
	decoded := decodeFrame(t, frame)

	if decoded["type"] != "control_response" {
		t.Fatalf("decision must be a control_response, got %v (the stdin-user-turn bug)", decoded["type"])
	}
	response := mapOf(t, decoded["response"])
	if response["subtype"] != "success" || response["request_id"] != "req-77" {
		t.Errorf("control_response not correlated: %+v", response)
	}
	result := mapOf(t, response["response"])
	if result["behavior"] != "allow" {
		t.Errorf("behavior = %v, want allow", result["behavior"])
	}
	updated := mapOf(t, result["updatedInput"])
	if updated["command"] != "curl -s https://example.com -o /tmp/out.txt" {
		t.Errorf("updatedInput must echo the original input, got %+v", updated)
	}
}

// TestPermissionDecisionFrame_Deny proves the DENY translation: behavior=deny carrying the
// operator-safe message naming the deciding identity, and NO updatedInput.
func TestPermissionDecisionFrame_Deny(t *testing.T) {
	t.Parallel()
	frame, err := claudeadapter.PermissionDecisionFrameForTest("req-9", false, "policy:clean-room", nil)
	if err != nil {
		t.Fatalf("build deny frame: %v", err)
	}
	decoded := decodeFrame(t, frame)
	result := mapOf(t, mapOf(t, decoded["response"])["response"])
	if result["behavior"] != "deny" {
		t.Errorf("behavior = %v, want deny", result["behavior"])
	}
	message, ok := result["message"].(string)
	if !ok {
		t.Fatalf("deny result must carry a string message, got %T", result["message"])
	}
	if !strings.Contains(message, "policy:clean-room") {
		t.Errorf("deny message must name the decider, got %q", message)
	}
	if _, present := result["updatedInput"]; present {
		t.Errorf("a deny must not carry updatedInput")
	}
}

// TestPermissionAnswerPrefix_MatchesLibrary pins the one-home invariant: the adapter's internal
// frame prefix equals the library's agentsession.permissionAnswer prefix. A drift would make
// the adapter mis-parse the library's resolved-decision frame and silently fall back to a user
// turn (the very bug being fixed). The library prefix is reconstructed from the frame a real
// Decision renders (TestResolve_TranslatesToControlResponse drives the live shape end-to-end);
// here the literal is pinned so the duplication is detectable.
func TestPermissionAnswerPrefix_MatchesLibrary(t *testing.T) {
	t.Parallel()
	if got := claudeadapter.PermissionAnswerPrefixForTest(); got != "eden:permission:" {
		t.Fatalf("adapter permission-answer prefix = %q, want eden:permission: (library drift)", got)
	}
}

// TestParsePermissionAnswer_Roundtrip proves the internal frame parse: an allow with a
// colon-bearing policy identity parses to (id, allow, by) with the identity intact, and a
// genuine Steer interjection (no prefix) is NOT parsed as a permission answer.
func TestParsePermissionAnswer_Roundtrip(t *testing.T) {
	t.Parallel()
	id, allow, by, ok := claudeadapter.ParsePermissionAnswerForTest("eden:permission:req-1:allow:policy:clean-room")
	if !ok || id != "req-1" || !allow || by != "policy:clean-room" {
		t.Errorf("parse allow frame = (%q,%v,%q,%v), want (req-1,true,policy:clean-room,true)", id, allow, by, ok)
	}
	id, allow, by, ok = claudeadapter.ParsePermissionAnswerForTest("eden:permission:req-2:deny:user-7")
	if !ok || id != "req-2" || allow || by != "user-7" {
		t.Errorf("parse deny frame = (%q,%v,%q,%v), want (req-2,false,user-7,true)", id, allow, by, ok)
	}
	if _, _, _, ok := claudeadapter.ParsePermissionAnswerForTest("focus on the tests"); ok {
		t.Errorf("a genuine Steer interjection must NOT parse as a permission answer")
	}
}

// TestParsePermissionAnswer_Rationale proves the ADDITIVE audit-rationale decode: a frame
// with the optional 0x1f-separated rationale splits the By identity from the rationale
// (the By identity stays intact, even a colon-bearing "policy:risk-clamp"), while a frame
// WITHOUT the separator parses byte-identically to the pre-ratification id:verdict:by (no
// rationale, By is the whole tail). This is the non-breaking-frame guarantee.
func TestParsePermissionAnswer_Rationale(t *testing.T) {
	t.Parallel()
	sep := claudeadapter.RationaleSeparatorForTest()
	// A clamped deny carries By="policy:risk-clamp" + a rationale; both decode intact.
	by, rationale, ok := claudeadapter.ParsePermissionAnswerRationaleForTest("eden:permission:req-1:deny:policy:risk-clamp" + sep + "high-risk tool: overridden")
	if !ok || by != "policy:risk-clamp" || rationale != "high-risk tool: overridden" {
		t.Errorf("rationale frame = (%q,%q,%v), want (policy:risk-clamp, high-risk tool: overridden, true)", by, rationale, ok)
	}
	// A frame with NO rationale: By is the whole tail, rationale empty (back-compat).
	by, rationale, ok = claudeadapter.ParsePermissionAnswerRationaleForTest("eden:permission:req-2:allow:user-7")
	if !ok || by != "user-7" || rationale != "" {
		t.Errorf("no-rationale frame = (%q,%q,%v), want (user-7, \"\", true)", by, rationale, ok)
	}
}

// TestRationaleSeparator_MatchesLibrary pins the one-home invariant for the audit-rationale
// separator: the adapter's separator equals the library's (a drift would corrupt the By
// identity by mis-splitting the frame). The library uses the ASCII unit separator (0x1f).
func TestRationaleSeparator_MatchesLibrary(t *testing.T) {
	t.Parallel()
	if got := claudeadapter.RationaleSeparatorForTest(); got != "\x1f" {
		t.Fatalf("adapter rationale separator = %q, want 0x1f (library drift)", got)
	}
}

// TestBuildArguments_PermissionPromptToolStdio proves the LOAD-BEARING flag: when OnPermission
// drives the round-trip (default mode), the args carry --permission-prompt-tool stdio (without
// which real claude bypasses the gate and auto-allows), and acceptEdits mode does NOT carry it.
func TestBuildArguments_PermissionPromptToolStdio(t *testing.T) {
	t.Parallel()
	withPolicy := agentsession.Spec{
		OnPermission: func(agentsession.PermissionRequest) agentsession.Decision { return agentsession.Decision{} },
	}
	args := claudeadapter.BuildArgumentsForTest(withPolicy, agentsession.Route{Model: "m"})
	if !argPairPresent(args, "--permission-prompt-tool", "stdio") {
		t.Errorf("default mode must carry --permission-prompt-tool stdio; got %v", args)
	}

	withoutPolicy := claudeadapter.BuildArgumentsForTest(agentsession.Spec{}, agentsession.Route{Model: "m"})
	if argPresent(withoutPolicy, "--permission-prompt-tool") {
		t.Errorf("acceptEdits mode must NOT carry --permission-prompt-tool; got %v", withoutPolicy)
	}
}

// TestBuildArguments_IncludePartialMessages proves the spawn enables token-level streaming:
// --include-partial-messages is what makes claude emit the incremental `stream_event` frames the
// normalizer turns into token-by-token text/thinking deltas (without it, text arrives as one
// finished message). It is unconditional (every session streams).
func TestBuildArguments_IncludePartialMessages(t *testing.T) {
	t.Parallel()
	args := claudeadapter.BuildArgumentsForTest(agentsession.Spec{}, agentsession.Route{Model: "m"})
	if !argPresent(args, "--include-partial-messages") {
		t.Errorf("the spawn must enable token streaming via --include-partial-messages; got %v", args)
	}
}

// TestHostToolRouter_ListAndCall proves the host-tool wire wiring: tools/list returns the
// HostTool descriptors, and tools/call routes into the Handler and returns its result plus an
// EventToolUpdate marked IsHostTool. The model sees the tool as mcp__eden__<name>.
func TestHostToolRouter_ListAndCall(t *testing.T) {
	t.Parallel()
	var handlerSaw string
	tools := []agentsession.HostTool{{
		Name:        "lookup",
		Description: "look up a record",
		Schema:      []byte(`{"type":"object","properties":{"id":{"type":"string"}}}`),
		Handler: func(_ context.Context, args []byte) ([]byte, error) {
			handlerSaw = string(args)
			return []byte(`{"record":"found"}`), nil
		},
	}}

	listResp, _, ok := claudeadapter.HostToolRouteForTest(tools, []byte(`{"jsonrpc":"2.0","id":1,"method":"tools/list"}`))
	if !ok {
		t.Fatal("tools/list must produce a response")
	}
	if !strings.Contains(jsonString(t, listResp), `"lookup"`) {
		t.Errorf("tools/list must advertise the host tool; got %s", jsonString(t, listResp))
	}

	callResp, events, ok := claudeadapter.HostToolRouteForTest(tools,
		[]byte(`{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup","arguments":{"id":"x"}}}`))
	if !ok {
		t.Fatal("tools/call must produce a response")
	}
	if handlerSaw == "" || !strings.Contains(handlerSaw, `"id":"x"`) {
		t.Errorf("Handler did not receive the arguments; saw %q", handlerSaw)
	}
	if !strings.Contains(jsonString(t, callResp), "found") {
		t.Errorf("tools/call result must carry the Handler output; got %s", jsonString(t, callResp))
	}
	if !hasHostToolUpdate(events) {
		t.Errorf("tools/call must surface an EventToolUpdate marked IsHostTool; got %+v", events)
	}
}

// decodeFrame parses a trailing-newline control frame into a map.
func decodeFrame(t *testing.T, frame []byte) map[string]any {
	t.Helper()
	var decoded map[string]any
	if err := json.Unmarshal(frame, &decoded); err != nil {
		t.Fatalf("frame is not valid JSON: %v\n%s", err, frame)
	}
	return decoded
}

// mapOf asserts v is a JSON object and returns it.
func mapOf(t *testing.T, v any) map[string]any {
	t.Helper()
	m, ok := v.(map[string]any)
	if !ok {
		t.Fatalf("expected a JSON object, got %T (%v)", v, v)
	}
	return m
}

// jsonString renders any value as compact JSON for substring assertions.
func jsonString(t *testing.T, v any) string {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	return string(b)
}

// hasHostToolUpdate reports whether events carry an EventToolUpdate marked IsHostTool.
func hasHostToolUpdate(events []agentsession.Event) bool {
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventToolUpdate && ev.Tool != nil && ev.Tool.IsHostTool {
			return true
		}
	}
	return false
}

// argPairPresent reports whether args contains flag immediately followed by value.
func argPairPresent(args []string, flag, value string) bool {
	for i := 0; i+1 < len(args); i++ {
		if args[i] == flag && args[i+1] == value {
			return true
		}
	}
	return false
}

// argPresent reports whether args contains flag.
func argPresent(args []string, flag string) bool {
	for _, a := range args {
		if a == flag {
			return true
		}
	}
	return false
}
