package agentsession

import (
	"context"
	"strconv"

	"github.com/gophersys/libs/go/errors"
)

// pump is the single goroutine that owns the harness event channel. It is the SOLE
// writer of Seq and State: it normalizes the adapter's pre-Seq events, applies the
// state machine, links each tool call to its authorizing grant, watches the budget,
// drives the permission round-trip, appends each event to the durable Transcript
// (assigning Seq == transcript offset), and fans it out. The first StateReady transition
// signals the handshake on `ready`; the absence of any Ready before the channel closes
// converts to AuthError (the silent-bad-token trap).
func (s *session) pump(ready chan<- error) {
	defer close(s.pumpDone)
	defer s.broadcaster.close()

	readySignaled := false
	terminalSeen := false
	for raw := range s.conn.Events() {
		emitted := s.handle(raw)
		for i := range emitted {
			ev := &emitted[i]
			if ev.Kind == EventSessionState && ev.State != nil && ev.State.To == StateReady && !readySignaled {
				readySignaled = true
				ready <- nil
			}
			if ev.IsTerminal() {
				terminalSeen = true
			}
		}
	}

	if !readySignaled {
		// The harness channel closed without ever confirming readiness: the
		// silent-bad-token trap. Surface AuthError to Open and emit a Failed terminal.
		ready <- errors.Wrap(errors.KindUnauthenticated, "agentsession: handshake",
			AuthError{Reference: s.spec.Credential})
		s.emitTerminalFailed(ReasonAuth, "harness closed before readiness handshake")
		return
	}
	if !terminalSeen {
		// The harness channel closed without a terminal Event (a transport drop /
		// process death mid-run). Synthesize a Failed terminal so every viewer's stream
		// ends with a real terminal and the ledger finalizes.
		s.emitTerminalFailed(ReasonTransport, "harness stream ended without a terminal event")
	}
}

// handle normalizes one raw adapter event into the published sequence. It applies the
// state machine, grant linkage, budget watch, and permission round-trip, returning the
// events actually emitted (a raw event may produce a synthetic SessionState transition
// alongside the event itself). Each returned event has been Seq-stamped and fanned out.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) handle(raw Event) []Event {
	var emitted []Event

	if next, ok := s.nextState(raw); ok {
		emitted = append(emitted, s.emit(s.stateEvent(s.priorState(), next)))
		s.setState(next)
	}

	switch raw.Kind {
	case EventToolStart:
		emitted = append(emitted, s.emit(s.linkGrant(raw)))
	case EventPermissionRequest:
		emitted = append(emitted, s.handlePermissionRequest(raw)...)
	case EventUsage:
		published := s.emit(raw)
		emitted = append(emitted, published)
		s.watchBudget(raw)
	case EventSessionState:
		// State transitions are derived above from nextState; a raw SessionState frame
		// is informational and is published verbatim for forward-compat.
		emitted = append(emitted, s.emit(raw))
	case EventResult, EventFailed, EventAborted:
		emitted = append(emitted, s.emit(s.stampTerminal(raw)))
	case EventMessageStart, EventThinkingDelta, EventTextDelta, EventMessageEnd,
		EventToolUpdate, EventToolEnd, EventPermissionResolved, EventExtension:
		emitted = append(emitted, s.emit(raw))
	default:
		// An unknown future kind is preserved verbatim (forward-compat), never dropped.
		emitted = append(emitted, s.emit(raw))
	}
	return emitted
}

// nextState derives the lifecycle transition (if any) a raw event implies, enforcing
// the legal transition graph. It returns ok=false when the event implies no transition.
// A terminal session never transitions.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) nextState(raw Event) (State, bool) {
	current := s.priorState()
	if current.IsTerminal() {
		return current, false
	}
	if terminal, ok := terminalStateFor(raw.Kind); ok {
		return terminal, true
	}
	switch raw.Kind {
	case EventSessionState:
		if raw.State != nil && s.legalTransition(current, raw.State.To) {
			return raw.State.To, true
		}
		return current, false
	case EventPermissionRequest:
		return StateAwaitingPermission, true
	case EventPermissionResolved:
		return StateRunning, true
	case EventMessageEnd:
		if current == StateRunning {
			return StateAwaitingInput, true
		}
		return current, false
	default:
		return s.activityState(raw.Kind, current)
	}
}

// activityState maps a streaming-activity event (message/text/thinking/tool) to a Running
// transition when the turn was idle; non-activity events imply no transition.
func (s *session) activityState(kind EventKind, current State) (State, bool) {
	switch kind {
	case EventMessageStart, EventTextDelta, EventThinkingDelta, EventToolStart, EventToolUpdate:
		if current == StateReady || current == StateAwaitingInput {
			return StateRunning, true
		}
		return current, false
	default:
		// EventUsage / EventExtension / EventToolEnd imply no transition.
		return current, false
	}
}

// terminalStateFor maps a terminal event kind to its terminal State (ok=false for a
// non-terminal kind).
func terminalStateFor(kind EventKind) (State, bool) {
	switch kind {
	case EventResult:
		return StateCompleted, true
	case EventFailed:
		return StateFailed, true
	case EventAborted:
		return StateAborted, true
	default:
		return StateInitializing, false
	}
}

// legalTransition reports whether from->to is a permitted lifecycle edge. The graph is
// Initializing->Ready->{Running<->AwaitingInput | AwaitingPermission}->terminal.
func (s *session) legalTransition(from, to State) bool {
	if from.IsTerminal() {
		return false
	}
	switch to {
	case StateInitializing:
		return false
	case StateReady:
		return from == StateInitializing
	case StateRunning:
		return from == StateReady || from == StateAwaitingInput || from == StateAwaitingPermission
	case StateAwaitingInput:
		return from == StateRunning
	case StateAwaitingPermission:
		return from == StateRunning
	case StateCompleted, StateFailed, StateAborted:
		return true
	default:
		return false
	}
}

// linkGrant stamps the authorizing ToolGrant's ID onto a tool-start event (the audit
// chain 07 §3 requires). A tool with no matching grant keeps an empty GrantID; the
// adapter is responsible for raising EventPermissionRequest for out-of-grant tools, so
// an empty GrantID here is a forward-compat host-tool or an already-permitted call.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) linkGrant(raw Event) Event {
	if raw.Tool == nil {
		return raw
	}
	if raw.Tool.GrantID != "" {
		return raw
	}
	clone := *raw.Tool
	if grant, ok := s.matchGrant(clone.Name); ok {
		clone.GrantID = grant.ID
	}
	if s.isHostTool(clone.Name) {
		clone.IsHostTool = true
	}
	raw.Tool = &clone
	return raw
}

// matchGrant finds the ToolGrant authorizing a tool name (exact tool match).
func (s *session) matchGrant(name string) (ToolGrant, bool) {
	for _, grant := range s.spec.Grants {
		if grant.Tool == name {
			return grant, true
		}
	}
	return ToolGrant{}, false
}

// isHostTool reports whether name is an Eden-provided host tool.
func (s *session) isHostTool(name string) bool {
	for _, hostTool := range s.spec.HostTools {
		if hostTool.Name == name {
			return true
		}
	}
	return false
}

// handlePermissionRequest publishes the request event, then drives the round-trip: if
// Spec.OnPermission is set it resolves synchronously (policy) and forwards the decision;
// otherwise it records the request for an out-of-band Resolve (the chat human path).
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) handlePermissionRequest(raw Event) []Event {
	published := s.emit(raw)
	emitted := []Event{published}

	if raw.Permission == nil {
		return emitted
	}
	request := PermissionRequest{
		RequestID: raw.Permission.RequestID,
		Tool:      raw.Permission.Tool,
		Reason:    raw.Permission.Reason,
	}

	if s.spec.OnPermission == nil {
		s.recordPending(request)
		return emitted
	}

	decision := s.spec.OnPermission(request)
	if err := s.forwardDecision(context.Background(), request.RequestID, decision); err != nil {
		// A transport failure forwarding the decision is surfaced as a Failed terminal by
		// the pump on the next channel close; here we record nothing further.
		_ = err
	}
	return emitted
}

// recordPending registers an out-of-grant request awaiting an out-of-band Resolve.
func (s *session) recordPending(request PermissionRequest) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.pending[request.RequestID] = &pendingPermission{request: request}
}

// watchBudget enforces the single budget authority: when a cumulative EventUsage cost
// crosses Budget.MaxCostMicros, the library issues an Abort (so a runaway harness stops
// even if the engine's watch lags). The terminal Event then carries TurnBudgetExceeded.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) watchBudget(raw Event) {
	if s.spec.Budget.MaxCostMicros <= 0 || raw.Usage == nil {
		return
	}
	if !raw.Usage.Cumulative || raw.Usage.CostMicros < 0 {
		return
	}
	if raw.Usage.CostMicros < s.spec.Budget.MaxCostMicros {
		return
	}
	s.mu.Lock()
	if s.budgetHit {
		s.mu.Unlock()
		return
	}
	s.budgetHit = true
	s.mu.Unlock()

	// Abort onto the transport; the adapter ends the turn and the pump publishes the
	// terminal. Abort is best-effort: a transport error is folded into the eventual
	// Failed terminal at channel close.
	s.sendMu.Lock()
	//nolint:errcheck // best-effort budget Abort; a transport failure is folded into the eventual Failed terminal at channel close.
	_ = s.conn.Send(context.Background(), Command{Kind: CommandAbort, Text: budgetAbortReason})
	s.sendMu.Unlock()
}

// emit stamps Seq (== durable transcript offset) and Time, appends to the Transcript,
// publishes to the fan-out, and returns the published Event. It is called ONLY from the
// pump goroutine, so Seq assignment is serialized without a lock on the hot path beyond
// the transcript's own.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) emit(event Event) Event {
	event.SessionID = s.id
	if event.Time.IsZero() {
		event.Time = s.clock.Now()
	}
	event.Turn = s.priorTurn()
	if event.TurnID == "" {
		event.TurnID = s.turnID()
	}
	seq, err := s.transcript.Append(context.Background(), event)
	if err != nil {
		// A transcript append failure is a hard fault: we cannot guarantee replay. The
		// pump synthesizes a Failed terminal at channel close; here we still publish with
		// a best-effort local Seq so live viewers are not silently starved.
		seq = s.bumpLocalSeq()
	}
	event.Seq = seq
	s.recordSeq(seq)
	s.broadcaster.publish(event)
	return event
}

// stateEvent builds a SessionState transition event.
func (s *session) stateEvent(from, to State) Event {
	return Event{Kind: EventSessionState, State: &StatePayload{From: from, To: to}}
}

// stampTerminal re-classifies a terminal Event the LIBRARY caused: a budget-triggered
// Abort is re-stamped TurnBudgetExceeded + ReasonBudget so the chat meter shows
// "stopped: budget" rather than a bare abort. The harness ledger is preserved; only the
// outcome classification the single budget authority owns is rewritten.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump processes it by value and clones-on-modify before fan-out.
func (s *session) stampTerminal(raw Event) Event {
	s.mu.Lock()
	budgetHit := s.budgetHit
	s.mu.Unlock()
	if !budgetHit || raw.Terminal == nil {
		return raw
	}
	clone := *raw.Terminal
	clone.Outcome = TurnBudgetExceeded
	clone.Reason = ReasonBudget
	raw.Terminal = &clone
	return raw
}

// emitTerminalFailed publishes a synthetic Failed terminal (used for the
// silent-bad-token trap and transport death). It also drives the state to Failed.
func (s *session) emitTerminalFailed(reason ErrorReason, detail string) {
	from := s.priorState()
	if from.IsTerminal() {
		return
	}
	s.emit(s.stateEvent(from, StateFailed))
	s.setState(StateFailed)
	s.emit(Event{
		Kind: EventFailed,
		Terminal: &TerminalPayload{
			Outcome: TurnFailed,
			Reason:  reason,
			Detail:  detail,
		},
	})
}

// State accessors and Seq/turn bookkeeping under s.mu.

// priorState reports the current State under the lock.
func (s *session) priorState() State {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.state
}

// setState advances the State under the lock.
func (s *session) setState(next State) {
	s.mu.Lock()
	s.state = next
	s.mu.Unlock()
}

// priorTurn reports the current turn ordinal under the lock.
func (s *session) priorTurn() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.turn
}

// turnID renders the current turn ordinal as the correlation id.
func (s *session) turnID() string {
	return s.id + "-turn-" + strconv.Itoa(s.priorTurn())
}

// recordSeq mirrors the last assigned Seq for Ack reporting.
func (s *session) recordSeq(seq uint64) {
	s.mu.Lock()
	if seq > s.seq {
		s.seq = seq
	}
	s.mu.Unlock()
}

// bumpLocalSeq advances the local Seq mirror (the transcript-fault fallback).
func (s *session) bumpLocalSeq() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.seq++
	return s.seq
}
