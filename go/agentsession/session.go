package agentsession

import (
	"context"
	"sync"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// session is the live, concrete Session the Pool returns. It wraps the adapter's
// HarnessConn with the lifecycle state machine, Seq assignment against the durable
// Transcript, multi-client fan-out, grant->audit linkage, the permission round-trip,
// and the budget watch. One pump goroutine owns the harness event channel and is the
// SOLE writer of Seq and State; control verbs are serialized onto the transport. The
// public methods (Events/Control/Resolve/Close) are safe for concurrent use.
type session struct {
	id          string
	spec        Spec
	route       Route
	conn        HarnessConn
	credential  InjectedCredential
	transcript  Transcript
	clock       Clock
	manifest    CapabilityManifest
	advisor     PermissionAdvisor // the ratified-model reasoning port (nil == degrade to OnPermission/default-deny)
	broadcaster *broadcaster

	mu            sync.Mutex // guards state, seq, turn, pending permissions, the session grant set, closed
	state         State
	seq           uint64 // mirror of the last assigned Seq (authoritative is the Transcript)
	turn          int
	promptPending bool                          // an admitted Prompt is awaiting the Running edge that opens its turn
	pending       map[string]*pendingPermission // RequestID -> awaiting resolution (the human-Resolve path)
	sessionGrants []ToolGrant                   // the in-memory grant set: Spec.Grants + ScopeSession widenings (07 §3; never persisted)
	recentDeltas  []string                      // a bounded ring of recent text/tool deltas for the advisor's AdviceContext
	budgetHit     bool
	closed        bool

	sendMu   sync.Mutex    // serializes control frames onto the transport (one writer at a time)
	pumpDone chan struct{} // closed when the pump goroutine exits
}

// pendingPermission is an out-of-grant request awaiting a decision: a human out-of-band
// Resolve (the chat round-trip) OR the timeout->advisor fallback. resolved guards
// first-decision-wins under multi-client races (a human Resolve and the timeout timer
// firing); whichever sets resolved first owns the decision and the pump forwards it.
type pendingPermission struct {
	request  PermissionRequest
	scopes   []string    // the tool's requested sub-scopes (drives the risk class for the clamp)
	resolved bool        // first decision (human Resolve or timeout fallback) wins
	timer    *time.Timer // the chat-chain human-Resolve timeout; nil for the autonomous/policy paths
}

// compile-time assertion: *session is the Session port.
var _ Session = (*session)(nil)

// newSession spawns the pump, drives the Initializing->Ready handshake, and returns a
// live Session at Seq 0 once StateReady is confirmed. The absence of an init/ready
// signal converts to AuthError (the silent-bad-token trap): a harness that exits or
// closes its event channel without ever reaching Ready is treated as unauthenticated,
// NOT trusted as success. On that failure it reaps the conn and zeroizes the secret.
//
//nolint:gocritic // contract §2: Spec is the frozen, copyable session input (the configuration pattern); the port takes it by value.
func newSession(ctx context.Context, spec Spec, route Route, conn HarnessConn, cred InjectedCredential, dependencies Deps) (*session, error) {
	s := &session{
		id:            sessionID(spec, route),
		spec:          spec,
		route:         route,
		conn:          conn,
		credential:    cred,
		transcript:    dependencies.Transcript,
		clock:         dependencies.Clock,
		manifest:      adapterManifest(dependencies, route.Harness),
		advisor:       dependencies.Advisor,
		broadcaster:   newBroadcaster(),
		state:         StateInitializing,
		pending:       make(map[string]*pendingPermission),
		sessionGrants: cloneGrants(spec.Grants),
		pumpDone:      make(chan struct{}),
	}

	ready := make(chan error, 1)
	go s.pump(ready)

	select {
	case err := <-ready:
		if err != nil {
			_ = s.conn.Close(context.Background()) //nolint:errcheck // best-effort reap on a failed handshake; the AuthError is the actionable outcome.
			s.credential.zeroize()
			return nil, err
		}
		return s, nil
	case <-ctx.Done():
		_ = s.conn.Close(context.Background()) //nolint:errcheck // best-effort reap on a canceled open; the AuthError is the actionable outcome.
		s.credential.zeroize()
		return nil, errors.Wrap(errors.KindUnauthenticated, "agentsession: open handshake",
			AuthError{Reference: spec.Credential})
	}
}

// Events returns an independent, Seq-ordered, gap-free view from the given cursor. Any
// number of concurrent Events calls are independent viewers (fan-out).
//
//nolint:ireturn // contract §2: Session.Events returns the Stream port (the frozen surface; the consumer holds the abstraction).
func (s *session) Events(_ context.Context, from Cursor) Stream {
	return newLiveStream(s, from)
}

// Control issues a turn-taking command. It validates the State (StateError if out of
// phase), the Capability (UnsupportedError if the adapter declares it absent), then
// forwards the normalized frame to the harness, returning the Seq it was admitted at.
func (s *session) Control(ctx context.Context, command Command) (Ack, error) {
	if err := s.guardControl(command); err != nil {
		return Ack{}, err
	}
	s.sendMu.Lock()
	defer s.sendMu.Unlock()
	// A Prompt opens a new turn: arm the ordinal advance BEFORE the send, because an adapter
	// whose Send streams the whole turn synchronously (omp's one-shot exec per turn) has
	// already published that turn's events by the time Send returns.
	opensTurn := command.Kind == CommandPrompt
	if opensTurn {
		s.armTurn()
	}
	if err := s.conn.Send(ctx, command); err != nil {
		if opensTurn {
			s.disarmTurn() // the prompt never reached the harness; no turn was opened
		}
		return Ack{}, errors.Wrap(errors.KindUnavailable, "agentsession: send control", err)
	}
	return Ack{Seq: s.currentSeq()}, nil
}

// Resolve answers a pending out-of-grant PermissionRequest. Idempotent on RequestID;
// first decision wins (UnknownPermissionError for an unknown/already-resolved id). It
// forwards the winning Decision to the harness; the resulting PermissionResolved event
// arrives on every viewer's stream.
func (s *session) Resolve(ctx context.Context, requestID string, decision Decision) (Ack, error) {
	s.mu.Lock()
	entry, ok := s.pending[requestID]
	if !ok || entry.resolved {
		s.mu.Unlock()
		return Ack{}, errors.Wrap(errors.KindNotFound, "agentsession: resolve permission",
			UnknownPermissionError{RequestID: requestID})
	}
	entry.resolved = true // first-decision-wins: the human beat the timeout->advisor fallback
	tool := entry.request.Tool
	scopes := entry.scopes
	timer := entry.timer
	s.mu.Unlock()
	if timer != nil {
		timer.Stop() // a human won the race; cancel the advisor fallback
	}

	// A human is the authority the high-risk wall escalates TO, so a human Resolve does NOT
	// pass through the risk-class clamp; it DOES honor ScopeSession widening.
	if err := s.resolveHuman(ctx, requestID, tool, scopes, decision); err != nil {
		return Ack{}, err
	}
	return Ack{Seq: s.currentSeq()}, nil
}

// Close releases the session handle: it signals the harness to stop (the graceful
// abort->stdin-close->wait->kill ladder lives in the adapter's conn.Close), drains the
// pump to its terminal Event, closes the fan-out, and zeroizes the credential. It does
// NOT tear down the pod (workspaceprovider's job). Idempotent.
func (s *session) Close(ctx context.Context) error {
	s.mu.Lock()
	if s.closed {
		s.mu.Unlock()
		return nil
	}
	s.closed = true
	// Stop any armed permission-timeout timers so the advisor-fallback goroutines do not
	// outlive the session (the goleak guarantee).
	for _, entry := range s.pending {
		if entry.timer != nil {
			entry.timer.Stop()
		}
	}
	s.mu.Unlock()

	err := s.conn.Close(ctx)
	// Wait for the pump to finish appending the terminal Event and close the fan-out,
	// bounded by ctx so Close never hangs on a wedged harness.
	select {
	case <-s.pumpDone:
	case <-ctx.Done():
	}
	s.broadcaster.close()
	s.credential.zeroize()
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentsession: close harness", err)
	}
	return nil
}

// guardControl validates the command against the current State and the adapter's
// declared Capability before it reaches the transport.
func (s *session) guardControl(command Command) error {
	s.mu.Lock()
	state := s.state
	s.mu.Unlock()

	// An unknown CommandKind is an INVALID request (not a state conflict), rejected before any
	// state/capability reasoning.
	switch command.Kind {
	case CommandPrompt, CommandSteer, CommandAbort:
		// a known turn-taking command — fall through to the capability + state-legality checks
	default:
		return errors.Wrap(errors.KindInvalid, "agentsession: control",
			StateError{From: state, Op: "Control"})
	}

	// CapSteer absence is a CAPABILITY fault (KindInvalid), checked BEFORE the state membership so an
	// adapter that cannot steer reports UnsupportedError regardless of phase (the capability-honesty
	// contract). It is the one legality input LegalControls deliberately does not encode.
	if command.Kind == CommandSteer && s.manifest.Status(CapSteer) == CapAbsent {
		return errors.Wrap(errors.KindInvalid, "agentsession: steer",
			UnsupportedError{Cap: CapSteer})
	}

	// The (state × command) legality is sourced from the ONE canonical home (LegalControls via
	// CanControl) — guardControl is its enforcer, the gateway projects the same set so the UI never
	// offers an illegal control, and a drift fails in exactly one place. An illegal command in the
	// current state is a typed StateError (KindConflict).
	if !CanControl(state, command.Kind) {
		return errors.Wrap(errors.KindConflict, "agentsession: "+command.Kind.String(),
			StateError{From: state, Op: commandOpNames[command.Kind]})
	}
	return nil
}

// forwardDecision sends a resolved permission Decision to the harness as a normalized
// answer frame (steer-shaped: a permission answer is an interjection, not a session
// Abort). The adapter that declares CapPermissionPrompt maps the answer frame to its
// native permission-answer; the harness then emits the EventPermissionResolved record
// the pump publishes. Allow and deny ride the same frame shape (the verdict is in the
// text), so the harness — not the library — applies or refuses the tool.
func (s *session) forwardDecision(ctx context.Context, requestID string, decision Decision) error {
	s.sendMu.Lock()
	defer s.sendMu.Unlock()
	frame := Command{Kind: CommandSteer, Text: permissionAnswer(requestID, decision)}
	if err := s.conn.Send(ctx, frame); err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentsession: forward decision", err)
	}
	return nil
}

// clampMode selects whether decide applies the risk-class wall. The advisor (and its
// timeout fallback) is clampOn; the trusted clean-room OnPermission policy and a
// session-grant auto-allow are clampOff (already-authorized / engine-trusted deciders).
type clampMode bool

const (
	clampOn  clampMode = true  // the advisor path — bound the verdict by the risk class
	clampOff clampMode = false // a trusted/already-granted decider — forward verbatim
)

// decide is the SINGLE chokepoint every non-human verdict (the OnPermission policy, the
// advisor, the timeout fallback, a session-grant auto-allow) funnels through: when clamp is
// clampOn it applies the RISK-CLASS WALL, then on a surviving allow with ScopeSession widens
// the session grant set, then forwards the decision to the harness. Because the clamp lives
// HERE in agentsession — not in the advisor — the high-risk wall holds for ANY advisor impl:
// an injected advisor that returns allow on a high-risk tool is overridden to deny. A human
// Resolve is the one path that does NOT pass through this chokepoint (a human is the authority
// the wall escalates TO); it routes through resolveHuman.
//
//nolint:gocritic // Decision is the contract's copyable value record (§2); decide takes it by value and re-stamps a clamped copy.
func (s *session) decide(requestID, tool string, scopes []string, decision Decision, clamp clampMode) {
	final := decision
	if clamp == clampOn {
		final = clampToRisk(tool, scopes, decision)
	}
	if final.Allow && (final.Scope == ScopeSession || final.Remember) {
		s.widenGrant(requestID, tool, scopes)
	}
	if err := s.forwardDecision(context.Background(), requestID, final); err != nil {
		// A transport failure forwarding the decision is surfaced as a Failed terminal by
		// the pump at the next channel close; nothing further to record here.
		_ = err
	}
}

// clampToRisk is the prompt-injection WALL: it bounds the advisor's verdict by the risk
// class derived from the request's tool+scope DATA (never the agent's prose). On RiskHigh
// the advisor may NEVER auto-allow — an allow is OVERRIDDEN to deny (the Rationale records
// the override). RiskLow/RiskMedium allows pass through unchanged. A deny always passes
// through. The tool name is the request's recorded tool (the trustworthy class key), so a
// forged scope in the returned Decision cannot lower the class. It is a PURE function (no
// receiver) so the wall is trivially testable in isolation.
//
//nolint:gocritic // Decision is the contract's copyable value record (§2); the clamp returns a re-stamped copy.
func clampToRisk(tool string, scopes []string, decision Decision) Decision {
	if !decision.Allow {
		return decision
	}
	if riskClass(tool, scopes) != RiskHigh {
		return decision
	}
	// HIGH-risk + an attempted allow: override to deny. The advisor cannot cross the wall;
	// the only authority that could is a human (the chat human-Resolve path, which does not
	// pass through this clamp).
	return Decision{
		Allow:     false,
		By:        "policy:risk-clamp",
		Scope:     ScopeOnce,
		Rationale: "high-risk tool: the advisor may not auto-allow (overridden to deny by the risk-class wall); original=" + decision.By,
	}
}

// resolveHuman applies a HUMAN Session.Resolve decision: it does NOT pass through the
// risk-class clamp (a human IS the authority the wall escalates to), but it DOES honor
// ScopeSession widening so a human "allow for the session" stops the re-ask. It forwards
// the human's verdict verbatim.
//
//nolint:gocritic // Decision is the contract's copyable value record (§2); resolveHuman takes it by value.
func (s *session) resolveHuman(ctx context.Context, requestID, tool string, scopes []string, decision Decision) error {
	if decision.Allow && (decision.Scope == ScopeSession || decision.Remember) {
		s.widenGrant(requestID, tool, scopes)
	}
	return s.forwardDecision(ctx, requestID, decision)
}

// widenGrant adds the request's tool+scopes to the session's in-memory grant set so the
// SAME tool is not re-asked this session (the ScopeSession semantics). It NEVER persists
// to the config-as-code Spec.Grants. A widening for a DIFFERENT tool still escalates.
func (s *session) widenGrant(requestID, tool string, scopes []string) {
	if tool == "" {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if grantCovers(s.sessionGrants, tool, scopes) {
		return
	}
	s.sessionGrants = append(s.sessionGrants, ToolGrant{
		ID:     "session-widen-" + requestID,
		Tool:   tool,
		Scopes: append([]string(nil), scopes...),
	})
}

// toolGranted reports whether a tool+scopes is covered by the CURRENT session grant set
// (Spec.Grants + any ScopeSession widenings). It is the grants-check-first gate the
// resolution chain runs before any prompt/advisor consult.
func (s *session) toolGranted(tool string, scopes []string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return grantCovers(s.sessionGrants, tool, scopes)
}

// permissionTimeout is the human-Resolve window (chat chain) and the advisor reasoning
// bound, defaulting to defaultPermissionTimeout when Spec.PermissionTimeout is unset.
func (s *session) permissionTimeout() time.Duration {
	if s.spec.PermissionTimeout > 0 {
		return s.spec.PermissionTimeout
	}
	return defaultPermissionTimeout
}

// recordRecentDelta appends a bounded recent text/tool delta to the advisor snippet ring
// (kept small and redacted; never a secret). Called from the pump goroutine.
func (s *session) recordRecentDelta(delta string) {
	if delta == "" {
		return
	}
	s.mu.Lock()
	s.recentDeltas = append(s.recentDeltas, delta)
	if len(s.recentDeltas) > recentDeltaWindow {
		s.recentDeltas = s.recentDeltas[len(s.recentDeltas)-recentDeltaWindow:]
	}
	s.mu.Unlock()
}

// armTurn records that an admitted Prompt is awaiting the Running edge that opens its turn,
// so the pump advances the ordinal on that edge and on no other.
func (s *session) armTurn() {
	s.mu.Lock()
	s.promptPending = true
	s.mu.Unlock()
}

// disarmTurn withdraws the arming when the prompt failed to reach the harness.
func (s *session) disarmTurn() {
	s.mu.Lock()
	s.promptPending = false
	s.mu.Unlock()
}

// currentSeq reports the last assigned Seq under the lock.
func (s *session) currentSeq() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.seq
}

// adapterManifest fetches the manifest for the resolved harness (empty manifest when
// the adapter is somehow absent — guarded earlier at route resolution).
func adapterManifest(dependencies Deps, harness string) CapabilityManifest {
	if adapter, ok := dependencies.Adapters[harness]; ok && adapter != nil {
		return adapter.Manifest()
	}
	return CapabilityManifest{}
}
