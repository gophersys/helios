//go:build integration

package peerplane

import (
	"context"
	"net"
	"path/filepath"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	liberrors "github.com/gophersys/libs/go/errors"
)

// The F3 spoof REGRESSION NET (design §5.2 SO_PEERCRED admission). serveSend NEVER trusts a
// frame's self-asserted identity: From is BOUND to the connection's joined name and Verified is
// STAMPED from the kernel-verified connection. This drives the REAL serveSend path with a RAW
// attacker connection over a REAL unix socket (SO_PEERCRED, Linux) — the credential-free
// real-substrate proof that a same-uid process cannot speak as another peer, send before joining,
// or forge the verified flag. Reverting serveSend to a pass-through `o.route(*f.Message)` makes
// all three sub-cases FAIL (proven in the scratch bite), so this pins a fix that would otherwise
// silently regress.

// TestIntegration_ServeSendRejectsSpoofAndBindsIdentity pins the three serveSend guards.
func TestIntegration_ServeSendRejectsSpoofAndBindsIdentity(t *testing.T) {
	t.Parallel()
	socket := filepath.Join(t.TempDir(), "mesh.sock")
	ctx := context.Background()

	orchestrator, err := New(Config{SocketPath: socket, DeliveryDeadline: time.Second}, Deps{Clock: integrationClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	listenCtx, stopListen := context.WithCancel(ctx)
	t.Cleanup(stopListen)
	go func() { _ = orchestrator.Listen(listenCtx) }() //nolint:errcheck // Listen returns on ctx cancel.
	waitForSocket(t, socket)

	// The observer is the delivery target, joined IN-PROCESS so the test can read its Inbound and
	// prove a rejected send delivers NOTHING (loud, not silent).
	observer, err := orchestrator.Join(ctx, "observer", "")
	if err != nil {
		t.Fatalf("Join observer: %v", err)
	}

	// 2: send-before-Join is a LOUD errNotJoined/KindPermission, and nothing is delivered.
	t.Run("SendBeforeJoinIsRejected", func(t *testing.T) {
		conn := dialRaw(t, socket)
		ack := attackerRequest(t, conn, &frame{Type: frameSend, Message: &agentsession.PeerMessage{To: "observer", Body: "no-join"}})
		assertPermissionAck(t, ack, errNotJoined.Error())
		expectNoInbound(t, observer, 500*time.Millisecond)
	})

	// 1: a From naming another peer is a LOUD errFromMismatch/KindPermission, and nothing is
	// delivered — the spoof is refused, never routed under the forged identity.
	t.Run("ForgedFromIsRejected", func(t *testing.T) {
		conn := dialRaw(t, socket)
		if ack := attackerRequest(t, conn, &frame{Type: frameJoin, Name: "attacker-a"}); !ack.OK {
			t.Fatalf("attacker join refused: %+v", ack)
		}
		ack := attackerRequest(t, conn, &frame{Type: frameSend, Message: &agentsession.PeerMessage{From: "observer", To: "observer", Body: "spoof"}})
		assertPermissionAck(t, ack, errFromMismatch.Error())
		expectNoInbound(t, observer, 500*time.Millisecond)
	})

	// 3: From is BOUND to the joined name (client omits it) and Verified is STAMPED from the
	// verified connection (true), overriding the client's Verified=false claim.
	t.Run("FromBoundAndVerifiedStampedFromConnection", func(t *testing.T) {
		conn := dialRaw(t, socket)
		if ack := attackerRequest(t, conn, &frame{Type: frameJoin, Name: "member-b"}); !ack.OK {
			t.Fatalf("member join refused: %+v", ack)
		}
		ack := attackerRequest(t, conn, &frame{Type: frameSend, Message: &agentsession.PeerMessage{To: "observer", Body: "legit", Verified: false}})
		if ack.ErrMsg != "" {
			t.Fatalf("a legitimate send was rejected: %+v", ack)
		}
		select {
		case got := <-observer.Inbound():
			if got.From != "member-b" {
				t.Errorf("delivered From = %q, want member-b (bound to the connection identity, not the client claim)", got.From)
			}
			if !got.Verified {
				t.Errorf("delivered Verified = false, want true (stamped from the SO_PEERCRED-verified connection, overriding the client's false claim)")
			}
			observer.Received(got.MsgID)
		case <-time.After(3 * time.Second):
			t.Fatal("observer never received the legitimate send")
		}
	})
}

// dialRaw opens a raw attacker connection to the root's socket, reaped on Cleanup.
func dialRaw(t *testing.T, socket string) net.Conn {
	t.Helper()
	conn, err := net.Dial("unix", socket)
	if err != nil {
		t.Fatalf("dial socket: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() }) //nolint:errcheck // best-effort reap.
	return conn
}

// attackerRequest writes a raw frame and reads the root's response, bounded by a read deadline so
// a missing response fails fast rather than hanging.
//
//nolint:gocritic // frame is the internal wire union; the helper returns it by value.
func attackerRequest(t *testing.T, conn net.Conn, f *frame) frame {
	t.Helper()
	if err := writeFrame(conn, f); err != nil {
		t.Fatalf("write %s frame: %v", f.Type, err)
	}
	_ = conn.SetReadDeadline(time.Now().Add(5 * time.Second)) //nolint:errcheck // best-effort deadline.
	resp, err := readFrame(conn)
	if err != nil {
		t.Fatalf("read response to %s: %v", f.Type, err)
	}
	return resp
}

// assertPermissionAck asserts a send-ack carries the expected KindPermission error message.
//
//nolint:gocritic // frame is the internal wire union; the helper reads a copy.
func assertPermissionAck(t *testing.T, ack frame, wantMsg string) {
	t.Helper()
	if ack.Type != frameSendAck {
		t.Fatalf("response type = %q, want %q", ack.Type, frameSendAck)
	}
	if ack.ErrMsg != wantMsg {
		t.Errorf("send-ack ErrMsg = %q, want %q", ack.ErrMsg, wantMsg)
	}
	if ack.ErrKind != uint8(liberrors.KindPermission) {
		t.Errorf("send-ack ErrKind = %d, want %d (KindPermission)", ack.ErrKind, uint8(liberrors.KindPermission))
	}
}

// expectNoInbound asserts the link receives NOTHING within timeout — a rejected send is loud
// (a typed ack), never a silent delivery.
func expectNoInbound(t *testing.T, link agentsession.PeerLink, timeout time.Duration) {
	t.Helper()
	select {
	case got := <-link.Inbound():
		t.Fatalf("a rejected send was delivered anyway: %+v", got)
	case <-time.After(timeout):
	}
}
