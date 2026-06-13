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
	if !asType[agentsession.UnknownPermissionError](second) {
		t.Errorf("second Resolve must be UnknownPermissionError, got %v (%T)", second, second)
	}
	// Resolving an unknown id is UnknownPermissionError too.
	_, unknown := session.Resolve(context.Background(), "nope", agentsession.Decision{Allow: true, By: "user-42"})
	if !asType[agentsession.UnknownPermissionError](unknown) {
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
	if !asType[agentsession.UnsupportedError](err) {
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
