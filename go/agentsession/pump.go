package agentsession

import (
	"context"
	"strconv"
	"time"

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
	// The last turn's authoritative ledger, cached on the PUMP GOROUTINE's own stack: it is
	// what a requested Close replays as the session's final accounting, and keeping it local
	// means the synthesis needs no shared state and no lock on the hot path.
	var lastTurnLedger TokenLedger
	for raw := range s.conn.Events() {
		emitted := s.handle(raw)
		for i := range emitted {
			ev := &emitted[i]
			if ev.Kind == EventSessionState && ev.State != nil && ev.State.To == StateReady && !readySignaled {
				readySignaled = true
				ready <- nil
			}
			if ev.Kind == EventTurnEnd && ev.Terminal != nil {
				lastTurnLedger = ev.Terminal.Ledger
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
	if terminalSeen {
		return
	}
	if s.closeRequested() {
		// A DELIBERATE Close reaped a healthy session (Close sets closed BEFORE it reaps the
		// conn, so this read cannot mistake a requested shutdown for a death). The session
		// ends on a clean Result replaying the last turn's ledger — not a transport fault.
		s.emitTerminalResult(&lastTurnLedger)
		return
	}
	// The harness channel closed without a terminal Event and without a Close (a transport
	// drop / process death mid-run). Synthesize a Failed terminal so every viewer's stream
	// ends with a real terminal and the ledger finalizes.
	s.emitTerminalFailed(ReasonTransport, "harness stream ended without a terminal event")
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
		prior := s.priorState()
		// A new prompt starts a new turn: the AwaitingInput->Running edge (a follow-up
		// prompt after a completed turn). The turn ordinal must advance BEFORE the
		// transition event is emitted so the new turn's first event already carries the
		// incremented Turn/TurnID. The first Ready->Running keeps Turn 0 (batch: 0; chat:
		// increments per message); AwaitingPermission->Running is a mid-turn continuation,
		// not a new turn, so it does not advance.
		s.advanceTurnOnPrompt(prior, next)
		emitted = append(emitted, s.emit(s.stateEvent(prior, next)))
		s.setState(next)
	}

	s.captureRecent(raw)

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
		EventToolUpdate, EventToolEnd, EventPermissionResolved, EventExtension, EventTurnEnd:
		// EventTurnEnd is published verbatim: it ends a TURN, so it is NOT re-classified by
		// stampTerminal, whose budget re-stamp belongs to the one event that ends the session.
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
	case EventMessageEnd, EventTurnEnd:
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

// handlePermissionRequest publishes the request event, then drives the RATIFIED
// resolution chain (founder model, 2026-06-15). Grants are auto-allowed first (the
// session's dynamically-widened grant set, so a ScopeSession allow is not re-asked); an
// out-of-grant request then takes the per-session chain:
//
//	OnPermission set (clean-room engine policy): resolve synchronously (the TRUSTED
//	    clean-room decider — set by the engine, not influenced by agent prose — so it is
//	    NOT risk-clamped; "no regression" for the existing batch path).
//	ResolveAutonomousAdvisor:  consult the advisor directly (no human wait), CLAMPED.
//	ResolveChatHumanThenAdvisor: record for the human Resolve, arm the timeout timer that
//	    falls back to the CLAMPED advisor, then default-deny.
//
// The terminal fallback is ALWAYS default-deny. The risk-class clamp is applied to the
// ADVISOR's verdict (clampAdvise=true) so the advisor — whose authority is bounded by the
// data-derived risk class, never the agent's prose — can never auto-allow a high-risk tool.
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
	scopes := scopesFor(raw.Permission)

	// Grants check FIRST: a tool already in the session grant set (including a prior
	// ScopeSession widening) is auto-allowed without a prompt or an advisor consult. A
	// grant is already an authorized allowlist entry, so it is not re-clamped.
	if s.toolGranted(request.Tool, scopes) {
		s.decide(request.RequestID, request.Tool, scopes, Decision{Allow: true, By: "grant:session", Scope: ScopeOnce}, clampOff)
		return emitted
	}

	switch {
	case s.spec.OnPermission != nil:
		// The trusted clean-room synchronous policy (the engine's auto-resolver): forwarded
		// without the risk clamp so the existing batch behavior is unchanged (no regression).
		s.decide(request.RequestID, request.Tool, scopes, s.spec.OnPermission(request), clampOff)
	case s.spec.PermissionResolution == ResolveAutonomousAdvisor:
		// Unattended: no human is present, so consult the advisor directly (or default-deny
		// when none is injected). CLAMPED — the advisor can never cross the high-risk wall.
		s.decide(request.RequestID, request.Tool, scopes, s.adviseOrDeny(request, scopes), clampOn)
	default:
		// ResolveChatHumanThenAdvisor: surface for the human Resolve and arm the timeout
		// that falls back to the CLAMPED advisor, then default-deny.
		s.recordPending(request, scopes)
	}
	return emitted
}

// captureRecent feeds the bounded advisor-snippet ring from streamed text/tool activity
// so the advisor's AdviceContext reflects what led to a request. Only redacted, bounded
// summaries ride here (deltas / tool arg summaries) — never a raw secret.
//
//nolint:gocritic // Event is the contract's immutable copyable record (§2); the pump reads it by value.
func (s *session) captureRecent(raw Event) {
	switch raw.Kind {
	case EventTextDelta, EventThinkingDelta:
		if raw.Message != nil {
			s.recordRecentDelta(raw.Message.Delta)
		}
	case EventToolStart:
		if raw.Tool != nil {
			s.recordRecentDelta(raw.Tool.Name + " " + raw.Tool.ArgsSummary)
		}
	default:
	}
}

// recordPending registers an out-of-grant request awaiting a human Resolve and arms the
// per-session timeout: on expiry it falls back to the advisor (then default-deny) UNLESS a
// human Resolve already won the race. The timer fires on a background goroutine; the
// first-decision-wins guard in decide makes a human-Resolve/timeout race deterministic.
func (s *session) recordPending(request PermissionRequest, scopes []string) {
	entry := &pendingPermission{request: request, scopes: scopes}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return
	}
	s.pending[request.RequestID] = entry
	// Arm the timeout under the lock so entry.timer is published before any reader (Resolve)
	// or the callback can observe it; AfterFunc only SCHEDULES here (the callback runs on its
	// own goroutine after the window and acquires s.mu itself, so this is deadlock-free).
	entry.timer = time.AfterFunc(s.permissionTimeout(), func() {
		s.onPermissionTimeout(request, scopes)
	})
}

// onPermissionTimeout is the chat-chain fallback: the human did not Resolve within the
// window, so consult the advisor (then default-deny). It claims the pending entry under the
// first-decision-wins guard; if a human Resolve already claimed it, this is a no-op.
func (s *session) onPermissionTimeout(request PermissionRequest, scopes []string) {
	s.mu.Lock()
	entry, ok := s.pending[request.RequestID]
	if !ok || entry.resolved {
		s.mu.Unlock()
		return
	}
	entry.resolved = true
	s.mu.Unlock()
	// The chat timeout fell back to the advisor: CLAMPED (the advisor can never cross the
	// high-risk wall even on the timeout path).
	s.decide(request.RequestID, request.Tool, scopes, s.adviseOrDeny(request, scopes), clampOn)
}

// adviseOrDeny consults the injected advisor for an out-of-grant request, falling back to
// the safe default-deny when no advisor is injected (degrade path) or the advisor errors /
// its ctx is exceeded (a slow or failing advisor is a deny, never an indefinite block).
// The returned Decision is still subject to the clamp in decide.
func (s *session) adviseOrDeny(request PermissionRequest, scopes []string) Decision {
	if s.advisor == nil {
		if s.spec.OnPermission != nil {
			return s.spec.OnPermission(request)
		}
		return Decision{Allow: false, By: "policy:default-deny", Rationale: "no advisor injected; default-deny"}
	}
	ctx, cancel := context.WithTimeout(context.Background(), s.permissionTimeout())
	defer cancel()
	decision, err := s.advisor.Advise(ctx, request, s.adviceContext(request, scopes))
	if err != nil {
		return Decision{Allow: false, By: "policy:default-deny", Rationale: "advisor error; default-deny"}
	}
	return decision
}

// adviceContext assembles the bundle handed to the advisor: the session goal/role/phase,
// a COPY of the current grant set, a bounded recent-transcript snippet, the security
// posture, and the per-request risk class — all WITHOUT any secret value (07 §2). The Risk
// is the same data-derived class the clamp enforces, handed to the advisor for
// transparency so it can self-escalate (but the wall is enforced in decide, not trusted).
func (s *session) adviceContext(request PermissionRequest, scopes []string) AdviceContext {
	s.mu.Lock()
	grants := cloneGrants(s.sessionGrants)
	transcript := joinRecent(s.recentDeltas)
	s.mu.Unlock()
	return AdviceContext{
		SessionGoal:      s.spec.SystemHints,
		Role:             s.spec.Routing.Role,
		Phase:            s.spec.Routing.Phase,
		Grants:           grants,
		RecentTranscript: transcript,
		SecurityPosture:  securityPosture(s.spec),
		Risk:             riskClass(request.Tool, scopes),
	}
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

// emitTerminalResult publishes the synthetic Result terminal a REQUESTED Close produces: the
// session is healthy and parked between turns, so its one terminal replays the last turn's
// authoritative ledger rather than reporting a fault. It also drives the state to Completed.
func (s *session) emitTerminalResult(ledger *TokenLedger) {
	from := s.priorState()
	if from.IsTerminal() {
		return
	}
	s.emit(s.stateEvent(from, StateCompleted))
	s.setState(StateCompleted)
	s.emit(Event{
		Kind: EventResult,
		Terminal: &TerminalPayload{
			Outcome: TurnCompleted,
			Ledger:  *ledger,
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

// closeRequested reports whether Close was called under the lock — how the pump tells a
// DELIBERATE shutdown from an unbidden harness death at the same event-channel close.
func (s *session) closeRequested() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.closed
}

// setState advances the State under the lock.
func (s *session) setState(next State) {
	s.mu.Lock()
	s.state = next
	s.mu.Unlock()
}

// advanceTurnOnPrompt increments the turn ordinal when an admitted PROMPT begins a new
// turn: the AwaitingInput->Running edge that prompt draws. The first turn (Ready->Running)
// stays at 0; a mid-turn continuation (AwaitingPermission->Running) keeps the current turn.
//
// The armed flag is what separates a prompt's edge from the identical-looking one the
// HARNESS draws resuming its own turn: one claude turn is several assistant messages, each
// ending in a MessageEnd that parks the session, so keying on the edge alone counted a turn
// per message. Every Running edge consumes the arming, so a stale flag cannot advance a
// later turn twice. It is called from the pump goroutine before the transition event is
// stamped.
func (s *session) advanceTurnOnPrompt(prior, next State) {
	if next != StateRunning {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	prompted := s.promptPending
	s.promptPending = false
	if prompted && prior == StateAwaitingInput {
		s.turn++
	}
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
