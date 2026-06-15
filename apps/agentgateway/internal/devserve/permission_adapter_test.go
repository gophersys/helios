package devserve

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// This white-box unit test proves the verdict-aware dev permission adapter's real logic — the one
// thing the agentsessiontest scripted fake cannot do: a single permission request resolves to a
// DIFFERENT continuation per verdict (Allow PROCEEDS with the out-of-grant tool; Deny BLOCKS it),
// and an ordinary prompt runs the canonical demo body. It drives a devConn directly (no HTTP, no
// real harness), feeding the normalized prompt + answer frames the session would forward, and
// asserts the emitted Event sequence. It is mock-free and leak-bounded (every conn is Closed).

// driveDevConn spawns a devConn, sends the first prompt, then sends each follow-up frame, draining
// the emitted events to the terminal (or the deadline). It returns the ordered events.
func driveDevConn(t *testing.T, firstPrompt string, follow ...agentsession.Command) []agentsession.Event {
	t.Helper()
	conn := newDevConn()
	conn.start()
	t.Cleanup(func() { _ = conn.Close(context.Background()) })

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// The conn emits Ready first (blocking on the unbuffered event channel until a reader drains
	// it), so the first prompt is sent on a goroutine — otherwise Send (blocking on the unbuffered
	// command channel) and the Ready emit would deadlock before the read loop starts.
	go func() {
		_ = conn.Send(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: firstPrompt})
	}()

	var events []agentsession.Event
	sentFollow := false
	for {
		select {
		case event, ok := <-conn.Events():
			if !ok {
				return events
			}
			events = append(events, event)
			// Once the request is on the wire, forward the queued answer frame(s).
			if !sentFollow && event.Kind == agentsession.EventPermissionRequest {
				sentFollow = true
				for _, frame := range follow {
					if err := conn.Send(ctx, frame); err != nil {
						t.Fatalf("send follow frame: %v", err)
					}
				}
			}
			if event.IsTerminal() {
				return events
			}
		case <-ctx.Done():
			t.Fatalf("dev conn did not reach terminal: %v (events=%d)", ctx.Err(), len(events))
		}
	}
}

// kindsOf renders the event kinds in order for a readable assertion failure.
func kindsOf(events []agentsession.Event) []agentsession.EventKind {
	out := make([]agentsession.EventKind, len(events))
	for i := range events {
		out[i] = events[i].Kind
	}
	return out
}

// answerFrame builds the steer-shaped permission-answer frame the session forwards on a human
// Resolve ("eden:permission:<id>:<verdict>:<by>").
func answerFrame(verdict string) agentsession.Command {
	return agentsession.Command{
		Kind: agentsession.CommandSteer,
		Text: answerFramePrefix + permissionDemoRequestID + ":" + verdict + ":human:operator",
	}
}

// findResolved returns the first EventPermissionResolved (or fails).
func findResolved(t *testing.T, events []agentsession.Event) agentsession.Event {
	t.Helper()
	for _, event := range events {
		if event.Kind == agentsession.EventPermissionResolved {
			return event
		}
	}
	t.Fatalf("no permission-resolved event in stream (kinds=%v)", kindsOf(events))
	return agentsession.Event{}
}

// findBashToolEnd returns the tool-end event for the out-of-grant Bash call (or fails).
func findBashToolEnd(t *testing.T, events []agentsession.Event) agentsession.Event {
	t.Helper()
	for _, event := range events {
		if event.Kind == agentsession.EventToolEnd && event.Tool != nil && event.Tool.CallID == "perm-call-1" {
			return event
		}
	}
	t.Fatalf("no Bash tool-end event in stream (kinds=%v)", kindsOf(events))
	return agentsession.Event{}
}

func TestPermissionAdapter_AllowProceeds(t *testing.T) {
	t.Parallel()
	events := driveDevConn(t, "please "+permissionDemoSentinel+" now", answerFrame("allow"))

	// The request was emitted, then resolved ALLOWED, the out-of-grant Bash tool ran to OK, and a
	// clean terminal Result closed the turn.
	resolved := findResolved(t, events)
	if resolved.Permission == nil || resolved.Permission.Decision != agentsession.GrantAllowed {
		t.Fatalf("expected resolved=allowed, got %+v", resolved.Permission)
	}
	bash := findBashToolEnd(t, events)
	if bash.Tool.Outcome != agentsession.ToolOutcomeOK {
		t.Fatalf("allow must run the tool to OK, got outcome %v", bash.Tool.Outcome)
	}
	last := events[len(events)-1]
	if last.Kind != agentsession.EventResult {
		t.Fatalf("allow must end on a clean Result, ended on %v (kinds=%v)", last.Kind, kindsOf(events))
	}
}

func TestPermissionAdapter_DenyBlocks(t *testing.T) {
	t.Parallel()
	events := driveDevConn(t, permissionDemoSentinel, answerFrame("deny"))

	// The request was resolved DENIED, the Bash tool was reported DENIED (blocked, not run), and a
	// clean terminal Result still closed the turn (the agent stopped at the gate, no error).
	resolved := findResolved(t, events)
	if resolved.Permission == nil || resolved.Permission.Decision != agentsession.GrantDenied {
		t.Fatalf("expected resolved=denied, got %+v", resolved.Permission)
	}
	bash := findBashToolEnd(t, events)
	if bash.Tool.Outcome != agentsession.ToolOutcomeDenied {
		t.Fatalf("deny must block the tool (outcome denied), got %v", bash.Tool.Outcome)
	}
	last := events[len(events)-1]
	if last.Kind != agentsession.EventResult {
		t.Fatalf("deny must end on a clean Result, ended on %v (kinds=%v)", last.Kind, kindsOf(events))
	}
}

func TestPermissionAdapter_OrdinaryPromptRunsCanonical(t *testing.T) {
	t.Parallel()
	// An ordinary prompt (no sentinel) runs the canonical demo body and terminates WITHOUT ever
	// emitting a permission request — the forced-CRUD path is unchanged.
	events := driveDevConn(t, "Write a note and say hello.")

	for _, event := range events {
		if event.Kind == agentsession.EventPermissionRequest {
			t.Fatalf("an ordinary prompt must not emit a permission request (kinds=%v)", kindsOf(events))
		}
	}
	last := events[len(events)-1]
	if last.Kind != agentsession.EventResult {
		t.Fatalf("canonical body must end on a clean Result, ended on %v", last.Kind)
	}
	// The canonical body carries the granted Write tool (the existing CRUD assertion).
	sawWrite := false
	for _, event := range events {
		if event.Kind == agentsession.EventToolStart && event.Tool != nil && event.Tool.Name == "Write" {
			sawWrite = true
		}
	}
	if !sawWrite {
		t.Fatalf("canonical body must include the granted Write tool (kinds=%v)", kindsOf(events))
	}
}

func TestPermissionAdapter_ManifestDeclaresPermissionPrompt(t *testing.T) {
	t.Parallel()
	manifest := newPermissionAdapter().Manifest()
	if manifest.Status(agentsession.CapPermissionPrompt) != agentsession.CapFull {
		t.Fatalf("the dev adapter must declare CapPermissionPrompt=CapFull, got %v",
			manifest.Status(agentsession.CapPermissionPrompt))
	}
}
