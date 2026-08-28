package codeinsight_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the root codeinsight package on ANY goroutine left running after the suite.
// The library spawns NO background daemon goroutine of its own: the SystemGitHistory adapter shells
// short-lived `git` child processes that are reaped synchronously by exec.CommandContext before Walk
// returns, and the analyzer holds only the injected ports. So a goroutine surviving the suite would
// mean a leaked git child reaper or an un-waited subprocess — exactly the leak this lane catches.
// The threshold is ZERO leaked goroutines/fds; the only ignores are the well-known benign roots.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own poller reaper, present in every Go test binary that touches the runtime
		// poller (os/exec wires the child's pipes through it); not a codeinsight goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		// os/exec's SIGCHLD-driven child reaper, present whenever a test binary has spawned a
		// subprocess; the git children are awaited synchronously, this is the runtime's own.
		goleak.IgnoreTopFunction("os/exec.(*Cmd).watchCtx"),
	)
}
