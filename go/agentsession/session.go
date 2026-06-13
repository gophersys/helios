package agentsession

import (
	"context"
	"sync"

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
	broadcaster *broadcaster

	mu        sync.Mutex // guards state, seq, turn, pending permissions, closed
	state     State
	seq       uint64 // mirror of the last assigned Seq (authoritative is the Transcript)
	turn      int
	pending   map[string]*pendingPermission // RequestID -> awaiting resolution (OnPermission nil path)
	budgetHit bool
	closed    bool

	sendMu   sync.Mutex    // serializes control frames onto the transport (one writer at a time)
	pumpDone chan struct{} // closed when the pump goroutine exits
}

// pendingPermission is an out-of-grant request awaiting an out-of-band Resolve (the
// chat's human round-trip). resolved guards first-decision-wins under multi-client
// races; the pump forwards the winning Decision to the harness.
type pendingPermission struct {
	request  PermissionRequest
	resolved bool
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
		id:          sessionID(spec, route),
		spec:        spec,
		route:       route,
		conn:        conn,
		credential:  cred,
		transcript:  dependencies.Transcript,
		clock:       dependencies.Clock,
		manifest:    adapterManifest(dependencies, route.Harness),
		broadcaster: newBroadcaster(),
		state:       StateInitializing,
		pending:     make(map[string]*pendingPermission),
		pumpDone:    make(chan struct{}),
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
	if err := s.conn.Send(ctx, command); err != nil {
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
	entry.resolved = true
	s.mu.Unlock()

	if err := s.forwardDecision(ctx, requestID, decision); err != nil {
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

	switch command.Kind {
	case CommandPrompt:
		if state != StateReady && state != StateAwaitingInput {
			return errors.Wrap(errors.KindConflict, "agentsession: prompt",
				StateError{From: state, Op: "Prompt"})
		}
	case CommandSteer:
		if s.manifest.Status(CapSteer) == CapAbsent {
			return errors.Wrap(errors.KindInvalid, "agentsession: steer",
				UnsupportedError{Cap: CapSteer})
		}
		if state != StateRunning {
			return errors.Wrap(errors.KindConflict, "agentsession: steer",
				StateError{From: state, Op: "Steer"})
		}
	case CommandAbort:
		if state.IsTerminal() {
			return errors.Wrap(errors.KindConflict, "agentsession: abort",
				StateError{From: state, Op: "Abort"})
		}
	default:
		return errors.Wrap(errors.KindInvalid, "agentsession: control",
			StateError{From: state, Op: "Control"})
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
