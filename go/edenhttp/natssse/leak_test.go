package natssse_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the natssse package on ANY goroutine left running after the suite. The bridge
// owns ONE pump goroutine per Stream call (the SSE handler's goroutine) plus the ephemeral JetStream
// consumer; both are reaped on the terminal event or a client disconnect (the deferred Unsubscribe).
// A regression that leaked a bridge goroutine or an un-unsubscribed consumer would surface here. The
// integration arm boots a REAL embedded nats-server + dials a REAL *nats.Conn whose background roots
// (the server's accept/route loops, the client's flusher/ping/read loops, and net/http transport
// reapers) are well-known benign roots listed explicitly — they are NOT bridge goroutines.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		// The nats.go client's background goroutines on a live *nats.Conn (flusher, read loop, msg
		// dispatcher). They live for the connection's life; the integration test reaps the conn on
		// t.Cleanup, but goleak snapshots before Cleanup on some paths — not bridge goroutines.
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).flusher"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).readLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).waitForMsgs"),
		// The embedded nats-server's own background roots (accept loop, JetStream, internal clients).
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*Server).AcceptLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*client).writeLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*client).readLoop"),
	)
}
