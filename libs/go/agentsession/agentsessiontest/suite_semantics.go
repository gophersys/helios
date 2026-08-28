package agentsessiontest

import (
	"context"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// permissionScript drives an out-of-grant request: a message, then a permission request
// for a tool NOT in the standing grant. The fake's OnPermissionAnswer pins the resolved
// record + continuation emitted after the SUT (policy or human) answers.
func permissionScript() []agentsession.Event {
	return []agentsession.Event{
		MessageStart("assistant"),
		TextDelta("I need to run a command"),
		PermissionRequest("req-1", "Bash", "run go test"),
	}
}

// assertPermissionPolicy proves the synchronous policy decider (Spec.OnPermission) is
// called and its decision forwarded; with default-deny the request is recorded denied.
func assertPermissionPolicy(t *testing.T, _ func() *Adapter) {
	t.Helper()
	adapter := New(permissionScript()...).
		OnPermissionAnswer(
			"req-1",
			PermissionResolved("req-1", agentsession.GrantAllowed, "policy:clean-room"),
			ToolStart("call-2", "Write", "path=out.txt"),
			ToolEnd("call-2", agentsession.ToolOutcomeOK, "ok", time.Millisecond),
			Usage(usageMeter()),
			Result(fullLedger(), "done", "end_turn"),
		)
	h := newHarness(t, adapter)

	var seen sync.Map
	session := h.open(t, func(spec *agentsession.Spec) {
		spec.OnPermission = func(request agentsession.PermissionRequest) agentsession.Decision {
			seen.Store(request.RequestID, request.Tool)
			return agentsession.Decision{Allow: true, By: "policy:clean-room"}
		}
	})
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	events, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
	if err != nil {
		t.Fatalf("drain: %v", err)
	}

	if tool, ok := seen.Load("req-1"); !ok || tool != "Bash" {
		t.Errorf("OnPermission was not called for req-1/Bash (saw %v/%v)", tool, ok)
	}
	if !hasKind(events, agentsession.EventPermissionRequest) {
		t.Errorf("expected an EventPermissionRequest on the stream")
	}
	if !hasKind(events, agentsession.EventPermissionResolved) {
		t.Errorf("expected an EventPermissionResolved after the policy decision")
	}
	// The session reached its clean terminal after the allowed continuation.
	if !events[len(events)-1].IsTerminal() {
		t.Errorf("session did not reach a terminal after the resolved permission")
	}
}

// assertPermissionHuman proves the out-of-band human path: with OnPermission nil, the
// request surfaces as an event and an out-of-band Resolve unblocks it; Resolve is
// idempotent (first decision wins; losers get UnknownPermissionError).
func assertPermissionHuman(t *testing.T, _ func() *Adapter) {
	t.Helper()
	adapter := New(permissionScript()...).
		OnPermissionAnswer(
			"req-1",
			PermissionResolved("req-1", agentsession.GrantAllowed, "user-42"),
			Usage(usageMeter()),
			Result(fullLedger(), "done", "end_turn"),
		)
	h := newHarness(t, adapter)
	session := h.open(t, nil) // OnPermission nil == the human path

	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}

	// A reader drains in the background while the human resolves out-of-band.
	var drained []agentsession.Event
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		events, derr := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
		if derr != nil {
			t.Errorf("background drain: %v", derr)
		}
		drained = events
	}()

	// Wait until the request is observable, then resolve it out-of-band.
	waitForRequest(t, session)
	ack, err := session.Resolve(context.Background(), "req-1", agentsession.Decision{Allow: true, By: "user-42"})
	if err != nil {
		t.Fatalf("Resolve: %v", err)
	}
	if ack.Seq == 0 {
		t.Errorf("Resolve must return the admitted Seq")
	}
	// First-decision-wins: a second Resolve loses with UnknownPermissionError.
	_, second := session.Resolve(context.Background(), "req-1", agentsession.Decision{Allow: false, By: "user-99"})
	if !errors.IsType[agentsession.UnknownPermissionError](second) {
		t.Errorf("second Resolve must be UnknownPermissionError, got %v (%T)", second, second)
	}
	// Resolving an unknown id is UnknownPermissionError too.
	_, unknown := session.Resolve(context.Background(), "nope", agentsession.Decision{Allow: true, By: "user-42"})
	if !errors.IsType[agentsession.UnknownPermissionError](unknown) {
		t.Errorf("Resolve of an unknown id must be UnknownPermissionError, got %v (%T)", unknown, unknown)
	}

	wg.Wait()
	if !hasKind(drained, agentsession.EventPermissionResolved) {
		t.Errorf("expected EventPermissionResolved after the human Resolve")
	}
}

// assertSteerObservable proves a Steer interjection produces an OBSERVABLE effect on the
// stream (the fake's pinned steer reaction) and that the Steer Command was recorded. The
// script deliberately ends WITHOUT a terminal so the steer is what drives the turn to its
// result — making the steer's effect deterministic, not a timing race.
func assertSteerObservable(t *testing.T, _ func() *Adapter) {
	t.Helper()
	steerText := "focus on tests"
	adapter := New(
		MessageStart("assistant"),
		TextDelta("starting"),
		// No terminal scripted: the turn pauses awaiting input; the Steer reaction below
		// injects the steered marker AND the terminal, so the effect is deterministic.
	).OnSteer(
		steerText,
		TextDelta("[steered] focusing on tests"),
		Usage(usageMeter()),
		Result(fullLedger(), "done", "end_turn"),
	)
	h := newHarness(t, adapter)

	session := h.open(t, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	stream := session.Events(context.Background(), agentsession.FromSeq(0))

	// Read the scripted lead-in, steer once, then drain to the steer-driven terminal.
	steered := false
	var collected []agentsession.Event
	for {
		event, ok := stream.Next(context.Background())
		if !ok {
			break
		}
		collected = append(collected, event)
		if !steered && event.Kind == agentsession.EventTextDelta {
			if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandSteer, Text: steerText}); err != nil {
				t.Fatalf("Steer: %v", err)
			}
			steered = true
		}
		if event.IsTerminal() {
			break
		}
	}

	if !commandRecorded(adapter, agentsession.CommandSteer, steerText) {
		t.Errorf("Steer command was not recorded by the adapter")
	}
	if !hasTextDelta(collected, "[steered]") {
		t.Errorf("the steer effect was not observable on the stream; deltas: %v", textDeltas(collected))
	}
}

// assertTurnOrdinalIncrements proves the per-turn ordinal is live, not dead-on-write: a
// two-prompt chat carries Turn 0 on the first turn and Turn 1 on the second, with a
// distinct TurnID per turn. The first turn's body ends at MessageEnd (-> AwaitingInput)
// with no terminal; the follow-up prompt drives the AwaitingInput->Running edge whose
// transition advances the ordinal BEFORE the second turn's events are stamped. Without
// the increment every event would carry Turn 0 and an identical TurnID (the dead field).
func assertTurnOrdinalIncrements(t *testing.T, _ func() *Adapter) {
	t.Helper()
	const followUp = "and now run the tests"
	adapter := New(
		// First turn: a message that ends WITHOUT a terminal, parking the session in
		// AwaitingInput so a follow-up prompt opens a genuine second turn.
		MessageStart("assistant"),
		TextDelta("first-turn answer"),
		MessageEnd(),
	).OnPrompt(
		followUp,
		// Second turn: a fresh message body and the clean terminal.
		MessageStart("assistant"),
		TextDelta("second-turn answer"),
		Usage(usageMeter()),
		MessageEnd(),
		Result(fullLedger(), "done", "end_turn"),
	)
	h := newHarness(t, adapter)
	session := h.open(t, nil)

	// Drive two prompts over one live stream. The first parks at AwaitingInput; a second
	// drainer (below) reads the whole stream to its terminal, so every event of both turns
	// is collected in Seq order.
	stream := session.Events(context.Background(), agentsession.FromSeq(0))
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("first Prompt: %v", err)
	}
	// Read up to the AwaitingInput park so the follow-up prompt is sent in the right phase,
	// then fire the second prompt and drain the remainder to the terminal.
	firstHalf := readThroughState(t, stream, agentsession.StateAwaitingInput)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: followUp}); err != nil {
		t.Fatalf("follow-up Prompt: %v", err)
	}
	secondHalf := readToTerminal(t, stream)
	all := make([]agentsession.Event, 0, len(firstHalf)+len(secondHalf))
	all = append(all, firstHalf...)
	all = append(all, secondHalf...)

	// Partition the full stream into turns at each transition INTO Running: the first such
	// edge (Ready->Running) opens turn ordinal 0, the second (AwaitingInput->Running) opens
	// ordinal 1. Each turn's events must all carry that single ordinal and a single TurnID.
	turns := partitionByRunningEdge(all)
	if len(turns) != 2 {
		t.Fatalf("expected 2 turns partitioned at the Running edges, got %d (turns=%v)", len(turns), turnOrdinalsOf(turns))
	}

	firstOrdinals, firstIDs := turnSetFor(turns[0])
	secondOrdinals, secondIDs := turnSetFor(turns[1])

	// The first turn carries Turn 0; the second carries Turn 1 — the increment is live.
	assertSingleTurnOrdinal(t, "first turn", firstOrdinals, 0)
	assertSingleTurnOrdinal(t, "second turn", secondOrdinals, 1)

	// The TurnID is distinct across turns (the correlation id is not frozen-at-zero).
	if len(firstIDs) == 0 || len(secondIDs) == 0 {
		t.Fatalf("a turn carried no TurnID (firstIDs=%v secondIDs=%v)", firstIDs, secondIDs)
	}
	for id := range secondIDs {
		if firstIDs[id] {
			t.Errorf("TurnID %q is shared across turns; the TurnID is frozen-at-zero (dead turn field)", id)
		}
	}
}

// readThroughState reads a stream up to and including the first transition INTO want,
// returning the events read. It bounds the read so a regression fails fast.
func readThroughState(t *testing.T, stream agentsession.Stream, want agentsession.State) []agentsession.Event {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("stream ended before reaching state %v", want)
		}
		events = append(events, event)
		if event.Kind == agentsession.EventSessionState && event.State != nil && event.State.To == want {
			return events
		}
	}
}

// readToTerminal reads a stream to its terminal, returning the events read.
func readToTerminal(t *testing.T, stream agentsession.Stream) []agentsession.Event {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatal("stream ended before a terminal event")
		}
		events = append(events, event)
		if event.IsTerminal() {
			return events
		}
	}
}

// partitionByRunningEdge splits the event stream into one slice per turn, cutting at each
// transition INTO StateRunning (the start of a turn). Events before the first Running edge
// (the Initializing->Ready handshake) join the first turn.
func partitionByRunningEdge(events []agentsession.Event) [][]agentsession.Event {
	var turns [][]agentsession.Event
	var current []agentsession.Event
	started := false
	for i := range events {
		ev := &events[i]
		isRunningEdge := ev.Kind == agentsession.EventSessionState && ev.State != nil && ev.State.To == agentsession.StateRunning
		if isRunningEdge && started {
			turns = append(turns, current)
			current = nil
		}
		started = started || isRunningEdge
		current = append(current, *ev)
	}
	if len(current) > 0 {
		turns = append(turns, current)
	}
	return turns
}

// turnSetFor projects the distinct Turn ordinals and TurnIDs carried by a turn's events.
// Every emitted event carries the turn ordinal/TurnID it was stamped under, so a healthy
// turn yields exactly one ordinal and one TurnID.
func turnSetFor(events []agentsession.Event) (ordinals map[int]bool, ids map[string]bool) {
	ordinals = make(map[int]bool)
	ids = make(map[string]bool)
	for i := range events {
		ev := &events[i]
		ordinals[ev.Turn] = true
		if ev.TurnID != "" {
			ids[ev.TurnID] = true
		}
	}
	return ordinals, ids
}

// assertSingleTurnOrdinal proves every event in a turn carries the same expected ordinal.
func assertSingleTurnOrdinal(t *testing.T, label string, ordinals map[int]bool, want int) {
	t.Helper()
	if len(ordinals) != 1 || !ordinals[want] {
		t.Errorf("%s: events carry Turn ordinals %v, want exactly {%d} (turn ordinal dead-on-write?)", label, ordinalKeys(ordinals), want)
	}
}

// ordinalKeys renders an ordinal set for diagnostics.
func ordinalKeys(ordinals map[int]bool) []int {
	out := make([]int, 0, len(ordinals))
	for k := range ordinals {
		out = append(out, k)
	}
	return out
}

// turnOrdinalsOf renders the per-turn ordinal sets for diagnostics.
func turnOrdinalsOf(turns [][]agentsession.Event) [][]int {
	out := make([][]int, len(turns))
	for i := range turns {
		ord, _ := turnSetFor(turns[i])
		out[i] = ordinalKeys(ord)
	}
	return out
}

// assertCapabilityHonesty proves a verb whose Capability the manifest declares CapAbsent
// returns UnsupportedError, and a declared-CapFull verb works.
func assertCapabilityHonesty(t *testing.T, _ func() *Adapter) {
	t.Helper()
	// Declare Steer absent; Steer must then be UnsupportedError even in a Running turn.
	adapter := New(canonicalScript()...).WithManifest(agentsession.CapabilityManifest{
		Capabilities: map[agentsession.Capability]agentsession.CapStatus{
			agentsession.CapSteer:            agentsession.CapAbsent,
			agentsession.CapPermissionPrompt: agentsession.CapFull,
		},
	})
	h := newHarness(t, adapter)
	session := h.open(t, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	// Steer is declared absent: UnsupportedError regardless of phase.
	_, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandSteer, Text: "x"})
	if !errors.IsType[agentsession.UnsupportedError](err) {
		t.Errorf("Steer with CapSteer absent must be UnsupportedError, got %v (%T)", err, err)
	}
	assertKind(t, err, errors.KindInvalid, "UnsupportedError")
	if _, derr := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0))); derr != nil {
		t.Errorf("drain to terminal: %v", derr)
	}
}

// hasKind reports whether any event has the given kind.
func hasKind(events []agentsession.Event, kind agentsession.EventKind) bool {
	for i := range events {
		ev := &events[i]
		if ev.Kind == kind {
			return true
		}
	}
	return false
}

// hasTextDelta reports whether any text delta contains substr.
func hasTextDelta(events []agentsession.Event, substr string) bool {
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventTextDelta && ev.Message != nil && strings.Contains(ev.Message.Delta, substr) {
			return true
		}
	}
	return false
}

// textDeltas projects the text-delta strings (for failure diagnostics).
func textDeltas(events []agentsession.Event) []string {
	var out []string
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventTextDelta && ev.Message != nil {
			out = append(out, ev.Message.Delta)
		}
	}
	return out
}

// commandRecorded reports whether the adapter recorded a command of the given kind+text.
func commandRecorded(adapter *Adapter, kind agentsession.CommandKind, text string) bool {
	for _, command := range adapter.Received() {
		if command.Kind == kind && command.Text == text {
			return true
		}
	}
	return false
}

// waitForRequest blocks until the session is awaiting a permission decision, observed via
// a short-lived tailer. It bounds the wait so a regression fails fast rather than hanging.
func waitForRequest(t *testing.T, session agentsession.Session) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatal("session ended before an EventPermissionRequest was observed")
		}
		if event.Kind == agentsession.EventPermissionRequest {
			return
		}
	}
}
