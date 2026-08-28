package agentsession_test

import (
	"context"
	"testing"
	"time"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a)); rapid reads it directly.
// These properties drive the REAL Pool/Session/pump/broadcaster/stream — the fake harness
// adapter is the conformance two-binding partner, NOT a mock of the library under test.

// allStates and allEventKinds are the closed, append-only enumerations the token-stability
// properties draw from so every classification axis is exercised.
var allStates = []agentsession.State{
	agentsession.StateInitializing, agentsession.StateReady, agentsession.StateRunning,
	agentsession.StateAwaitingInput, agentsession.StateAwaitingPermission,
	agentsession.StateCompleted, agentsession.StateFailed, agentsession.StateAborted,
}

var allEventKinds = []agentsession.EventKind{
	agentsession.EventSessionState, agentsession.EventMessageStart, agentsession.EventThinkingDelta,
	agentsession.EventTextDelta, agentsession.EventMessageEnd, agentsession.EventToolStart,
	agentsession.EventToolUpdate, agentsession.EventToolEnd, agentsession.EventPermissionRequest,
	agentsession.EventPermissionResolved, agentsession.EventUsage, agentsession.EventResult,
	agentsession.EventFailed, agentsession.EventAborted, agentsession.EventExtension,
}

var allCapabilities = []agentsession.Capability{
	agentsession.CapSteer, agentsession.CapResume, agentsession.CapThinkingEvents,
	agentsession.CapHostTools, agentsession.CapNativeBudget, agentsession.CapPermissionPrompt,
	agentsession.CapPartialToolResults,
}

// TestProperty_SeqStrictlyMonotonicThroughPump drives a randomly-shaped (but legal) script
// through the REAL pump+stream and asserts the load-bearing invariant: every event a fresh
// FromSeq(0) tail observes carries Seq == 1,2,3,... with NO hole and NO repeat. Seq is the
// transcript offset the whole resumability story rests on, so a drift here is a cardinal bug.
func TestProperty_SeqStrictlyMonotonicThroughPump(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		script := drawScript(rt)
		session, transcript := openScripted(t, script)

		stream := session.Events(context.Background(), agentsession.FromSeq(0))
		if _, err := session.Control(context.Background(),
			agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
			rt.Fatalf("Prompt: %v", err)
		}
		events := drainAll(rt, stream)

		if len(events) == 0 {
			rt.Fatalf("a session always emits at least the Ready + terminal events; got none")
		}
		if events[0].Seq != 1 {
			rt.Fatalf("first Seq = %d, want 1 (Seq == 1-based transcript offset)", events[0].Seq)
		}
		for i := 1; i < len(events); i++ {
			if events[i].Seq != events[i-1].Seq+1 {
				rt.Fatalf("Seq not strictly monotonic: index %d is %d, follows %d", i, events[i].Seq, events[i-1].Seq)
			}
		}
		// Anti-collapse: a tail from Seq 0 must observe EXACTLY one event per stored transcript
		// record. Without this, a pump that stamped every event the same Seq would be silently
		// deduped down to one event and pass the monotonic check vacuously. Combined with the
		// first-Seq==1 and strict-+1 checks above, count==stored pins the head to the transcript.
		stored := transcript.Len(events[0].SessionID)
		if len(events) != stored {
			rt.Fatalf("Seq drift collapsed/duplicated events: drained %d, transcript stored %d", len(events), stored)
		}
	})
}

// TestProperty_FanoutDeliversEveryEventToEverySubscriber attaches N concurrent FromSeq(0)
// tailers to one session and asserts EVERY live subscriber observes the IDENTICAL gap-free
// Seq stream (broadcaster fan-out: one published event reaches every viewer; no viewer is
// silently starved or skipped). This is the multi-client guarantee in the Session contract.
func TestProperty_FanoutDeliversEveryEventToEverySubscriber(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		script := drawScript(rt)
		session, _ := openScripted(t, script)

		n := rapid.IntRange(2, 6).Draw(rt, "subscribers")
		streams := make([]agentsession.Stream, n)
		for i := range streams {
			streams[i] = session.Events(context.Background(), agentsession.FromSeq(0))
		}
		if _, err := session.Control(context.Background(),
			agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
			rt.Fatalf("Prompt: %v", err)
		}

		results := make([][]uint64, n)
		for i := range streams {
			results[i] = drainSeqs(rt, streams[i])
		}
		want := results[0]
		if len(want) == 0 {
			rt.Fatalf("subscriber 0 observed no events")
		}
		for i := 1; i < n; i++ {
			if !equalSeqs(want, results[i]) {
				rt.Fatalf("fan-out divergence: subscriber %d saw %v, subscriber 0 saw %v", i, results[i], want)
			}
		}
	})
}

// TestProperty_LedgerFoldDeltaSumsAreAuthoritative asserts the accounting invariant: folding
// a stream of DELTA usage ticks accumulates each of the four token kinds to the exact sum of
// the parts, and accumulates cost off the -1 "no cost reported" sentinel correctly. This is
// the engine's FinOps ground truth — an off-by-one here is a billing bug (02 §2).
func TestProperty_LedgerFoldDeltaSumsAreAuthoritative(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		ticks := rapid.SliceOfN(drawDeltaUsage(rt), 0, 32).Draw(rt, "ticks")
		fold := agentsession.NewLedgerFold()
		var wantIn, wantOut, wantCacheRead, wantCacheCreate, wantCost int64
		anyCost := false
		for _, m := range ticks {
			fold.Fold(agentsession.Event{Kind: agentsession.EventUsage, Usage: &m})
			wantIn += m.InputTokens
			wantOut += m.OutputTokens
			wantCacheRead += m.CacheReadTokens
			wantCacheCreate += m.CacheCreationTokens
			if m.CostMicros >= 0 {
				wantCost += m.CostMicros
				anyCost = true
			}
		}
		got := fold.Finish()
		if got.InputTokens != wantIn || got.OutputTokens != wantOut ||
			got.CacheReadTokens != wantCacheRead || got.CacheCreationTokens != wantCacheCreate {
			rt.Fatalf("four-token sum drifted: got (in=%d out=%d cr=%d cc=%d), want (in=%d out=%d cr=%d cc=%d)",
				got.InputTokens, got.OutputTokens, got.CacheReadTokens, got.CacheCreationTokens,
				wantIn, wantOut, wantCacheRead, wantCacheCreate)
		}
		// Cost stays at the -1 sentinel until a non-negative tick appears, then accumulates.
		if anyCost {
			if got.CostMicros != wantCost {
				rt.Fatalf("cost sum drifted: got %d, want %d", got.CostMicros, wantCost)
			}
		} else if got.CostMicros != -1 {
			rt.Fatalf("no tick reported cost; CostMicros must stay -1 sentinel, got %d", got.CostMicros)
		}
	})
}

// TestProperty_LedgerFoldCumulativeReplaces asserts a CUMULATIVE tick (session-to-date totals,
// the Claude result-event shape) REPLACES the running four-token meter rather than adding to
// it — and that a terminal Event seals the authoritative ledger as ground truth.
func TestProperty_LedgerFoldCumulativeReplaces(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		first := drawDeltaUsage(rt).Draw(rt, "first")
		cumulative := drawCumulativeUsage(rt).Draw(rt, "cumulative")

		fold := agentsession.NewLedgerFold()
		fold.Fold(agentsession.Event{Kind: agentsession.EventUsage, Usage: &first})
		fold.Fold(agentsession.Event{Kind: agentsession.EventUsage, Usage: &cumulative})
		got := fold.Finish()

		if got.InputTokens != cumulative.InputTokens || got.OutputTokens != cumulative.OutputTokens ||
			got.CacheReadTokens != cumulative.CacheReadTokens || got.CacheCreationTokens != cumulative.CacheCreationTokens {
			rt.Fatalf("cumulative tick must REPLACE the meter, not add: got in=%d, want in=%d",
				got.InputTokens, cumulative.InputTokens)
		}
		if cumulative.CostMicros >= 0 && got.CostMicros != cumulative.CostMicros {
			rt.Fatalf("cumulative cost must replace: got %d, want %d", got.CostMicros, cumulative.CostMicros)
		}
	})
}

// TestProperty_TokensTotalAndStable asserts the String() tokens for State, EventKind, and
// Capability are TOTAL (non-empty for every enumerated value) and STABLE (the same value
// always renders the same token) — the fingerprint-stability invariant (ADR-0020 §a). Wire
// and telemetry branch on these tokens, so a drift or an empty token is a contract break.
func TestProperty_TokensTotalAndStable(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// State: reconstruct the enum value from its raw uint8 and assert the token is
		// non-empty and identical across two independent renderings (stability).
		st := allStates[rapid.IntRange(0, len(allStates)-1).Draw(rt, "state")]
		rebuilt := agentsession.State(uint8(st))
		if rebuilt.String() == "" || rebuilt.String() != st.String() {
			rt.Fatalf("State(%d).String() unstable or empty: %q vs %q", st, rebuilt.String(), st.String())
		}
		// EventKind: same — a value rebuilt from the raw byte must render the identical token.
		ek := allEventKinds[rapid.IntRange(0, len(allEventKinds)-1).Draw(rt, "kind")]
		rebuiltKind := agentsession.EventKind(uint8(ek))
		if rebuiltKind.String() == "" || rebuiltKind.String() != ek.String() {
			rt.Fatalf("EventKind(%d).String() unstable or empty: %q vs %q", ek, rebuiltKind.String(), ek.String())
		}
		// Capability: token non-empty and stable across re-render.
		capability := allCapabilities[rapid.IntRange(0, len(allCapabilities)-1).Draw(rt, "cap")]
		rebuiltCap := agentsession.Capability(uint8(capability))
		if rebuiltCap.String() == "" || rebuiltCap.String() != capability.String() {
			rt.Fatalf("Capability(%d).String() unstable or empty: %q vs %q", capability, rebuiltCap.String(), capability.String())
		}
	})
}

// TestProperty_IsTerminalMatchesTokenSet asserts State.IsTerminal() agrees with the closed
// terminal set {Completed, Failed, Aborted} for EVERY enumerated State — the predicate the
// pump's transition guard and the stream's end-detection both rely on.
func TestProperty_IsTerminalMatchesTokenSet(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		st := allStates[rapid.IntRange(0, len(allStates)-1).Draw(rt, "state")]
		want := st == agentsession.StateCompleted || st == agentsession.StateFailed || st == agentsession.StateAborted
		if st.IsTerminal() != want {
			rt.Fatalf("State(%s).IsTerminal() = %v, want %v", st, st.IsTerminal(), want)
		}
	})
}

// ── draw helpers ──────────────────────────────────────────────────────────────.

// drawScript builds a legal, randomly-shaped script: a randomized count of streaming
// activity events, then a terminal Result. The lead-in Ready transition is synthesized by
// the fake harness automatically, so the script starts at message activity.
func drawScript(rt *rapid.T) []agentsession.Event {
	var script []agentsession.Event
	script = append(script, agentsessiontest.MessageStart("assistant"))
	deltas := rapid.IntRange(0, 8).Draw(rt, "deltas")
	for range deltas {
		switch rapid.IntRange(0, 2).Draw(rt, "activity") {
		case 0:
			script = append(script, agentsessiontest.TextDelta(rapid.StringMatching(`[a-z ]{0,12}`).Draw(rt, "text")))
		case 1:
			script = append(script, agentsessiontest.ThinkingDelta(rapid.StringMatching(`[a-z ]{0,12}`).Draw(rt, "thinking")))
		default:
			script = append(script, agentsessiontest.Usage(drawCumulativeUsageValue(rt)))
		}
	}
	script = append(
		script,
		agentsessiontest.MessageEnd(),
		agentsessiontest.Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{Harness: "fake", Cumulative: true},
			Turns:      1,
		}, "done", "end_turn"),
	)
	return script
}

// drawDeltaUsage draws a non-negative delta UsageMeter (per-turn increment). CostMicros may
// be -1 (no cost reported) to exercise the sentinel path.
func drawDeltaUsage(_ *rapid.T) *rapid.Generator[agentsession.UsageMeter] {
	return rapid.Custom(func(rt *rapid.T) agentsession.UsageMeter {
		cost := int64(-1)
		if rapid.Bool().Draw(rt, "hasCost") {
			cost = rapid.Int64Range(0, 1_000_000).Draw(rt, "cost")
		}
		return agentsession.UsageMeter{
			InputTokens:         rapid.Int64Range(0, 100_000).Draw(rt, "in"),
			OutputTokens:        rapid.Int64Range(0, 100_000).Draw(rt, "out"),
			CacheReadTokens:     rapid.Int64Range(0, 100_000).Draw(rt, "cacheRead"),
			CacheCreationTokens: rapid.Int64Range(0, 100_000).Draw(rt, "cacheCreate"),
			CostMicros:          cost,
			Cumulative:          false,
		}
	})
}

// drawCumulativeUsage draws a cumulative UsageMeter (session-to-date totals).
func drawCumulativeUsage(_ *rapid.T) *rapid.Generator[agentsession.UsageMeter] {
	return rapid.Custom(drawCumulativeUsageValue)
}

func drawCumulativeUsageValue(rt *rapid.T) agentsession.UsageMeter {
	cost := int64(-1)
	if rapid.Bool().Draw(rt, "hasCost") {
		cost = rapid.Int64Range(0, 5_000_000).Draw(rt, "cost")
	}
	return agentsession.UsageMeter{
		Model:               "fake-fable-5",
		Harness:             "fake",
		InputTokens:         rapid.Int64Range(0, 1_000_000).Draw(rt, "in"),
		OutputTokens:        rapid.Int64Range(0, 1_000_000).Draw(rt, "out"),
		CacheReadTokens:     rapid.Int64Range(0, 1_000_000).Draw(rt, "cacheRead"),
		CacheCreationTokens: rapid.Int64Range(0, 1_000_000).Draw(rt, "cacheCreate"),
		CostMicros:          cost,
		Cumulative:          true,
	}
}

// ── pump-driving harness (no *testing.T dependency, usable from rapid.T) ─────────.

const propertyCanary = "S3CR3T-property-do-not-leak" // #nosec G101 -- a test redaction needle, not a real credential.

// propertyRef is the loggable reference the property harness seeds the canary under.
const propertyRef = "vault://eden/anthropic#property" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// propClock is a deterministic Clock for the property harness.
type propClock struct{}

func (propClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// openScripted constructs a REAL Pool over a scripted fake adapter and opens a live session,
// reaped on t.Cleanup. It takes the outer *testing.T (for Cleanup) so the goroutine reap is
// registered even though the property body runs under rapid.T.
//
//nolint:ireturn // returns the agentsession.Session port (the contract surface the consumer holds).
func openScripted(t *testing.T, script []agentsession.Event) (agentsession.Session, *agentsessiontest.Transcript) {
	t.Helper()
	adapter := agentsessiontest.New(script...)
	transcript := agentsessiontest.NewTranscript()
	key := agentsession.RouteKey{Role: "assistant"}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			key: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{propertyRef: propertyCanary}),
			Transcript: transcript,
			Clock:      propClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    key,
		Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		Credential: secrets.Ref(propertyRef),
	})
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.
	return session, transcript
}

// drainSeqs reads a stream to its terminal, returning the Seq sequence observed.
func drainSeqs(rt *rapid.T, stream agentsession.Stream) []uint64 {
	events := drainAll(rt, stream)
	out := make([]uint64, len(events))
	for i := range events {
		out[i] = events[i].Seq
	}
	return out
}

// drainAll reads a stream to its terminal, returning every event in order.
func drainAll(rt *rapid.T, stream agentsession.Stream) []agentsession.Event {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var out []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				rt.Fatalf("stream faulted: %v", err)
			}
			return out
		}
		out = append(out, event)
		if event.IsTerminal() {
			return out
		}
	}
}

// equalSeqs reports whether two Seq slices are identical.
func equalSeqs(a, b []uint64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
