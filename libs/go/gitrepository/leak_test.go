package gitrepository_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the root gitrepository package on ANY goroutine left
// running after the suite. The library spawns NO background daemon goroutine of its own:
// the system-git Backend shells short-lived `git` child processes that are reaped
// synchronously by exec.CommandContext before each verb returns, and the per-worktree
// serialization locks own no goroutine. So a goroutine surviving the suite would mean a
// leaked git child reaper or an un-waited subprocess — exactly the leak this lane catches.
// The threshold is ZERO leaked goroutines/fds; the only ignores are the well-known benign
// runtime/test-harness roots.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that
		// touches the runtime poller (os/exec wires the child's pipes through it); not a
		// gitrepository goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		// os/exec's SIGCHLD-driven child reaper, present whenever a test binary has spawned a
		// subprocess; the git children are awaited synchronously, this is the runtime's own.
		goleak.IgnoreTopFunction("os/exec.(*Cmd).watchCtx"),
	)
}
