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
	"sync"
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

// drainDeadline bounds the STUB arm's drain. A scripted stub is instant or broken, so one
// absolute bound is the whole story there and no inactivity window is needed. Exceeding it is a
// FAILURE that says so, never a quiet return of a partial event list. The LIVE arms do NOT use
// it — they carry liveDrainBounds below.
const drainDeadline = 60 * time.Second

// liveDrainBounds is the live arm's two-clock bound, cited by every live call site. The LIVE arm
// is bounded by INACTIVITY, not by a total: an absolute total cannot tell a harness that is
// streaming steadily from one that is dead, and CI proved that twice, both times in the EDEN
// monorepo (`gophersys/eden`, not this repository): 18 events by 60s in eden run 32935203884
// and, after the constant was raised, 27 by 120s in eden run 32998558460. Both harnesses were
// progressing, so raising the constant only moves the flake threshold.
//
// Idle is the longest a REAL turn may go silent between events; Total is the absolute safety net
// so a harness that streams forever cannot pin CI. omp can carry the IDLE window because
// ompadapter's normalizer preserves every unmodeled frame as an extension, so the idle clock can
// actually SEE the harness being alive. The claudeadapter twin deliberately runs Total-only; the
// reason is documented on its own liveDrainTotal.
//
// The two figures are inlined rather than named constants: under `-tags lifecycle|load` this
// shared file compiles without the live arm that reads them, and each extra name would be one
// more `unused` finding in a lane that legitimately does not use it.
var liveDrainBounds = drainBounds{Idle: 60 * time.Second, Total: 10 * time.Minute}

// drainBounds bounds a drain by two INDEPENDENT clocks. Idle is the maximum gap between
// CONSECUTIVE events — a harness that is still producing never trips it, however long the whole
// turn takes. Total is the absolute safety cap so a harness that streams forever without drawing
// a boundary cannot pin CI. Zero disables that bound, so the zero value drainBounds{} disables
// BOTH and drains unbounded — never construct one; every call site names at least Total.
type drainBounds struct {
	Idle  time.Duration
	Total time.Duration
}

// drainToTurnBoundary drains a session's stream to the end of its FIRST TURN, bounded so a
// regression fails fast rather than hanging.
//
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
	// The STUB arm keeps an absolute bound and no idle bound: a stub is instant or broken.
	return drainToTurnBoundaryWithin(session, drainBounds{Total: drainDeadline})
}

// drainToTurnBoundaryWithin takes the bounds as a parameter so a test can drive each timeout
// branch in seconds instead of waiting out the production bound. It derives ONE total-scoped
// context for the stream and a FRESH per-wait child for EACH Next, so an arriving event resets
// the idle clock and only a genuine silence trips it.
func drainToTurnBoundaryWithin(session agentsession.Session, bounds drainBounds) ([]agentsession.Event, error) {
	totalCtx, cancelTotal := boundedContext(context.Background(), bounds.Total)
	defer cancelTotal()
	stream := session.Events(totalCtx, agentsession.FromSeq(0))

	started := time.Now()
	progress := drainProgress{started: started, lastEvent: started}
	for {
		event, ok, idleExpired := nextWithin(totalCtx, stream, bounds.Idle)
		if !ok {
			return progress.events, drainFault(totalCtx, stream, idleExpired, bounds, progress)
		}
		progress.events = append(progress.events, event)
		progress.lastEvent = time.Now()
		if event.Terminal != nil || event.IsTerminal() {
			return progress.events, nil
		}
	}
}

// nextWithin waits for one event under a FRESH child context bounded by idle, canceled the
// moment Next returns rather than held across the loop — that is what makes an arriving event
// reset the inactivity clock. idleExpired says this wait ran out of time; the caller still has
// to rule the TOTAL bound out first, because a total expiry cancels this child too.
func nextWithin(parent context.Context, stream agentsession.Stream, idle time.Duration) (event agentsession.Event, ok, idleExpired bool) {
	waitCtx, cancel := boundedContext(parent, idle)
	defer cancel()
	event, ok = stream.Next(waitCtx)
	return event, ok, waitCtx.Err() != nil
}

// boundedContext derives a child bounded by limit, or a plain cancellable child when limit is 0
// (that bound is disabled). Both arms return a cancel func, so no caller carries a nil check.
func boundedContext(parent context.Context, limit time.Duration) (context.Context, context.CancelFunc) {
	if limit <= 0 {
		return context.WithCancel(parent)
	}
	return context.WithTimeout(parent, limit)
}

// drainProgress is how far a drain got before it ended — what both bound messages report, so a
// reader sees the clock AND the stream state instead of guessing from the last event kind.
type drainProgress struct {
	events    []agentsession.Event
	started   time.Time
	lastEvent time.Time
}

// describe renders the progress for a bound message, rounded so the line reads at a glance.
func (p drainProgress) describe() string {
	return fmt.Sprintf("%d event(s) seen, last = %s %s ago, %s elapsed",
		len(p.events), lastKind(p.events),
		time.Since(p.lastEvent).Round(time.Millisecond),
		time.Since(p.started).Round(time.Millisecond))
}

// drainFault classifies an ended wait, in the ONE order that cannot mislabel a bound: a stream
// fault, then the ABSOLUTE cap — whose expiry cancels the per-wait child too, so reading the
// child first would report every cap as an idle window — then the idle window, then a clean end
// of stream, which stays exactly what it was: no error.
func drainFault(totalCtx context.Context, stream agentsession.Stream, idleExpired bool, bounds drainBounds, progress drainProgress) error {
	if err := stream.Err(); err != nil {
		return fmt.Errorf("stream fault: %w", err)
	}
	// A bound is NOT a clean end of stream. This used to return the events collected so far, so
	// the caller reported whatever the last event happened to be and the reader looked at event
	// kinds instead of the clock. Name the bound here, where it is known.
	// The cap measures the WHOLE drain and nothing about liveness, so it must not claim any: it
	// fires identically on a harness that streamed to the last millisecond and on one that went
	// silent after two events. Saying "the harness streamed" would be a lie in the second case —
	// exactly the misdescription this change exists to end. The `last = ... ago` figure that
	// describe() already renders is what separates the two, so point at it instead of guessing.
	if totalCtx.Err() != nil {
		return fmt.Errorf("no turn boundary within %s (the ABSOLUTE cap): %s; the cap bounds the WHOLE drain and measures no liveness — the `last = ... ago` figure above tells a streaming harness from a silent one",
			bounds.Total, progress.describe())
	}
	if idleExpired {
		return fmt.Errorf("no event for %s (the IDLE bound): %s; the harness stopped producing",
			bounds.Idle, progress.describe())
	}
	return nil
}

// kindsOf projects the event kinds for a failure diagnostic, so a count assertion that trips says
// WHICH events arrived instead of only how many.
func kindsOf(events []agentsession.Event) []agentsession.EventKind {
	out := make([]agentsession.EventKind, len(events))
	for i := range events {
		out[i] = events[i].Kind
	}
	return out
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

// ── the timed drip fixture (a harness that is SLOW, not silent) ──────────────────────────────.

// dripAdapter is a TIMED agentsession.Adapter. agentsessiontest.Adapter emits its whole script
// the instant the pump reads it, so it can prove a SILENT harness but never a SLOW one — and
// slow-but-progressing is exactly the shape the live CI failures had. It embeds the canonical
// fake so Manifest() stays the real full-capability one, and overrides only Spawn.
type dripAdapter struct {
	*agentsessiontest.Adapter
	gap   time.Duration
	count int
}

// newDripAdapter builds a harness that emits count non-boundary events spaced gap apart and then
// draws a turn boundary. count <= 0 drips forever and never draws one.
func newDripAdapter(gap time.Duration, count int) *dripAdapter {
	return &dripAdapter{Adapter: agentsessiontest.New(), gap: gap, count: count}
}

// Spawn returns a fresh dripping conn, shadowing the embedded fake's instant one.
//
//nolint:gocritic,ireturn // contract §2/§3: Spec is the frozen copyable input and Spawn returns the HarnessConn port — this fixture mirrors the frozen seam.
func (a *dripAdapter) Spawn(_ context.Context, _ agentsession.Spec, _ agentsession.Route, _ agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	conn := &dripConn{
		events:   make(chan agentsession.Event),
		commands: make(chan agentsession.Command),
		stop:     make(chan struct{}),
		done:     make(chan struct{}),
		gap:      a.gap,
		count:    a.count,
	}
	go conn.drive()
	return conn, nil
}

// dripConn is the HarnessConn dripAdapter spawns: Ready, then one non-boundary event every gap,
// then (when count > 0) a turn boundary. It mirrors agentsessiontest's fakeConn shape — one
// driver goroutine owns the outbound channel, Send never deadlocks, Close is idempotent and the
// driver exits on it, so this package's goleak TestMain stays green.
type dripConn struct {
	events   chan agentsession.Event
	commands chan agentsession.Command
	stop     chan struct{}
	done     chan struct{}

	gap   time.Duration
	count int

	closeOnce sync.Once
	doneOnce  sync.Once
}

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *dripConn) Events() <-chan agentsession.Event { return c.events }

// Send hands a control frame to the driver, or drops it once the driver has stopped, so a late
// Send never deadlocks.
func (c *dripConn) Send(ctx context.Context, command agentsession.Command) error {
	select {
	case c.commands <- command:
		return nil
	case <-c.done:
		return nil // the driver has stopped; the frame is a no-op
	case <-ctx.Done():
		return nil
	}
}

// Close stops the driver and waits for it to exit. Idempotent.
func (c *dripConn) Close(_ context.Context) error {
	c.closeOnce.Do(func() { close(c.stop) })
	<-c.done
	return nil
}

// drive is the conn's single goroutine: Ready, wait for the first Prompt, then drip.
func (c *dripConn) drive() {
	defer c.finish()
	if !c.emit(agentsessiontest.ReadyEvent()) {
		return
	}
	if !c.awaitFirstPrompt() {
		return
	}
	c.dripBody()
}

// awaitFirstPrompt blocks until the SUT prompts, or the conn is stopped.
func (c *dripConn) awaitFirstPrompt() bool {
	for {
		select {
		case command := <-c.commands:
			if command.Kind == agentsession.CommandPrompt {
				return true
			}
		case <-c.stop:
			return false
		}
	}
}

// dripBody emits count non-boundary events one gap apart and then the turn boundary. count <= 0
// drips forever and never draws one — the endless-stream shape only an absolute cap can end.
func (c *dripConn) dripBody() {
	for i := 0; c.count <= 0 || i < c.count; i++ {
		if !c.waitOneGap() {
			return
		}
		if !c.emit(agentsessiontest.Extension(fmt.Appendf(nil, `{"type":"drip","n":%d}`, i))) {
			return
		}
	}
	c.emit(agentsessiontest.Result(agentsession.TokenLedger{
		UsageMeter: agentsession.UsageMeter{Harness: "omp", Cumulative: true},
		Turns:      1,
	}, "ok", "end_turn"))
}

// waitOneGap sleeps one gap, returning false if the conn was stopped meanwhile.
func (c *dripConn) waitOneGap() bool {
	timer := time.NewTimer(c.gap)
	defer timer.Stop()
	select {
	case <-timer.C:
		return true
	case <-c.stop:
		return false
	}
}

// emit hands one event to the library pump, honoring stop so the driver never blocks on a
// consumer that has gone away.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this fixture emits by value.
func (c *dripConn) emit(event agentsession.Event) bool {
	select {
	case c.events <- event:
		return true
	case <-c.stop:
		return false
	}
}

// finish closes the event channel and signals done exactly once.
func (c *dripConn) finish() {
	c.doneOnce.Do(func() {
		close(c.events)
		close(c.done)
	})
}

// compile-time assertions: the drip fixture satisfies the frozen ports.
var (
	_ agentsession.Adapter     = (*dripAdapter)(nil)
	_ agentsession.HarnessConn = (*dripConn)(nil)
)

// openPromptedSession opens a session over adapter and sends the first Prompt, so the harness is
// actually streaming when the drain under test faces it. Reaped on Cleanup.
//
//nolint:ireturn // Session is the frozen port Pool.Open returns; a test helper can only re-surface it.
func openPromptedSession(t *testing.T, adapter agentsession.Adapter) agentsession.Session {
	t.Helper()
	pool := newPool(t, adapter)
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  "/workspace",
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		t.Fatalf("open on the fake: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap.
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("prompt the fake: %v", err)
	}
	return session
}

// TestDrainToTurnBoundary_SlowButProgressingSurvivesTheIdleWindow pins the CI defect this change
// exists to fix. The live drain was bounded by an ABSOLUTE total deadline, which cannot tell a
// harness that is streaming steadily from one that is dead. CI proved it twice, both times in the
// EDEN monorepo (`gophersys/eden`, not this repository): eden run 32935203884 died at 60s with 18
// events seen, and after the constant was raised, eden run 32998558460 died at 120s with 27. Both
// harnesses were PROGRESSING. An INACTIVITY bound reads the gap between CONSECUTIVE events
// instead, so a turn that runs many multiples of the window survives as long as events keep
// arriving — and raising a constant stops being the fix.
func TestDrainToTurnBoundary_SlowButProgressingSurvivesTheIdleWindow(t *testing.T) {
	t.Parallel()

	const (
		gap        = 150 * time.Millisecond
		dripCount  = 12
		idleWindow = 750 * time.Millisecond
	)
	session := openPromptedSession(t, newDripAdapter(gap, dripCount))

	events, drainErr := drainToTurnBoundaryWithin(session, drainBounds{Idle: idleWindow, Total: 30 * time.Second})
	if drainErr != nil {
		t.Fatalf("a harness that never stopped producing tripped a bound: %v", drainErr)
	}
	if len(events) == 0 {
		t.Fatal("the dripping harness produced no events")
	}
	if events[len(events)-1].Terminal == nil {
		t.Fatalf("the drain ended on %s, not on a turn boundary (%d event(s) seen)", lastKind(events), len(events))
	}
	// The fixture is fully determined, so the drain has exactly ONE correct length: the handshake
	// events, then dripCount drips, then the boundary. Pinning the number is what a CHANGED
	// fixture breaks — this replaces an arithmetic guard (`len(events) <= int(idleWindow/gap)+1`,
	// i.e. 6) that could never fail, because the Terminal assertion above already forces every
	// drip through and 13 > 6. An assertion that cannot fail is worse than none.
	//
	// The arithmetic is still the POINT, and it is stated in the failure text rather than
	// asserted: an ABSOLUTE idleWindow deadline reaches only about int(idleWindow/gap)+1 events
	// before firing, so reaching all expectedEvents is possible only because the clock being read
	// is the GAP between consecutive events, not the total.
	//
	// Measured, not guessed: [session-state session-state] + 12 [extension] drips +
	// [session-state result].
	const expectedEvents = 2 + dripCount + 2
	if len(events) != expectedEvents {
		t.Fatalf("the drip drained %d event(s), want exactly %d (2 handshake, %d drips, a state change, the boundary); kinds = %v. "+
			"An ABSOLUTE %s deadline reaches only about %d, so a short count means the idle window did not hold",
			len(events), expectedEvents, dripCount, kindsOf(events), idleWindow, int(idleWindow/gap)+1)
	}
}

// TestDrainToTurnBoundary_AnIdleHarnessTripsTheIdleBound is the other half of the contract: an
// inactivity bound that never fires would turn every hang into a 10-minute wait. agentsessiontest
// streams its script the instant the pump reads it and then blocks in its service loop, so the
// gap after the last event is unbounded — the genuinely SILENT harness. The idle bound must end
// the drain and say which bound it was, so a reader is not left guessing at the absolute cap.
func TestDrainToTurnBoundary_AnIdleHarnessTripsTheIdleBound(t *testing.T) {
	t.Parallel()

	const (
		idleWindow = 500 * time.Millisecond
		// The fixture is fully determined, so the message's figures are too. These are LITERALS on
		// purpose: asserting `fmt.Sprintf("%d event(s) seen", len(events))` and `lastKind(events)`
		// is tautological — describe() built the message from the SAME slice, so those assertions
		// hold for any value and only detect a deleted field, never a wrong one.
		//
		// Measured, not guessed: kinds = [session-state session-state extension extension extension].
		expectedEvents   = 5 // the 2 handshake state events + the 3 scripted extensions
		expectedLastKind = "extension"
	)
	// Three non-boundary events, then silence: the script ends without ever drawing a boundary.
	session := openPromptedSession(t, agentsessiontest.New(
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
	))

	events, drainErr := drainToTurnBoundaryWithin(session, drainBounds{Idle: idleWindow, Total: 20 * time.Second})
	if drainErr == nil {
		t.Fatalf("a harness that went silent drained cleanly; got %d event(s)", len(events))
	}
	if len(events) != expectedEvents || lastKind(events) != expectedLastKind {
		t.Fatalf("the fixture drained %d event(s) ending on %s, want %d ending on %s; the literals below no longer describe it. kinds = %v",
			len(events), lastKind(events), expectedEvents, expectedLastKind, kindsOf(events))
	}
	message := drainErr.Error()
	if !strings.Contains(message, "the IDLE bound") {
		t.Fatalf("the error does not name the IDLE bound: %v", drainErr)
	}
	if strings.Contains(message, "the ABSOLUTE cap") {
		t.Fatalf("a silent harness was reported against the ABSOLUTE cap, which had not expired: %v", drainErr)
	}
	if !strings.Contains(message, idleWindow.String()) {
		t.Fatalf("the error does not carry the idle bound value %s: %v", idleWindow, drainErr)
	}
	if !strings.Contains(message, fmt.Sprintf("%d event(s) seen", expectedEvents)) {
		t.Fatalf("the error does not carry the event count %d: %v", expectedEvents, drainErr)
	}
	if !strings.Contains(message, "last = "+expectedLastKind+" ") {
		t.Fatalf("the error does not carry the last event kind %s: %v", expectedLastKind, drainErr)
	}
}

// TestDrainToTurnBoundary_AnEndlessStreamTripsTheAbsoluteCap proves the safety net an inactivity
// bound alone would remove: a harness that streams forever and never draws a boundary would keep
// resetting the idle clock and hold CI open indefinitely. The absolute cap must end the drain,
// and it must say so.
//
// The idle window is 200ms over a 50ms drip — ARMED, and deliberately SHORTER than the 1s cap.
// That is what makes this test exercise the idle RESET rather than merely the cap: surviving 1s
// of 50ms drips under a 200ms window is possible only if each arriving event restarts the
// window, so a reset that stops working turns this test red on the IDLE bound. It was previously
// written Idle:2s over Total:1s — idle longer than the cap, which made it a cap-only test and
// left the reset pinned by nothing.
func TestDrainToTurnBoundary_AnEndlessStreamTripsTheAbsoluteCap(t *testing.T) {
	t.Parallel()

	const (
		absoluteCap = 1 * time.Second
		idleWindow  = 200 * time.Millisecond
	)
	session := openPromptedSession(t, newDripAdapter(50*time.Millisecond, 0)) // 0 == drip forever

	events, drainErr := drainToTurnBoundaryWithin(session, drainBounds{Idle: idleWindow, Total: absoluteCap})
	if drainErr == nil {
		t.Fatalf("an endless stream drained cleanly; got %d event(s)", len(events))
	}
	message := drainErr.Error()
	if !strings.Contains(message, "the ABSOLUTE cap") {
		t.Fatalf("the error does not name the ABSOLUTE cap: %v", drainErr)
	}
	// This is also the RESET assertion. The window is 200ms and the drip is 50ms, so surviving the
	// full 1s to reach the cap is only possible because every arriving event restarts the window.
	// A reset that stopped working would land here, not on the cap.
	if strings.Contains(message, "the IDLE bound") {
		t.Fatalf("an endlessly-producing harness was reported against the IDLE bound: the %s window did not reset on each arriving event: %v", idleWindow, drainErr)
	}
	if !strings.Contains(message, absoluteCap.String()) {
		t.Fatalf("the error does not carry the absolute cap value %s: %v", absoluteCap, drainErr)
	}
	// Events kept arriving right up to the cap: this is a streaming harness, not a hung one.
	if len(events) == 0 {
		t.Fatal("the endless drip produced no events, so the cap was not proven against a PRODUCING harness")
	}
}

// TestDrainToTurnBoundary_ADeadlineNamesItself drives the absolute-cap branch on the STUB arm's
// shape: idle left zero, one total bound. The scripted fake emits 1 event that draws no boundary
// and then holds the stream open, so the drain can only end on that bound.
//
// Before this, the bound returned the events collected so far and the caller blamed whatever the
// last event happened to be. That is how a 64-second omp run was reported as "last = extension"
// in eden#4, with the clock nowhere in the message. Both packages carry this identical test: the
// ompadapter copy of the helper had one and the claudeadapter copy had none, and an untested copy
// is a copy that drifts.
func TestDrainToTurnBoundary_ADeadlineNamesItself(t *testing.T) {
	t.Parallel()

	// No boundary-bearing event in the script, so the stream never ends by itself.
	session := openPromptedSession(t, agentsessiontest.New(agentsession.Event{Kind: agentsession.EventExtension}))

	// 2 seconds, not the production bound: this test is about the branch, not about how long the
	// real harness is given.
	const testDeadline = 2 * time.Second
	// Idle left zero — the STUB arm's shape: one absolute bound, no inactivity window.
	events, drainErr := drainToTurnBoundaryWithin(session, drainBounds{Total: testDeadline})
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
