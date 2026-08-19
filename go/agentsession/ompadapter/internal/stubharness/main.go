// Command stubharness is a TRIVIAL scripted stand-in for the headless `omp -p --mode json`
// CLI. omp's headless json mode is ONE-SHOT per turn, so this stub is too: each invocation
// emits exactly ONE turn (a session startup frame, an agent/turn start, an assistant
// message_start, streaming thinking/text deltas via message_update, a top-level
// tool_execution_start/tool_execution_end pair, a usage-bearing message_end, a turn_end, and
// an agent_end with the four-token ledger + USD cost), then exits 0. N consecutive turns on
// one session are therefore N invocations — the adapter's per-turn exec model, driven for
// real.
//
// The turn prompt arrives as the LAST positional argv exactly as real omp expects (the spike
// proved omp's headless json mode does NOT read the turn from stdin), and this stub ECHOES it
// into the frames, so consecutive turns on one session are distinguishable. It needs no
// credential and no network — it exists ONLY so the agentsession integration arm can exercise
// the REAL os/exec subprocess lifecycle and the REAL json parser on an ACTUAL process, WITHOUT
// a live OpenRouter call. It is never shipped.
//
// It also emits an UNKNOWN top-level frame ("rate_limit_event") so the integration arm proves
// the Extension survives a real subprocess too, and it copies the OPENROUTER_API_KEY canary
// nowhere — the credential-never-leaks guarantee is asserted on the real stream.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"time"
)

func main() {
	writer := bufio.NewWriter(os.Stdout)
	for _, line := range frames(turnPrompt(os.Args)) {
		emit(writer, line)
	}
}

// turnPrompt reads the turn text from the LAST positional argv, where buildArguments appends
// it after every flag. An invocation carrying no arguments yields the empty prompt.
func turnPrompt(arguments []string) string {
	if len(arguments) < 2 {
		return ""
	}
	return arguments[len(arguments)-1]
}

// frames is the scripted omp json stream for ONE turn — real omp json shapes captured in the
// live spike (session, agent_start, turn_start, assistant message_start, thinking/text deltas,
// a top-level tool execution pair, a usage-bearing message_end, turn_end, and the agent_end
// terminal with the four-token usage + USD cost split) — with this invocation's prompt echoed
// into the user message and the assistant's thinking/reply.
func frames(prompt string) []string {
	echoed := jsonString(prompt)
	thinking := jsonString("Considering: " + prompt)
	reply := jsonString("ok: " + prompt)
	return []string{
		`{"type":"session","version":3,"id":"stub-omp-1","timestamp":"2026-06-13T00:00:00.000Z","cwd":"/tmp/stub"}`,
		`{"type":"agent_start"}`,
		`{"type":"turn_start"}`,
		`{"type":"rate_limit_event","retryAfter":7}`,
		fmt.Sprintf(`{"type":"message_start","message":{"role":"user","content":[{"type":"text","text":%s}],"attribution":"user"}}`, echoed),
		fmt.Sprintf(`{"type":"message_end","message":{"role":"user","content":[{"type":"text","text":%s}],"attribution":"user"}}`, echoed),
		`{"type":"message_start","message":{"role":"assistant","content":[],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop"}}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"thinking_start","contentIndex":0},"message":{"role":"assistant","content":[]}}`,
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","contentIndex":0,"delta":%s},"message":{"role":"assistant","content":[]}}`, thinking),
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"thinking_end","contentIndex":0,"content":%s},"message":{"role":"assistant","content":[]}}`, thinking),
		`{"type":"tool_execution_start","toolCallId":"call_1","toolName":"read","args":{"path":"sample.txt"},"intent":"read sample.txt"}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"toolcall_delta","contentIndex":1,"delta":"{\"path\":\"sample.txt\"}"},"message":{"role":"assistant","content":[]}}`,
		`{"type":"tool_execution_end","toolCallId":"call_1","toolName":"read","result":{"content":[{"type":"text","text":"hello world\n"}]},"isError":false}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"text_start","contentIndex":2},"message":{"role":"assistant","content":[]}}`,
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","contentIndex":2,"delta":%s},"message":{"role":"assistant","content":[]}}`, reply),
		fmt.Sprintf(`{"type":"message_update","assistantMessageEvent":{"type":"text_end","contentIndex":2,"content":%s},"message":{"role":"assistant","content":[]}}`, reply),
		fmt.Sprintf(`{"type":"message_end","message":{"role":"assistant","content":[{"type":"thinking","thinking":%s},{"type":"text","text":%s}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop","usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"totalTokens":1078,"reasoningTokens":12,"cost":{"input":0.01,"output":0.002,"cacheRead":0.0003,"cacheWrite":0,"total":0.0123}}}}`, thinking, reply),
		fmt.Sprintf(`{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":%s}],"usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"cost":{"total":0.0123}}},"toolResults":[]}`, reply),
		fmt.Sprintf(`{"type":"agent_end","messages":[{"role":"user","content":[{"type":"text","text":%s}]},{"role":"assistant","content":[{"type":"thinking","thinking":%s},{"type":"text","text":%s}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop","duration":1500,"usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"totalTokens":1078,"reasoningTokens":12,"cost":{"input":0.01,"output":0.002,"cacheRead":0.0003,"cacheWrite":0,"total":0.0123}}}]}`, echoed, thinking, reply),
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

// emit writes one scripted line and flushes it, with a small pace so the parent's scanner
// observes a genuinely streamed sequence. A write fault means the parent is gone; exit rather
// than script into a closed pipe.
func emit(writer *bufio.Writer, line string) {
	if _, err := fmt.Fprintln(writer, line); err != nil {
		os.Exit(1)
	}
	if err := writer.Flush(); err != nil {
		os.Exit(1)
	}
	time.Sleep(2 * time.Millisecond)
}
