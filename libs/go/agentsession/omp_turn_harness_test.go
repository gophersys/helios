//go:build harness

package agentsession_test

import (
	"context"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The REAL-omp TURN-BOUNDARY acceptance, moved here from the ompadapter integration lane.
//
// It is NOT one of the lettered peer obligations (A/B/C, design §9.2) — it is the adapter-level
// proof that one live `omp --mode rpc` turn reaches a turn boundary carrying a ledger, against
// the real binary and a real model. It belongs in THIS lane and only this lane: the harness lane
// is the on-demand acceptance verb (`ctl.sh harness`), it holds the vendor credentials, it runs
// in NO CI job today, and it has ZERO skip path by construction — a missing credential or a
// missing binary is a t.Fatalf naming it.
//
// It is EXPECTED TO FAIL today, and that is the correct behaviour for an acceptance lane.
// omp 17.2.5 emits its burst (last frame an `extension`) and then never writes `agent_end`: 8m
// of silence after a 2.881s max inter-event gap, measured in eden run 33012361974. The protocol
// is proven correct locally end-to-end against the pinned binary, so the defect is upstream —
// TASK #24: omp defers the wire `agent_end` while promptInFlightCount > 0
// (`agent-session.ts:1963-1971`) and the release never fires. An acceptance run should say that
// out loud rather than report a pass, so this test carries no XFAIL branch and no skip. When #24
// lands, this is the test that turns green and proves it.
//
// The integration lane carries NO live-omp arm at all. That lane gates `-tags integration`
// (claude's live arms, the omp stub-subprocess arms, and the parser conformance fixtures); the
// live omp TURN lives here. Mateo's ruling, 2026-08-26, verbatim: "skip the omp, as lomg as
// claude works thats waht we really actaulyl acre about".

// The live-drain clocks, carried over unchanged from ompadapter's `liveDrainBounds` (libs #33).
//
// Two INDEPENDENT clocks, because an absolute total alone cannot tell a harness that is
// streaming steadily from one that is dead — CI proved that twice (eden runs 32935203884 and
// 32998558460, both on PROGRESSING harnesses). Idle is the longest a real turn may go silent
// BETWEEN events; the cap is the absolute safety net.
//
// The figures are #33's and are deliberately NOT re-tightened here. #33 opened Idle to 8m as a
// diagnostic widening because no run had ever observed a live omp turn boundary and the true
// pre-boundary gap had never been measured — and it still has not, because of #24. Re-tightening
// from the 2.881s max INTER-EVENT gap would be bounding the burst, not the wait before
// `agent_end`. The cost is real and is accepted: while #24 stands, this test burns the full idle
// window before it fails. The first PASSING run is what finally re-tightens Idle, in a PR that
// quotes it.
const (
	ompLiveIdleBound   = 8 * time.Minute
	ompLiveAbsoluteCap = 10 * time.Minute
)

// TestHarness_OmpLiveTurnReachesItsBoundary drives ONE real omp turn end to end against the
// pinned binary and the operator's OpenRouter route: Open -> Prompt -> drain to a TURN boundary,
// then assert the boundary carries a ledger attributed to omp, that the Ready handshake reached
// the library, and that the credential appears in NO event. The key is NEVER logged.
//
// Contract revision R1: a live turn ends on a TURN boundary and the SESSION stays alive for the
// next Prompt, so what proves the turn completed is the boundary payload, not a session terminal.
func TestHarness_OmpLiveTurnReachesItsBoundary(t *testing.T) {
	// RequireLiveCredential FAILS naming the variable; it never skips. The plaintext is bound here
	// because the no-leak sweep at the end needs something to search the stream for.
	key := agentsessiontest.RequireLiveCredential(t, openRouterKey)
	requirePinnedBinary(t, "omp")
	session := openLiveOmpTurnSession(t, key)

	if _, err := session.Control(context.Background(), agentsession.Command{
		Kind: agentsession.CommandPrompt,
		Text: "Reply with exactly: ok",
	}); err != nil {
		t.Fatalf("live omp Prompt: %v", err)
	}

	events, drainErr := awaitOmpTurnBoundary(session, ompLiveIdleBound, ompLiveAbsoluteCap)
	if drainErr != nil {
		t.Fatalf("live omp turn: %v", drainErr)
	}
	boundary := &events[len(events)-1]
	if boundary.Terminal == nil {
		t.Fatalf("the live omp turn drew no boundary carrying a ledger; last = %s", boundary.Kind)
	}
	if boundary.IsTerminal() {
		t.Fatalf("the live omp turn ended the SESSION (kind %s, Detail %q); a clean `agent_end` is a TURN boundary — check the OpenRouter credit/route if the stop was an error",
			boundary.Kind, boundary.Terminal.Detail)
	}
	if boundary.Kind != agentsession.EventTurnEnd {
		t.Fatalf("live turn-boundary kind = %s (Detail %q), want %s — check the OpenRouter credit/route",
			boundary.Kind, boundary.Terminal.Detail, agentsession.EventTurnEnd)
	}
	ledger := boundary.Terminal.Ledger
	if ledger.InputTokens == 0 && ledger.OutputTokens == 0 {
		t.Errorf("live turn-boundary ledger is empty: %+v", ledger)
	}
	if ledger.Harness != "omp" {
		t.Errorf("live ledger harness = %q, want omp", ledger.Harness)
	}
	if !readyHandshakeObserved(events) {
		t.Errorf("live omp did not produce the Initializing->Ready handshake")
	}
	// Redaction by construction, swept over the REAL stream. The key is never passed to a log or
	// an assertion message.
	agentsessiontest.AssertNoSecretInStream(t, events, key)

	t.Logf("live omp turn boundary: kind=%s result=%q tokens(in/out)=%d/%d costMicros=%d",
		boundary.Kind, boundary.Terminal.ResultText, ledger.InputTokens, ledger.OutputTokens, ledger.CostMicros)
}

// openLiveOmpTurnSession builds a REAL omp pool routed at the model the #24 evidence was
// gathered on, opens one session on a per-session t.TempDir workspace (MANDATORY: <ws>/.omp-session
// collides otherwise) under a cost ceiling, and reaps it on Cleanup.
//
// It deliberately does NOT use this lane's shared liveOmpPool/openLivePeer pair. Those wire the
// PEER plane and pin Route.Model to the placeholder "live", which ompadapter passes straight
// through as `omp --model live`. For the peer obligations the model barely matters; for THIS test
// it is the whole point — a wrong model fails the turn for a reason that is NOT #24, and a
// misdiagnosed acceptance failure is worse than no test. The model below is the one the deleted
// integration arm drove and the one eden run 33012361974 measured. This test needs no peer plane,
// so it opens none.
//
//nolint:ireturn // Session is the frozen port Pool.Open returns; a test helper can only re-surface it.
func openLiveOmpTurnSession(t *testing.T, key string) agentsession.Session {
	t.Helper()
	adapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		t.Fatalf("ompadapter.New: %v", err)
	}
	// The same opaque vault reference the rest of this lane uses; the key is resolved through the
	// real Secret seam, never minted or logged here.
	const vaultReference = "vault://eden/live#token"
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "omp", Model: "openrouter/deepseek/deepseek-v4-flash"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"omp": adapter},
			Secrets:    secretstest.New(map[string]string{vaultReference: key}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      harnessClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Budget:     agentsession.Budget{MaxCostMicros: 2_000_000},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		t.Fatalf("live omp Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap.
	return session
}

// awaitOmpTurnBoundary drains a live session's stream to the end of its FIRST TURN under the two
// clocks above, returning every event seen. It stops on the boundary PAYLOAD (`Terminal != nil`),
// which is the same event on both sides of contract revision R1.
//
// Every exit that is not a boundary is an error that NAMES which clock ended the drain and how
// far the drain got, because the whole diagnostic value of an acceptance failure is the
// difference between "streamed to the last millisecond" and "burst, then silence" — and #24 is
// the second. The order of the three checks is load-bearing: a stream fault first, then the
// ABSOLUTE cap (whose expiry cancels the per-wait child too, so reading the child first would
// report every cap as an idle window), then the idle window.
//
// It returns an error rather than taking a *testing.T and calling t.Fatalf. That is not a style
// preference: libs #32 shipped the ompadapter twin with a *testing.T, and its bound branches
// "could not be reached by any test, and it shipped unproven". The error return is what lets
// TestOmpTurnDrain_* below drive all three exits on sub-second fixtures.
//
// This is a lane-local spelling of a drain that ompadapter and claudeadapter each also carry in
// their integration lanes. Consolidating the three into one shipped home is an open follow-up
// from libs #32; it is not done here because this change is a test MOVE, not a refactor.
func awaitOmpTurnBoundary(session agentsession.Session, idle, absoluteCap time.Duration) ([]agentsession.Event, error) {
	totalCtx, cancelTotal := context.WithTimeout(context.Background(), absoluteCap)
	defer cancelTotal()
	stream := session.Events(totalCtx, agentsession.FromSeq(0))

	started := time.Now()
	lastEvent := started
	var events []agentsession.Event
	for {
		// A FRESH child per wait, cancelled the moment Next returns: that is what makes an
		// arriving event reset the inactivity clock, so a slow-but-progressing turn survives.
		waitCtx, cancelWait := context.WithTimeout(totalCtx, idle)
		event, ok := stream.Next(waitCtx)
		cancelWait()
		if !ok {
			return events, ompDrainFault(stream, totalCtx.Err(), idle, absoluteCap, describeOmpDrain(events, lastEvent, started))
		}
		events = append(events, event)
		lastEvent = time.Now()
		if event.Terminal != nil || event.IsTerminal() {
			return events, nil
		}
	}
}

// ompDrainFault classifies an ended wait in the one order that cannot mislabel a bound. progress
// is rendered by the caller, at the instant the wait ended, so the `last event ... ago` figure is
// not inflated by the time this classification takes.
func ompDrainFault(stream agentsession.Stream, capExpiry error, idle, absoluteCap time.Duration, progress string) error {
	if err := stream.Err(); err != nil {
		return fmt.Errorf("live omp stream fault: %w; %s", err, progress)
	}
	if capExpiry != nil {
		return fmt.Errorf("live omp drew no turn boundary within the %s ABSOLUTE cap: %s; the cap bounds the WHOLE drain and measures no liveness — the `last =` figure separates a streaming harness from a silent one",
			absoluteCap, progress)
	}
	return fmt.Errorf("live omp produced no event for %s (the IDLE bound): %s; burst-then-silence is the TASK #24 signature — omp defers the wire `agent_end` while promptInFlightCount > 0 and never releases it",
		idle, progress)
}

// describeOmpDrain renders how far a drain got, for a failure message. Below one event it says
// nothing ever arrived rather than naming a last event that does not exist.
func describeOmpDrain(events []agentsession.Event, lastEvent, started time.Time) string {
	elapsed := time.Since(started).Round(time.Millisecond)
	if len(events) == 0 {
		return fmt.Sprintf("0 event(s) seen — nothing ever arrived, %s elapsed", elapsed)
	}
	return fmt.Sprintf("%d event(s) seen, last = %s %s ago, %s elapsed",
		len(events), events[len(events)-1].Kind,
		time.Since(lastEvent).Round(time.Millisecond), elapsed)
}

// readyHandshakeObserved reports whether the stream carries the Initializing->Ready transition.
func readyHandshakeObserved(events []agentsession.Event) bool {
	for i := range events {
		event := &events[i]
		if event.Kind == agentsession.EventSessionState && event.State != nil && event.State.To == agentsession.StateReady {
			return true
		}
	}
	return false
}

// ── the drain's own bound branches, proven on sub-second fixtures ─────────────────────────────
//
// These live in the harness lane because awaitOmpTurnBoundary does, and they need NO credential
// and NO vendor binary: they drive the SCRIPTED fake and finish in under a second. libs #32
// recorded the reason they exist — its ompadapter twin took a *testing.T, so "that branch could
// not be reached by any test, and it shipped unproven". A bound message is the entire diagnostic
// value of an acceptance failure; an unproven one is a guess.

// promptedScriptedSession opens a session over the scripted fake and sends the first Prompt, so
// the harness is actually streaming when the drain under test faces it. The fake holds its script
// until a Prompt arrives (agentsessiontest fakeConn.awaitFirstPrompt).
//
//nolint:ireturn // Session is the frozen port Pool.Open returns; a test helper can only re-surface it.
func promptedScriptedSession(t *testing.T, script []agentsession.Event) agentsession.Session {
	t.Helper()
	session, _ := openScripted(t, script)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("prompt the fake: %v", err)
	}
	return session
}

// TestOmpTurnDrain_SilentHarnessTripsTheIdleBound is the #24 shape in miniature: a harness that
// emits a burst and then goes quiet forever. The fake streams its script the instant the pump
// reads it and then blocks in its service loop, so the gap after the last event is unbounded.
// The idle window must end the drain, name ITSELF rather than the cap, and carry enough of the
// stream state that a reader sees burst-then-silence instead of guessing.
func TestOmpTurnDrain_SilentHarnessTripsTheIdleBound(t *testing.T) {
	t.Parallel()
	const (
		idleWindow = 300 * time.Millisecond
		// The fixture is fully determined, so these are LITERALS on purpose: asserting
		// fmt.Sprintf("%d event(s) seen", len(events)) against a message built from the SAME slice
		// is tautological and would hold for any value.
		expectedEvents   = 4 // the 2 handshake state events + the 2 scripted extensions
		expectedLastKind = "extension"
	)
	session := promptedScriptedSession(t, []agentsession.Event{
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
	})

	events, drainErr := awaitOmpTurnBoundary(session, idleWindow, 20*time.Second)
	if drainErr == nil {
		t.Fatalf("a harness that went silent drained cleanly; got %d event(s)", len(events))
	}
	if len(events) != expectedEvents {
		t.Fatalf("the fixture drained %d event(s), want %d; the literals below no longer describe it", len(events), expectedEvents)
	}
	message := drainErr.Error()
	if !strings.Contains(message, "the IDLE bound") {
		t.Fatalf("the error does not name the IDLE bound: %v", drainErr)
	}
	// "ABSOLUTE cap" without the article: the cap message interpolates its value between the two
	// ("the 300ms ABSOLUTE cap"), so asserting "the ABSOLUTE cap" here would match nothing under
	// any implementation — a negative check that cannot fire. Caught by running it: the first
	// spelling passed this test while the cap test failed on the identical literal.
	if strings.Contains(message, "ABSOLUTE cap") {
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
	if !strings.Contains(message, "TASK #24") {
		t.Fatalf("the idle message does not point at task #24, which is the whole reason an acceptance reader is looking at it: %v", drainErr)
	}
}

// TestOmpTurnDrain_ExpiredCapIsReportedAsTheCapNotTheIdleWindow pins the classification ORDER,
// which is the one thing about this drain that is easy to get silently wrong. The absolute cap's
// expiry ALSO cancels the per-wait child context, so a classifier that read the child first would
// report every cap trip as an idle window. The cap here is deliberately SHORTER than the idle
// window, so only the correct order produces the correct name.
func TestOmpTurnDrain_ExpiredCapIsReportedAsTheCapNotTheIdleWindow(t *testing.T) {
	t.Parallel()
	const absoluteCap = 300 * time.Millisecond
	session := promptedScriptedSession(t, []agentsession.Event{
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
	})

	events, drainErr := awaitOmpTurnBoundary(session, 20*time.Second, absoluteCap)
	if drainErr == nil {
		t.Fatalf("a session that drew no turn boundary drained cleanly; got %d event(s)", len(events))
	}
	message := drainErr.Error()
	if !strings.Contains(message, "ABSOLUTE cap") {
		t.Fatalf("the error does not name the ABSOLUTE cap: %v", drainErr)
	}
	if strings.Contains(message, "the IDLE bound") {
		t.Fatalf("a cap expiry was reported against the IDLE bound — the classification order is inverted: %v", drainErr)
	}
	if !strings.Contains(message, absoluteCap.String()) {
		t.Fatalf("the error does not carry the absolute cap value %s: %v", absoluteCap, drainErr)
	}
}

// TestOmpTurnDrain_ReturnsOnTheTurnBoundary is the other half of the contract: a drain that never
// returned on a boundary would turn every real turn into a bound trip. It stops on the boundary
// PAYLOAD, not on a session terminal — contract revision R1.
func TestOmpTurnDrain_ReturnsOnTheTurnBoundary(t *testing.T) {
	t.Parallel()
	session := promptedScriptedSession(t, []agentsession.Event{
		agentsessiontest.Extension([]byte(`{"type":"rate_limit_event"}`)),
		agentsessiontest.Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{Harness: "omp", Cumulative: true},
			Turns:      1,
		}, "ok", "end_turn"),
	})

	events, drainErr := awaitOmpTurnBoundary(session, 20*time.Second, 30*time.Second)
	if drainErr != nil {
		t.Fatalf("a harness that drew a turn boundary tripped a bound: %v", drainErr)
	}
	if len(events) == 0 {
		t.Fatal("the scripted harness produced no events")
	}
	if events[len(events)-1].Terminal == nil {
		t.Fatalf("the drain ended on %s, which carries no boundary payload (%d event(s) seen)",
			events[len(events)-1].Kind, len(events))
	}
}
