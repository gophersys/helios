package ompadapter_test

import (
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
// per-message usage ticks, and a terminal EventResult carrying the four-token ledger with the
// USD cost converted to micro-units (no float drift). The user echo is dropped; the chrome
// frames survive as Extension.
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

	// Exactly one terminal, an EventResult carrying the four-token ledger.
	terminal := lastEvent(t, events)
	if terminal.Kind != agentsession.EventResult {
		t.Fatalf("terminal Kind = %s, want result", terminal.Kind)
	}
	if terminal.Terminal == nil {
		t.Fatal("terminal carries no payload")
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
