//go:build integration

// Package ompadapter_test's integration arm exercises the REAL os/exec subprocess lifecycle
// and the REAL omp json parser on an ACTUAL process — a trivial scripted stub binary
// (internal/stubharness), NOT omp — so the spawn/scan/Close ladder is proven on a genuine
// process WITHOUT a live OpenRouter call. The credential is a FAKE secret (a canary), threaded
// through Secret.Use exactly as production does, asserted never to leak.
//
// There is NO live-omp arm in this lane, by Mateo's ruling of 2026-08-26 (verbatim: "skip the
// omp, as lomg as claude works thats waht we really actaulyl acre about"). What `-tags
// integration` gates is the omp PROTOCOL — these real-subprocess arms plus the parser
// conformance fixtures — and, in the sibling claudeadapter package, claude's live arms. The REAL
// `omp` TURN lives in the harness lane instead: `agentsession/omp_turn_harness_test.go`, under
// `//go:build harness`, run on demand by `ctl.sh harness` with the vendor credentials. It fails
// there today because of task #24 (omp 17.2.5 bursts and then never writes `agent_end`), which
// is the honest result for an acceptance lane and is why it does not belong in a gate lane.
//
//	go test -tags integration ./ompadapter/... -race
//
// Everything is reaped on t.Cleanup.
package ompadapter_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets"
)

// The shared REAL-subprocess scaffolding (fakeCanary, vaultReference, buildStub, newPool,
// newPoolWithKey, drainTerminal, readyObserved, kindObserved, integrationClock) lives in
// harness_helpers_test.go, compiled for this lane and the lifecycle/load lanes alike.

// TestIntegration_StubBinary_RealSubprocessLifecycle spawns the REAL os/exec stub process
// through the omp adapter's genuine Spawn path, drives Open -> Prompt -> drain to the TURN
// BOUNDARY, and asserts: the Ready handshake reached the library, the assistant thinking/text +
// tool start/update/end frames parsed, the unknown rate_limit_event survived as Extension
// through a real pipe, the boundary carried the four-token ledger with the cost converted with
// no float drift, Seq is monotonic, and the credential canary never leaked. Reaped on Cleanup.
//
// One Prompt draws one TURN boundary. The one long-lived `omp --mode rpc` process does NOT exit
// at turn end — it survives every turn, and the SESSION accepts the next Prompt on the same conn.
// The three-Prompt proof over that conn is its multi-turn sibling (multiturn_integration_test.go).
func TestIntegration_StubBinary_RealSubprocessLifecycle(t *testing.T) {
	t.Parallel()
	stub := buildStub(t)

	adapter := ompadapter.MustNewForTest(t, ompadapter.Config{Binary: stub})
	pool := newPool(t, adapter)

	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-read", Tool: "read", ReadOnly: true}},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		t.Fatalf("Open over the stub subprocess: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "read the file"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}

	events, drainErr := drainToTurnBoundary(session)
	if drainErr != nil {
		t.Fatal(drainErr)
	}
	if len(events) == 0 {
		t.Fatal("the stub subprocess produced no events")
	}
	assertSubprocessKinds(t, events)
	assertSubprocessBoundaryLedger(t, events[len(events)-1])
	assertSubprocessSeqAndNoLeak(t, events)
}

// assertSubprocessKinds proves the real subprocess stream parsed into the expected kinds.
func assertSubprocessKinds(t *testing.T, events []agentsession.Event) {
	t.Helper()
	if !readyObserved(events) {
		t.Errorf("the omp adapter did not produce the Ready handshake")
	}
	if !kindObserved(events, agentsession.EventExtension) {
		t.Errorf("the rate_limit_event must survive as Extension through a real subprocess")
	}
	if !kindObserved(events, agentsession.EventThinkingDelta) {
		t.Errorf("the omp thinking_delta did not parse into EventThinkingDelta")
	}
	if !kindObserved(events, agentsession.EventTextDelta) {
		t.Errorf("the omp text_delta did not parse into EventTextDelta")
	}
	if !kindObserved(events, agentsession.EventToolStart) || !kindObserved(events, agentsession.EventToolUpdate) || !kindObserved(events, agentsession.EventToolEnd) {
		t.Errorf("the omp tool_execution frames did not parse into ToolStart/Update/End")
	}
	if !kindObserved(events, agentsession.EventUsage) {
		t.Errorf("the omp usage block did not parse into EventUsage")
	}
}

// assertSubprocessBoundaryLedger proves the TURN boundary carries the four-token ledger and the
// cost converted with no float drift (0.0123 USD -> 12300 micros) — and that it ends the TURN,
// not the session (R1: the conn accepts the next Prompt and execs omp again).
func assertSubprocessBoundaryLedger(t *testing.T, boundary agentsession.Event) { //nolint:gocritic // Event is the contract's copyable value record (§2); this test helper takes it by value.
	t.Helper()
	if boundary.Terminal == nil {
		t.Fatalf("the real subprocess turn did not end on a boundary carrying a ledger (last kind %s)", boundary.Kind)
	}
	if boundary.IsTerminal() {
		t.Fatalf("the real subprocess turn ended the SESSION (kind %s); a clean `agent_end` is a TURN boundary", boundary.Kind)
	}
	if got := boundary.Kind.String(); got != turnEndToken {
		t.Errorf("turn-boundary token = %q, want %q", got, turnEndToken)
	}
	ledger := boundary.Terminal.Ledger
	if ledger.InputTokens == 0 || ledger.OutputTokens == 0 || ledger.CacheReadTokens == 0 || ledger.CacheCreationTokens == 0 {
		t.Errorf("terminal ledger missing token kinds: %+v", ledger)
	}
	if ledger.CostMicros != 12300 {
		t.Errorf("CostMicros = %d, want 12300 (0.0123 USD)", ledger.CostMicros)
	}
	if ledger.Harness != "omp" {
		t.Errorf("ledger harness = %q, want omp", ledger.Harness)
	}
}

// assertSubprocessSeqAndNoLeak proves Seq is monotonic + gap-free and the credential canary
// never leaked onto the real-subprocess stream.
func assertSubprocessSeqAndNoLeak(t *testing.T, events []agentsession.Event) {
	t.Helper()
	var prev uint64
	for i := range events {
		if events[i].Seq != prev+1 {
			t.Fatalf("event %d Seq = %d, want %d", i, events[i].Seq, prev+1)
		}
		prev = events[i].Seq
	}
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], fakeCanary)
	}
}

// TestIntegration_StubBinary_CloseReapsBetweenTurns proves the Close ladder reaps the conn
// without a hang even when Close is called before any Prompt (no in-flight process), and is
// idempotent.
func TestIntegration_StubBinary_CloseReapsBetweenTurns(t *testing.T) {
	t.Parallel()
	stub := buildStub(t)
	adapter := ompadapter.MustNewForTest(t, ompadapter.Config{Binary: stub})
	pool := newPool(t, adapter)

	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := session.Close(ctx); err != nil {
		t.Errorf("Close errored: %v", err)
	}
	if err := session.Close(context.Background()); err != nil {
		t.Errorf("second Close must be idempotent: %v", err)
	}
}
