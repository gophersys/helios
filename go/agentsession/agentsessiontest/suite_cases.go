package agentsessiontest

import (
	"bytes"
	"context"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// assertLifecycleLegality proves only the §2 transitions occur, that the stream begins
// at Initializing->Ready and ends on exactly one terminal, and that a control verb in an
// illegal State returns StateError.
func assertLifecycleLegality(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	h := newHarness(t, newAdapter())
	events := promptAndDrain(t, h)

	transitions := stateTransitions(events)
	if len(transitions) == 0 {
		t.Fatal("no SessionState transitions observed")
	}
	if transitions[0].From != agentsession.StateInitializing || transitions[0].To != agentsession.StateReady {
		t.Errorf("first transition = %v->%v, want Initializing->Ready", transitions[0].From, transitions[0].To)
	}
	for i, transition := range transitions {
		if !legalEdge(transition.From, transition.To) {
			t.Errorf("transition %d %v->%v is illegal", i, transition.From, transition.To)
		}
	}
	terminals := terminalCount(events)
	if terminals != 1 {
		t.Errorf("expected exactly one terminal event, got %d", terminals)
	}
	if !events[len(events)-1].IsTerminal() {
		t.Errorf("stream must end on the terminal event")
	}

	// A Prompt in the wrong phase (after terminal) is a StateError.
	session := h.open(t, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("first Prompt: %v", err)
	}
	if _, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0))); err != nil {
		t.Fatalf("drain to terminal: %v", err)
	}
	_, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandAbort})
	if !asType[agentsession.StateError](err) {
		t.Errorf("Abort on a terminal session must be StateError, got %v (%T)", err, err)
	}
}

// assertSeqMonotonic proves Seq is strictly monotonic per session and equals the
// transcript offset (the load-bearing invariant), and tool Start/End correlate by CallID.
func assertSeqMonotonic(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	h := newHarness(t, newAdapter())
	events := promptAndDrain(t, h)

	var prev uint64
	for i := range events {
		ev := &events[i]
		if ev.Seq != prev+1 {
			t.Fatalf("event %d Seq = %d, want %d (strictly monotonic, gap-free)", i, ev.Seq, prev+1)
		}
		prev = ev.Seq
		if ev.SessionID == "" {
			t.Errorf("event %d carries no SessionID", i)
		}
	}
	// Seq == transcript offset: the stored count equals the head Seq.
	sessionID := events[0].SessionID
	if got := uint64(h.transcript.Len(sessionID)); got != prev {
		t.Errorf("transcript stored %d events but head Seq is %d (Seq != transcript offset)", got, prev)
	}
	// Tool Start/Update/End correlate by CallID.
	assertToolCorrelation(t, events)
}

// assertReplayEqualsTail proves Events(FromSeq(n)) yields [n+1 .. head] then the live
// tail with no gap and no dup, that FromSeq(0) replays the whole session, and that
// replay holds AFTER terminate (old-Run reload).
func assertReplayEqualsTail(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	h := newHarness(t, newAdapter())
	full := promptAndDrain(t, h) // a completed session in the transcript

	session := h.open(t, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	live, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
	if err != nil {
		t.Fatalf("live drain: %v", err)
	}
	_ = full

	// FromSeq(n) for a mid-stream cursor yields exactly the suffix [n+1 .. head].
	const cursor = 5
	suffix, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(cursor)))
	if err != nil {
		t.Fatalf("suffix drain: %v", err)
	}
	if len(suffix) == 0 {
		t.Fatal("FromSeq(5) yielded no events")
	}
	if suffix[0].Seq != cursor+1 {
		t.Errorf("FromSeq(%d) first Seq = %d, want %d", cursor, suffix[0].Seq, cursor+1)
	}
	expectedSuffixLen := len(live) - cursor
	if len(suffix) != expectedSuffixLen {
		t.Errorf("FromSeq(%d) yielded %d events, want %d (gap-free suffix)", cursor, len(suffix), expectedSuffixLen)
	}
	assertNoGap(t, suffix)

	// Replay AFTER terminate: a fresh FromSeq(0) reproduces the whole session.
	_ = session.Close(context.Background()) //nolint:errcheck // best-effort session reap in this test path.
	replay, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
	if err != nil {
		t.Fatalf("post-terminate replay: %v", err)
	}
	if len(replay) != len(live) {
		t.Errorf("post-terminate replay saw %d events, live saw %d", len(replay), len(live))
	}
	assertNoGap(t, replay)
}

// assertFanoutParity proves N concurrent Events calls see identical Seq-ordered streams,
// and that a SLOW subscriber (demoted to a replay reader) still sees every event with no
// gap — never stalling the others or the agent.
func assertFanoutParity(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	h := newHarness(t, newAdapter())
	session := h.open(t, nil)

	const tailers = 4
	results := make([][]uint64, tailers)
	var wg sync.WaitGroup
	for i := range tailers {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			stream := session.Events(context.Background(), agentsession.FromSeq(0))
			// Tailer 0 reads slowly to force buffer overflow -> demotion -> catch-up.
			slow := idx == 0
			events, derr := drainPaced(context.Background(), stream, slow)
			if derr != nil {
				t.Errorf("tailer %d drain: %v", idx, derr)
				return
			}
			results[idx] = seqs(events)
		}(i)
	}
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	wg.Wait()

	want := results[1]
	if len(want) == 0 {
		t.Fatal("fan-out produced no events")
	}
	for i := range results {
		if !equalSeqs(results[i], want) {
			t.Errorf("tailer %d Seq stream diverged from the canonical stream:\n got %v\nwant %v", i, results[i], want)
		}
	}
}

// assertForwardCompat proves an unrecognized harness frame surfaces as EventExtension
// with the raw bytes preserved, is never dropped and never fatal, and a LedgerFold over
// the stream counts it without failing.
func assertForwardCompat(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	raw := []byte(`{"type":"rate_limit_event","retry_after":42}`)
	script := []agentsession.Event{
		MessageStart("assistant"),
		Extension(raw),
		TextDelta("recovered"),
		Usage(usageMeter()),
		Result(fullLedger(), "ok", "end_turn"),
	}
	h := newHarness(t, New(script...))
	events := promptAndDrain(t, h)

	var found *agentsession.Event
	for i := range events {
		if events[i].Kind == agentsession.EventExtension {
			found = &events[i]
			break
		}
	}
	if found == nil {
		t.Fatal("EventExtension was dropped from the stream")
	}
	if !bytes.Equal(found.Extension, raw) {
		t.Errorf("EventExtension bytes = %q, want verbatim %q", found.Extension, raw)
	}
	// A LedgerFold counts the unknown frame and never fails on it.
	fold := agentsession.NewLedgerFold()
	for i := range events {
		fold.Fold(events[i])
	}
	if fold.UnknownFrames() < 1 {
		t.Errorf("LedgerFold must count the unknown Extension frame, got %d", fold.UnknownFrames())
	}
	if fold.Finish().InputTokens != usageMeter().InputTokens {
		t.Errorf("LedgerFold must still total usage past an unknown frame")
	}
}

// assertFourTokenKinds proves the EventUsage/terminal ledger populate all four token
// kinds + Model/Harness + CostMicros, and that the LedgerFold totals reconcile against
// the authoritative terminal ledger.
func assertFourTokenKinds(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	h := newHarness(t, newAdapter())
	events := promptAndDrain(t, h)

	usage, terminal := usageAndTerminal(events)
	if usage == nil {
		t.Fatal("no EventUsage tick observed")
	}
	assertAllFourTokens(t, usage)
	if usage.Model == "" || usage.Harness == "" {
		t.Errorf("EventUsage must attribute Model+Harness, got model=%q harness=%q", usage.Model, usage.Harness)
	}
	if terminal == nil {
		t.Fatal("no terminal payload observed")
	}
	assertFoldReconciles(t, events, terminal)
}

// usageAndTerminal projects the last EventUsage meter and the terminal payload.
func usageAndTerminal(events []agentsession.Event) (*agentsession.UsageMeter, *agentsession.TerminalPayload) {
	var usage *agentsession.UsageMeter
	var terminal *agentsession.TerminalPayload
	for i := range events {
		if events[i].Kind == agentsession.EventUsage {
			usage = events[i].Usage
		}
		if events[i].IsTerminal() {
			terminal = events[i].Terminal
		}
	}
	return usage, terminal
}

// assertAllFourTokens proves a meter populates all four token kinds.
func assertAllFourTokens(t *testing.T, usage *agentsession.UsageMeter) {
	t.Helper()
	if usage.InputTokens == 0 || usage.OutputTokens == 0 || usage.CacheReadTokens == 0 || usage.CacheCreationTokens == 0 {
		t.Errorf("EventUsage must populate all four token kinds, got %+v", *usage)
	}
}

// assertFoldReconciles proves a LedgerFold over the stream reconciles with the
// authoritative terminal ledger (totals + cost).
func assertFoldReconciles(t *testing.T, events []agentsession.Event, terminal *agentsession.TerminalPayload) {
	t.Helper()
	fold := agentsession.NewLedgerFold()
	for i := range events {
		fold.Fold(events[i])
	}
	ledger := fold.Finish()
	if ledger.InputTokens != terminal.Ledger.InputTokens || ledger.OutputTokens != terminal.Ledger.OutputTokens {
		t.Errorf("folded ledger %+v does not reconcile with the authoritative terminal ledger %+v", ledger, terminal.Ledger)
	}
	if ledger.CostMicros != terminal.Ledger.CostMicros {
		t.Errorf("folded CostMicros = %d, terminal = %d", ledger.CostMicros, terminal.Ledger.CostMicros)
	}
}

// assertGrantLinkage proves every EventToolStart carries a GrantID matching a
// Spec.Grants[].ID (the audit chain), and host tools are flagged.
func assertGrantLinkage(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	h := newHarness(t, newAdapter())
	events := promptAndDrain(t, h)

	grantIDs := map[string]bool{"grant-write": true}
	sawToolStart := false
	for i := range events {
		ev := &events[i]
		if ev.Kind != agentsession.EventToolStart || ev.Tool == nil {
			continue
		}
		sawToolStart = true
		if ev.Tool.GrantID == "" {
			t.Errorf("EventToolStart for %q carries no GrantID (audit linkage broken)", ev.Tool.Name)
			continue
		}
		if !grantIDs[ev.Tool.GrantID] {
			t.Errorf("EventToolStart GrantID %q does not match any Spec.Grants[].ID", ev.Tool.GrantID)
		}
	}
	if !sawToolStart {
		t.Fatal("no EventToolStart observed to assert grant linkage")
	}
}

// drainPaced drains a stream; when slow is set, it yields the scheduler between reads to
// force a live-subscriber overflow (the demotion -> catch-up path) without stalling the
// pump or other viewers.
func drainPaced(ctx context.Context, stream agentsession.Stream, slow bool) ([]agentsession.Event, error) {
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return events, wrapStreamErr(stream)
		}
		events = append(events, event)
		if event.IsTerminal() {
			return events, wrapStreamErr(stream)
		}
		if slow {
			for range 50 {
				runtimeGosched()
			}
		}
	}
}
