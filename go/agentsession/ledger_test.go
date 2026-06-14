package agentsession_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// TestLedgerFold_FullTurnSealsAuthoritativeLedger folds a complete normalized turn (message,
// tool start/end, usage tick, terminal Result) and asserts the sealed ledger + the terminal
// accessors. Covers foldToolStart (per-tool breakdown), foldTerminal (the terminal ground truth
// wins for the four-token totals while the fold-accumulated tool breakdown is preserved), and the
// Outcome/StopReason accessors. Reuses benchEventSequence from bench_test.go (same test package).
func TestLedgerFold_FullTurnSealsAuthoritativeLedger(t *testing.T) {
	t.Parallel()
	fold := agentsession.NewLedgerFold()
	for i := range benchEventSequence {
		fold.Fold(benchEventSequence[i])
	}
	ledger := fold.Finish()

	if fold.Outcome() != agentsession.TurnCompleted {
		t.Fatalf("Outcome() = %v, want TurnCompleted", fold.Outcome())
	}
	if got := fold.StopReason(); got != "end_turn" {
		t.Fatalf("StopReason() = %q, want end_turn", got)
	}
	if ledger.ToolUses != 1 || ledger.ToolUsesByName["Write"] != 1 {
		t.Fatalf("tool accounting drifted: ToolUses=%d byName=%v", ledger.ToolUses, ledger.ToolUsesByName)
	}
	if ledger.OutputTokens != benchUsageTick.OutputTokens {
		t.Fatalf("terminal ledger not authoritative: OutputTokens=%d want %d", ledger.OutputTokens, benchUsageTick.OutputTokens)
	}
}

// TestLedgerFold_DeltaTicksAndUnknownFrames covers the delta (non-cumulative) usage branch — two
// delta ticks accumulate rather than replace — and the forward-compatibility UnknownFrames
// counter: an event carrying un-normalized Extension bytes is counted, never fatal.
func TestLedgerFold_DeltaTicksAndUnknownFrames(t *testing.T) {
	t.Parallel()
	fold := agentsession.NewLedgerFold()
	delta := agentsession.UsageMeter{InputTokens: 10, OutputTokens: 5, CostMicros: 100} // Cumulative:false
	fold.Fold(agentsession.Event{Kind: agentsession.EventUsage, Usage: &delta})
	fold.Fold(agentsession.Event{Kind: agentsession.EventUsage, Usage: &delta})
	fold.Fold(agentsession.Event{Kind: agentsession.EventExtension, Extension: []byte(`{"type":"rate_limit"}`)})

	ledger := fold.Finish()
	if ledger.InputTokens != 20 || ledger.OutputTokens != 10 || ledger.CostMicros != 200 {
		t.Fatalf("delta accumulation drifted: in=%d out=%d cost=%d", ledger.InputTokens, ledger.OutputTokens, ledger.CostMicros)
	}
	if fold.UnknownFrames() != 1 {
		t.Fatalf("UnknownFrames() = %d, want 1", fold.UnknownFrames())
	}
}
