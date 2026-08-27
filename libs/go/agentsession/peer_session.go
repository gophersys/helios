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

// peerRecoveredSendBuffer bounds the hand-off queue that carries a full-mesh recovered send from
// the pump to the DEDICATED deliver goroutine. Recovered sends are rare (only a cross-harness
// native send the harness's own plane refused), so the buffer is small; the pump enqueues
// NON-BLOCKING onto it (it owns Seq and may never block), and the deliver goroutine does the
// actual bus Send.
const peerRecoveredSendBuffer = 8

// peerRecoveredSendDetail marks an EventPeerSent as a ROUTING INSTRUCTION rather than a receipt:
// the harness's own plane refused the send and the adapter recovered {to, body} from the model's
// tool call. It is the contract between the two halves and is spelled identically in the adapter
// that produces it (claudeadapter/peer.go). It cannot be shared as one constant without adding an
// exported symbol to the frozen surface, so each side names it and the tests pin them equal.
//
// It must differ from the adapters' "send-receipt-unparsed", which marks a send the native plane
// DID accept and which is therefore never re-routed.
const peerRecoveredSendDetail = "native-send-unreachable"

// peerRecoveryDroppedDetail REPLACES peerRecoveredSendDetail on the published EventPeerSent when
// the recovery could not even be handed to the deliver goroutine. It is LIBRARY-owned: no adapter
// produces it, because only the library knows whether it took the routing instruction.
//
// It exists because the two outcomes were byte-identical on the stream. The recovered EventPeerSent
// is published VERBATIM, so a consumer reading Detail=="native-send-unreachable" is entitled to
// conclude "the library is routing this over the bus" — and a dropped hand-off published exactly
// that while routing nothing. A silently held message is the one failure this whole plane exists
// to make impossible, so the drop gets its own literal and the consumer can see it.
const peerRecoveryDroppedDetail = "native-send-unrecovered"

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
		case message := <-s.recoveredSends:
			// The full-mesh recovery Send belongs HERE, not on the pump: the plane's Send blocks
			// (a socket handshake, an inbox push), and this is the goroutine allowed to block.
			s.routeRecoveredOnBus(message)
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
// routes it over the bus so the peer really receives it. It runs ON THE PUMP, so it does the
// discrimination and the copy here but hands the actual bus Send to the deliver goroutine: the
// pump owns Seq and must NEVER block, and the plane's Send does (a socket handshake, an inbox
// push). It returns the event to PUBLISH: verbatim when the recovery was taken (the native send
// failed visibly to the model — the accepted full-mesh caveat — and the recovery delivers
// underneath it), re-stamped when it was not.
//
// The discrimination is load-bearing in BOTH directions. An already-accepted send must not be
// re-routed (every native message would be delivered twice), and a "send-receipt-unparsed" one
// is a send the native plane DID accept whose id was merely unreadable — also never re-routed.
//
//nolint:gocritic // Event is the contract's immutable copyable record; the pump reads it by value.
func (s *session) routeRecoveredSend(raw Event) Event {
	if !isRecoveredSend(raw.Peer) {
		return raw
	}
	// From is the SENDING SESSION's own name, never the model's claim in the failed tool_use.
	if s.queueRecoveredSend(PeerMessage{
		From:    s.spec.Name,
		To:      raw.Peer.To,
		ReplyTo: raw.Peer.ReplyTo,
		Body:    raw.Peer.Body,
	}) {
		return raw
	}
	// The hand-off was refused, so NOTHING will route this message. Clone-on-modify (the pump's
	// rule) and re-stamp, so the one event this send produces says what actually happened.
	dropped := *raw.Peer
	dropped.Detail = peerRecoveryDroppedDetail
	raw.Peer = &dropped
	return raw
}

// queueRecoveredSend hands a recovered send to the deliver goroutine WITHOUT blocking the pump,
// reporting whether the deliver goroutine took it. A full queue does NOT stall Seq assignment —
// the pump may never block — so the message is not routed, and the caller re-stamps the published
// event to say so. Recovered sends are rare, so the bounded buffer is not reached in practice;
// what matters is that reaching it is VISIBLE rather than silent.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record; the queue takes it by value.
func (s *session) queueRecoveredSend(message PeerMessage) bool {
	select {
	case s.recoveredSends <- message:
		return true
	default:
		return false
	}
}

// routeRecoveredOnBus performs the recovered send on the DEDICATED deliver goroutine, where a
// blocking plane Send is allowed. A bus failure is folded into the stream that already reports
// the native failure, rather than a swallowed error, so nothing is silently lost.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record; the Send takes it by value.
func (s *session) routeRecoveredOnBus(message PeerMessage) {
	//nolint:errcheck // a bus failure leaves the send visibly unaccepted on the stream (the model saw the native failure).
	_, _ = s.peerLink.Send(context.Background(), message)
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
