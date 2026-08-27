package vaultadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the vaultadapter package on ANY goroutine left running after the suite.
// The adapter is request-scoped: New dials nothing, Resolve makes a synchronous login/read through
// the transport and returns — it spawns no background goroutine. The only ignore is the well-known
// benign runtime poller root. A regression that, say, launched a token-refresh goroutine per
// Resolve and never joined it would surface here. The real Vault SDK client (integration lane)
// keeps an idle-connection pool whose reaper is a net/http transport root, also benign.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that touches
		// the runtime poller; not a vaultadapter goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		// net/http's idle-connection reaper the real Vault SDK client uses (integration lane only);
		// it is a transport-pool background root, not an adapter leak.
		goleak.IgnoreAnyFunction("net/http.(*persistConn).readLoop"),
		goleak.IgnoreAnyFunction("net/http.(*persistConn).writeLoop"),
	)
}
