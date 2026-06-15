package claudeadapter_test

import (
	"bufio"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// TestManifest_DeclaresHeadlessCapabilities proves the adapter's manifest is the honest
// headless-Claude shape: Steer is CapPartial (queue-for-next-turn), partial tool results are
// absent, host tools are CapPartial (the stdio control-channel SDK-MCP-server protocol is
// wired and unit-proven, but the live in-process MCP handshake does not complete end-to-end on
// the pinned claude — see Manifest doc), and resume/thinking/permission/native-budget are full.
func TestManifest_DeclaresHeadlessCapabilities(t *testing.T) {
	t.Parallel()
	manifest := claudeadapter.MustNewForTest(t, claudeadapter.Config{}).Manifest()
	want := map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapPartial,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapPartial,
		agentsession.CapNativeBudget:       agentsession.CapFull,
		agentsession.CapPermissionPrompt:   agentsession.CapFull,
		agentsession.CapPartialToolResults: agentsession.CapAbsent,
	}
	for capability, status := range want {
		if got := manifest.Status(capability); got != status {
			t.Errorf("Manifest[%s] = %v, want %v", capability, got, status)
		}
	}
}

// TestNormalize_SampleStream proves the stream-json normalizer maps a REAL recorded
// Claude Code transcript onto the Eden Event taxonomy: the init line becomes the Ready
// handshake, assistant text/thinking/tool_use become their distinct Kinds, the user
// tool_result becomes EventToolEnd, the unknown rate_limit_event survives as
// EventExtension (never dropped), and the result line becomes a terminal carrying the
// four-token ledger. This is the parser arm of the conformance proof, run WITHOUT a live
// authenticated process.
func TestNormalize_SampleStream(t *testing.T) {
	t.Parallel()
	events := normalizeFixture(t, "sample-stream.jsonl")

	counts := map[agentsession.EventKind]int{}
	for i := range events {
		ev := &events[i]
		counts[ev.Kind]++
	}

	// The init line is preserved as session-metadata Extension (NOT the Ready handshake):
	// real claude defers system/init until the first stdin turn, so the conn signals Ready on
	// spawn instead (processConn.scan) and the normalizer never emits a Ready transition.
	if events[0].Kind != agentsession.EventExtension {
		t.Errorf("first normalized event (the init line) must be a metadata Extension, got %v", events[0].Kind)
	}
	for i := range events {
		if events[i].Kind == agentsession.EventSessionState && events[i].State != nil && events[i].State.To == agentsession.StateReady {
			t.Errorf("the normalizer must NOT emit a Ready transition (Ready is conn-emitted on spawn); event %d did", i)
		}
	}
	// The unknown rate_limit_event survived verbatim as EventExtension (forward-compat).
	if counts[agentsession.EventExtension] < 1 {
		t.Errorf("the rate_limit_event line must survive as EventExtension (never dropped)")
	}
	assertExtensionVerbatim(t, events)
	// Distinct delta kinds appeared.
	if counts[agentsession.EventThinkingDelta] < 1 {
		t.Errorf("expected at least one EventThinkingDelta")
	}
	if counts[agentsession.EventTextDelta] < 1 {
		t.Errorf("expected at least one EventTextDelta")
	}
	// Tool start/end correlate by CallID.
	assertToolCorrelation(t, events)
	// Exactly one terminal carrying the four-token ledger.
	assertTerminalLedger(t, events)
}

// TestNormalize_UnknownTypeNeverFatal proves an unrecognized line type is preserved as
// EventExtension verbatim and never errors (the rate_limit_event lesson, isolated).
func TestNormalize_UnknownTypeNeverFatal(t *testing.T) {
	t.Parallel()
	line := []byte(`{"type":"some_future_event","payload":{"x":1}}`)
	events := normalizeLine(t, line)
	if len(events) != 1 || events[0].Kind != agentsession.EventExtension {
		t.Fatalf("unknown type must yield exactly one EventExtension, got %+v", events)
	}
	if !bytes.Equal(events[0].Extension, line) {
		t.Errorf("EventExtension must carry the raw bytes verbatim, got %q", events[0].Extension)
	}
}

// TestNormalize_MalformedLineNeverFatal proves a non-JSON line becomes an EventExtension
// rather than a fatal parse error (resilience).
func TestNormalize_MalformedLineNeverFatal(t *testing.T) {
	t.Parallel()
	events := normalizeLine(t, []byte(`not json at all`))
	if len(events) != 1 || events[0].Kind != agentsession.EventExtension {
		t.Fatalf("a malformed line must yield one EventExtension, got %+v", events)
	}
}

// TestNormalize_ThinkingTokensBecomesProgress proves a `system/thinking_tokens` heartbeat is
// surfaced as EventThinkingProgress carrying the running estimated token count (the live
// "thinking…" status signal) — NOT dropped into the opaque Extension bucket the UI is blind to
// (the dead-screen-during-a-long-think bug). The raw line still rides along as the Extension.
func TestNormalize_ThinkingTokensBecomesProgress(t *testing.T) {
	t.Parallel()
	line := []byte(`{"type":"system","subtype":"thinking_tokens","estimated_tokens":142,"estimated_tokens_delta":26}`)
	events := normalizeLine(t, line)
	if len(events) != 1 {
		t.Fatalf("a thinking_tokens line must yield exactly one event, got %d: %+v", len(events), events)
	}
	ev := events[0]
	if ev.Kind != agentsession.EventThinkingProgress {
		t.Fatalf("thinking_tokens must become EventThinkingProgress, got %v", ev.Kind)
	}
	if ev.Message == nil || ev.Message.Tokens != 142 {
		t.Fatalf("EventThinkingProgress must carry the estimated token count 142, got %+v", ev.Message)
	}
	if !bytes.Equal(ev.Extension, line) {
		t.Errorf("the raw thinking_tokens line must ride along as the Extension (never dropped)")
	}
}

// TestNormalize_OtherSystemLineStaysExtension proves the thinking_tokens mapping is NARROW: a
// different system subtype (init) is still preserved as a metadata Extension, so the change did
// not start swallowing other system lines.
func TestNormalize_OtherSystemLineStaysExtension(t *testing.T) {
	t.Parallel()
	line := []byte(`{"type":"system","subtype":"init","session_id":"x","tools":["Read"]}`)
	events := normalizeLine(t, line)
	if len(events) != 1 || events[0].Kind != agentsession.EventExtension {
		t.Fatalf("a non-thinking_tokens system line must stay an Extension, got %+v", events)
	}
}

// assertExtensionVerbatim proves every EventExtension carries non-empty raw bytes.
func assertExtensionVerbatim(t *testing.T, events []agentsession.Event) {
	t.Helper()
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventExtension && len(ev.Extension) == 0 {
			t.Errorf("EventExtension must carry the raw bytes, got empty")
		}
	}
}

// assertToolCorrelation proves every EventToolEnd correlates to a preceding ToolStart by
// CallID.
func assertToolCorrelation(t *testing.T, events []agentsession.Event) {
	t.Helper()
	started := map[string]bool{}
	sawStart, sawEnd := false, false
	for i := range events {
		ev := &events[i]
		if ev.Tool == nil {
			continue
		}
		switch ev.Kind {
		case agentsession.EventToolStart:
			started[ev.Tool.CallID] = true
			sawStart = true
			if ev.Tool.Name == "" {
				t.Errorf("EventToolStart must carry a tool Name")
			}
		case agentsession.EventToolEnd:
			sawEnd = true
			if ev.Tool.CallID != "" && !started[ev.Tool.CallID] {
				t.Errorf("EventToolEnd CallID %q has no preceding ToolStart", ev.Tool.CallID)
			}
		default:
		}
	}
	if !sawStart || !sawEnd {
		t.Errorf("sample stream must contain tool start (%v) and end (%v)", sawStart, sawEnd)
	}
}

// assertTerminalLedger proves exactly one terminal event carries the four-token ledger
// with model/harness attribution and a non-negative cost.
func assertTerminalLedger(t *testing.T, events []agentsession.Event) {
	t.Helper()
	terminals := 0
	var terminal *agentsession.TerminalPayload
	for i := range events {
		ev := &events[i]
		if ev.IsTerminal() {
			terminals++
			terminal = ev.Terminal
		}
	}
	if terminals != 1 {
		t.Fatalf("expected exactly one terminal event, got %d", terminals)
	}
	if terminal == nil {
		t.Fatal("terminal event carried no payload")
	}
	ledger := terminal.Ledger
	if ledger.InputTokens == 0 || ledger.OutputTokens == 0 || ledger.CacheReadTokens == 0 || ledger.CacheCreationTokens == 0 {
		t.Errorf("terminal ledger must populate all four token kinds, got %+v", ledger)
	}
	if ledger.Harness != "claude-code" {
		t.Errorf("terminal ledger Harness = %q, want claude-code", ledger.Harness)
	}
	if ledger.Model == "" {
		t.Errorf("terminal ledger must attribute the Model")
	}
	if ledger.CostMicros < 0 {
		t.Errorf("the sample result reports a cost; CostMicros must be >= 0, got %d", ledger.CostMicros)
	}
}

// normalizeFixture reads a testdata stream-json file and normalizes every line, exactly
// as the live conn's scanner does — but with no process.
func normalizeFixture(t *testing.T, name string) []agentsession.Event {
	t.Helper()
	file, err := os.Open(filepath.Join("testdata", name)) //nolint:gosec // a fixed test fixture path
	if err != nil {
		t.Fatalf("open fixture %s: %v", name, err)
	}
	t.Cleanup(func() { _ = file.Close() }) //nolint:errcheck // best-effort fixture-file close on test cleanup.

	var events []agentsession.Event
	normalize := claudeadapter.StreamNormalizerForTest() // one normalizer for the whole stream
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

// normalizeLine normalizes a single line via the test seam.
func normalizeLine(t *testing.T, line []byte) []agentsession.Event {
	t.Helper()
	return claudeadapter.NormalizeLineForTest(line)
}

// containsAll reports whether args contains every wanted token in order-independent form.
func containsAll(args []string, wanted ...string) bool {
	present := map[string]bool{}
	for _, a := range args {
		present[a] = true
	}
	for _, w := range wanted {
		if !present[w] {
			return false
		}
	}
	return true
}

// joinArgs renders args for diagnostics.
func joinArgs(args []string) string { return strings.Join(args, " ") }
