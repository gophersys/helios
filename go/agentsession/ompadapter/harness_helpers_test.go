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
	"fmt"
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
	"github.com/gophersys/libs/go/secrets"
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

// drainToTurnBoundary drains a session's stream to the end of its FIRST TURN, bounded so a
// regression fails fast rather than hanging.
// drainDeadline bounds a live harness run. Exceeding it is a FAILURE that says
// so, never a quiet return of a partial event list.
const drainDeadline = 60 * time.Second

// liveDrainDeadline bounds a drain against the REAL omp harness. The 60s above is sized
// for the in-repo stub, and the first live run that ever reached this code died on it
// with 18 events still streaming — a healthy-but-slow turn reported as a hang, which is
// the failure mode drainToTurnBoundaryWithin exists to name rather than cause. 120s
// matches the claudeadapter live arms.
const liveDrainDeadline = 120 * time.Second

// Re-pinned for contract revision R1: the drain stops on the boundary PAYLOAD
// (`event.Terminal != nil`), which is the SAME event on both sides of the revision — a clean
// `agent_end` today, and the non-terminal turn-end it becomes once a session survives its own
// turn. Stopping on IsTerminal() alone would wait out the whole deadline post-R1, since a
// healthy multi-turn session emits no terminal until it is Closed.
//
// It returns an error rather than calling t.Fatalf, so that the deadline branch
// below can be driven from a test. While it took a *testing.T that branch could
// not be reached by any test, and it shipped unproven.
func drainToTurnBoundary(session agentsession.Session) ([]agentsession.Event, error) {
	return drainToTurnBoundaryWithin(session, drainDeadline)
}

// drainToTurnBoundaryWithin takes the deadline as a parameter so a test can drive the
// timeout branch in seconds instead of waiting out the production deadline.
func drainToTurnBoundaryWithin(session agentsession.Session, deadline time.Duration) ([]agentsession.Event, error) {
	ctx, cancel := context.WithTimeout(context.Background(), deadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				return events, fmt.Errorf("stream fault: %w", err)
			}
			// A deadline is NOT a clean end of stream. This used to return the
			// events collected so far, so the caller reported whatever the last
			// event happened to be and the reader looked at event kinds instead
			// of the clock. Name the timeout here, where it is known.
			if ctx.Err() != nil {
				return events, fmt.Errorf("no turn boundary within %s (%d event(s) seen, last = %s); the harness is hung or slower than this deadline",
					deadline, len(events), lastKind(events))
			}
			return events, nil
		}
		events = append(events, event)
		if event.Terminal != nil || event.IsTerminal() {
			return events, nil
		}
	}
}

// lastKind names the final event for a diagnostic, or "none". It renders through String(), not
// through a conversion: EventKind's underlying type is uint8, so `string(kind)` is a rune
// conversion that go vet's stringintconv permits (uint8 IS byte) and that prints an
// unprintable byte instead of the token — the diagnostic this deadline message exists to give.
func lastKind(events []agentsession.Event) string {
	if len(events) == 0 {
		return "none"
	}
	return events[len(events)-1].Kind.String()
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

// TestDrainToTurnBoundary_ADeadlineNamesItself drives the branch that shipped
// unproven. The scripted fake emits 1 event that draws no boundary and then holds
// the stream open, so the drain can only end on its deadline.
//
// Before this, the deadline returned the events collected so far and the caller
// blamed whatever the last event happened to be. That is how a 64-second omp run
// was reported as "last = extension" in eden#4, with the clock nowhere in the
// message.
func TestDrainToTurnBoundary_ADeadlineNamesItself(t *testing.T) {
	t.Parallel()

	// No boundary-bearing event in the script, so the stream never ends by itself.
	pool := newPool(t, agentsessiontest.New(agentsession.Event{Kind: agentsession.EventExtension}))
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  "/workspace",
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		t.Fatalf("open on the fake: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap.

	// 2 seconds, not the production deadline: this test is about the branch,
	// not about how long the real harness is given.
	const testDeadline = 2 * time.Second
	events, drainErr := drainToTurnBoundaryWithin(session, testDeadline)
	if drainErr == nil {
		t.Fatalf("a session that drew no turn boundary drained cleanly; got %d event(s)", len(events))
	}
	if !strings.Contains(drainErr.Error(), "no turn boundary within") {
		t.Fatalf("the error does not name the deadline: %v", drainErr)
	}
	if !strings.Contains(drainErr.Error(), testDeadline.String()) {
		t.Fatalf("the error does not carry the deadline value %s: %v", testDeadline, drainErr)
	}
}
