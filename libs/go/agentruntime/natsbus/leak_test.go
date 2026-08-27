package natsbus_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the natsbus package on ANY goroutine left running after the suite. The
// adapter itself spawns NO background goroutine (publish is synchronous; the control subscription is
// owned by the sidecar's Run, reaped on ctx cancel). The integration arm boots a REAL embedded
// nats-server + dials a REAL *nats.Conn whose background roots (the server's accept/route loops, the
// client's flusher/ping/reconnect goroutines, and net/http transport reapers) are well-known benign
// roots listed explicitly — a regression that leaked an ADAPTER goroutine would still surface.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that touches the
		// runtime poller.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		// The nats.go client's background goroutines on a live *nats.Conn (flusher, ping/pong, the
		// reconnect/read loops). They live for the connection's life; the integration test reaps the
		// conn on t.Cleanup, but goleak snapshots before Cleanup runs on some paths, so the client
		// roots are ignored explicitly — they are not natsbus adapter goroutines.
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).flusher"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).readLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).waitForMsgs"),
		// The embedded nats-server's own background roots (accept loop, JetStream, internal clients);
		// they belong to the in-process server the integration arm runs, not to the adapter.
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*Server).AcceptLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*client).writeLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*client).readLoop"),
	)
}
