package ompadapter_test

import (
	"bufio"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// liveStream is the EXACT omp json frame sequence captured from a live
// `omp -p --mode json --no-session --no-tools --thinking minimal --model
// openrouter/deepseek/deepseek-v4-flash "Reply with exactly: ok"` run (the spike), with the
// per-delta partial snapshots elided for length but the load-bearing frames verbatim. It is
// the parser's ground truth: the normalizer must fold these into the Event taxonomy.
var liveStream = []string{
	`{"type":"session","version":3,"id":"019ec2ee-47da-7000-9d7b-b00508f50bfc","timestamp":"2026-06-13T21:40:56.410Z","cwd":"/tmp/jsonyml"}`,
	`{"type":"agent_start"}`,
	`{"type":"turn_start"}`,
	`{"type":"message_start","message":{"role":"user","content":[{"type":"text","text":"Reply with exactly: ok"}],"attribution":"user","timestamp":1781386856505}}`,
	`{"type":"message_end","message":{"role":"user","content":[{"type":"text","text":"Reply with exactly: ok"}],"attribution":"user","timestamp":1781386856505}}`,
	`{"type":"message_start","message":{"role":"assistant","content":[],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop","responseId":"gen-1"}}`,
	`{"type":"message_update","assistantMessageEvent":{"type":"thinking_start","contentIndex":0},"message":{"role":"assistant","content":[]}}`,
	`{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","contentIndex":0,"delta":"The user asked"},"message":{"role":"assistant","content":[]}}`,
	`{"type":"message_update","assistantMessageEvent":{"type":"thinking_end","contentIndex":0,"content":"The user asked me to reply with exactly \"ok\"."},"message":{"role":"assistant","content":[]}}`,
	`{"type":"message_update","assistantMessageEvent":{"type":"text_start","contentIndex":1},"message":{"role":"assistant","content":[]}}`,
	`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","contentIndex":1,"delta":"ok"},"message":{"role":"assistant","content":[]}}`,
	`{"type":"message_update","assistantMessageEvent":{"type":"text_end","contentIndex":1,"content":"ok"},"message":{"role":"assistant","content":[]}}`,
	`{"type":"message_end","message":{"role":"assistant","content":[{"type":"thinking","thinking":"The user asked me to reply with exactly \"ok\"."},{"type":"text","text":"ok"}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","usage":{"input":3494,"output":19,"cacheRead":0,"cacheWrite":0,"totalTokens":3513,"reasoningTokens":16,"cost":{"input":0.000342412,"output":0.0000037,"cacheRead":0,"cacheWrite":0,"total":0.000346136}},"stopReason":"stop","duration":2554}}`,
	`{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"usage":{"input":3494,"output":19,"cacheRead":0,"cacheWrite":0,"cost":{"total":0.000346136}}},"toolResults":[]}`,
	`{"type":"agent_end","messages":[{"role":"user","content":[{"type":"text","text":"Reply with exactly: ok"}]},{"role":"assistant","content":[{"type":"thinking","thinking":"The user asked me to reply with exactly \"ok\"."},{"type":"text","text":"ok"}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","usage":{"input":3494,"output":19,"cacheRead":0,"cacheWrite":0,"totalTokens":3513,"reasoningTokens":16,"cost":{"input":0.000342412,"output":0.0000037,"cacheRead":0,"cacheWrite":0,"total":0.000346136}},"stopReason":"stop","duration":2554}]}`,
}

// TestNormalize_LiveStreamFoldsToTaxonomy proves the captured live omp json stream folds into
// the full Event taxonomy: the assistant message boundaries, a thinking delta, a text delta,
// per-message usage ticks, and a TURN BOUNDARY carrying the four-token ledger with the USD cost
// converted to micro-units (no float drift). The user echo is dropped; the chrome frames
// survive as Extension.
//
// Re-pinned for contract revision R1: the captured `agent_end` reports a clean stop, so the
// boundary it draws ends the TURN and leaves the omp process alive for the next prompt. The
// kind is identified by its stable token so this file compiles against the pre-R1 tree.
func TestNormalize_LiveStreamFoldsToTaxonomy(t *testing.T) {
	t.Parallel()
	normalize := ompadapter.StreamNormalizerForTest()
	var events []agentsession.Event
	for _, line := range liveStream {
		events = append(events, normalize([]byte(line))...)
	}

	requireKind(t, events, agentsession.EventMessageStart)
	requireKind(t, events, agentsession.EventThinkingDelta)
	requireKind(t, events, agentsession.EventTextDelta)
	requireKind(t, events, agentsession.EventMessageEnd)
	requireKind(t, events, agentsession.EventUsage)

	// Exactly one boundary event, carrying the four-token ledger, ending the TURN and NOT the
	// session (R1: one omp process serves many turns).
	terminal := lastEvent(t, events)
	if terminal.Terminal == nil {
		t.Fatalf("the stream did not end on a boundary carrying a payload (last kind %s)", terminal.Kind)
	}
	if terminal.IsTerminal() {
		t.Fatalf("a clean agent_end ENDED THE SESSION (kind %s); it is a turn boundary, not a session terminal", terminal.Kind)
	}
	if got := terminal.Kind.String(); got != "turn-end" {
		t.Fatalf("turn-boundary token = %q, want \"turn-end\"", got)
	}
	ledger := terminal.Terminal.Ledger
	if ledger.InputTokens != 3494 || ledger.OutputTokens != 19 {
		t.Errorf("ledger tokens = in %d/out %d, want 3494/19", ledger.InputTokens, ledger.OutputTokens)
	}
	if ledger.Harness != "omp" {
		t.Errorf("ledger harness = %q, want omp", ledger.Harness)
	}
	if ledger.Model != "deepseek/deepseek-v4-flash" {
		t.Errorf("ledger model = %q, want deepseek/deepseek-v4-flash", ledger.Model)
	}
	// 0.000346136 USD -> 346 micros (round to nearest micro-unit, no float drift).
	if ledger.CostMicros != 346 {
		t.Errorf("ledger CostMicros = %d, want 346 (0.000346136 USD)", ledger.CostMicros)
	}
	if terminal.Terminal.ResultText != "ok" {
		t.Errorf("terminal ResultText = %q, want %q", terminal.Terminal.ResultText, "ok")
	}

	// The assistant text delta carried the model's reply.
	if d := firstDelta(events, agentsession.EventTextDelta); d != "ok" {
		t.Errorf("text delta = %q, want %q", d, "ok")
	}
}

// TestNormalize_PartialMessageStreaming proves omp streams text TOKEN-BY-TOKEN natively against
// the REAL omp json frame shapes (testdata/partial-stream.jsonl): omp is delta-native, so a
// single assistant message's text arrives as multiple incremental message_update text_delta
// fragments (not one finished block), and the normalizer maps each to a distinct EventTextDelta.
// The assertions: >=2 incremental EventTextDelta fragments accrete (concatenated, in order) to
// the full sentence, no single delta re-emits the whole text (no doubling), the assistant message
// boundary is emitted exactly ONCE (message_start/message_end, not also fabricated from agent_end),
// and the tool_execution frame surfaces as one EventToolStart. This is the smooth-typing UX,
// mock-free, off a fixture captured in the live omp wire shape.
func TestNormalize_PartialMessageStreaming(t *testing.T) {
	t.Parallel()
	textDeltas, counts, toolName := tallyOmpStream(realOmpFixture(t, "partial-stream.jsonl"))

	if len(textDeltas) < 2 {
		t.Fatalf("expected token-level streaming (>=2 incremental text deltas), got %d: %q", len(textDeltas), textDeltas)
	}
	if got := strings.Join(textDeltas, ""); got != "Hello, world." {
		t.Fatalf("accreted streamed text = %q, want %q", got, "Hello, world.")
	}
	if slices.Contains(textDeltas, "Hello, world.") {
		t.Fatalf("the full assistant text was re-emitted as a single delta — streamed text is DOUBLED")
	}
	if counts[agentsession.EventMessageStart] != 1 || counts[agentsession.EventMessageEnd] != 1 {
		t.Fatalf("the assistant message boundary must be emitted exactly once (message_start/message_end), got start=%d end=%d",
			counts[agentsession.EventMessageStart], counts[agentsession.EventMessageEnd])
	}
	if counts[agentsession.EventToolStart] != 1 || toolName != "write" {
		t.Fatalf("a tool_execution must surface as one EventToolStart (one write tool), got tools=%d name=%q",
			counts[agentsession.EventToolStart], toolName)
	}
}

// TestNormalize_UnknownFrameSurvivesAsExtension proves an unmodeled top-level frame (the
// rate_limit_event lesson) is preserved VERBATIM as EventExtension — never dropped, never
// fatal.
func TestNormalize_UnknownFrameSurvivesAsExtension(t *testing.T) {
	t.Parallel()
	line := `{"type":"rate_limit_event","retryAfter":7}`
	events := ompadapter.NormalizeLineForTest([]byte(line))
	if len(events) != 1 || events[0].Kind != agentsession.EventExtension {
		t.Fatalf("unknown frame must produce one EventExtension; got %+v", events)
	}
	if string(events[0].Extension) != line {
		t.Errorf("Extension must carry the raw line verbatim; got %q", events[0].Extension)
	}
}

// TestNormalize_MalformedJSONSurvivesAsExtension proves a line that is not valid JSON becomes
// an EventExtension rather than a fatal scan error.
func TestNormalize_MalformedJSONSurvivesAsExtension(t *testing.T) {
	t.Parallel()
	line := `{"type": this is not json`
	events := ompadapter.NormalizeLineForTest([]byte(line))
	if len(events) != 1 || events[0].Kind != agentsession.EventExtension {
		t.Fatalf("malformed line must produce one EventExtension; got %+v", events)
	}
}

// TestNormalize_ToolExecutionFoldsToStartUpdateEnd proves the top-level tool frames and the
// toolcall_delta fold to EventToolStart/EventToolUpdate/EventToolEnd with the digested
// (bounded, redacted) summaries — the omp partial-result streaming the taxonomy models.
func TestNormalize_ToolExecutionFoldsToStartUpdateEnd(t *testing.T) {
	t.Parallel()
	normalize := ompadapter.StreamNormalizerForTest()
	lines := []string{
		`{"type":"tool_execution_start","toolCallId":"call_1","toolName":"read","args":{"path":"sample.txt"},"intent":"read sample.txt"}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"toolcall_delta","contentIndex":1,"delta":"partial-args"}}`,
		`{"type":"tool_execution_end","toolCallId":"call_1","toolName":"read","result":{"content":[{"type":"text","text":"hello world\n"}]},"isError":false}`,
	}
	var events []agentsession.Event
	for _, l := range lines {
		events = append(events, normalize([]byte(l))...)
	}
	start := requireKind(t, events, agentsession.EventToolStart)
	if start.Tool == nil || start.Tool.CallID != "call_1" || start.Tool.Name != "read" {
		t.Errorf("tool start missing CallID/Name: %+v", start.Tool)
	}
	if start.Tool.ArgsSummary == "" {
		t.Errorf("tool start must carry a digested args summary")
	}
	requireKind(t, events, agentsession.EventToolUpdate)
	end := requireKind(t, events, agentsession.EventToolEnd)
	if end.Tool == nil || end.Tool.CallID != "call_1" || end.Tool.Outcome != agentsession.ToolOutcomeOK {
		t.Errorf("tool end missing correlation/outcome: %+v", end.Tool)
	}
	if end.Tool.ResultDigest == "" {
		t.Errorf("tool end must carry a digested result")
	}
}

// TestNormalize_ErrorTerminalClassifiesByStatus proves an agent_end whose final assistant
// message carries stopReason:"error" + an HTTP errorStatus folds to EventFailed with the
// branchable reason (402 -> Budget, 401 -> Auth, 429 -> RateLimit) — and that the provider's
// errorMessage text is NEVER placed on the Event (redaction by construction).
func TestNormalize_ErrorTerminalClassifiesByStatus(t *testing.T) {
	t.Parallel()
	cases := []struct {
		status int
		reason agentsession.ErrorReason
	}{
		{402, agentsession.ReasonBudget},
		{401, agentsession.ReasonAuth},
		{429, agentsession.ReasonRateLimit},
		{500, agentsession.ReasonHarnessError},
	}
	for _, tc := range cases {
		normalize := ompadapter.StreamNormalizerForTest()
		const canaryMessage = "402 leaked-request-body-must-not-appear-on-the-event"
		line := `{"type":"agent_end","messages":[{"role":"assistant","content":[],"model":"deepseek/deepseek-v4-flash","stopReason":"error","errorStatus":` +
			itoaTest(tc.status) + `,"errorMessage":"` + canaryMessage + `"}]}`
		events := normalize([]byte(line))
		if len(events) != 1 {
			t.Fatalf("status %d: want one terminal event, got %d", tc.status, len(events))
		}
		ev := events[0]
		if ev.Kind != agentsession.EventFailed {
			t.Fatalf("status %d: Kind = %s, want failed", tc.status, ev.Kind)
		}
		if ev.Terminal.Reason != tc.reason {
			t.Errorf("status %d: Reason = %v, want %v", tc.status, ev.Terminal.Reason, tc.reason)
		}
		// The provider errorMessage must never reach the Event (it can echo a request body).
		if strings.Contains(ev.Terminal.Detail, canaryMessage) || strings.Contains(ev.Terminal.StopReason, canaryMessage) {
			t.Errorf("status %d: provider errorMessage leaked onto the terminal Event", tc.status)
		}
	}
}

// Test helpers follow.

// realOmpFixture reads a testdata omp json-frame file and normalizes every line through ONE
// stream normalizer, exactly as the live conn's scanner does — but with no process. It is the
// streaming arm of the conformance proof off a fixture in the real omp wire shape.
func realOmpFixture(t *testing.T, name string) []agentsession.Event {
	t.Helper()
	file, err := os.Open(filepath.Join("testdata", name)) //nolint:gosec // a fixed test fixture path
	if err != nil {
		t.Fatalf("open fixture %s: %v", name, err)
	}
	t.Cleanup(func() { _ = file.Close() }) //nolint:errcheck // best-effort fixture-file close on test cleanup.

	var events []agentsession.Event
	normalize := ompadapter.StreamNormalizerForTest() // one normalizer threads the whole stream
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 8<<20)
	for scanner.Scan() {
		line := make([]byte, len(scanner.Bytes()))
		copy(line, scanner.Bytes())
		events = append(events, normalize(line)...)
	}
	if serr := scanner.Err(); serr != nil {
		t.Fatalf("scan fixture: %v", serr)
	}
	if len(events) == 0 {
		t.Fatal("fixture produced no events")
	}
	return events
}

// tallyOmpStream collects, from a normalized event slice, the ordered text-delta fragments, a
// count per Event kind, and the first tool name — the shape the streaming assertions read.
func tallyOmpStream(events []agentsession.Event) (textDeltas []string, counts map[agentsession.EventKind]int, toolName string) {
	counts = make(map[agentsession.EventKind]int)
	for i := range events {
		counts[events[i].Kind]++
		if events[i].Kind == agentsession.EventTextDelta && events[i].Message != nil {
			textDeltas = append(textDeltas, events[i].Message.Delta)
		}
		if events[i].Kind == agentsession.EventToolStart && events[i].Tool != nil {
			toolName = events[i].Tool.Name
		}
	}
	return textDeltas, counts, toolName
}

// requireKind asserts at least one event of kind exists and returns the first such event.
func requireKind(t *testing.T, events []agentsession.Event, kind agentsession.EventKind) agentsession.Event { //nolint:gocritic // Event is the contract's copyable value record (§2); returned by value.
	t.Helper()
	for i := range events {
		if events[i].Kind == kind {
			return events[i]
		}
	}
	t.Fatalf("no event of kind %s in the stream", kind)
	return agentsession.Event{}
}

// lastEvent returns the final event (the terminal), failing on an empty stream.
func lastEvent(t *testing.T, events []agentsession.Event) agentsession.Event { //nolint:gocritic // Event is the contract's copyable value record (§2); returned by value.
	t.Helper()
	if len(events) == 0 {
		t.Fatal("empty event stream")
	}
	return events[len(events)-1]
}

// firstDelta returns the Delta of the first message-bearing event of kind.
func firstDelta(events []agentsession.Event, kind agentsession.EventKind) string {
	for i := range events {
		if events[i].Kind == kind && events[i].Message != nil {
			return events[i].Message.Delta
		}
	}
	return ""
}

// itoaTest renders a small int for fixture construction.
func itoaTest(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [12]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}
