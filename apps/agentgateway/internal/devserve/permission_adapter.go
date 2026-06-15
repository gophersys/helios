// This file holds the DEV-ONLY permission-aware harness adapter: a scripted, reactive
// agentsession.Adapter that the dev composition wires so the SvelteKit frontend can exercise
// the LIVE permission round-trip (ADR-0025) end-to-end over real REST+SSE WITHOUT a real
// claude/omp process.
//
// It is the verdict-AWARE counterpart to the agentsessiontest scripted fake: the canonical
// scripted fake's single OnPermissionAnswer reaction cannot branch allow-vs-deny (it discards
// the verdict), but the demo's whole point is that Allow PROCEEDS and Deny BLOCKS. So this
// adapter parses the normalized answer frame the session forwards on a human Resolve
// ("eden:permission:<id>:<verdict>:<by>"), and emits the matching continuation: on allow, the
// out-of-grant tool runs to completion + a clean terminal; on deny, the tool is reported denied
// + a terminal noting the block.
//
// One adapter serves every dev session and dispatches by the FIRST prompt: the permission-demo
// sentinel drives the gate; any other prompt runs the canonical demo body byte-for-byte
// identical to agentsessiontest.CanonicalScript() — so the forced-CRUD path is unchanged.
package devserve

import (
	"context"
	"strings"
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// permissionDemoSentinel is the marker the dev frontend includes in the FIRST prompt to drive
// the out-of-grant permission round-trip instead of the canonical demo turn. The chat surface
// surfaces a "Request an out-of-grant tool" affordance that sends a prompt carrying it.
const permissionDemoSentinel = "eden:demo:permission"

// permissionDemoRequestID is the stable RequestID the dev permission demo's EventPermissionRequest
// carries, so the SSE permission card and the resolve POST correlate deterministically.
const permissionDemoRequestID = "dev-permission-1"

// permissionDemoTool is the OUT-OF-GRANT tool the dev demo agent asks to run (the standing grant
// authorizes only Write — see BuildDevGateway). A scoped Bash is a realistic high-signal ask.
const permissionDemoTool = "Bash(rm -rf build)"

// answerFramePrefix mirrors the library's normalized permission-answer frame tag. The library
// forwards a human Resolve as a steer-shaped frame "eden:permission:<id>:<verdict>:<by>"; this
// adapter parses it to drive the verdict-aware continuation.
const answerFramePrefix = "eden:permission:"

// permissionAdapter is a verdict-aware, reactive agentsession.Adapter for the dev plane. It
// declares CapFull (the full surface, incl. CapPermissionPrompt) and spawns one devConn per
// session. It is safe for concurrent use (it holds no per-session mutable state).
type permissionAdapter struct{}

// newPermissionAdapter builds the dev permission-aware adapter.
func newPermissionAdapter() *permissionAdapter { return &permissionAdapter{} }

// Spawn launches a scripted dev session. The credential is resolved server-side and never read
// here (the dev harness has no upstream) — exactly the credential-never-leaks guarantee.
//
//nolint:gocritic,ireturn // contract §2/§3: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the dev adapter mirrors the frozen seam.
func (permissionAdapter) Spawn(_ context.Context, _ agentsession.Spec, _ agentsession.Route, _ agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	conn := newDevConn()
	conn.start()
	return conn, nil
}

// Manifest declares the full capability surface so the gateway exercises the whole path,
// including CapPermissionPrompt (the permission round-trip).
func (permissionAdapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapFull,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapFull,
		agentsession.CapNativeBudget:       agentsession.CapFull,
		agentsession.CapPermissionPrompt:   agentsession.CapFull,
		agentsession.CapPartialToolResults: agentsession.CapFull,
	}}
}

// compile-time assertion: *permissionAdapter is an agentsession.Adapter.
var _ agentsession.Adapter = (*permissionAdapter)(nil)

// devConn is the reactive, in-memory agentsession.HarnessConn the dev adapter spawns. It emits
// the Ready handshake, awaits the first prompt, dispatches (canonical demo vs permission gate),
// and — for the gate — BLOCKS for the human's answer frame before emitting the verdict-aware
// continuation. No real subprocess.
type devConn struct {
	events   chan agentsession.Event
	commands chan agentsession.Command
	stop     chan struct{}
	done     chan struct{}

	closeOnce sync.Once
	doneOnce  sync.Once
}

// newDevConn builds a fresh dev conn.
func newDevConn() *devConn {
	return &devConn{
		events:   make(chan agentsession.Event),
		commands: make(chan agentsession.Command),
		stop:     make(chan struct{}),
		done:     make(chan struct{}),
	}
}

// start launches the driver goroutine.
func (c *devConn) start() { go c.drive() }

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *devConn) Events() <-chan agentsession.Event { return c.events }

// Send forwards a normalized control frame to the driver (or drops it if the driver already
// stopped, so a late Send after terminal never deadlocks).
func (c *devConn) Send(ctx context.Context, command agentsession.Command) error {
	select {
	case c.commands <- command:
		return nil
	case <-c.done:
		return nil
	case <-ctx.Done():
		return nil
	}
}

// Close stops the driver and waits for it to finish (idempotent).
func (c *devConn) Close(_ context.Context) error {
	c.closeOnce.Do(func() { close(c.stop) })
	<-c.done
	return nil
}

// drive is the conn's single goroutine: Ready -> await first prompt -> dispatch.
func (c *devConn) drive() {
	defer c.finish()
	if !c.emit(agentsessiontest.ReadyEvent()) {
		return
	}
	prompt, ok := c.awaitFirstPrompt()
	if !ok {
		return
	}
	if strings.Contains(prompt, permissionDemoSentinel) {
		c.streamPermissionDemo()
		return
	}
	c.streamCanonical()
}

// awaitFirstPrompt blocks until the SUT sends the first Prompt, returning its text. An early
// Abort/Close emits the aborted terminal and returns ok=false.
func (c *devConn) awaitFirstPrompt() (string, bool) {
	for {
		select {
		case command := <-c.commands:
			switch command.Kind {
			case agentsession.CommandPrompt:
				return command.Text, true
			case agentsession.CommandAbort:
				c.emit(abortedTerminal(command.Text))
				return "", false
			default:
				// A steer/answer before any prompt is a no-op for the dev conn.
			}
		case <-c.stop:
			c.emit(abortedTerminal("eden:closed"))
			return "", false
		}
	}
}

// streamCanonical emits the canonical demo turn — byte-for-byte identical to
// agentsessiontest.CanonicalScript(): a message + thinking + text deltas, a granted Write tool
// start/end, a four-token usage tick, and a clean terminal Result. The forced-CRUD path runs
// here unchanged.
func (c *devConn) streamCanonical() {
	for _, event := range agentsessiontest.CanonicalScript() {
		if !c.emit(event) {
			return
		}
	}
}

// streamPermissionDemo emits the permission round-trip: a brief lead-in, then an
// EventPermissionRequest for the OUT-OF-GRANT tool, then it BLOCKS for the human's answer frame
// and emits the verdict-aware continuation (allow -> tool proceeds + clean terminal; deny -> tool
// denied + terminal noting the block). An Abort/Close before the answer ends the session cleanly.
func (c *devConn) streamPermissionDemo() {
	leadIn := []agentsession.Event{
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.ThinkingDelta("the user asked to clean the build — that needs a shell tool outside my standing grant"),
		agentsessiontest.TextDelta("I need to run a tool outside my standing grant. Requesting permission."),
		agentsessiontest.MessageEnd(),
		agentsessiontest.PermissionRequest(
			permissionDemoRequestID,
			permissionDemoTool,
			"Clean the build directory — a shell command outside the standing Write grant.",
		),
	}
	for _, event := range leadIn {
		if !c.emit(event) {
			return
		}
	}

	// Block for the human's answer frame (the session forwards a Resolve as a steer-shaped
	// "eden:permission:<id>:<verdict>:<by>"). An Abort/Close while waiting ends the session.
	for {
		select {
		case command := <-c.commands:
			if command.Kind == agentsession.CommandAbort {
				c.emit(abortedTerminal(command.Text))
				return
			}
			requestID, verdict, ok := parseAnswerFrame(command.Text)
			if !ok || requestID != permissionDemoRequestID {
				continue // an unrelated frame; keep waiting for the matching answer
			}
			c.emitVerdictContinuation(verdict)
			return
		case <-c.stop:
			c.emit(abortedTerminal("eden:closed"))
			return
		}
	}
}

// emitVerdictContinuation emits the post-resolution body for the parsed verdict: ALLOW runs the
// out-of-grant tool to completion and ends on a clean Result; DENY reports the tool denied and
// ends on a Result noting the human blocked it. Both carry the authoritative ledger.
func (c *devConn) emitVerdictContinuation(allow bool) {
	if allow {
		allowed := []agentsession.Event{
			agentsessiontest.PermissionResolved(permissionDemoRequestID, agentsession.GrantAllowed, "human:operator"),
			agentsessiontest.ToolStart("perm-call-1", "Bash", "rm -rf build"),
			agentsessiontest.ToolEnd("perm-call-1", agentsession.ToolOutcomeOK, "removed build/ (3 entries)", 7*time.Millisecond),
			agentsessiontest.MessageStart("assistant"),
			agentsessiontest.TextDelta("Permission granted — the build directory is clean."),
			agentsessiontest.MessageEnd(),
			permissionResult("Done — cleaned the build directory.", 2),
		}
		for _, event := range allowed {
			if !c.emit(event) {
				return
			}
		}
		return
	}
	denied := []agentsession.Event{
		agentsessiontest.PermissionResolved(permissionDemoRequestID, agentsession.GrantDenied, "human:operator"),
		agentsessiontest.ToolStart("perm-call-1", "Bash", "rm -rf build"),
		agentsessiontest.ToolEnd("perm-call-1", agentsession.ToolOutcomeDenied, "blocked by the permission gate", 1*time.Millisecond),
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.TextDelta("Permission denied — I will not run that tool."),
		agentsessiontest.MessageEnd(),
		permissionResult("Stopped — the out-of-grant tool was denied.", 1),
	}
	for _, event := range denied {
		if !c.emit(event) {
			return
		}
	}
}

// permissionResult builds the clean terminal Result for the permission demo, carrying a
// deterministic ledger (one turn over the demo, the given tool-use count).
func permissionResult(resultText string, toolUses int32) agentsession.Event {
	return agentsessiontest.Result(agentsession.TokenLedger{
		UsageMeter: agentsession.UsageMeter{
			Model: devModelName, Harness: devHarnessName,
			InputTokens: 120, OutputTokens: 48, CacheReadTokens: 64, CacheCreationTokens: 24,
			CostMicros: 1800, Cumulative: true,
		},
		Turns: 1, ToolUses: toolUses, WallTime: 14 * time.Millisecond,
	}, resultText, "end_turn")
}

// abortedTerminal builds the aborted terminal the dev conn synthesizes on an Abort/Close.
func abortedTerminal(by string) agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventAborted,
		Terminal: &agentsession.TerminalPayload{
			Outcome: agentsession.TurnAborted,
			Ledger:  agentsession.TokenLedger{UsageMeter: agentsession.UsageMeter{Harness: devHarnessName, Cumulative: true}},
			By:      by,
		},
	}
}

// parseAnswerFrame interprets the library's normalized permission-answer frame
// "eden:permission:<id>:<verdict>:<by>[:<rationale>]". It returns the request id, whether the
// verdict was allow, and ok=false for any non-answer frame.
func parseAnswerFrame(text string) (requestID string, allow, ok bool) {
	if !strings.HasPrefix(text, answerFramePrefix) {
		return "", false, false
	}
	rest := strings.TrimPrefix(text, answerFramePrefix)
	parts := strings.SplitN(rest, ":", 3)
	if len(parts) < 2 {
		return "", false, false
	}
	return parts[0], parts[1] == "allow", true
}

// emit sends one event to the library pump, honoring stop. Returns false if the conn was stopped.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this dev helper takes it by value.
func (c *devConn) emit(event agentsession.Event) bool {
	select {
	case c.events <- event:
		return true
	case <-c.stop:
		return false
	}
}

// finish closes the event channel and signals done exactly once.
func (c *devConn) finish() {
	c.doneOnce.Do(func() {
		close(c.events)
		close(c.done)
	})
}

// compile-time assertion: *devConn is an agentsession.HarnessConn.
var _ agentsession.HarnessConn = (*devConn)(nil)
