// Command stubharness is a TRIVIAL scripted stand-in for the `omp --mode rpc` CLI. Like the
// real thing it is ONE LONG-LIVED process per session: it announces `ready`, reads NDJSON
// commands on stdin, emits NDJSON frames on stdout, serves EVERY prompt it is given on the
// same process, and exits 0 on stdin EOF. N consecutive turns on one session are therefore ONE
// invocation — the adapter's long-lived session model, driven for real.
//
// It reproduces the three bidirectional exchanges the adapter must survive, each measured on
// omp 17.3.7 (fixtures/q3-probe*.txt):
//
//   - the startup handshake: `ready` first, then the host's negotiate_protocol and, when host
//     tools are registered, set_host_tools — each answered with its `response` frame;
//   - the approval dialog: a `select` extension_ui_request carrying NO timeout field, which
//     BLOCKS the turn until the host answers it (an unanswered one would stall the turn exactly
//     as the real harness does);
//   - the host-tool round trip: a host_tool_call the host answers with host_tool_result,
//     correlated on the RPC frame id.
//
// The turn prompt arrives on the stdin `prompt` frame (never argv) and is ECHOED into the
// frames, so consecutive turns on one session are distinguishable. It needs no credential and
// no network — it exists ONLY so the agentsession integration/lifecycle/load lanes can exercise
// the REAL os/exec subprocess lifecycle and the REAL frame parser on an ACTUAL process, WITHOUT
// a live OpenRouter call. It is never shipped.
//
// It also emits an UNKNOWN top-level frame ("rate_limit_event") so those lanes prove the
// Extension survives a real subprocess too, and it copies the OPENROUTER_API_KEY canary
// nowhere — the credential-never-leaks guarantee is asserted on the real stream.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"
)

// answerDeadline bounds the wait for a host answer to a blocking frame (the approval dialog or
// a host_tool_call). The real harness waits forever — that is the stall this stub exists to
// reproduce — but a test binary that hangs teaches nothing, so an unanswered frame ENDS the
// process and the lane fails on the turn boundary that never arrived.
const answerDeadline = 20 * time.Second

// emitPace spaces the scripted lines so the parent observes a genuinely streamed sequence.
const emitPace = 2 * time.Millisecond

// commandQueue buffers commands that arrive while a turn is being served.
const commandQueue = 16

// stubVersion is the coding-agent version line the adapter's binary-identity guard accepts
// (`omp/<semver>`), so the stub passes the same `--version` check the real omp does.
const stubVersion = "omp/17.3.7"

func main() {
	if wantsVersion(os.Args[1:]) {
		fmt.Println(stubVersion)
		return
	}
	agent := newAgent()
	agent.emit(`{"type":"ready","protocolVersion":1,"supportedProtocolVersions":[1,2],"maxFrameBytes":1048576,"maxReassembledFrameBytes":67108864}`)
	commands := make(chan frame, commandQueue)
	go agent.read(commands)
	for command := range commands {
		agent.serve(&command)
	}
}

// wantsVersion reports whether the adapter invoked the stub for its version line (Spawn's
// binary-identity probe) rather than to run a session.
func wantsVersion(args []string) bool {
	for _, arg := range args {
		if arg == "--version" {
			return true
		}
	}
	return false
}

// frame is the decoded stdin command envelope. The stub reads only the fields it acts on: an
// answer that carries no approving `value` — a confirm, a cancel, an unknown label — leaves
// Value empty, which the gate reads as "not approved".
type frame struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Message string `json:"message"`
	Tools   []struct {
		Name string `json:"name"`
	} `json:"tools"`
	Value string `json:"value"`
}

// agent holds the scripted session state: the stdout writer, the host tools the host
// registered, and the answers the reader routes back to a blocked turn.
type agent struct {
	out *bufio.Writer

	mu        sync.Mutex
	hostTools []string
	answers   map[string]chan frame

	nextID int
}

// newAgent builds the scripted session.
func newAgent() *agent {
	return &agent{out: bufio.NewWriter(os.Stdout), answers: make(map[string]chan frame)}
}

// read scans stdin, routing every answer to the turn waiting for it and every command to the
// serving loop. Closing commands on EOF is what ends the process — the stdin EOF the adapter's
// Close hands over.
func (a *agent) read(commands chan<- frame) {
	defer close(commands)
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 0, 64*1024), 4<<20)
	for scanner.Scan() {
		var command frame
		if err := json.Unmarshal(scanner.Bytes(), &command); err != nil {
			continue
		}
		switch command.Type {
		case "extension_ui_response", "host_tool_result":
			a.deliver(&command)
		default:
			commands <- command
		}
	}
}

// serve runs one stdin command to completion.
func (a *agent) serve(command *frame) {
	switch command.Type {
	case "negotiate_protocol":
		a.emit(fmt.Sprintf(`{"id":%s,"type":"response","command":"negotiate_protocol","success":true,"data":{"protocolVersion":2}}`, jsonString(command.ID)))
	case "set_host_tools":
		a.registerHostTools(command)
	case "prompt", "steer":
		a.emit(fmt.Sprintf(`{"id":%s,"type":"response","command":%s,"success":true}`, jsonString(command.ID), jsonString(command.Type)))
		a.turn(command.Message)
	case "abort":
		a.emit(fmt.Sprintf(`{"id":%s,"type":"response","command":"abort","success":true}`, jsonString(command.ID)))
	default:
		// An unmodeled command is acknowledged rather than dropped, so the host is never left
		// waiting on a response that will not come.
		a.emit(fmt.Sprintf(`{"id":%s,"type":"response","command":%s,"success":true}`, jsonString(command.ID), jsonString(command.Type)))
	}
}

// registerHostTools mounts the host's tools and acknowledges them exactly as the real harness
// does — the xd:// notice, then the response echoing the accepted names.
func (a *agent) registerHostTools(command *frame) {
	names := make([]string, 0, len(command.Tools))
	for _, tool := range command.Tools {
		names = append(names, tool.Name)
	}
	a.mu.Lock()
	a.hostTools = names
	a.mu.Unlock()
	for _, name := range names {
		a.emit(fmt.Sprintf(`{"type":"notice","level":"info","message":%s,"source":"xdev"}`, jsonString("xd://: mounted "+name)))
	}
	encoded, err := json.Marshal(names)
	if err != nil {
		encoded = []byte("[]")
	}
	a.emit(fmt.Sprintf(`{"id":%s,"type":"response","command":"set_host_tools","success":true,"data":{"toolNames":%s}}`,
		jsonString(command.ID), encoded))
}

// turn emits ONE turn's frames for the given prompt: the lifecycle chrome, an unknown frame,
// the echoed user message, the assistant's thinking, the approval-gated `read` tool, the host
// tool when one is registered, the assistant's reply, and the usage-bearing boundary.
func (a *agent) turn(prompt string) {
	echoed := jsonString(prompt)
	thinking := jsonString("Considering: " + prompt)
	reply := jsonString("ok: " + prompt)

	a.emit(`{"type":"agent_start"}`, `{"type":"turn_start"}`, `{"type":"rate_limit_event","retryAfter":7}`)
	a.emit(
		fmt.Sprintf(`{"type":"message_start","message":{"role":"user","content":[{"type":"text","text":%s}],"attribution":"user"}}`, echoed),
		fmt.Sprintf(`{"type":"message_end","message":{"role":"user","content":[{"type":"text","text":%s}],"attribution":"user"}}`, echoed),
		`{"type":"message_start","message":{"role":"assistant","content":[],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop"}}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"thinking_start","contentIndex":0},"message":{"role":"assistant","content":[]}}`,
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","contentIndex":0,"delta":%s},"message":{"role":"assistant","content":[]}}`, thinking),
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"thinking_end","contentIndex":0,"content":%s},"message":{"role":"assistant","content":[]}}`, thinking),
	)

	a.gatedRead()
	a.hostToolRoundTrip()

	a.emit(
		`{"type":"message_update","assistantMessageEvent":{"type":"text_start","contentIndex":2},"message":{"role":"assistant","content":[]}}`,
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","contentIndex":2,"delta":%s},"message":{"role":"assistant","content":[]}}`, reply),
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"text_end","contentIndex":2,"content":%s},"message":{"role":"assistant","content":[]}}`, reply),
		fmt.Sprintf(`{"type":"message_end","message":{"role":"assistant","content":[{"type":"thinking","thinking":%s},{"type":"text","text":%s}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop","usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"totalTokens":1078,"reasoningTokens":12,"cost":{"input":0.01,"output":0.002,"cacheRead":0.0003,"cacheWrite":0,"total":0.0123}}}}`, thinking, reply),
		fmt.Sprintf(`{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":%s}],"usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"cost":{"total":0.0123}}},"toolResults":[]}`, reply),
		fmt.Sprintf(`{"type":"agent_end","messages":[{"role":"user","content":[{"type":"text","text":%s}]},{"role":"assistant","content":[{"type":"thinking","thinking":%s},{"type":"text","text":%s}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop","duration":1500,"usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"totalTokens":1078,"reasoningTokens":12,"cost":{"input":0.01,"output":0.002,"cacheRead":0.0003,"cacheWrite":0,"total":0.0123}}}]}`, echoed, thinking, reply),
	)
}

// gatedRead runs the turn's `read` tool THROUGH the approval gate: the no-timeout `select`
// dialog goes out and the turn waits for the host's answer, exactly as `--approval-mode
// always-ask` makes the real harness wait. An approval runs the tool; anything else denies it
// and the turn continues (a denial is a tool result, not a transport fault).
func (a *agent) gatedRead() {
	dialogID := a.snowflake()
	answer, answered := a.await(dialogID, fmt.Sprintf(
		`{"type":"extension_ui_request","id":%s,"method":"select","title":"Allow tool: read\nCommand: read sample.txt","options":["Approve","Deny"]}`,
		jsonString(dialogID),
	))
	if !answered {
		return
	}
	a.emit(
		`{"type":"tool_execution_start","toolCallId":"call_1","toolName":"read","args":{"path":"sample.txt"},"intent":"read sample.txt"}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"toolcall_delta","contentIndex":1,"delta":"{\"path\":\"sample.txt\"}"},"message":{"role":"assistant","content":[]}}`,
	)
	if answer.Value == "Approve" {
		a.emit(`{"type":"tool_execution_end","toolCallId":"call_1","toolName":"read","result":{"content":[{"type":"text","text":"hello world\n"}]},"isError":false}`)
		return
	}
	a.emit(`{"type":"tool_execution_end","toolCallId":"call_1","toolName":"read","result":{"content":[{"type":"text","text":"Tool call denied by user: read"}]},"isError":true}`)
}

// hostToolRoundTrip calls the FIRST registered host tool and waits for the host's
// host_tool_result, echoing it back as the tool execution pair the model sees. With no host
// tools registered there is nothing to call and the turn moves on.
func (a *agent) hostToolRoundTrip() {
	a.mu.Lock()
	tools := a.hostTools
	a.mu.Unlock()
	if len(tools) == 0 {
		return
	}
	name := tools[0]
	callID := a.snowflake()
	if _, answered := a.await(callID, fmt.Sprintf(
		`{"type":"host_tool_call","id":%s,"toolCallId":"call_host_1","toolName":%s,"arguments":{"payload":"hello-eden"}}`,
		jsonString(callID), jsonString(name),
	)); !answered {
		return
	}
	a.emit(
		fmt.Sprintf(`{"type":"tool_execution_start","toolCallId":"call_host_1","toolName":%s,"args":{"payload":"hello-eden"}}`, jsonString(name)),
		fmt.Sprintf(`{"type":"tool_execution_end","toolCallId":"call_host_1","toolName":%s,"result":{"content":[{"type":"text","text":"host tool answered"}],"details":{}},"isError":false}`, jsonString(name)),
	)
}

// await emits a frame that BLOCKS the turn and waits for the host's answer to its id. A wait
// that runs out ends the process rather than hanging the lane. The waiting entry is dropped on
// both arms explicitly rather than on a defer, which the timeout's exit would skip.
func (a *agent) await(id, request string) (frame, bool) {
	waiting := make(chan frame, 1)
	a.mu.Lock()
	a.answers[id] = waiting
	a.mu.Unlock()

	a.emit(request)
	select {
	case answer := <-waiting:
		a.forget(id)
		return answer, true
	case <-time.After(answerDeadline):
		a.forget(id)
		fmt.Fprintf(os.Stderr, "stubharness: no answer to %s within %s\n", id, answerDeadline)
		os.Exit(1)
		return frame{}, false
	}
}

// forget drops a settled waiting entry.
func (a *agent) forget(id string) {
	a.mu.Lock()
	delete(a.answers, id)
	a.mu.Unlock()
}

// deliver routes an answer to the turn waiting on its id. An answer to an id nobody is waiting
// on is dropped, exactly as the real bridge drops an unmatched correlation id.
func (a *agent) deliver(answer *frame) {
	a.mu.Lock()
	waiting, found := a.answers[answer.ID]
	a.mu.Unlock()
	if !found {
		return
	}
	select {
	case waiting <- *answer:
	default:
	}
}

// snowflake returns the next agent-side frame id (omp's are snowflakes; the shape of the value
// is not part of the contract, only that the host echoes it back).
func (a *agent) snowflake() string {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.nextID++
	return "stub-frame-" + strconv.Itoa(a.nextID)
}

// emit writes scripted lines and flushes them. A write fault means the parent is gone; exit
// rather than script into a closed pipe.
func (a *agent) emit(lines ...string) {
	for _, line := range lines {
		if _, err := fmt.Fprintln(a.out, line); err != nil {
			os.Exit(1)
		}
		if err := a.out.Flush(); err != nil {
			os.Exit(1)
		}
		time.Sleep(emitPace)
	}
}

// jsonString renders s as a JSON string literal, quotes included, so an echoed prompt cannot
// break the frame it rides in.
func jsonString(s string) string {
	encoded, err := json.Marshal(s)
	if err != nil {
		return `""`
	}
	return string(encoded)
}
