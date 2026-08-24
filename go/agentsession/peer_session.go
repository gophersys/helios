package agentsession

import (
	"context"
	"regexp"

	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/errors"
)

// peerNameRE is the addressability grammar (§4.2): a Spec.Name is safe as a CLI argument, a
// unix-socket filename, AND a roster entry (a space or '[' would break the "name [ref]" form
// the harness roster uses). Open validates the caller-assigned name against it, TOTALLY.
var peerNameRE = regexp.MustCompile(`^[a-z][a-z0-9-]{1,61}[a-z0-9]$`)

// peerDedupeRing bounds the per-session ring of recently-seen inbound MsgIDs. A second arrival
// of an id already in the ring is dropped so EventPeerMessage is emitted EXACTLY ONCE per
// message even when both the bus and a native plane could deliver it (C5).
const peerDedupeRing = 256

// peerRecoveredSendDetail marks an EventPeerSent as a ROUTING INSTRUCTION rather than a receipt:
// the harness's own plane refused the send and the adapter recovered {to, body} from the model's
// tool call. It is the contract between the two halves and is spelled identically in the adapter
// that produces it (claudeadapter/peer.go). It cannot be shared as one constant without adding an
// exported symbol to the frozen surface, so each side names it and the tests pin them equal.
//
// It must differ from the adapters' "send-receipt-unparsed", which marks a send the native plane
// DID accept and which is therefore never re-routed.
const peerRecoveredSendDetail = "native-send-unreachable"

// validatePeerSpec enforces the Open-time peer contract. Deps.Peer set with an empty Name is a
// session that believes it is reachable and is not — the silent failure this design removes; a
// non-empty Name that violates the grammar is a ConfigError, never a mangled argv or socket
// filename. It is pure, so Open rejects before any I/O.
//
//nolint:gocritic // Spec is the frozen copyable session input (the configuration pattern).
func validatePeerSpec(spec Spec, hasPlane bool) error {
	if hasPlane && spec.Name == "" {
		return errors.Wrap(errors.KindInvalid, "agentsession: open",
			ConfigError{Field: "Name", Message: "Deps.Peer is set but Spec.Name is empty (no silent non-membership)"})
	}
	if spec.Name != "" && !peerNameRE.MatchString(spec.Name) {
		return errors.Wrap(errors.KindInvalid, "agentsession: open",
			ConfigError{Field: "Name", Message: "Spec.Name must match ^[a-z][a-z0-9-]{1,61}[a-z0-9]$"})
	}
	return nil
}

// joinPeer registers the session on the injected plane, returning its PeerLink. It returns
// nil,nil when there is no plane (or no name), which is the no-regression path: a plane-less
// session emits no peer event. A refused Join (duplicate name, unknown parent, cycle, failed
// handshake) is a wrapped, typed error surfaced at Open.
//
//nolint:gocritic,ireturn // Spec is the frozen copyable session input; joinPeer returns the injected PeerLink port.
func (p *Pool) joinPeer(ctx context.Context, spec Spec) (PeerLink, error) {
	if p.dependencies.Peer == nil || spec.Name == "" {
		return nil, nil //nolint:nilnil // no plane == no link and no error; the caller treats nil as "no peer path".
	}
	link, err := p.dependencies.Peer.Join(ctx, spec.Name, spec.Parent)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "agentsession: join peer plane", err)
	}
	return link, nil
}

// deliverLoop is the DEDICATED deliver goroutine (C2): it drains the plane-routed inbound queue
// and delivers each message to the harness. It is NEVER the pump goroutine — the pump owns Seq
// and must never block writing to the harness (the adapter's events channel is unbuffered and
// its scanner blocks on send, so a pump blocked in a stdin write deadlocks the child's stdout
// pipe permanently). It exits on Close.
func (s *session) deliverLoop() {
	defer close(s.deliverDone)
	inbound := s.peerLink.Inbound()
	for {
		select {
		case <-s.deliverStop:
			return
		case message, ok := <-inbound:
			if !ok {
				return
			}
			s.deliverToHarness(message)
		}
	}
}

// deliverToHarness tunnels one inbound peer message into the harness as a control frame. The
// verb is chosen from LegalControls (C4) — Prompt when Ready/AwaitingInput, Steer when Running
// — never an unguarded write, because an unsolicited peer frame has no precondition that the
// harness is waiting. A body that cannot be encoded (it carries the envelope terminator) is
// rejected at this boundary, never forwarded.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record.
func (s *session) deliverToHarness(message PeerMessage) {
	frame, err := controlframe.EncodePeer(message.From, message.To, message.MsgID, message.ReplyTo, message.Body, message.Verified)
	if err != nil {
		return
	}
	verb, ok := s.peerDeliveryVerb()
	if !ok {
		return
	}
	s.sendMu.Lock()
	//nolint:errcheck // best-effort delivery; a transport failure is folded into the eventual terminal at channel close.
	_ = s.conn.Send(context.Background(), Command{Kind: verb, Text: frame})
	s.sendMu.Unlock()
}

// peerDeliveryVerb picks the state-legal turn-taking verb to deliver an inbound peer message,
// sourced from LegalControls so it is never hard-coded. ok=false in AwaitingPermission or a
// terminal state, where a delivery is not currently legal.
func (s *session) peerDeliveryVerb() (CommandKind, bool) {
	switch s.priorState() {
	case StateReady, StateAwaitingInput:
		return CommandPrompt, true
	case StateRunning:
		return CommandSteer, true
	default:
		return CommandPrompt, false
	}
}

// deliverInboundPeer emits an inbound EventPeerMessage exactly once and corroborates delivery.
// It suppresses the event entirely when there is no plane (no regression), drops a duplicate
// MsgID via the bounded dedupe ring (C5), and calls PeerLink.Received AFTER the emit so the
// receipt reaches the root's reconciler.
//
//nolint:gocritic // Event is the contract's immutable copyable record; the pump processes it by value.
func (s *session) deliverInboundPeer(raw Event) []Event {
	if s.peerLink == nil {
		return nil
	}
	msgID := ""
	if raw.Peer != nil {
		msgID = raw.Peer.MsgID
	}
	if s.peerAlreadySeen(msgID) {
		return nil
	}
	published := s.emit(raw)
	s.peerLink.Received(msgID)
	return []Event{published}
}

// routeRecoveredSend carries the FULL-MESH recovery: a send the harness's own plane could not
// make (claude cannot reach a non-claude peer) is surfaced by the adapter with the payload
// recovered from the model's tool call, and the LIBRARY — the only side holding a PeerLink —
// routes it over the bus so the peer really receives it. It returns the event to publish,
// re-stamped with what the plane did: the routing outcome IS how the error is reported, so a
// send nothing accepted stays visibly unaccepted on the stream.
//
// The discrimination is load-bearing in BOTH directions. An already-accepted send must not be
// re-routed (every native message would be delivered twice), and a "send-receipt-unparsed" one
// is a send the native plane DID accept whose id was merely unreadable — also never re-routed.
//
//nolint:gocritic // Event is the contract's immutable copyable record; the pump processes it by value and clones-on-modify.
func (s *session) routeRecoveredSend(raw Event) Event {
	if !isRecoveredSend(raw.Peer) {
		return raw
	}
	recovered := *raw.Peer
	// From is the SENDING SESSION's own name, never the model's claim.
	msgID, err := s.peerLink.Send(context.Background(), PeerMessage{
		From:    s.spec.Name,
		To:      recovered.To,
		ReplyTo: recovered.ReplyTo,
		Body:    recovered.Body,
	})
	if err != nil {
		// Unreachable natively AND on the bus: the event already says nothing accepted it, so
		// the fact is on the stream rather than in a swallowed error.
		return raw
	}
	recovered.MsgID = msgID
	recovered.Accepted = true
	raw.Peer = &recovered
	return raw
}

// isRecoveredSend reports whether an observed send is the adapter's recovery instruction: not
// accepted by the harness's own plane, carrying the recovery discriminator, and carrying both
// halves of a routable message.
func isRecoveredSend(message *PeerMessage) bool {
	return message != nil && !message.Accepted && message.Detail == peerRecoveredSendDetail &&
		message.To != "" && message.Body != ""
}

// peerAlreadySeen reports whether msgID is already in the bounded dedupe ring, recording it
// when new. An empty id is never deduped (it cannot be keyed) and is not recorded. Held under
// s.mu; the pump is the only caller, but the guard keeps the ring consistent with any future
// reader.
func (s *session) peerAlreadySeen(msgID string) bool {
	if msgID == "" {
		return false
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.peerSeen[msgID]; ok {
		return true
	}
	if s.peerSeen == nil {
		s.peerSeen = make(map[string]struct{}, peerDedupeRing)
		s.peerRing = make([]string, 0, peerDedupeRing)
	}
	if len(s.peerRing) == peerDedupeRing {
		evicted := s.peerRing[s.peerRingNext]
		delete(s.peerSeen, evicted)
		s.peerRing[s.peerRingNext] = msgID
		s.peerRingNext = (s.peerRingNext + 1) % peerDedupeRing
	} else {
		s.peerRing = append(s.peerRing, msgID)
	}
	s.peerSeen[msgID] = struct{}{}
	return false
}
