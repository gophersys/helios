//go:build lifecycle

package agentsession_test

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestLifecycle_SessionDoubleCloseIdempotentNoOrphans is the full-object-lifecycle
// conformance (ADR-0020 dimension (c)) for the agentsession closeable handle: the live
// Session returned by Pool.Open. It drives testing.AssertLifecycle over a probe whose
// owned resource is the underlying harness connection — construct -> use -> first Close ->
// SECOND Close is a no-op -> CountOwned()==0 (the conn was reaped, no orphan). The
// orphan-GOROUTINE half (the pump must be reaped, no subscriber left attached) is asserted
// by the surrounding goleak.VerifyNone. The probe is tagged `//go:build lifecycle` so the
// double-close/reap drive stays out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_SessionDoubleCloseIdempotentNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newSessionProbe)
}

// sessionProbe is the testing.LifecycleProbe binding for an agentsession.Session. Its
// "owned resource" is the harness connection: a countingConn that increments a live-conn
// counter at Spawn and decrements it at Close. After the session's double-Close, CountOwned
// must read zero — the conn was reaped exactly once and the orphan budget is clean.
type sessionProbe struct {
	session agentsession.Session
	conn    *countingConn
}

// newSessionProbe constructs a fresh live Session over a real Pool + a countingConn adapter,
// opened and ready. It is the testing.LifecycleFactory the driver invokes once per run.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newSessionProbe(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	conn := &countingConn{
		events:   make(chan agentsession.Event),
		commands: make(chan agentsession.Command),
		stop:     make(chan struct{}),
		done:     make(chan struct{}),
	}
	conn.live.Store(1)
	conn.start()

	adapter := &countingAdapter{conn: conn}
	const ref = "vault://eden/anthropic#lifecycle" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value
	key := agentsession.RouteKey{Role: "assistant"}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			key: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{ref: "S3CR3T-lifecycle-do-not-leak"}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      lifecycleClock{},
		},
	)
	if err != nil {
		return nil, nil, err
	}
	session, err := pool.Open(ctx, agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    key,
		Credential: secrets.Ref(ref),
	})
	if err != nil {
		return nil, nil, err
	}
	probe := &sessionProbe{session: session, conn: conn}
	// Teardown is a final best-effort Close so a failed assertion never leaks the session.
	teardown := func() { _ = probe.session.Close(context.Background()) } //nolint:errcheck // best-effort final reap; the assertions own the real Close checks.
	return probe, teardown, nil
}

// Use exercises the live session once: open a tail, prompt, and drain to terminal so the
// pump runs the full path before Close.
func (p *sessionProbe) Use(ctx context.Context) error {
	stream := p.session.Events(ctx, agentsession.FromSeq(0))
	if _, err := p.session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		return err
	}
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			return stream.Err()
		}
		if ev.IsTerminal() {
			return nil
		}
	}
}

// Close closes the session. The library guarantees Close is idempotent, so the driver's
// SECOND call must also return nil (the double-close invariant).
func (p *sessionProbe) Close(ctx context.Context) error { return p.session.Close(ctx) }

// CountOwned reports how many harness connections are still live (open). After Close it must
// be zero: the conn was reaped exactly once with no orphan.
func (p *sessionProbe) CountOwned(context.Context) (int, error) {
	return int(p.conn.live.Load()), nil
}

// ── a counting HarnessConn + Adapter (a real binding, not a mock of the library) ──────.

// countingAdapter is a minimal agentsession.Adapter whose Spawn hands back a single
// pre-built countingConn (one session per run, as the lifecycle driver needs).
type countingAdapter struct{ conn *countingConn }

func (countingAdapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{}
}

//nolint:ireturn // contract §2: Adapter.Spawn returns the HarnessConn port (the frozen lower seam).
func (a *countingAdapter) Spawn(context.Context, agentsession.Spec, agentsession.Route, agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	return a.conn, nil
}

// countingConn is a real agentsession.HarnessConn that tracks whether it is still live. It
// emits a Ready handshake, waits for the first Prompt, then a clean Result terminal, and
// reaps its driver goroutine on Close. live drops to 0 exactly once at Close.
type countingConn struct {
	events   chan agentsession.Event
	commands chan agentsession.Command
	stop     chan struct{}
	done     chan struct{}

	live      atomic.Int32
	closeOnce sync.Once
	doneOnce  sync.Once
}

func (c *countingConn) start() { go c.drive() }

func (c *countingConn) Events() <-chan agentsession.Event { return c.events }

func (c *countingConn) Send(ctx context.Context, command agentsession.Command) error {
	select {
	case c.commands <- command:
		return nil
	case <-c.done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// Close stops the driver and decrements the live-conn counter exactly once (idempotent).
func (c *countingConn) Close(context.Context) error {
	c.closeOnce.Do(func() {
		close(c.stop)
		c.live.Add(-1)
	})
	<-c.done
	return nil
}

// drive emits Ready, waits for the first Prompt (or an early stop), then a clean Result.
func (c *countingConn) drive() {
	defer c.finish()
	if !c.emit(readyState()) {
		return
	}
	for {
		select {
		case cmd := <-c.commands:
			if cmd.Kind == agentsession.CommandPrompt {
				c.emit(cleanResult())
				return
			}
		case <-c.stop:
			c.emit(cleanResult())
			return
		}
	}
}

//nolint:gocritic // Event is the contract's copyable value record (§2); the conn emits a value copy.
func (c *countingConn) emit(event agentsession.Event) bool {
	select {
	case c.events <- event:
		return true
	case <-c.stop:
		return false
	}
}

func (c *countingConn) finish() {
	c.doneOnce.Do(func() {
		close(c.events)
		close(c.done)
	})
}

func readyState() agentsession.Event {
	return agentsession.Event{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}
}

func cleanResult() agentsession.Event {
	return agentsession.Event{
		Kind: agentsession.EventResult,
		Terminal: &agentsession.TerminalPayload{
			Outcome:    agentsession.TurnCompleted,
			Ledger:     agentsession.TokenLedger{UsageMeter: agentsession.UsageMeter{Harness: "fake", Cumulative: true}, Turns: 1},
			ResultText: "done",
			StopReason: "end_turn",
		},
	}
}

// lifecycleClock is a deterministic Clock for the lifecycle harness.
type lifecycleClock struct{}

func (lifecycleClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// ── *testing.T adapters for the testing.Harness / testing.Report ports ────────────────.

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup
// and Context are exercised by AssertLifecycle; the deterministic-source accessors are part
// of the frozen 5-method port and are never called on this path. Cleanup delegates to
// *testing.T.Cleanup so the teardown runs (LIFO) at test end — keeping the goleak check at
// the top of the test honest even if an assertion fails mid-run.
type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract §2: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract §2: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
