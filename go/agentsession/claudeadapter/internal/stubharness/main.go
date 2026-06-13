// Command stubharness is a TRIVIAL scripted stand-in for the headless `claude` CLI: it
// emits a fixed sequence of stream-json lines to stdout (a system/init handshake, an
// assistant message with text + a tool_use, a user tool_result, a usage-bearing assistant
// line, and a terminal result with the four-token ledger), then exits 0. It reads its
// stdin to EOF (the library's Abort/Close closes stdin) and does NOT require any
// credential or network — it exists ONLY so the agentsession integration arm can exercise
// the REAL os/exec subprocess lifecycle and the REAL stream-json parser on an ACTUAL
// process, WITHOUT a live authenticated claude. It is never shipped.
package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"time"
)

// streamLines is the scripted stream-json the stub emits — real Claude Code shapes
// (system init, assistant text/tool_use, user tool_result, the four-token result),
// including an unknown rate_limit_event so the integration arm proves the Extension
// survives a real subprocess too.
var streamLines = []string{
	`{"type":"system","subtype":"init","session_id":"stub-1","model":"stub-fable","tools":["Write"]}`,
	`{"type":"rate_limit_event","retry_after":7}`,
	`{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"text","text":"Creating the file."}]}}`,
	`{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"tool_use","id":"toolu_1","name":"Write","input":{"file_path":"note.txt","content":"hi"}}]}}`,
	`{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"File created"}]}}`,
	`{"type":"assistant","message":{"model":"stub-fable","role":"assistant","content":[{"type":"text","text":"Done."}],"usage":{"input_tokens":120,"output_tokens":18,"cache_read_input_tokens":900,"cache_creation_input_tokens":40}}}`,
	`{"type":"result","subtype":"success","is_error":false,"num_turns":2,"duration_ms":1500,"total_cost_usd":0.0123,"result":"Done.","stop_reason":"end_turn","usage":{"input_tokens":120,"output_tokens":18,"cache_read_input_tokens":900,"cache_creation_input_tokens":40}}`,
}

func main() {
	writer := bufio.NewWriter(os.Stdout)
	for _, line := range streamLines {
		if _, err := fmt.Fprintln(writer, line); err != nil {
			os.Exit(1)
		}
		if err := writer.Flush(); err != nil {
			os.Exit(1)
		}
		// A small pace so the parent's scanner observes a genuinely streamed sequence.
		time.Sleep(2 * time.Millisecond)
	}
	// Drain stdin to EOF (the library closes stdin on Abort/Close) so the process exits
	// cleanly rather than on a broken pipe.
	_, _ = io.Copy(io.Discard, os.Stdin) //nolint:errcheck // the stub drains stdin only to exit cleanly; the copy result is irrelevant.
}
