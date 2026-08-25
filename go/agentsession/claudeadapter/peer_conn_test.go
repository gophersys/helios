package claudeadapter_test

import (
	"context"
	"encoding/json"
	"io"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
)

// The DELIVERY side of the claude peer binding, over an in-memory transport.
//
// It is the exact mirror of ompadapter/peer_test.go: the two adapters owe the SAME contract, so
// the two tests are spelled the same way on purpose. The library's deliver goroutine hands the
// adapter an inbound peer message as the internal `eden:peer:` control frame; the adapter must
// UNWRAP it into the model-facing <eden-peer-message> envelope on the wire and publish EXACTLY
// ONE EventPeerMessage.
//
// This file needs an in-memory conn — the same conn Spawn wraps around the child's pipes,
// without the child — because the delivery path runs through Send and the scanner together and
// cannot be reached from the pure normalizer. ompadapter already has that seam
// (RPCConnForTest); claudeadapter does not, so PipeConnForTest is DECLARED in export_test.go
// and this test is a COMPILE-DEP red until the constructor behind it exists.

// The identifiers this delivery is asserted on (the same names the omp mirror uses).
const (
	claudePeerFrom  = "impl-a"
	claudePeerTo    = "review-c"
	claudePeerMsgID = "msg-7f3c"
	claudePeerBody  = "please review the pump change"
)

// claudePeerDeadline bounds every wait. A wait that runs out is a FAILURE naming what never
// arrived, never a quiet return.
const claudePeerDeadline = 2 * time.Second

// TestPeerDelivery_ClaudeUnwrapsControlFrameToEnvelope is test 6, claude half.
//
//	WIRE  — the stdin user turn must carry the <eden-peer-message> envelope. The internal
//	        `eden:peer:` prefix and its 0x1f separators must NEVER reach the model: a model that
//	        reads them learns Eden's private control grammar and can forge a delivery by typing
//	        it, which is exactly why the two forms are different.
//	EVENT — exactly one EventPeerMessage is published for the delivery. The library's dedupe
//	        ring bounds a second arrival; the adapter must not manufacture one.
//
// FALSIFICATION: writing command.Text through unchanged (the pre-binding behavior) puts the raw frame
// in front of the model and publishes no peer event at all.
func TestPeerDelivery_ClaudeUnwrapsControlFrameToEnvelope(t *testing.T) {
	t.Parallel()
	harness := newClaudePeerHarness(t, agentsession.Spec{Name: claudePeerTo})

	frame, err := controlframe.EncodePeer(claudePeerFrom, claudePeerTo, claudePeerMsgID, "", claudePeerBody, true)
	if err != nil {
		t.Fatalf("EncodePeer: %v", err)
	}
	if err := harness.conn.Send(context.Background(),
		agentsession.Command{Kind: agentsession.CommandPrompt, Text: frame}); err != nil {
		t.Fatalf("Send peer frame: %v", err)
	}

	wire := harness.waitUserTurn(t, claudePeerBody)
	assertClaudePeerEnvelope(t, wire)

	event := harness.waitEvent(t, "the inbound EventPeerMessage", func(e *agentsession.Event) bool {
		return e.Kind == agentsession.EventPeerMessage
	})
	if event.Peer == nil {
		t.Fatalf("EventPeerMessage carried a nil Peer payload")
	}
	if event.Peer.MsgID != claudePeerMsgID {
		t.Errorf("Peer.MsgID = %q, want %q", event.Peer.MsgID, claudePeerMsgID)
	}
	if event.Peer.From != claudePeerFrom {
		t.Errorf("Peer.From = %q, want %q", event.Peer.From, claudePeerFrom)
	}
	if event.Peer.Body != claudePeerBody {
		t.Errorf("Peer.Body = %q, want %q verbatim", event.Peer.Body, claudePeerBody)
	}
	if !event.Peer.Verified {
		t.Errorf("Peer.Verified = false; the frame carried verified=true and the adapter may not downgrade it")
	}
	if count := harness.countKind(agentsession.EventPeerMessage); count != 1 {
		t.Errorf("one delivered frame published %d EventPeerMessage; the adapter must emit exactly one", count)
	}
}

// TestPeerEnvelope_CarriesTheTrustFlagBothWays pins the PURE renderer behind the delivery: the
// same envelope contract, asserted without a transport, plus the half the transport test cannot
// reach — an UNVERIFIED sender must render as visibly unverified. The trust flag is the model's
// only signal that a "from" is a kernel fact rather than a claim, so an envelope that omits it
// when false silently promotes every unverified sender.
//
// FALSIFICATION: rendering the attribute only when true. A model reading two envelopes could not
// then tell "unverified" from "an older Eden that did not stamp it".
func TestPeerEnvelope_CarriesTheTrustFlagBothWays(t *testing.T) {
	t.Parallel()
	verified := claudeadapter.PeerEnvelopeForTest(claudePeerFrom, claudePeerMsgID, "", claudePeerBody, true)
	assertClaudePeerEnvelope(t, verified)
	if !strings.Contains(verified, `verified="true"`) {
		t.Errorf("a kernel-verified sender must render verified=\"true\"; got %q", verified)
	}

	unverified := claudeadapter.PeerEnvelopeForTest(claudePeerFrom, claudePeerMsgID, "", claudePeerBody, false)
	if !strings.Contains(unverified, `verified="false"`) {
		t.Errorf("an UNVERIFIED sender must render verified=\"false\" explicitly, never by omission; got %q", unverified)
	}
}

// assertClaudePeerEnvelope pins what the MODEL is allowed to see — identical to the omp mirror.
func assertClaudePeerEnvelope(t *testing.T, wire string) {
	t.Helper()
	if strings.Contains(wire, controlframe.PeerPrefix) {
		t.Errorf("the internal %q frame reached the model verbatim: %q", controlframe.PeerPrefix, wire)
	}
	if strings.ContainsRune(wire, '\x1f') {
		t.Errorf("the internal 0x1f field separator reached the model: %q", wire)
	}
	if !strings.HasPrefix(wire, "<eden-peer-message") {
		t.Errorf("the delivery must open the <eden-peer-message> envelope; got %q", wire)
	}
	if !strings.HasSuffix(wire, "</eden-peer-message>") {
		t.Errorf("the delivery must close the </eden-peer-message> envelope; got %q", wire)
	}
	for _, want := range []string{claudePeerFrom, claudePeerMsgID, claudePeerBody, "verified"} {
		if !strings.Contains(wire, want) {
			t.Errorf("the envelope must carry %q so the model can tell WHO sent it, WHICH message it is, and whether the sender is kernel-verified; got %q",
				want, wire)
		}
	}
}

// ── the in-memory claude transport ────────────────────────────────────────────────────────────.

// claudePeerHarness drives one conn over an in-memory transport: what the test writes to stdout
// is what the real `claude` would print, and every line the conn writes to stdin is recorded.
// Every published event is drained continuously, exactly as the library's pump does, so the
// conn's unbuffered event channel is never blocked on a reader that is not there.
type claudePeerHarness struct {
	conn    agentsession.HarnessConn
	stdout  *io.PipeWriter
	stdin   *claudeRecordingStdin
	mu      sync.Mutex
	events  []agentsession.Event
	drained chan struct{}
}

// newClaudePeerHarness builds the conn over in-memory pipes and reaps it at cleanup, asserting
// the event channel closes — a conn whose scanner outlives Close is a leak the package's goleak
// TestMain would report against whichever test ran last.
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
func newClaudePeerHarness(t *testing.T, spec agentsession.Spec) *claudePeerHarness {
	t.Helper()
	reader, writer := io.Pipe()
	harness := &claudePeerHarness{stdout: writer, stdin: &claudeRecordingStdin{}, drained: make(chan struct{})}
	harness.conn = claudeadapter.PipeConnForTest(spec, reader, harness.stdin)
	go harness.drain()
	t.Cleanup(func() {
		_ = harness.conn.Close(context.Background()) //nolint:errcheck // best-effort reap; Close is idempotent and this second call also exercises that.
		_ = writer.Close()                           //nolint:errcheck // releases any test-side write still blocked on the conn's reader.
		_ = reader.Close()                           //nolint:errcheck // ends the conn's scanner if Close did not.
		select {
		case <-harness.drained:
		case <-time.After(claudePeerDeadline):
			t.Errorf("the conn's event channel was still open %s after Close: the scanner outlives the session", claudePeerDeadline)
		}
	})
	return harness
}

// drain consumes the conn's event channel for the whole test.
func (h *claudePeerHarness) drain() {
	defer close(h.drained)
	for event := range h.conn.Events() {
		h.mu.Lock()
		h.events = append(h.events, event)
		h.mu.Unlock()
	}
}

// waitUserTurn returns the content of the first stream-json user turn the conn wrote on stdin
// that carries want, or FAILS naming everything it did write.
func (h *claudePeerHarness) waitUserTurn(t *testing.T, want string) string {
	t.Helper()
	deadline := time.Now().Add(claudePeerDeadline)
	for {
		for _, line := range h.stdin.lines() {
			var turn struct {
				Type    string `json:"type"`
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			}
			if json.Unmarshal(line, &turn) != nil || turn.Type != "user" {
				continue
			}
			if strings.Contains(turn.Message.Content, want) {
				return turn.Message.Content
			}
		}
		if time.Now().After(deadline) {
			t.Fatalf("no stdin user turn carrying %q within %s; the conn wrote: %s", want, claudePeerDeadline, h.stdin.render())
		}
		time.Sleep(5 * time.Millisecond)
	}
}

// waitEvent returns the first published event that matches, or FAILS naming what never arrived.
func (h *claudePeerHarness) waitEvent(t *testing.T, what string, match func(*agentsession.Event) bool) agentsession.Event {
	t.Helper()
	deadline := time.Now().Add(claudePeerDeadline)
	for {
		h.mu.Lock()
		for i := range h.events {
			if match(&h.events[i]) {
				found := h.events[i]
				h.mu.Unlock()
				return found
			}
		}
		kinds := renderKinds(h.events)
		h.mu.Unlock()
		if time.Now().After(deadline) {
			t.Fatalf("no event matching %s within %s; the conn published: %s", what, claudePeerDeadline, kinds)
		}
		time.Sleep(5 * time.Millisecond)
	}
}

// countKind counts every published event of one kind.
func (h *claudePeerHarness) countKind(kind agentsession.EventKind) int {
	h.mu.Lock()
	defer h.mu.Unlock()
	count := 0
	for i := range h.events {
		if h.events[i].Kind == kind {
			count++
		}
	}
	return count
}

// claudeRecordingStdin is the child's stdin as the test sees it: every whole line the conn
// writes is kept, and a write never blocks the conn. Close is the EOF the conn owes the child.
type claudeRecordingStdin struct {
	mu      sync.Mutex
	partial []byte
	written [][]byte
	closed  bool
}

// Write records whole newline-terminated lines.
func (s *claudeRecordingStdin) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.partial = append(s.partial, p...)
	for {
		at := strings.IndexByte(string(s.partial), '\n')
		if at < 0 {
			break
		}
		line := make([]byte, at)
		copy(line, s.partial[:at])
		s.written = append(s.written, line)
		s.partial = s.partial[at+1:]
	}
	return len(p), nil
}

// Close marks the EOF the conn hands the child.
func (s *claudeRecordingStdin) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.closed = true
	return nil
}

// lines returns a copy of every whole line written so far.
func (s *claudeRecordingStdin) lines() [][]byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([][]byte, len(s.written))
	copy(out, s.written)
	return out
}

// render lists what was written for a failure message.
func (s *claudeRecordingStdin) render() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.written) == 0 {
		return "(nothing)"
	}
	out := make([]string, 0, len(s.written))
	for _, line := range s.written {
		out = append(out, truncateForFailure(line))
	}
	return strings.Join(out, " | ")
}
