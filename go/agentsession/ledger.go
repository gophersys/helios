package agentsession

// LedgerFold is the engine's running fold over the Event stream (the
// poc/codingharness ledger fold, promoted into the library). It accumulates the
// authoritative TokenLedger from the stream of EventUsage ticks and the terminal
// Event, and is FORWARD-COMPATIBLE: an unrecognized EventExtension is counted, never
// fatal (the rate_limit_event lesson). Fold is the one place usage accounting lives;
// the engine emits the result into the T6 observability.Ledger and the FinOps
// UsageRecord (this library emits; it does not bill).
//
// Concurrency: a LedgerFold is owned by ONE draining goroutine (the engine's single
// in-process consumer); it is not safe for concurrent Fold calls. The fan-out is on
// the Stream, not the fold.
type LedgerFold struct {
	ledger        TokenLedger
	outcome       TurnOutcome
	stopReason    string
	terminalSeen  bool
	unknownFrames int64
}

// NewLedgerFold returns a fresh fold with a zeroed ledger and a -1 cost sentinel
// (so "no harness reported cost" is distinguishable from "zero cost").
func NewLedgerFold() *LedgerFold {
	return &LedgerFold{ledger: TokenLedger{UsageMeter: UsageMeter{CostMicros: -1}}}
}

// Fold incorporates one Event. EventUsage advances the four-token meter and cost
// (cumulative ticks replace, delta ticks add); EventToolStart counts a tool use and
// per-tool breakdown; a terminal Event seals the authoritative ledger; an
// EventExtension (or any kind carrying Extension bytes) is counted but never fatal.
//
//nolint:gocritic // contract §5: LedgerFold.Fold takes the Event value (the immutable record the engine folds; the frozen surface).
func (f *LedgerFold) Fold(event Event) {
	if len(event.Extension) > 0 {
		f.unknownFrames++
	}
	switch event.Kind {
	case EventUsage:
		f.foldUsage(event.Usage)
	case EventToolStart:
		f.foldToolStart(event.Tool)
	case EventResult, EventFailed, EventAborted:
		f.foldTerminal(event.Terminal)
	case EventSessionState, EventMessageStart, EventThinkingDelta, EventTextDelta,
		EventMessageEnd, EventToolUpdate, EventToolEnd, EventPermissionRequest,
		EventPermissionResolved, EventExtension:
		// Not ledger-relevant; counted above if it carried Extension bytes.
	default:
		// An unknown future kind is never fatal (forward-compat).
	}
}

// foldUsage merges one EventUsage tick into the running meter. Cumulative ticks are
// session-to-date totals (replace); delta ticks are per-turn increments (add). Model
// and Harness attribution always follow the latest tick.
func (f *LedgerFold) foldUsage(meter *UsageMeter) {
	if meter == nil {
		return
	}
	if meter.Model != "" {
		f.ledger.Model = meter.Model
	}
	if meter.Harness != "" {
		f.ledger.Harness = meter.Harness
	}
	if meter.Cumulative {
		f.ledger.InputTokens = meter.InputTokens
		f.ledger.OutputTokens = meter.OutputTokens
		f.ledger.CacheReadTokens = meter.CacheReadTokens
		f.ledger.CacheCreationTokens = meter.CacheCreationTokens
		if meter.CostMicros >= 0 {
			f.ledger.CostMicros = meter.CostMicros
		}
		return
	}
	f.ledger.InputTokens += meter.InputTokens
	f.ledger.OutputTokens += meter.OutputTokens
	f.ledger.CacheReadTokens += meter.CacheReadTokens
	f.ledger.CacheCreationTokens += meter.CacheCreationTokens
	if meter.CostMicros >= 0 {
		if f.ledger.CostMicros < 0 {
			f.ledger.CostMicros = 0
		}
		f.ledger.CostMicros += meter.CostMicros
	}
}

// foldToolStart counts one tool use and its per-name breakdown.
func (f *LedgerFold) foldToolStart(tool *ToolPayload) {
	if tool == nil {
		return
	}
	f.ledger.ToolUses++
	if f.ledger.ToolUsesByName == nil {
		f.ledger.ToolUsesByName = make(map[string]int32)
	}
	f.ledger.ToolUsesByName[tool.Name]++
}

// foldTerminal seals the authoritative ledger from the terminal Event. The terminal
// TokenLedger is the harness ground truth, so it WINS over the running aggregate for
// the four-token totals and cost; the fold-accumulated tool breakdown is preserved
// when the terminal omits it.
func (f *LedgerFold) foldTerminal(terminal *TerminalPayload) {
	if terminal == nil {
		return
	}
	f.terminalSeen = true
	f.outcome = terminal.Outcome
	f.stopReason = terminal.StopReason

	toolUses := f.ledger.ToolUses
	toolsByName := f.ledger.ToolUsesByName
	authoritative := terminal.Ledger
	if authoritative.ToolUses == 0 {
		authoritative.ToolUses = toolUses
	}
	if authoritative.ToolUsesByName == nil {
		authoritative.ToolUsesByName = toolsByName
	}
	f.ledger = authoritative
}

// Finish returns the authoritative TokenLedger accumulated so far (the terminal
// ledger when a terminal Event was seen, else the running aggregate).
func (f *LedgerFold) Finish() TokenLedger { return f.ledger }

// Outcome reports the terminal TurnOutcome (TurnCompleted until a terminal Event is
// folded).
func (f *LedgerFold) Outcome() TurnOutcome { return f.outcome }

// StopReason reports the harness stop reason from the terminal Event ("" until one is
// folded).
func (f *LedgerFold) StopReason() string { return f.stopReason }

// UnknownFrames reports how many events carried un-normalized Extension bytes — the
// forward-compatibility counter (never fatal).
func (f *LedgerFold) UnknownFrames() int64 { return f.unknownFrames }
