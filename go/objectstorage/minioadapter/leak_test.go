package minioadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the minioadapter package on ANY goroutine left running after the suite. The
// adapter is request-scoped: New resolves the credential synchronously and builds the client (no
// goroutine); each Backend method makes a synchronous SDK call. The only ignores are the benign
// runtime poller root and net/http's idle-connection pool reaper the real SDK client uses
// (integration lane), which is a transport-pool background root, not an adapter leak. A regression
// that, say, launched a per-Put uploader goroutine and never joined it would surface here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary touching the
		// runtime poller; not a minioadapter goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		// net/http's idle-connection reaper the real MinIO SDK client uses (integration lane only);
		// a transport-pool background root, not an adapter leak.
		goleak.IgnoreAnyFunction("net/http.(*persistConn).readLoop"),
		goleak.IgnoreAnyFunction("net/http.(*persistConn).writeLoop"),
	)
}
