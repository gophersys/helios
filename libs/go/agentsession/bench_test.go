package agentsession_test

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// sink keeps the benchmarked work observable so the compiler cannot prove the result dead
// and elide it (a package-level `any` per ADR-0020 dimension (g); kept off any sentinel path).
//
//nolint:gochecknoglobals // benchmark sink must be package-level so the compiler cannot elide the work.
var sink any

// benchUsageTick is a representative cumulative four-token usage tick — the shape the engine
// folds on every EventUsage.
var benchUsageTick = agentsession.UsageMeter{
	Model: "fake-fable-5", Harness: "fake",
	InputTokens: 100, OutputTokens: 40, CacheReadTokens: 60, CacheCreationTokens: 20,
	CostMicros: 1500, Cumulative: true,
}

// benchEventSequence is a full normalized turn the engine drains and folds: message activity,
// a tool start, a usage tick, and a terminal Result carrying the authoritative ledger.
var benchEventSequence = []agentsession.Event{
	{Kind: agentsession.EventMessageStart, Message: &agentsession.MessagePayload{Role: "assistant"}},
	{Kind: agentsession.EventTextDelta, Message: &agentsession.MessagePayload{Role: "assistant", Delta: "Hello, world"}},
	{Kind: agentsession.EventToolStart, Tool: &agentsession.ToolPayload{CallID: "c1", Name: "Write"}},
	{Kind: agentsession.EventToolEnd, Tool: &agentsession.ToolPayload{CallID: "c1", Outcome: agentsession.ToolOutcomeOK}},
	{Kind: agentsession.EventUsage, Usage: &benchUsageTick},
	{Kind: agentsession.EventResult, Terminal: &agentsession.TerminalPayload{
		Outcome: agentsession.TurnCompleted,
		Ledger: agentsession.TokenLedger{
			UsageMeter: benchUsageTick, Turns: 1, ToolUses: 1, WallTime: 12 * time.Millisecond,
			ToolUsesByName: map[string]int32{"Write": 1},
		},
		ResultText: "Hello, world", StopReason: "end_turn",
	}},
}

// BenchmarkLedgerFold_Usage measures the per-EventUsage fold — the hottest accounting path
// (the engine folds one per usage tick across a whole agent loop).
func BenchmarkLedgerFold_Usage(b *testing.B) {
	event := agentsession.Event{Kind: agentsession.EventUsage, Usage: &benchUsageTick}
	b.ReportAllocs()
	var fold *agentsession.LedgerFold
	for b.Loop() {
		fold = agentsession.NewLedgerFold()
		fold.Fold(event)
	}
	sink = fold
}

// BenchmarkLedgerFold_FullTurn measures folding a complete normalized turn to the sealed
// authoritative ledger — the engine's batch execute() spine over one turn.
func BenchmarkLedgerFold_FullTurn(b *testing.B) {
	b.ReportAllocs()
	var ledger agentsession.TokenLedger
	for b.Loop() {
		fold := agentsession.NewLedgerFold()
		for i := range benchEventSequence {
			fold.Fold(benchEventSequence[i])
		}
		ledger = fold.Finish()
	}
	sink = ledger
}

// BenchmarkEventKind_String measures the normalized-kind token rendering the transport
// boundary and chat surface call on every event.
func BenchmarkEventKind_String(b *testing.B) {
	b.ReportAllocs()
	var s string
	for b.Loop() {
		s = agentsession.EventToolStart.String()
	}
	sink = s
}

// BenchmarkEvent_IsTerminal measures the terminal predicate the pump and every stream consult
// per event.
func BenchmarkEvent_IsTerminal(b *testing.B) {
	event := agentsession.Event{Kind: agentsession.EventResult}
	b.ReportAllocs()
	var terminal bool
	for b.Loop() {
		terminal = event.IsTerminal()
	}
	sink = terminal
}
