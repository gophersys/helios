package agentsessiontest

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// fakeConn is the reactive, in-memory agentsession.HarnessConn the fake Adapter
// spawns. It emits a leading Ready handshake, waits for the first Prompt, then streams
// the scripted body one event at a time, injecting the pinned reaction for each Steer
// or permission-answer control frame and ending on a terminal Event (scripted or, on
// Abort, synthesized). It uses NO real subprocess.
//
// Concurrency: one driver goroutine owns the outbound channel; Send is called by the
// SUT's control goroutine(s) and forwards frames to the driver over an unbuffered
// command channel under serialization by the session's sendMu. Close is idempotent and
// stops the driver.
type fakeConn struct {
	events   chan agentsession.Event
	commands chan agentsession.Command
	stop     chan struct{}

	script          []agentsession.Event
	reactions       map[string][]agentsession.Event
	steerReactions  map[string][]agentsession.Event
	promptReactions map[string][]agentsession.Event
	record          func(agentsession.Command)

	// nonReadying makes the driver exit BEFORE the Ready handshake (the silent-bad-token
	// shape): finish() then closes the event channel with no Ready event ever emitted, so
	// the library pump's genuine no-ready->AuthError path fires — NOT a Spawn-error shortcut.
	nonReadying bool

	closeOnce sync.Once
	doneOnce  sync.Once
	done      chan struct{}
}

// newFakeConn builds a reactive conn over a copied script. record is the Adapter's
// command recorder.
func newFakeConn(
	script []agentsession.Event,
	reactions, steerReactions, promptReactions map[string][]agentsession.Event,
	record func(agentsession.Command),
) *fakeConn {
	return &fakeConn{
		events:          make(chan agentsession.Event),
		commands:        make(chan agentsession.Command),
		stop:            make(chan struct{}),
		done:            make(chan struct{}),
		script:          script,
		reactions:       reactions,
		steerReactions:  steerReactions,
		promptReactions: promptReactions,
		record:          record,
	}
}

// start launches the driver goroutine.
func (c *fakeConn) start() { go c.drive() }

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *fakeConn) Events() <-chan agentsession.Event { return c.events }

// Send forwards a normalized control frame to the driver. It records the command for
// the Adapter's assertions, then hands it to the driver (or drops it if the driver has
// already stopped, so a late Send after terminal never deadlocks).
func (c *fakeConn) Send(ctx context.Context, command agentsession.Command) error {
	if c.record != nil {
		c.record(command)
	}
	select {
	case c.commands <- command:
		return nil
	case <-c.done:
		return nil // the session has terminated; the frame is a no-op
	case <-ctx.Done():
		if err := errors.FromContext(ctx); err != nil {
			return err
		}
		return nil
	}
}

// Close stops the driver (the graceful ladder a real adapter implements: signal stop,
// let the driver emit its terminal, close the channel). Idempotent.
func (c *fakeConn) Close(_ context.Context) error {
	c.closeOnce.Do(func() { close(c.stop) })
	<-c.done
	return nil
}

// drive is the conn's single goroutine. It emits the Ready handshake, waits for the
// first Prompt, streams the scripted body with reactions, and ends on a terminal.
func (c *fakeConn) drive() {
	defer c.finish()

	if c.nonReadying {
		// The harness exits before confirming readiness (silent bad token). Returning here
		// lets the deferred finish() close the event channel with no Ready ever emitted.
		return
	}
	if !c.emitValue(readyEvent()) {
		return
	}
	// Wait for the first Prompt (or Abort/Close before any prompt).
	if !c.awaitFirstPrompt() {
		return
	}
	c.streamBody()
}

// awaitFirstPrompt blocks until the SUT sends the first CommandPrompt, handling an
// early Abort/Close. It returns false if the conn was stopped or aborted before a
// prompt arrived.
func (c *fakeConn) awaitFirstPrompt() bool {
	for {
		select {
		case command := <-c.commands:
			switch command.Kind {
			case agentsession.CommandPrompt:
				return true
			case agentsession.CommandAbort:
				c.emitValue(abortedEvent(command.Text))
				return false
			case agentsession.CommandSteer:
				// A steer before any prompt is a no-op for the fake.
			default:
			}
		case <-c.stop:
			c.emitValue(abortedEvent("eden:closed"))
			return false
		}
	}
}

// streamBody emits the scripted events one at a time. Between events it services
// pending control frames (Steer reactions, permission answers, Abort) WITHOUT blocking
// so a mid-stream steer is observable. After the script is exhausted it enters the
// service loop, blocking for control frames (e.g. a permission answer whose reaction
// carries the terminal) until a terminal is emitted or a stop/abort arrives.
func (c *fakeConn) streamBody() {
	for i := range c.script {
		event := &c.script[i]
		done, terminal := c.serviceReady()
		if done {
			return
		}
		if terminal {
			return
		}
		if !c.emit(event) {
			return
		}
		if event.IsTerminal() {
			return
		}
	}
	c.serviceUntilTerminal()
}

// serviceReady drains any ready control frames WITHOUT blocking, injecting Steer and
// permission-answer reactions and handling Abort. done=true means the session ended
// (abort/stop); terminal=true means a reaction emitted a terminal Event.
func (c *fakeConn) serviceReady() (done, terminal bool) {
	for {
		select {
		case command := <-c.commands:
			ended, term := c.applyControl(command)
			if ended {
				return true, false
			}
			if term {
				return false, true
			}
		case <-c.stop:
			c.emitValue(abortedEvent("eden:closed"))
			return true, false
		default:
			return false, false
		}
	}
}

// serviceUntilTerminal blocks for control frames after the scripted body, injecting
// reactions, until a terminal is emitted (by a reaction or synthesized on stop). It is
// how an out-of-grant request waits for its answer and how a no-terminal script reaches
// a clean Result on Close.
func (c *fakeConn) serviceUntilTerminal() {
	for {
		select {
		case command := <-c.commands:
			ended, terminal := c.applyControl(command)
			if ended || terminal {
				return
			}
		case <-c.stop:
			c.emitValue(resultEvent())
			return
		}
	}
}

// applyControl injects the reaction for a control frame. ended=true on an Abort that
// ends the session; terminal=true when the injected reaction emitted a terminal Event.
func (c *fakeConn) applyControl(command agentsession.Command) (ended, terminal bool) {
	switch command.Kind {
	case agentsession.CommandAbort:
		c.emitValue(abortedEvent(command.Text))
		return true, false
	case agentsession.CommandSteer:
		if requestID, _, ok := parsePermissionAnswer(command.Text); ok {
			return c.injectReaction(c.reactions[requestID])
		}
		return c.injectReaction(c.steerReactions[command.Text])
	case agentsession.CommandPrompt:
		if reaction, ok := c.promptReactions[command.Text]; ok {
			// A pinned follow-up prompt injects a deterministic second-turn body so a
			// multi-turn test drives the real AwaitingInput->Running edge.
			return c.injectReaction(reaction)
		}
		return false, false // an unpinned follow-up prompt continues the same script body
	default:
		return false, false
	}
}

// injectReaction emits a pinned reaction sequence. ended=true if a stop interrupted the
// emit; terminal=true if the reaction contained a terminal Event.
func (c *fakeConn) injectReaction(events []agentsession.Event) (ended, terminal bool) {
	for i := range events {
		event := &events[i]
		if !c.emit(event) {
			return true, false
		}
		if event.IsTerminal() {
			return false, true
		}
	}
	return false, false
}

// emit sends one event to the library pump, honoring stop. It returns false if the conn
// was stopped (so the driver unwinds without blocking on a closed consumer). It takes a
// pointer so the scripted-event slice is not copied per emit.
func (c *fakeConn) emit(event *agentsession.Event) bool {
	select {
	case c.events <- *event:
		return true
	case <-c.stop:
		return false
	}
}

// emitValue is the value-taking emit convenience for the synthesized lifecycle events
// (ready/aborted/result) whose constructors return a fresh value.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this fake/test helper takes it by value.
func (c *fakeConn) emitValue(event agentsession.Event) bool {
	return c.emit(&event)
}

// finish closes the event channel and signals done exactly once.
func (c *fakeConn) finish() {
	c.doneOnce.Do(func() {
		close(c.events)
		close(c.done)
	})
}

// compile-time assertion: *fakeConn is an agentsession.HarnessConn.
var _ agentsession.HarnessConn = (*fakeConn)(nil)
