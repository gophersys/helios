package composition_test

import (
	"context"
	"net/http"
	"os"
	"os/exec"
	"syscall"
	"testing"
	"time"
)

// TestProbeOnlyServesLiveAndShutsDown is the in-process smoke for the composition root's probe-only
// path: it builds the binary, runs it in EDEN_PROBE_ONLY mode on a random port, asserts /live answers
// 200, sends SIGTERM, and asserts a graceful exit-0 — the PID-1 entrypoint contract (serves the
// kubelet probe, shuts down cleanly on a signal) without a live NATS bus or an authenticated harness.
func TestProbeOnlyServesLiveAndShutsDown(t *testing.T) {
	t.Parallel()
	binary := buildBinary(t)
	port := "21555"

	cmd := exec.Command(binary) // #nosec G204 -- the binary path is test-built into t.TempDir(), not user input.
	cmd.Env = append(
		os.Environ(),
		"EDEN_PROBE_ONLY=1",
		"EDEN_AGENT_ID=smoke-test",
		"EDEN_PROBE_ADDR=:"+port,
	)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		t.Fatalf("start agent-runtime: %v", err)
	}
	t.Cleanup(func() {
		if cmd.Process != nil {
			_ = cmd.Process.Kill() //nolint:errcheck // best-effort reap if the test failed before SIGTERM.
		}
	})

	waitForLive(t, "http://127.0.0.1:"+port+"/live")

	if err := cmd.Process.Signal(syscall.SIGTERM); err != nil {
		t.Fatalf("SIGTERM: %v", err)
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("agent-runtime did not exit 0 on SIGTERM: %v", err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("agent-runtime did not shut down within 10s of SIGTERM")
	}
}

// buildBinary compiles the agent-runtime command into t.TempDir() and returns its path.
func buildBinary(t *testing.T) string {
	t.Helper()
	binary := t.TempDir() + "/agent-runtime"
	build := exec.Command("go", "build", "-o", binary, "../../cmd/agent-runtime") // #nosec G204 -- fixed go build of the in-repo command.
	build.Env = os.Environ()
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build agent-runtime: %v\n%s", err, out)
	}
	return binary
}

// waitForLive polls the /live URL until it answers 200 or the deadline passes.
func waitForLive(t *testing.T, url string) {
	t.Helper()
	deadline := time.After(8 * time.Second)
	for {
		request, _ := http.NewRequestWithContext(context.Background(), http.MethodGet, url, http.NoBody) //nolint:errcheck // a fixed URL.
		response, err := http.DefaultClient.Do(request)
		if err == nil {
			_ = response.Body.Close() //nolint:errcheck // probe body unused.
			if response.StatusCode == http.StatusOK {
				return
			}
		}
		select {
		case <-deadline:
			t.Fatalf("/live at %s never answered 200", url)
		case <-time.After(100 * time.Millisecond):
		}
	}
}
