//go:build integration || lifecycle || load

// The shared REAL-subprocess test scaffolding for the omp adapter's host-leveraging lanes —
// integration (dimension d), lifecycle (c), and load (e). Every one of those lanes drives the
// GENUINE os/exec stub-harness subprocess (internal/stubharness, NOT omp) through the adapter's
// real Spawn/scan/Close ladder with a FAKE seeded credential (a canary asserted never to leak),
// so the spawn/parse/reap path is proven on an actual process WITHOUT a live OpenRouter call.
// One home for these helpers (cohesion): the three lanes share the build-the-stub / open-the-pool
// / drain-to-terminal mechanics; only their assertions differ.
package ompadapter_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// fakeCanary is the credential plaintext the stub session resolves; it must appear in NO emitted
// Event and no recorded output (the credential-never-leaks guarantee, on a real process).
const fakeCanary = "STUB-OPENROUTER-KEY-do-not-leak"

// vaultReference is the opaque vault reference the Spec carries; the test provider resolves it to
// the canary (stub arm) or the operator key (live arm) — never minted here.
const vaultReference = "vault://eden/openrouter#api-key"

// buildStub compiles the stub harness binary into t.TempDir() and returns its path.
func buildStub(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	binary := filepath.Join(dir, "stubharness")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	build := exec.Command("go", "build", "-o", binary, ".") //nolint:gosec // fixed `go build` of the in-repo stub package; binary is a t.TempDir path, not user input.
	build.Dir = stubSourceDir(t)
	build.Env = os.Environ()
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build stub harness: %v\n%s", err, out)
	}
	return binary
}

// stubSourceDir locates the stub harness package source relative to this test file.
func stubSourceDir(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot locate the test source path")
	}
	return filepath.Join(filepath.Dir(file), "internal", "stubharness")
}

// newPool constructs a Pool over the adapter with a FAKE seeded credential (the canary).
func newPool(t *testing.T, adapter agentsession.Adapter) *agentsession.Pool {
	t.Helper()
	return newPoolWithKey(t, adapter, fakeCanary, "stub-deepseek")
}

// newPoolWithKey constructs a Pool whose provider resolves the credential reference to the given
// key (a fake canary in the stub arm; the operator-supplied OpenRouter key in the gated live arm
// — never minted here) and routes the assistant role to the given model.
func newPoolWithKey(t *testing.T, adapter agentsession.Adapter, key, model string) *agentsession.Pool {
	t.Helper()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "omp", Model: model},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"omp": adapter},
			Secrets:    secretstest.New(map[string]string{vaultReference: key}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      integrationClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}

// integrationClock is a deterministic clock for the subprocess-backed pools.
type integrationClock struct{}

func (integrationClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// drainTerminal drains a session's stream to its terminal, bounded so a regression fails fast
// rather than hanging.
func drainTerminal(t *testing.T, session agentsession.Session) []agentsession.Event {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				t.Fatalf("stream fault: %v", err)
			}
			return events
		}
		events = append(events, event)
		if event.IsTerminal() {
			return events
		}
	}
}

// readyObserved reports whether the stream contains the Initializing->Ready handshake.
func readyObserved(events []agentsession.Event) bool {
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventSessionState && ev.State != nil && ev.State.To == agentsession.StateReady {
			return true
		}
	}
	return false
}

// kindObserved reports whether any event has the given kind.
func kindObserved(events []agentsession.Event, kind agentsession.EventKind) bool {
	for i := range events {
		if events[i].Kind == kind {
			return true
		}
	}
	return false
}

// ── real-process accounting (the no-orphan-process half of dimensions c/e) ───────────────.

// liveStubChildren counts processes parented to THIS test process whose command is the stub
// harness binary, by scanning /proc (the devcontainer is Linux). Field 2 of /proc/<pid>/stat is
// the comm in parens (kernel-truncated to 15 chars — "stubharness" fits); the field after the
// closing paren sequence [state, ppid, ...] gives the PPID. A non-zero count after a Close/join
// is a leaked (orphaned) subprocess.
func liveStubChildren() (int, error) {
	self := os.Getpid()
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return 0, err
	}
	count := 0
	for _, e := range entries {
		pid, convErr := strconv.Atoi(e.Name())
		if convErr != nil {
			continue // not a pid dir
		}
		comm, ppid, ok := procCommPPID(pid)
		if !ok {
			continue // the process vanished between ReadDir and read — already reaped
		}
		if ppid == self && strings.Contains(comm, "stubharness") {
			count++
		}
	}
	return count, nil
}

// procCommPPID reads the comm (field 2, in parens) and PPID (the field after the closing paren)
// from /proc/<pid>/stat.
func procCommPPID(pid int) (comm string, ppid int, ok bool) {
	data, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat") //nolint:gosec // pid is an integer from the /proc dir listing, not user input.
	if err != nil {
		return "", 0, false
	}
	s := string(data)
	open := strings.IndexByte(s, '(')
	closeIdx := strings.LastIndexByte(s, ')')
	if open < 0 || closeIdx < 0 || closeIdx < open {
		return "", 0, false
	}
	comm = s[open+1 : closeIdx]
	rest := strings.Fields(s[closeIdx+1:]) // fields after ')': [state, ppid, ...]
	if len(rest) < 2 {
		return "", 0, false
	}
	ppid, err = strconv.Atoi(rest[1])
	if err != nil {
		return "", 0, false
	}
	return comm, ppid, true
}
