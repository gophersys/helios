package agentsession_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// This file pins the SESSION half of contract revision R1: what ends a session, and how many
// times. Today `Session.Close` contradicts its own doc — "drain the in-flight turn, EMIT THE
// TERMINAL EVENT, then reap the process" — because the pump has no way to tell a REQUESTED
// close from a harness that died: both arrive as "the event channel closed with no terminal",
// and both synthesize EventFailed{ReasonTransport}. So a clean, deliberate Close reports a
// transport failure, and "exactly one terminal event per session" is aspirational rather than
// true. R1 makes the requested close synthesize EventResult{TurnCompleted} replaying the last
// cached turn ledger, and leaves the unbidden death exactly as it is.
//
// The turn bodies below are driven through the pump as an adapter would emit them; the
// turn-boundary kind is spelled POSITIONALLY (see eventTurnEnd) so this file compiles against
// the pre-R1 tree and every failure is behavioral.

// eventTurnEnd is the EventKind contract revision R1 APPENDS to the taxonomy — the member
// immediately after the current last one (EventThinkingProgress), spelled positionally so this
// file compiles BEFORE the constant exists (the red-first order: a test whose failure is
// `undefined: agentsession.EventTurnEnd` proves nothing about behavior).
//
// Its identity is not assumed: TestTurnEnd_RendersTheAppendedTurnBoundaryToken (turn_test.go)
// pins this ordinal to the token "turn-end", so if Round B appends some OTHER member here the
// suite fails loudly instead of quietly testing the wrong constant.
const eventTurnEnd = agentsession.EventThinkingProgress + 1

// turnLedger is the authoritative per-turn accounting the scripted turn boundary carries. The
// requested-close terminal must replay THIS ledger — a zeroed one would mean the session's
// final accounting was lost at the very moment it is supposed to be finalized.
func turnLedger() agentsession.TokenLedger {
	return agentsession.TokenLedger{
		UsageMeter: agentsession.UsageMeter{
			Model: "claude-fable-5", Harness: "claude-code",
			InputTokens: 3944, OutputTokens: 394,
			CacheReadTokens: 56397, CacheCreationTokens: 5689,
			CostMicros: 229861, Cumulative: true,
		},
		Turns:    1,
		ToolUses: 2,
		WallTime: 16342 * time.Millisecond,
	}
}

// TestClose_RequestedCloseSynthesizesTheResultTerminal is the R1 core for the session boundary:
// after a turn has ended and the session is parked awaiting the next Prompt, a DELIBERATE Close
// must produce exactly one terminal — EventResult{TurnCompleted} carrying the last turn's
// ledger. Today the pump cannot distinguish the requested close from process death, so it
// synthesizes EventFailed{ReasonTransport} and a clean shutdown is reported as a fault.
func TestClose_RequestedCloseSynthesizesTheResultTerminal(t *testing.T) {
	t.Parallel()
	conn := newTurnConn(gracefulClose, oneTurnScript())
	session, transcriptEvents := openScriptedSession(t, conn)

	promptAndAwaitTurnBoundary(t, session)
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("Close: %v", err)
	}

	events := transcriptEvents()
	terminal := soleTerminal(t, events)
	if terminal.Kind != agentsession.EventResult {
		t.Errorf("a REQUESTED Close must synthesize EventResult, got %s (detail=%q) — a deliberate shutdown is being reported as a transport fault",
			terminal.Kind, terminalDetail(terminal))
	}
	if terminal.Terminal == nil {
		t.Fatalf("the synthesized terminal carries no TerminalPayload")
	}
	if terminal.Terminal.Outcome != agentsession.TurnCompleted {
		t.Errorf("requested-close Outcome = %v, want TurnCompleted", terminal.Terminal.Outcome)
	}
	assertLedgerReplayed(t, terminal.Terminal.Ledger)
}

// TestClose_UnbiddenDeathStaysTransportFailed is the GUARD half: a harness whose event channel
// closes on its own — process death, a stdio drop — is STILL EventFailed{ReasonTransport}.
// It passes today and must keep passing: without it, R1 could be satisfied by calling every
// channel close a clean result, which would report a crashed agent as a successful run.
func TestClose_UnbiddenDeathStaysTransportFailed(t *testing.T) {
	t.Parallel()
	conn := newTurnConn(unbiddenDeath, oneTurnScript())
	session, transcriptEvents := openScriptedSession(t, conn)

	promptAndAwaitTurnBoundary(t, session)
	// The conn's driver exits on its own after the scripted turn: no Close was requested.
	awaitStreamEnd(t, session)

	terminal := soleTerminal(t, transcriptEvents())
	if terminal.Kind != agentsession.EventFailed {
		t.Fatalf("an UNBIDDEN channel close must stay EventFailed, got %s", terminal.Kind)
	}
	if terminal.Terminal == nil || terminal.Terminal.Reason != agentsession.ReasonTransport {
		t.Errorf("unbidden death reason = %+v, want ReasonTransport", terminal.Terminal)
	}
	if terminal.Terminal != nil && terminal.Terminal.Outcome != agentsession.TurnFailed {
		t.Errorf("unbidden death Outcome = %v, want TurnFailed", terminal.Terminal.Outcome)
	}
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("Close after unbidden death: %v", err)
	}
	// The post-mortem Close must not append a SECOND terminal.
	soleTerminal(t, transcriptEvents())
}

// TestClose_ExactlyOneTerminalPerSession pins the invariant the contract states and R1 finally
// makes true: whatever path a session ends by, its durable transcript carries EXACTLY ONE
// terminal event, and it is the LAST event. A double Close must not append another.
func TestClose_ExactlyOneTerminalPerSession(t *testing.T) {
	t.Parallel()
	conn := newTurnConn(gracefulClose, oneTurnScript())
	session, transcriptEvents := openScriptedSession(t, conn)

	promptAndAwaitTurnBoundary(t, session)
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("first Close: %v", err)
	}
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("second Close must be idempotent: %v", err)
	}

	events := transcriptEvents()
	terminal := soleTerminal(t, events)
	if last := events[len(events)-1]; last.Seq != terminal.Seq {
		t.Errorf("the terminal is at Seq %d but the last event is %s at Seq %d; nothing may follow the terminal",
			terminal.Seq, last.Kind, last.Seq)
	}
}

// ── the scripted turn conn (shared with turn_test.go) ────────────────────────────────────.

// closeMode selects how the scripted conn's event channel ends: on a REQUESTED Close (the
// graceful ladder a real adapter runs) or on its own, mid-session (process death).
type closeMode int

const (
	gracefulClose closeMode = iota // the channel closes only after conn.Close is called
	unbiddenDeath                  // the channel closes by itself once the script is exhausted
)

// turnConn is a hand-written agentsession.HarnessConn that emits ONE scripted body per Prompt
// — the multi-turn shape a post-R1 adapter produces. It exists in this package (rather than
// reusing agentsessiontest's fake) because the R1 behavior under test is precisely how the
// PUMP reacts to a turn-boundary event and to the way the channel closes, and both must be
// controlled exactly.
//
// Concurrency: one driver goroutine owns the outbound channel. Send is called by the session's
// control path under its sendMu; Close is idempotent and reaps the driver.
type turnConn struct {
	events   chan agentsession.Event
	commands chan agentsession.Command
	stop     chan struct{}
	done     chan struct{}

	mode  closeMode
	turns [][]agentsession.Event

	closeOnce sync.Once
	doneOnce  sync.Once
}

// newTurnConn builds and starts a scripted conn over one body per turn.
func newTurnConn(mode closeMode, turns ...[]agentsession.Event) *turnConn {
	conn := &turnConn{
		events:   make(chan agentsession.Event),
		commands: make(chan agentsession.Command),
		stop:     make(chan struct{}),
		done:     make(chan struct{}),
		mode:     mode,
		turns:    turns,
	}
	go conn.drive()
	return conn
}

func (c *turnConn) Events() <-chan agentsession.Event { return c.events }

// Send hands a control frame to the driver, dropping it once the driver has stopped so a late
// frame never deadlocks the caller.
func (c *turnConn) Send(ctx context.Context, command agentsession.Command) error {
	select {
	case c.commands <- command:
		return nil
	case <-c.done:
		return nil
	case <-ctx.Done():
		return nil
	}
}

// Close is the graceful ladder: signal the driver to stop, wait for it to finish. Idempotent.
func (c *turnConn) Close(context.Context) error {
	c.closeOnce.Do(func() { close(c.stop) })
	<-c.done
	return nil
}

// drive emits the Ready handshake, then one scripted body per Prompt. When the script is
// exhausted it either parks until Close (gracefulClose) or exits immediately (unbiddenDeath).
func (c *turnConn) drive() {
	defer c.finish()
	if !c.emit(agentsession.Event{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}) {
		return
	}
	for _, body := range c.turns {
		if !c.awaitPrompt() {
			return
		}
		for i := range body {
			if !c.emit(body[i]) {
				return
			}
		}
	}
	if c.mode == unbiddenDeath {
		return // the harness process dies with the session mid-flight: no terminal, no warning
	}
	<-c.stop // park alive, awaiting the next Prompt, until the session is deliberately Closed
}

// awaitPrompt blocks for the next Prompt frame, returning false if the conn was stopped first.
func (c *turnConn) awaitPrompt() bool {
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

//nolint:gocritic // Event is the contract's copyable value record (§2); the conn emits a value copy.
func (c *turnConn) emit(event agentsession.Event) bool {
	select {
	case c.events <- event:
		return true
	case <-c.stop:
		return false
	}
}

func (c *turnConn) finish() {
	c.doneOnce.Do(func() {
		close(c.events)
		close(c.done)
	})
}

// compile-time assertion: *turnConn is an agentsession.HarnessConn.
var _ agentsession.HarnessConn = (*turnConn)(nil)

// scriptedAdapter hands the one pre-built turnConn to the single session under test.
type scriptedAdapter struct{ conn *turnConn }

func (scriptedAdapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer: agentsession.CapFull,
	}}
}

//nolint:ireturn // contract §2: Adapter.Spawn returns the HarnessConn port (the frozen lower seam).
func (a scriptedAdapter) Spawn(context.Context, agentsession.Spec, agentsession.Route, agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	return a.conn, nil
}

// ── scripts + assertions ─────────────────────────────────────────────────────────────────.

// turnBody is ONE complete assistant turn as a post-R1 adapter emits it: the message opens,
// text streams, and the TURN BOUNDARY closes it carrying that turn's authoritative ledger.
//
// It deliberately carries NO EventMessageEnd. MessageEnd already parks Running->AwaitingInput
// today, so a body containing one would park the session for a reason that has nothing to do
// with R1 — the follow-up Prompt would be legal even on the unfixed tree and the test would
// prove nothing. Leaving it out makes the turn boundary the ONLY thing that can end the turn,
// which is exactly the edge R1 adds.
func turnBody(text string) []agentsession.Event {
	return []agentsession.Event{
		{Kind: agentsession.EventMessageStart, Message: &agentsession.MessagePayload{Role: "assistant"}},
		{Kind: agentsession.EventTextDelta, Message: &agentsession.MessagePayload{Role: "assistant", Delta: text}},
		{
			Kind: eventTurnEnd,
			Terminal: &agentsession.TerminalPayload{
				Outcome: agentsession.TurnCompleted, Ledger: turnLedger(),
				ResultText: text, StopReason: "end_turn",
			},
		},
	}
}

// oneTurnScript is a single scripted turn.
func oneTurnScript() []agentsession.Event { return turnBody("the answer") }

// recordingTranscript is a mutex-guarded in-memory agentsession.Transcript whose whole
// contents these tests read back after the session ends. It is separate from this package's
// other in-memory transcript because the assertions here read the record from the TEST
// goroutine while the pump writes it from its own, so the snapshot must be guarded.
type recordingTranscript struct {
	mu     sync.Mutex
	events map[string][]agentsession.Event
}

func newRecordingTranscript() *recordingTranscript {
	return &recordingTranscript{events: make(map[string][]agentsession.Event)}
}

//nolint:gocritic // contract §2: Transcript.Append takes the Event value (the immutable record; the fake mirrors the frozen seam).
func (r *recordingTranscript) Append(_ context.Context, event agentsession.Event) (uint64, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	existing := r.events[event.SessionID]
	seq := uint64(len(existing)) + 1
	event.Seq = seq
	r.events[event.SessionID] = append(existing, event)
	return seq, nil
}

//nolint:ireturn // contract §2: Transcript.ReadFrom returns the Stream port (the frozen replay seam).
func (r *recordingTranscript) ReadFrom(_ context.Context, sessionID string, from agentsession.Cursor) (agentsession.Stream, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	stored := r.events[sessionID]
	start := min(max(int(from), 0), len(stored)) // #nosec G115 -- a bounded replay cursor, clamped here
	snapshot := make([]agentsession.Event, len(stored)-start)
	copy(snapshot, stored[start:])
	return &memStream{events: snapshot}, nil
}

// snapshot returns every event recorded across the (single) session under test, in Seq order.
func (r *recordingTranscript) snapshot() []agentsession.Event {
	r.mu.Lock()
	defer r.mu.Unlock()
	var out []agentsession.Event
	for _, events := range r.events {
		out = append(out, events...)
	}
	return out
}

// openScriptedSession opens a live session over the scripted conn and returns it plus a reader
// of the DURABLE transcript (the authoritative Seq-ordered record every viewer replays).
//
//nolint:ireturn // contract §2: Factory.Open returns the Session port; the helper mirrors the frozen seam.
func openScriptedSession(t *testing.T, conn *turnConn) (session agentsession.Session, transcriptEvents func() []agentsession.Event) {
	t.Helper()
	const reference = "vault://eden/anthropic#setup-token"
	transcript := newRecordingTranscript()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "claude-code", Model: "claude-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": scriptedAdapter{conn: conn}},
			Secrets:    secretstest.New(map[string]string{reference: "S3CR3T"}),
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	session, err = pool.Open(context.Background(), agentsession.Spec{
		Workspace:  "/workspace",
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(reference),
	})
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.
	return session, transcript.snapshot
}

// promptAndAwaitTurnBoundary fires one Prompt and reads the live tail until the turn's boundary
// event (the one carrying the turn's TerminalPayload) has been published.
func promptAndAwaitTurnBoundary(t *testing.T, session agentsession.Session) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("the stream ended before the turn boundary: %v", stream.Err())
		}
		if event.Terminal != nil {
			return
		}
	}
}

// awaitStreamEnd reads the live tail to its end (the pump's terminal), bounded so a regression
// fails fast instead of hanging the lane.
func awaitStreamEnd(t *testing.T, session agentsession.Session) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return
		}
		if event.IsTerminal() {
			return
		}
	}
}

// soleTerminal asserts the transcript carries EXACTLY ONE terminal event and returns it.
func soleTerminal(t *testing.T, events []agentsession.Event) agentsession.Event {
	t.Helper()
	var terminals []agentsession.Event
	for i := range events {
		if events[i].IsTerminal() {
			terminals = append(terminals, events[i])
		}
	}
	if len(terminals) != 1 {
		t.Fatalf("a session must carry EXACTLY ONE terminal event, got %d: %v (full stream: %v)",
			len(terminals), kindsOf(terminals), kindsOf(events))
	}
	return terminals[0]
}

// assertLedgerReplayed asserts the synthesized terminal carries the LAST TURN's accounting.
// TokenLedger embeds a map (ToolUsesByName), so the scalar accounting is compared instead.
//
//nolint:gocritic // TokenLedger is the contract's copyable value record (§2); this helper takes it by value.
func assertLedgerReplayed(t *testing.T, got agentsession.TokenLedger) {
	t.Helper()
	want := turnLedger()
	if got.UsageMeter != want.UsageMeter || got.Turns != want.Turns ||
		got.ToolUses != want.ToolUses || got.WallTime != want.WallTime {
		t.Errorf("the requested-close terminal must replay the last turn's ledger: got %+v, want %+v", got, want)
	}
}

// terminalDetail renders a terminal's diagnostic detail for a failure message.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this helper takes it by value.
func terminalDetail(event agentsession.Event) string {
	if event.Terminal == nil {
		return ""
	}
	return event.Terminal.Detail
}

// kindsOf projects the event kinds for a failure message.
func kindsOf(events []agentsession.Event) []string {
	out := make([]string, 0, len(events))
	for i := range events {
		out = append(out, events[i].Kind.String())
	}
	return out
}
