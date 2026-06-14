package stateless_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the stateless gateway's SSE goroutine + the natssse
// JetStream consumer are asserted reaped after every suite (the ADR-0022 reap invariant: the SSE
// goroutine + JetStream consumer reaped on disconnect). The integration arm boots a REAL embedded
// nats-server + dials a REAL *nats.Conn whose background roots (server accept loops, the client's
// flusher/read loops) are well-known benign roots listed explicitly — they are NOT gateway goroutines.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).flusher"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).readLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats.go.(*Conn).waitForMsgs"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*Server).AcceptLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*client).writeLoop"),
		goleak.IgnoreAnyFunction("github.com/nats-io/nats-server/v2/server.(*client).readLoop"),
	)
}
