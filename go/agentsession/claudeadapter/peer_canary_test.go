package claudeadapter_test

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// The SeededCanary sweep over the PEER path (ADR-0020 dimension (f), rule 21 §f).
//
// A peer body is UNTRUSTED foreign prose that another agent wrote. It is the one payload on
// this stream whose content Eden did not produce and cannot vouch for, so it is exactly the
// place a secret can arrive from outside and then be copied onto a second, unbounded surface.
// The sweep here runs the needle through the REAL binding — the committed capture, rewritten
// so origin.body IS the needle — rather than through the fake's PeerMessageEvent builder,
// because the builder cannot prove anything about what the adapter does with a capture line.

// peerRedactionSpy is a TestingT that records whether AssertNoSecretInEvent flagged a leak, so
// the test can assert the sweep READS the field rather than merely not-failing on it. A sweep
// that reads nothing never fails, which is the worst possible canary.
type peerRedactionSpy struct{ flagged bool }

func (*peerRedactionSpy) Helper()                 {}
func (s *peerRedactionSpy) Errorf(string, ...any) { s.flagged = true }

// TestPeerCanary_InboundBodyStaysInThePeerPayload is test 10, adapter half. The needle is
// planted in origin.body of the real captured result line. Two things must hold:
//
//	(1) it lands in the peer payload VERBATIM — the body is the message, and a digest there
//	    would break the delivery the library performs from it; and
//	(2) it lands NOWHERE ELSE. If the same result line also surfaced as a verbatim Extension,
//	    or folded the body into the turn's ResultText, a foreign secret would ride a second
//	    surface that no redaction policy is watching.
//
// FALSIFICATION: preserving the origin-bearing result line as an Extension "for forward
// compatibility" (the reflex this whole file exists to catch) republishes the untrusted body
// unbounded, and the sweep below fires on the Extension bytes.
func TestPeerCanary_InboundBodyStaysInThePeerPayload(t *testing.T) {
	t.Parallel()
	lines := peerFixtureLines(t, fixtureReceiveOrigin)
	lines[len(lines)-1] = reseedOriginBody(t, lines[len(lines)-1], seededCanary)
	events := normalizePeerStream(t, lines)

	peers := eventsOfKind(events, agentsession.EventPeerMessage)
	if len(peers) != 1 {
		t.Fatalf("the canary-seeded origin line must yield exactly 1 EventPeerMessage, got %d; kinds: %s",
			len(peers), renderKinds(events))
	}
	if peers[0].Peer == nil || peers[0].Peer.Body != seededCanary {
		t.Errorf("Peer.Body must carry origin.body verbatim; got %#v", peers[0].Peer)
	}

	// (1) the sweep READS the peer body of the REAL binding's output — non-vacuity.
	spy := &peerRedactionSpy{}
	agentsessiontest.AssertNoSecretInEvent(spy, peers[0], seededCanary)
	if !spy.flagged {
		t.Errorf("AssertNoSecretInEvent did NOT reach the real adapter's EventPeerMessage body; a secret arriving from a peer would surface undetected")
	}

	// (2) no OTHER event this stream produced may carry it.
	for i := range events {
		if events[i].Kind == agentsession.EventPeerMessage {
			continue
		}
		other := &peerRedactionSpy{}
		agentsessiontest.AssertNoSecretInEvent(other, events[i], seededCanary)
		if other.flagged {
			t.Errorf("the untrusted peer body also surfaced on a %s event — one arrival, one payload, one surface", events[i].Kind)
		}
	}
}

// TestPeerCanary_SendReceiptNeverCarriesTheCredential is test 10, sender half. The receipt path
// reads the model's own tool arguments; the credential the session was spawned with must have
// no path onto it. The needle is planted as the SendMessage body a compromised model chose to
// send, and the assertion is that the EventPeerSent stays inside its own bounded payload — the
// same one-surface rule, from the outbound side.
func TestPeerCanary_SendReceiptNeverCarriesTheCredential(t *testing.T) {
	t.Parallel()
	lines := peerFixtureLines(t, fixtureSendReceipt)
	lines[0] = reseedSendBody(t, lines[0], seededCanary)
	events := normalizePeerStream(t, lines)

	sent := eventsOfKind(events, agentsession.EventPeerSent)
	if len(sent) != 1 {
		t.Fatalf("the canary-seeded send must still yield exactly 1 EventPeerSent, got %d; kinds: %s",
			len(sent), renderKinds(events))
	}
	spy := &peerRedactionSpy{}
	agentsessiontest.AssertNoSecretInEvent(spy, sent[0], seededCanary)
	if !spy.flagged {
		t.Errorf("AssertNoSecretInEvent did NOT reach the real adapter's EventPeerSent payload; a secret a model sends to a peer would surface undetected")
	}
}

// reseedOriginBody rewrites origin.body of a captured result line to the needle, leaving every
// other byte of the capture (msg_id, name, verifiedPeerPid, the usage block) untouched.
func reseedOriginBody(t *testing.T, line []byte, needle string) []byte {
	t.Helper()
	var envelope map[string]json.RawMessage
	if err := json.Unmarshal(line, &envelope); err != nil {
		t.Fatalf("decode captured result line: %v", err)
	}
	raw, ok := envelope["origin"]
	if !ok {
		t.Fatalf("the fixture's last line carries no origin: %s", truncateForFailure(line))
	}
	var origin map[string]any
	if err := json.Unmarshal(raw, &origin); err != nil {
		t.Fatalf("decode origin: %v", err)
	}
	origin["body"] = needle
	reseeded, err := json.Marshal(origin)
	if err != nil {
		t.Fatalf("re-encode origin: %v", err)
	}
	envelope["origin"] = reseeded
	out, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("re-encode result line: %v", err)
	}
	return out
}

// reseedSendBody rewrites the SendMessage tool_use input body of a captured assistant line to
// the needle, leaving the tool_use id (the correlation the receipt is matched on) untouched.
func reseedSendBody(t *testing.T, line []byte, needle string) []byte {
	t.Helper()
	var envelope map[string]json.RawMessage
	if err := json.Unmarshal(line, &envelope); err != nil {
		t.Fatalf("decode captured assistant line: %v", err)
	}
	var message map[string]json.RawMessage
	if err := json.Unmarshal(envelope["message"], &message); err != nil {
		t.Fatalf("decode assistant message: %v", err)
	}
	var content []map[string]any
	if err := json.Unmarshal(message["content"], &content); err != nil {
		t.Fatalf("decode assistant content: %v", err)
	}
	seeded := false
	for i := range content {
		name, _ := content[i]["name"].(string)
		if !strings.EqualFold(name, "SendMessage") {
			continue
		}
		input, ok := content[i]["input"].(map[string]any)
		if !ok {
			t.Fatalf("the SendMessage tool_use carried no input object")
		}
		input["message"] = needle
		input["content"] = needle
		seeded = true
	}
	if !seeded {
		t.Fatalf("the fixture's first line carries no SendMessage tool_use: %s", truncateForFailure(line))
	}
	encoded, err := json.Marshal(content)
	if err != nil {
		t.Fatalf("re-encode assistant content: %v", err)
	}
	message["content"] = encoded
	encodedMessage, err := json.Marshal(message)
	if err != nil {
		t.Fatalf("re-encode assistant message: %v", err)
	}
	envelope["message"] = encodedMessage
	out, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("re-encode assistant line: %v", err)
	}
	return out
}
