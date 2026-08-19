package claudeadapter_test

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// This file pins contract revision R1 at the claude PARSER seam: a `result` line is a TURN
// boundary, not a session terminal. The probe fixtures settle it by measurement — one claude
// process emits MANY `result` lines across a multi-turn exchange — so mapping every one of
// them to the session-terminal EventResult makes an eden claude session single-turn and a
// receive-then-reply peer exchange impossible.
//
// The assertions here are deliberately BEHAVIORAL (Event.IsTerminal / Kind.String), not
// written against the EventTurnEnd identifier, so this file COMPILES against the pre-R1 tree
// and its failure is the real defect rather than a missing symbol. The session-level halves
// (three consecutive Prompts on one live session; the stream not closing at a turn boundary)
// live in the root terminal_test.go / turn_test.go and in the harness lane.

// turnEndToken is the stable lower-kebab token the R1 turn-boundary EventKind renders. Pinning
// the TOKEN rather than the constant keeps this file compilable before the member exists while
// still identifying it exactly: EventKind.String() falls back to "extension" for any member with
// no token row, so "turn-end" can only come from the real appended member plus its token row.
const turnEndToken = "turn-end"

// TestResult_SuccessIsATurnBoundaryNotASessionTerminal is the R1 core: the REAL recorded
// success `result` line normalizes to a NON-terminal turn-boundary event that still carries the
// authoritative four-token ledger, the result text, and the stop reason. Today it maps to
// EventResult, whose IsTerminal() is true, which latches the session at StateCompleted and ends
// every viewer's stream after the first assistant turn.
func TestResult_SuccessIsATurnBoundaryNotASessionTerminal(t *testing.T) {
	t.Parallel()
	line := recordedSuccessResultLine(t)

	events := normalizeOne(t, line)
	if events[0].Terminal == nil {
		t.Fatalf("a success result must still carry the authoritative TerminalPayload, got %+v", events[0])
	}
	if events[0].IsTerminal() {
		t.Errorf("a success result is a TURN boundary, not a session terminal: kind=%s IsTerminal=true (R1: the session stays alive for the next Prompt)",
			events[0].Kind)
	}
	if got := events[0].Kind.String(); got != turnEndToken {
		t.Errorf("a success result must map to the turn-end kind, got token %q (want %q)", got, turnEndToken)
	}

	// The payload the turn boundary carries is UNCHANGED by R1 — only its terminality moves.
	payload := events[0].Terminal
	if payload.Outcome != agentsession.TurnCompleted {
		t.Errorf("turn-boundary Outcome = %v, want TurnCompleted", payload.Outcome)
	}
	if payload.StopReason != "end_turn" {
		t.Errorf("turn-boundary StopReason = %q, want end_turn (surfaced verbatim)", payload.StopReason)
	}
	if payload.ResultText == "" {
		t.Errorf("turn-boundary ResultText must carry the final assistant text")
	}
	assertRecordedLedger(t, payload.Ledger)
}

// TestResult_ErrorStaysASessionTerminal is the GUARD half: an error result really does end the
// session, so R1 must not move it. It passes today and must keep passing — without it the
// change above could be satisfied by making EVERY result non-terminal, which would strand a
// failed session with no terminal event and no finalized ledger.
func TestResult_ErrorStaysASessionTerminal(t *testing.T) {
	t.Parallel()
	for _, testCase := range []struct {
		name    string
		line    string
		wantKey agentsession.ErrorReason
	}{
		{
			name:    "is_error flag on a success subtype",
			line:    `{"type":"result","subtype":"success","is_error":true,"num_turns":1,"total_cost_usd":0.01,"result":"boom","stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1,"cache_read_input_tokens":1,"cache_creation_input_tokens":1}}`,
			wantKey: agentsession.ReasonHarnessError,
		},
		{
			name:    "error_max_turns subtype",
			line:    `{"type":"result","subtype":"error_max_turns","is_error":true,"num_turns":9,"total_cost_usd":0.02,"stop_reason":"max_turns","usage":{"input_tokens":1,"output_tokens":1,"cache_read_input_tokens":1,"cache_creation_input_tokens":1}}`,
			wantKey: agentsession.ReasonMaxTurns,
		},
	} {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			events := normalizeOne(t, []byte(testCase.line))
			if events[0].Kind != agentsession.EventFailed {
				t.Fatalf("an error result must stay EventFailed, got %v", events[0].Kind)
			}
			if !events[0].IsTerminal() {
				t.Errorf("an error result must stay a SESSION terminal (IsTerminal), got kind %v", events[0].Kind)
			}
			if events[0].Terminal == nil || events[0].Terminal.Outcome != agentsession.TurnFailed {
				t.Errorf("an error result must carry TurnFailed, got %+v", events[0].Terminal)
			}
			if events[0].Terminal != nil && events[0].Terminal.Reason != testCase.wantKey {
				t.Errorf("error reason = %v, want %v", events[0].Terminal.Reason, testCase.wantKey)
			}
		})
	}
}

// TestResult_EveryTurnBoundaryInOneStreamStaysNonTerminal drives the SAME stateful normalizer a
// live conn uses over TWO consecutive success turns — the shape the probe fixtures measured
// (one process, many `result` lines). Neither boundary may be a session terminal, and BOTH must
// carry their own turn's ledger: the second `result` is what proves the parser has no
// once-per-process latch hiding behind the first.
func TestResult_EveryTurnBoundaryInOneStreamStaysNonTerminal(t *testing.T) {
	t.Parallel()
	normalize := claudeadapter.StreamNormalizerForTest()

	var boundaries []agentsession.Event
	for _, line := range twoTurnLines(t) {
		for _, event := range normalize(line) {
			if event.Terminal != nil {
				boundaries = append(boundaries, event)
			}
		}
	}
	if len(boundaries) != 2 {
		t.Fatalf("two consecutive success turns must yield two turn boundaries, got %d", len(boundaries))
	}
	for i := range boundaries {
		if boundaries[i].IsTerminal() {
			t.Errorf("turn %d boundary is a session terminal (kind=%s); a claude process emits one `result` PER TURN",
				i+1, boundaries[i].Kind)
		}
		if got := boundaries[i].Kind.String(); got != turnEndToken {
			t.Errorf("turn %d boundary token = %q, want %q", i+1, got, turnEndToken)
		}
		if boundaries[i].Terminal.Ledger.Harness != "claude-code" {
			t.Errorf("turn %d boundary ledger lost its harness attribution: %+v", i+1, boundaries[i].Terminal.Ledger)
		}
	}
	if boundaries[0].Terminal.ResultText == boundaries[1].Terminal.ResultText {
		t.Errorf("both turn boundaries carried the same ResultText %q; each turn's own text must ride its own boundary",
			boundaries[0].Terminal.ResultText)
	}
}

// assertRecordedLedger pins the four token kinds the RECORDED success result reports, so the
// turn boundary is proven to carry the authoritative accounting and not a zeroed placeholder.
// The numbers are read back off the same fixture line, so the assertion cannot drift from it.
//
//nolint:gocritic // TokenLedger is the contract's copyable value record (§2); this helper takes it by value.
func assertRecordedLedger(t *testing.T, ledger agentsession.TokenLedger) {
	t.Helper()
	var recorded struct {
		Usage struct {
			InputTokens              int64 `json:"input_tokens"`
			OutputTokens             int64 `json:"output_tokens"`
			CacheReadInputTokens     int64 `json:"cache_read_input_tokens"`
			CacheCreationInputTokens int64 `json:"cache_creation_input_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(recordedSuccessResultLine(t), &recorded); err != nil {
		t.Fatalf("decode recorded usage: %v", err)
	}
	if recorded.Usage.CacheReadInputTokens == 0 || recorded.Usage.CacheCreationInputTokens == 0 {
		t.Fatal("the recorded fixture reports no cache tokens; the ledger assertion would be vacuous")
	}
	if ledger.InputTokens != recorded.Usage.InputTokens || ledger.OutputTokens != recorded.Usage.OutputTokens ||
		ledger.CacheReadTokens != recorded.Usage.CacheReadInputTokens ||
		ledger.CacheCreationTokens != recorded.Usage.CacheCreationInputTokens {
		t.Errorf("turn-boundary ledger drifted from the recorded wire usage: got %+v, want in=%d out=%d cacheRead=%d cacheCreate=%d",
			ledger, recorded.Usage.InputTokens, recorded.Usage.OutputTokens,
			recorded.Usage.CacheReadInputTokens, recorded.Usage.CacheCreationInputTokens)
	}
	if ledger.Harness != "claude-code" {
		t.Errorf("turn-boundary ledger harness = %q, want claude-code", ledger.Harness)
	}
	if ledger.CostMicros <= 0 {
		t.Errorf("turn-boundary ledger must carry the reported cost, got %d micros", ledger.CostMicros)
	}
}

// ── fixtures + helpers ───────────────────────────────────────────────────────────────────.

// recordedSuccessResultLine returns the REAL recorded success `result` line from the committed
// claude stream fixture (the last line of testdata/sample-stream.jsonl) — measured wire bytes,
// not a hand-written approximation.
func recordedSuccessResultLine(t *testing.T) []byte {
	t.Helper()
	for _, line := range fixtureLines(t, "sample-stream.jsonl") {
		var envelope struct {
			Type    string `json:"type"`
			Subtype string `json:"subtype"`
		}
		if json.Unmarshal(line, &envelope) != nil {
			continue
		}
		if envelope.Type == "result" && envelope.Subtype == "success" {
			return line
		}
	}
	t.Fatal("testdata/sample-stream.jsonl carries no success result line")
	return nil
}

// twoTurnLines assembles the ONE-PROCESS two-turn stream: the recorded assistant + success
// `result` body, replayed twice with distinct result text. It is ASSEMBLED from the recorded
// single-turn fixture (not itself a recording) so the second turn's bytes are the same measured
// wire shape as the first.
func twoTurnLines(t *testing.T) [][]byte {
	t.Helper()
	recorded := recordedSuccessResultLine(t)
	return [][]byte{
		[]byte(`{"type":"assistant","message":{"model":"claude-fable-5","role":"assistant","content":[{"type":"text","text":"first turn"}]}}`),
		retextResultLine(t, recorded, "first turn answer"),
		[]byte(`{"type":"assistant","message":{"model":"claude-fable-5","role":"assistant","content":[{"type":"text","text":"second turn"}]}}`),
		retextResultLine(t, recorded, "second turn answer"),
	}
}

// retextResultLine rewrites only the `result` text of a recorded result line, leaving every
// other measured field (usage, cost, subtype, stop_reason) byte-faithful.
func retextResultLine(t *testing.T, recorded []byte, text string) []byte {
	t.Helper()
	var decoded map[string]any
	if err := json.Unmarshal(recorded, &decoded); err != nil {
		t.Fatalf("decode recorded result line: %v", err)
	}
	decoded["result"] = text
	line, err := json.Marshal(decoded)
	if err != nil {
		t.Fatalf("re-encode result line: %v", err)
	}
	return line
}

// fixtureLines reads a committed stream fixture into its lines.
func fixtureLines(t *testing.T, name string) [][]byte {
	t.Helper()
	file, err := os.Open(filepath.Join("testdata", name)) //nolint:gosec // a fixed committed test fixture path
	if err != nil {
		t.Fatalf("open fixture %s: %v", name, err)
	}
	t.Cleanup(func() { _ = file.Close() }) //nolint:errcheck // best-effort fixture-file close on test cleanup.
	var lines [][]byte
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 8<<20)
	for scanner.Scan() {
		if strings.TrimSpace(scanner.Text()) == "" {
			continue
		}
		line := make([]byte, len(scanner.Bytes()))
		copy(line, scanner.Bytes())
		lines = append(lines, line)
	}
	if err := scanner.Err(); err != nil {
		t.Fatalf("scan fixture %s: %v", name, err)
	}
	return lines
}

// normalizeOne normalizes a line expected to produce exactly one Event.
func normalizeOne(t *testing.T, line []byte) []agentsession.Event {
	t.Helper()
	events := claudeadapter.NormalizeLineForTest(line)
	if len(events) != 1 {
		t.Fatalf("expected exactly one event from %s, got %d: %+v", line, len(events), events)
	}
	return events
}
