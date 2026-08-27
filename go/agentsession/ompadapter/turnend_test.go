package ompadapter_test

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// This file is the SYMMETRIC half of claudeadapter/turnend_test.go: contract revision R1 gives
// ONE turn semantics to BOTH harnesses. An omp `agent_end` frame that reports a clean stop is a
// TURN boundary — the process is alive and accepts the next prompt — while an `agent_end`
// carrying stopReason:"error" really does end the session. Today normalize.go maps both to the
// session-terminal EventResult/EventFailed pair, so an eden omp session is single-turn exactly
// as the claude one is.
//
// The assertions are BEHAVIORAL (Event.IsTerminal / Kind.String), never written against the
// EventTurnEnd identifier, so this file compiles against the pre-R1 tree and its failure is the
// real defect rather than a missing symbol.

// turnEndToken is the stable lower-kebab token the R1 turn-boundary EventKind renders. Pinning
// the TOKEN rather than the constant keeps this file compilable before the member exists while
// still identifying it exactly: EventKind.String() falls back to "extension" for any member
// with no token row, so "turn-end" can only come from the real appended member plus its row.
const turnEndToken = "turn-end"

// TestAgentEnd_CleanStopIsATurnBoundaryNotASessionTerminal is the R1 core for omp: the recorded
// `agent_end` frame that reports stopReason "stop" normalizes to a NON-terminal turn boundary
// still carrying the authoritative four-token ledger and the final assistant text. Today it maps
// to EventResult, whose IsTerminal() is true, latching the session at StateCompleted.
func TestAgentEnd_CleanStopIsATurnBoundaryNotASessionTerminal(t *testing.T) {
	t.Parallel()
	events := ompadapter.NormalizeLineForTest(recordedAgentEndLine(t))
	if len(events) != 1 {
		t.Fatalf("agent_end must normalize to exactly one event, got %d: %+v", len(events), events)
	}
	event := events[0]
	if event.Terminal == nil {
		t.Fatalf("a clean agent_end must still carry the authoritative TerminalPayload, got %+v", event)
	}
	if event.IsTerminal() {
		t.Errorf("a clean agent_end is a TURN boundary, not a session terminal: kind=%s IsTerminal=true (R1: the session stays alive for the next Prompt)",
			event.Kind)
	}
	if got := event.Kind.String(); got != turnEndToken {
		t.Errorf("a clean agent_end must map to the turn-end kind, got token %q (want %q)", got, turnEndToken)
	}

	// The payload is UNCHANGED by R1 — only its terminality moves.
	if event.Terminal.Outcome != agentsession.TurnCompleted {
		t.Errorf("turn-boundary Outcome = %v, want TurnCompleted", event.Terminal.Outcome)
	}
	if event.Terminal.StopReason != "stop" {
		t.Errorf("turn-boundary StopReason = %q, want stop (surfaced verbatim)", event.Terminal.StopReason)
	}
	if event.Terminal.ResultText == "" {
		t.Errorf("turn-boundary ResultText must carry the final assistant text")
	}
	assertRecordedOmpLedger(t, event.Terminal.Ledger)
}

// TestAgentEnd_ErrorStopStaysASessionTerminal is the GUARD half: an agent_end reporting
// stopReason "error" ends the session, so R1 must not move it. It passes today and must keep
// passing — without it the change above could be satisfied by making EVERY agent_end
// non-terminal, stranding a failed session with no terminal event and no finalized ledger.
func TestAgentEnd_ErrorStopStaysASessionTerminal(t *testing.T) {
	t.Parallel()
	for _, testCase := range []struct {
		name       string
		status     int
		wantReason agentsession.ErrorReason
	}{
		{"upstream 401 is an auth failure", 401, agentsession.ReasonAuth},
		{"upstream 429 is a rate limit", 429, agentsession.ReasonRateLimit},
	} {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			events := ompadapter.NormalizeLineForTest(errorAgentEndLine(t, testCase.status))
			if len(events) != 1 {
				t.Fatalf("agent_end must normalize to exactly one event, got %d: %+v", len(events), events)
			}
			event := events[0]
			if event.Kind != agentsession.EventFailed {
				t.Fatalf("an error agent_end must stay EventFailed, got %v", event.Kind)
			}
			if !event.IsTerminal() {
				t.Errorf("an error agent_end must stay a SESSION terminal (IsTerminal), got kind %v", event.Kind)
			}
			if event.Terminal == nil || event.Terminal.Outcome != agentsession.TurnFailed {
				t.Errorf("an error agent_end must carry TurnFailed, got %+v", event.Terminal)
			}
			if event.Terminal != nil && event.Terminal.Reason != testCase.wantReason {
				t.Errorf("error reason = %v, want %v", event.Terminal.Reason, testCase.wantReason)
			}
		})
	}
}

// TestAgentEnd_EveryTurnBoundaryInOneStreamStaysNonTerminal drives the SAME stateful normalizer
// a live conn uses over TWO consecutive clean turns on ONE process. Neither boundary may be a
// session terminal: the second `agent_end` is what proves the parser has no once-per-process
// latch hiding behind the first.
func TestAgentEnd_EveryTurnBoundaryInOneStreamStaysNonTerminal(t *testing.T) {
	t.Parallel()
	normalize := ompadapter.StreamNormalizerForTest()

	var boundaries []agentsession.Event
	for _, line := range twoTurnOmpLines(t) {
		for _, event := range normalize(line) {
			if event.Terminal != nil {
				boundaries = append(boundaries, event)
			}
		}
	}
	if len(boundaries) != 2 {
		t.Fatalf("two consecutive clean turns must yield two turn boundaries, got %d", len(boundaries))
	}
	for i := range boundaries {
		if boundaries[i].IsTerminal() {
			t.Errorf("turn %d boundary is a session terminal (kind=%s); one omp process serves many turns",
				i+1, boundaries[i].Kind)
		}
		if got := boundaries[i].Kind.String(); got != turnEndToken {
			t.Errorf("turn %d boundary token = %q, want %q", i+1, got, turnEndToken)
		}
		if boundaries[i].Terminal.Ledger.Harness != "omp" {
			t.Errorf("turn %d boundary ledger lost its harness attribution: %+v", i+1, boundaries[i].Terminal.Ledger)
		}
	}
	if boundaries[0].Terminal.ResultText == boundaries[1].Terminal.ResultText {
		t.Errorf("both turn boundaries carried the same ResultText %q; each turn's own text must ride its own boundary",
			boundaries[0].Terminal.ResultText)
	}
}

// ── fixtures + helpers ───────────────────────────────────────────────────────────────────.

// recordedAgentEndLine returns the REAL recorded `agent_end` frame from the committed omp
// stream fixture (the terminal aggregate of testdata/partial-stream.jsonl) — measured wire
// bytes, not a hand-written approximation.
func recordedAgentEndLine(t *testing.T) []byte {
	t.Helper()
	for _, line := range ompFixtureLines(t, "partial-stream.jsonl") {
		var envelope struct {
			Type string `json:"type"`
		}
		if json.Unmarshal(line, &envelope) != nil {
			continue
		}
		if envelope.Type == "agent_end" {
			return line
		}
	}
	t.Fatal("testdata/partial-stream.jsonl carries no agent_end frame")
	return nil
}

// errorAgentEndLine rewrites the recorded agent_end's final assistant message into the FAILURE
// shape omp reports (stopReason "error" plus the upstream HTTP errorStatus), leaving every
// other measured field intact.
func errorAgentEndLine(t *testing.T, status int) []byte {
	t.Helper()
	return rewriteFinalAssistant(t, recordedAgentEndLine(t), func(message map[string]any) {
		message["stopReason"] = "error"
		message["errorStatus"] = status
	})
}

// twoTurnOmpLines assembles the ONE-PROCESS two-turn stream: the recorded clean agent_end
// replayed twice with distinct assistant text. It is ASSEMBLED from the recorded single-turn
// fixture (not itself a recording) so the second turn's bytes match the first's measured shape.
func twoTurnOmpLines(t *testing.T) [][]byte {
	t.Helper()
	recorded := recordedAgentEndLine(t)
	return [][]byte{
		retextAgentEnd(t, recorded, "first turn answer"),
		retextAgentEnd(t, recorded, "second turn answer"),
	}
}

// retextAgentEnd rewrites only the final assistant message's text blocks.
func retextAgentEnd(t *testing.T, recorded []byte, text string) []byte {
	t.Helper()
	return rewriteFinalAssistant(t, recorded, func(message map[string]any) {
		message["content"] = []any{map[string]any{"type": "text", "text": text}}
	})
}

// rewriteFinalAssistant decodes an agent_end frame, applies mutate to its LAST assistant
// message (the authoritative terminal aggregate), and re-encodes the frame.
func rewriteFinalAssistant(t *testing.T, recorded []byte, mutate func(map[string]any)) []byte {
	t.Helper()
	var decoded map[string]any
	if err := json.Unmarshal(recorded, &decoded); err != nil {
		t.Fatalf("decode recorded agent_end: %v", err)
	}
	messages, ok := decoded["messages"].([]any)
	if !ok || len(messages) == 0 {
		t.Fatalf("recorded agent_end carries no messages list: %s", recorded)
	}
	mutated := false
	for i := len(messages) - 1; i >= 0; i-- {
		message, isObject := messages[i].(map[string]any)
		if !isObject || message["role"] != "assistant" {
			continue
		}
		mutate(message)
		mutated = true
		break
	}
	if !mutated {
		t.Fatalf("recorded agent_end carries no assistant message: %s", recorded)
	}
	line, err := json.Marshal(decoded)
	if err != nil {
		t.Fatalf("re-encode agent_end: %v", err)
	}
	return line
}

// assertRecordedOmpLedger pins the four token kinds the RECORDED agent_end reports, so the turn
// boundary is proven to carry the authoritative accounting and not a zeroed placeholder. The
// numbers are read back off the same fixture frame, so the assertion cannot drift from it.
//
//nolint:gocritic // TokenLedger is the contract's copyable value record (§2); this helper takes it by value.
func assertRecordedOmpLedger(t *testing.T, ledger agentsession.TokenLedger) {
	t.Helper()
	var recorded struct {
		Messages []struct {
			Role  string `json:"role"`
			Usage *struct {
				Input      int64 `json:"input"`
				Output     int64 `json:"output"`
				CacheRead  int64 `json:"cacheRead"`
				CacheWrite int64 `json:"cacheWrite"`
			} `json:"usage"`
		} `json:"messages"`
	}
	if err := json.Unmarshal(recordedAgentEndLine(t), &recorded); err != nil {
		t.Fatalf("decode recorded usage: %v", err)
	}
	for i := len(recorded.Messages) - 1; i >= 0; i-- {
		message := recorded.Messages[i]
		if message.Role != "assistant" || message.Usage == nil {
			continue
		}
		if message.Usage.Input == 0 || message.Usage.Output == 0 {
			t.Fatal("the recorded fixture reports no token usage; the ledger assertion would be vacuous")
		}
		if ledger.InputTokens != message.Usage.Input || ledger.OutputTokens != message.Usage.Output ||
			ledger.CacheReadTokens != message.Usage.CacheRead || ledger.CacheCreationTokens != message.Usage.CacheWrite {
			t.Errorf("turn-boundary ledger drifted from the recorded wire usage: got %+v, want in=%d out=%d cacheRead=%d cacheWrite=%d",
				ledger, message.Usage.Input, message.Usage.Output, message.Usage.CacheRead, message.Usage.CacheWrite)
		}
		if ledger.Harness != "omp" {
			t.Errorf("turn-boundary ledger harness = %q, want omp", ledger.Harness)
		}
		return
	}
	t.Fatal("recorded agent_end carries no assistant usage block")
}

// ompFixtureLines reads a committed stream fixture into its lines.
func ompFixtureLines(t *testing.T, name string) [][]byte {
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
