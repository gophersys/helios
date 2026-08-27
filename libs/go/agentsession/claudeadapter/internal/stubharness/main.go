// Command stubharness is a TRIVIAL scripted stand-in for the headless `claude` CLI. It is
// TURN-DRIVEN: it reads the adapter's stream-json stdin line by line and, for every
// {"type":"user"} turn, emits ONE scripted turn on stdout (an assistant message with text +
// a tool_use, a user tool_result, a usage-bearing assistant line, and a terminal result with
// the four-token ledger), then goes back to reading. One process therefore serves N
// consecutive turns, which is what a session that survives its own turn needs proven on a
// REAL subprocess. Every other stdin line — the initialize control_request, a permission or
// mcp control_response — is read and ignored: only a user turn scripts a turn. On stdin EOF
// (the library's Abort/Close closes stdin) it exits 0.
//
// The turn number and the prompt text are woven into each turn, so consecutive turns on one
// process are distinguishable. It needs no credential and no network — it exists ONLY so the
// agentsession integration arm can exercise the REAL os/exec subprocess lifecycle and the
// REAL stream-json parser on an ACTUAL process, WITHOUT a live authenticated claude. It is
// never shipped.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"time"
)

// maxLineBytes bounds one stdin line, mirroring the adapter's own scanner budget so a long
// turn is read whole rather than split into fragments that parse as nothing.
const maxLineBytes = 4 << 20

// sessionInit is the once-per-session system/init handshake, emitted ahead of the FIRST turn
// exactly as real claude does in stream-json input mode (it withholds init until a turn
// arrives — the conn signals Ready itself, so this line is session metadata, not readiness).
const sessionInit = `{"type":"system","subtype":"init","session_id":"stub-1","model":"stub-fable","tools":["Write"]}`

func main() {
	writer := bufio.NewWriter(os.Stdout)
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	turn := 0
	for scanner.Scan() {
		prompt, isTurn := userTurnText(scanner.Bytes())
		if !isTurn {
			continue
		}
		turn++
		if turn == 1 {
			emit(writer, sessionInit)
		}
		for _, line := range turnLines(turn, prompt) {
			emit(writer, line)
		}
	}
}

// userTurnText reports whether a stdin line is a {"type":"user"} turn, and returns that turn's
// text. The adapter renders the turn content as a plain JSON string; any other content shape
// still scripts a turn, with an empty echo.
func userTurnText(line []byte) (string, bool) {
	var envelope struct {
		Type    string `json:"type"`
		Message struct {
			Content json.RawMessage `json:"content"`
		} `json:"message"`
	}
	if err := json.Unmarshal(line, &envelope); err != nil || envelope.Type != "user" {
		return "", false
	}
	var text string
	if err := json.Unmarshal(envelope.Message.Content, &text); err != nil {
		return "", true
	}
	return text, true
}

// turnLines scripts ONE turn: the real Claude Code shapes, with the turn number and the prompt
// woven in. The tool_use id is per-turn because the normalizer correlates ToolStart/ToolEnd by
// it, and an id reused across turns would fold two turns' tool calls into one. The unknown
// rate_limit_event rides along so the integration arm proves the Extension survives a real
// subprocess on every turn, not only the first.
func turnLines(turn int, prompt string) []string {
	call := fmt.Sprintf("toolu_%d", turn)
	opening := jsonString("Creating the file for: " + prompt)
	closing := jsonString("Done: " + prompt)
	return []string{
		`{"type":"rate_limit_event","retry_after":7}`,
		fmt.Sprintf(`{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"text","text":%s}]}}`, opening),
		fmt.Sprintf(`{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"tool_use","id":%q,"name":"Write","input":{"file_path":"note.txt","content":"hi"}}]}}`, call),
		fmt.Sprintf(`{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":%q,"content":"File created"}]}}`, call),
		fmt.Sprintf(`{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"text","text":%s}],"usage":{"input_tokens":120,"output_tokens":18,"cache_read_input_tokens":900,"cache_creation_input_tokens":40}}}`, closing),
		fmt.Sprintf(`{"type":"result","subtype":"success","is_error":false,"num_turns":%d,"duration_ms":1500,"total_cost_usd":0.0123,"result":%s,"stop_reason":"end_turn","usage":{"input_tokens":120,"output_tokens":18,"cache_read_input_tokens":900,"cache_creation_input_tokens":40}}`, turn, closing),
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
