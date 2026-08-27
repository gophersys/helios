package agentruntime

import (
	"context"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// Run is the PID-1 run loop AND the graceful-shutdown state machine (ADR-0022 Consequences). The
// caller passes the parent ctx from signal.NotifyContext (so a SIGTERM/SIGINT cancels it); Run:
//
//  1. derives the agent ctx and REGISTERS it (the kill path),
//  2. Opens the harness session through the agentsession Factory (in-process),
//  3. SUBSCRIBES agent.<id>.control and starts the heartbeat ticker,
//  4. PUMPS the session's Event stream, publishing each Seq-stamped envelope to agent.<id>.events,
//  5. on a termination trigger (parent-ctx signal | STOP verb | KILL verb | session terminal) DRAINS
//     the in-flight turn (bounded by DrainTimeout), CLOSEs the session, FLUSHes OTel, and returns the
//     typed TerminationReason.
//
// Run reaps the pump, heartbeat, and subscription goroutines before returning (goleak-clean). It is
// called ONCE per Runtime; a second call returns an error (the session is single-use).
func (r *Runtime) Run(ctx context.Context) (TerminationReason, error) {
	agentCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	id := r.configuration.AgentID
	r.registry.register(id, cancel)
	defer r.registry.deregister(id)

	r.observer.Logf(ctx, "agentruntime: agent %q starting", id)

	session, err := r.sessions.Open(agentCtx, r.configuration.Spec)
	if err != nil {
		_ = r.observer.Flush(ctx) //nolint:errcheck // shutdown flush is best-effort; the Open error is the authoritative return.
		return TerminationFault, errors.Wrap(errors.KindUnavailable, "agentruntime: open harness session", err)
	}

	loop := &runLoop{
		runtime:     r,
		agentCtx:    agentCtx,
		cancel:      cancel,
		session:     session,
		killed:      &atomic.Bool{},
		stopRequest: make(chan struct{}, 1),
		killRequest: make(chan struct{}, 1),
	}
	return loop.drive(ctx)
}

// runLoop is the per-Run mutable state (kept off *Runtime so a Runtime stays reusable-by-contract and
// the loop's channels/goroutines are scoped to one Run). It owns the pump, the heartbeat ticker, and
// the control subscription, and joins them all on the way out.
type runLoop struct {
	runtime  *Runtime
	agentCtx context.Context
	cancel   context.CancelFunc
	session  agentsession.Session

	killed      *atomic.Bool // set when a KILL verb fired, so the reason is control-kill, not signal
	stopReason  atomic.Uint32
	stopRequest chan struct{} // a STOP verb requests a graceful drain
	killRequest chan struct{} // a KILL verb requests an immediate cancel

	lastSeq      atomic.Uint64 // the highest event Seq published (the heartbeat LastSeq)
	sessionState atomic.Uint32 // the latest agentsession.State seen on the stream (the heartbeat field)
}

// drive runs the loop body: start the heartbeat + control subscription, pump the events, then on the
// first termination trigger drain+close+flush and return the typed reason.
func (l *runLoop) drive(shutdownCtx context.Context) (TerminationReason, error) {
	r := l.runtime
	l.sessionState.Store(uint32(agentsession.StateInitializing))

	var workers sync.WaitGroup
	workers.Add(2)
	go l.runHeartbeat(&workers)
	go l.runControl(&workers)

	if l.runtime.configuration.InitialPrompt != "" {
		l.seedInitialPrompt()
	}

	reason, sessionAlive := l.pump() // blocks until the stream terminates or a trigger cancels agentCtx

	// Publish the explicit PhaseDraining beat BEFORE the cancel: the heartbeat goroutine returns the
	// instant agentCtx cancels (so it cannot emit a drain beat itself once we cancel below), yet the
	// orchestrator must observe the drain window. This beat rides the still-live agentCtx so the OTel
	// carrier parents the drain to the run span; PhaseStopped (below) rides the detached shutdownCtx.
	l.publishHealth(l.agentCtx, PhaseDraining)

	// Termination: stop the workers (cancel the agent ctx if not already), then drain+close the
	// session under a bounded ctx, then flush OTel. Cancel first so the control sub + heartbeat unwind.
	l.cancel()
	workers.Wait()

	drainCtx, drainCancel := context.WithTimeout(context.WithoutCancel(shutdownCtx), r.drainTimeout())
	defer drainCancel()
	if err := l.session.Close(drainCtx); err != nil {
		r.observer.Logf(shutdownCtx, "agentruntime: agent %q session close error: %v", r.configuration.AgentID, err)
	}
	if sessionAlive {
		l.publishSessionTail(drainCtx)
	}
	l.publishHealth(shutdownCtx, PhaseStopped)

	if err := r.observer.Flush(context.WithoutCancel(shutdownCtx)); err != nil {
		// Flush is the LAST step; a flush error is surfaced but never masks the termination reason —
		// the loop already drained cleanly, telemetry delivery is a separate concern.
		r.observer.Logf(shutdownCtx, "agentruntime: agent %q otel flush error: %v", r.configuration.AgentID, err)
	}
	r.observer.Logf(shutdownCtx, "agentruntime: agent %q stopped (%s)", r.configuration.AgentID, reason)
	return reason, nil
}

// pump reads the session's Event stream from Seq 0, publishing each event as a Seq-stamped envelope
// to agent.<id>.events, until the stream reaches a TURN BOUNDARY or a session terminal, OR a
// termination trigger fires. It returns the typed reason plus whether the session is STILL ALIVE at
// that point — true when the loop ended on a turn boundary, so drive knows the session's own
// terminal is still to come from the Close. The pump is the single writer of lastSeq/sessionState.
func (l *runLoop) pump() (reason TerminationReason, sessionAlive bool) {
	stream := l.session.Events(l.agentCtx, agentsession.FromSeq(0))
	for {
		// A termination trigger pre-empts a blocking Next: check the request channels first so a
		// STOP/KILL/signal does not wait on the next event.
		if reason, done := l.checkTriggers(); done {
			return reason, false
		}
		event, ok := stream.Next(l.agentCtx)
		if !ok {
			return l.streamEndReason(stream), false
		}
		l.recordAndPublish(l.agentCtx, event)
		if event.IsTerminal() {
			return TerminationSessionEnd, false
		}
		if event.Kind == agentsession.EventTurnEnd {
			// The harness ended its TURN and is waiting for the next Prompt. The sidecar runs one
			// turn, so this ends the run — but the session is alive, and Close is what produces
			// the terminal every viewer's replay ends on.
			return TerminationSessionEnd, true
		}
	}
}

// publishSessionTail publishes whatever the Close appended past the pump's last event — the
// session's own terminal, synthesized when the harness only ever ended its TURN. Without it a
// clean multi-turn run would leave the bus with no terminal to end a replay on. It reads from the
// last published Seq, so nothing is republished, and the session is already closed, so the drain
// is bounded by the transcript head.
func (l *runLoop) publishSessionTail(ctx context.Context) {
	stream := l.session.Events(ctx, agentsession.FromSeq(l.lastSeq.Load()))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return
		}
		l.recordAndPublish(ctx, event)
	}
}

// checkTriggers reports a termination reason if a STOP/KILL request or the agent ctx fired, without
// blocking on the event stream. KILL is checked before STOP (hard beats soft); a canceled agentCtx
// with no explicit verb is the signal path.
func (l *runLoop) checkTriggers() (TerminationReason, bool) {
	select {
	case <-l.killRequest:
		return TerminationControlKill, true
	default:
	}
	select {
	case <-l.stopRequest:
		return TerminationControlStop, true
	default:
	}
	select {
	case <-l.agentCtx.Done():
		if l.killed.Load() {
			return TerminationControlKill, true
		}
		return TerminationSignal, true
	default:
		return TerminationUnknown, false
	}
}

// streamEndReason classifies why the event stream ended with ok=false: a stream fault is a transport
// fault; a clean end under a fired trigger is that trigger's reason; otherwise the session reached
// its own terminal (the harness exited).
func (l *runLoop) streamEndReason(stream agentsession.Stream) TerminationReason {
	if err := stream.Err(); err != nil {
		l.runtime.observer.Logf(l.agentCtx, "agentruntime: agent %q stream fault: %v", l.runtime.configuration.AgentID, err)
		return TerminationFault
	}
	if reason, done := l.checkTriggers(); done {
		return reason
	}
	return TerminationSessionEnd
}

// recordAndPublish stamps the loop's lastSeq/sessionState from the event and publishes the Seq-stamped
// envelope to agent.<id>.events with the OTel carrier. A publish error is logged, never dropped
// silently, and never stalls the pump (the durable JetStream append is the consumer's replay source;
// a transient publish failure is surfaced and the pump continues so the harness is not blocked).
//
//nolint:gocritic // agentsession.Event is the frozen, copyable record (agentsession contract §2); this writer takes it by value, mirroring the upstream seam.
func (l *runLoop) recordAndPublish(ctx context.Context, event agentsession.Event) {
	r := l.runtime
	l.lastSeq.Store(event.Seq)
	if event.Kind == agentsession.EventSessionState && event.State != nil {
		l.sessionState.Store(uint32(event.State.To))
	}
	envelope := EventEnvelope{
		AgentID:  r.configuration.AgentID,
		Seq:      event.Seq,
		Event:    event,
		OTel:     r.observer.Inject(ctx),
		EmitTime: r.clock.Now(),
	}
	if err := r.bus.PublishEvent(ctx, envelope); err != nil {
		r.observer.Logf(ctx, "agentruntime: agent %q publish event seq=%d error: %v", r.configuration.AgentID, event.Seq, err)
	}
}

// seedInitialPrompt sends the configured InitialPrompt as the first turn (the batch/seed path). The
// agentsession Open returned at StateReady, so a Prompt is in phase; a send error is logged (the
// pump continues — the operator may still drive it via a control PROMPT).
func (l *runLoop) seedInitialPrompt() {
	r := l.runtime
	_, err := l.session.Control(l.agentCtx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: r.configuration.InitialPrompt})
	if err != nil {
		r.observer.Logf(l.agentCtx, "agentruntime: agent %q initial prompt error: %v", r.configuration.AgentID, err)
	}
}

// runHeartbeat publishes a Heartbeat at the configured cadence until the agent ctx is canceled. It is
// joined by drive via the WaitGroup. It leads the closed phase progression on the wire: an immediate
// PhaseStarting beat (the orchestrator sees the sidecar attached the moment the run loop comes up,
// before the first event has pumped), then PhaseRunning (the steady state), then a PhaseRunning beat
// every interval until cancel. The terminal PhaseDraining→PhaseStopped pair is published by drive on
// the shutdown path (the heartbeat goroutine returns the instant agentCtx cancels). Every advertised
// HealthPhase is thus emitted on some path across the lifecycle.
func (l *runLoop) runHeartbeat(workers *sync.WaitGroup) {
	defer workers.Done()
	r := l.runtime
	l.publishHealth(l.agentCtx, PhaseStarting)
	l.publishHealth(l.agentCtx, PhaseRunning)
	ticker := time.NewTicker(r.heartbeatInterval())
	defer ticker.Stop()
	for {
		select {
		case <-l.agentCtx.Done():
			return
		case <-ticker.C:
			phase := PhaseRunning
			if l.draining() {
				phase = PhaseDraining
			}
			l.publishHealth(l.agentCtx, phase)
		}
	}
}

// publishHealth publishes one heartbeat with the loop's current LastSeq + SessionState + the OTel
// carrier. A publish error is logged, never dropped (a heartbeat is best-effort liveness, but a
// silent failure would hide a dead bus). The terminal PhaseDraining (live agentCtx) and PhaseStopped
// (detached shutdownCtx, agentCtx already canceled) beats are published by drive on the shutdown path.
func (l *runLoop) publishHealth(ctx context.Context, phase HealthPhase) {
	r := l.runtime
	// #nosec G115 -- sessionState only ever holds a uint8 agentsession.State widened to uint32 by recordAndPublish; the narrowing back is lossless by construction (the value is bounded to the State enum).
	state := agentsession.State(l.sessionState.Load())
	heartbeat := Heartbeat{
		AgentID:      r.configuration.AgentID,
		Phase:        phase,
		SessionState: state,
		LastSeq:      l.lastSeq.Load(),
		At:           r.clock.Now(),
		OTel:         r.observer.Inject(ctx),
	}
	if err := r.bus.PublishHealth(ctx, heartbeat); err != nil {
		r.observer.Logf(ctx, "agentruntime: agent %q publish health error: %v", r.configuration.AgentID, err)
	}
}

// draining reports whether a STOP/KILL/signal trigger has fired (the heartbeat phase flips to
// draining). It reads the same triggers without consuming them.
func (l *runLoop) draining() bool {
	return l.stopReason.Load() != 0 || l.agentCtx.Err() != nil
}

// runControl subscribes to agent.<id>.control and enacts each verb until the agent ctx is canceled.
// It is joined by drive via the WaitGroup. The subscription blocks in the bus adapter until ctx is
// canceled; a subscribe error is logged (a sidecar with no control channel still pumps + heartbeats —
// it just cannot be steered, which is surfaced, not hidden).
func (l *runLoop) runControl(workers *sync.WaitGroup) {
	defer workers.Done()
	r := l.runtime
	err := r.bus.SubscribeControl(l.agentCtx, r.configuration.AgentID, l.onControl)
	if err != nil && l.agentCtx.Err() == nil {
		r.observer.Logf(l.agentCtx, "agentruntime: agent %q control subscribe error: %v", r.configuration.AgentID, err)
	}
}

// onControl maps ONE decoded control message onto the agentsession session (+ the registry kill
// path). It runs on the bus adapter's delivery goroutine; the agentsession Session serializes the
// command internally, so concurrent control delivery is safe. The trace carrier on the message
// parents the verb's telemetry to the orchestrator's publish span (OTel-on-every-message).
func (l *runLoop) onControl(message ControlMessage) {
	r := l.runtime
	ctx := r.observer.Extract(l.agentCtx, message.OTel)
	r.observer.Logf(ctx, "agentruntime: agent %q control verb=%s by=%q", r.configuration.AgentID, message.Verb, message.By)

	switch message.Verb {
	case VerbPrompt:
		l.sendCommand(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: message.Text})
	case VerbSteer:
		l.sendCommand(ctx, agentsession.Command{Kind: agentsession.CommandSteer, Text: message.Text})
	case VerbAbort:
		l.sendCommand(ctx, agentsession.Command{Kind: agentsession.CommandAbort})
	case VerbStop:
		l.requestStop()
	case VerbKill:
		l.requestKill()
	default:
		r.observer.Logf(ctx, "agentruntime: agent %q unknown control verb %d ignored", r.configuration.AgentID, message.Verb)
	}
}

// sendCommand issues a turn-taking command to the session; an out-of-phase / unsupported error is
// logged (the orchestrator surfaces it via the resulting event stream — a steer onto a non-Running
// turn or an unsupported verb degrades per agentsession, never panics the sidecar).
func (l *runLoop) sendCommand(ctx context.Context, command agentsession.Command) {
	r := l.runtime
	if _, err := l.session.Control(ctx, command); err != nil {
		r.observer.Logf(ctx, "agentruntime: agent %q control command %v error: %v", r.configuration.AgentID, command.Kind, err)
	}
}

// requestStop signals a graceful drain (the STOP verb): the pump observes it and returns
// TerminationControlStop, which drains the in-flight turn before closing. Idempotent (the buffered
// channel + the stopReason guard collapse repeats).
func (l *runLoop) requestStop() {
	if l.stopReason.CompareAndSwap(0, uint32(TerminationControlStop)) {
		select {
		case l.stopRequest <- struct{}{}:
		default:
		}
		l.cancel() // unblock a Next that is waiting on the stream
	}
}

// requestKill signals an immediate hard stop (the KILL verb): mark killed so the reason is
// control-kill, then cancel the agent ctx now (the registry kill path). Idempotent.
func (l *runLoop) requestKill() {
	l.killed.Store(true)
	l.stopReason.CompareAndSwap(0, uint32(TerminationControlKill))
	select {
	case l.killRequest <- struct{}{}:
	default:
	}
	l.runtime.registry.kill(l.runtime.configuration.AgentID)
}
