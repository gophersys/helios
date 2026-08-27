//go:build integration

// Package claudeadapter_test's integration arm exercises the REAL os/exec subprocess
// lifecycle and the REAL stream-json parser on an ACTUAL process — a trivial scripted stub
// binary (internal/stubharness), NOT claude — so the spawn/scan/Close ladder is proven on
// a genuine process WITHOUT a live authenticated claude. The credential is a FAKE secret
// (a canary), threaded through Secret.Use exactly as production does, asserted never to
// leak. A SEPARATE, GATED test drives the real `claude` binary only when an external token
// is explicitly supplied (CLAUDEADAPTER_LIVE_TOKEN) — it is SKIPPED by default and never
// mints a token, never launches auth, never touches ~/.claude.
//
//	go test -tags integration ./... -race
//
// Everything is reaped on t.Cleanup.
package claudeadapter_test

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// fakeCanary is the credential plaintext the stub session resolves; it must appear in NO
// emitted Event and no recorded output (the credential-never-leaks guarantee, on a real
// process).
const fakeCanary = "STUB-FAKE-TOKEN-do-not-leak"

// TestIntegration_StubBinary_RealSubprocessLifecycle spawns the REAL os/exec stub process
// through the claude-code adapter's genuine Spawn path, drives Open -> Prompt -> drain to the
// TURN BOUNDARY, and asserts: the init handshake reached Ready, the assistant text/tool events
// parsed, the rate_limit_event survived as Extension through a real pipe, the boundary carried
// the four-token ledger, Seq is monotonic, and the credential canary never leaked.
// The process is reaped on Cleanup.
//
// Re-pinned for contract revision R1: one Prompt draws one TURN boundary, and the process stays
// alive for the next one — so what this arm reads at the end of the turn is the boundary, not a
// session terminal. The three-Prompt proof over the same process is its multi-turn sibling
// (multiturn_integration_test.go).
func TestIntegration_StubBinary_RealSubprocessLifecycle(t *testing.T) {
	t.Parallel()
	stub := buildStub(t)

	adapter := claudeadapter.MustNewForTest(t, claudeadapter.Config{Binary: stub})
	pool := newPool(t, adapter)

	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-write", Tool: "Write"}},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	})
	if err != nil {
		t.Fatalf("Open over the stub subprocess: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "make a file"}); err != nil {
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

// assertSubprocessKinds proves the real subprocess stream parsed into the expected
// kinds (Ready handshake, the surviving rate_limit_event Extension, tool start/end).
func assertSubprocessKinds(t *testing.T, events []agentsession.Event) {
	t.Helper()
	if !readyObserved(events) {
		t.Errorf("the real subprocess init line did not produce the Ready handshake")
	}
	if !kindObserved(events, agentsession.EventExtension) {
		t.Errorf("the rate_limit_event must survive as Extension through a real subprocess")
	}
	if !kindObserved(events, agentsession.EventToolStart) || !kindObserved(events, agentsession.EventToolEnd) {
		t.Errorf("the real subprocess tool_use/tool_result did not parse into ToolStart/ToolEnd")
	}
}

// assertSubprocessBoundaryLedger proves the TURN boundary carries the four-token ledger and
// the cost converted with no float drift (0.0123 USD -> 12300 micros) — and that it ends the
// TURN, not the session (R1: the process keeps reading stdin for the next Prompt).
func assertSubprocessBoundaryLedger(t *testing.T, boundary agentsession.Event) { //nolint:gocritic // Event is the contract's copyable value record (§2); this test helper takes it by value.
	t.Helper()
	if boundary.Terminal == nil {
		t.Fatalf("the real subprocess turn did not end on a boundary carrying a ledger (last kind %s)", boundary.Kind)
	}
	if boundary.IsTerminal() {
		t.Fatalf("the real subprocess turn ended the SESSION (kind %s); a success `result` is a TURN boundary", boundary.Kind)
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
}

// assertSubprocessSeqAndNoLeak proves Seq is monotonic + gap-free and the credential
// canary never leaked onto the real-subprocess stream.
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

// TestIntegration_StubBinary_AbortClosesProcess proves the graceful Close ladder reaps a
// real subprocess (close stdin -> the stub drains stdin and exits -> the conn drains). No
// leaked process: the test would hang on Close if the ladder were broken, and the context
// cancel is the backstop.
func TestIntegration_StubBinary_AbortClosesProcess(t *testing.T) {
	t.Parallel()
	stub := buildStub(t)
	adapter := claudeadapter.MustNewForTest(t, claudeadapter.Config{Binary: stub})
	pool := newPool(t, adapter)

	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	})
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	// Close immediately (before draining): the ladder must reap the process without a hang.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := session.Close(ctx); err != nil {
		t.Errorf("Close over a real subprocess errored: %v", err)
	}
	// Idempotent second close.
	if err := session.Close(context.Background()); err != nil {
		t.Errorf("second Close must be idempotent: %v", err)
	}
}

// TestIntegration_LiveClaude_Gated drives the REAL `claude` binary end-to-end — but ONLY
// when an external setup-token is explicitly provided via CLAUDEADAPTER_LIVE_TOKEN. It is
// SKIPPED by default. It NEVER mints a token, NEVER launches interactive auth, and NEVER
// reads ~/.claude: the token is taken verbatim from the env var the operator set, wrapped
// as a fake secret, and threaded through the SAME injection path. This is the wired-but-
// gated live arm the contract names; in CI without the token it is a skip, not a failure.
func TestIntegration_LiveClaude_Gated(t *testing.T) {
	t.Parallel()
	token := os.Getenv("CLAUDEADAPTER_LIVE_TOKEN")
	if token == "" {
		t.Skip("CLAUDEADAPTER_LIVE_TOKEN not set: the live authenticated claude run is gated and skipped (no token minted, no auth launched)")
	}
	if _, err := exec.LookPath("claude"); err != nil {
		t.Skip("claude binary not on PATH: skipping the live arm")
	}

	pool := newLivePool(t, token)
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-read", Tool: "Read", ReadOnly: true}},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	})
	if err != nil {
		t.Fatalf("live Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "Reply with exactly: ok"}); err != nil {
		t.Fatalf("live Prompt: %v", err)
	}
	events, drainErr := drainToTurnBoundaryWithin(session, liveDrainBounds)
	if drainErr != nil {
		t.Fatal(drainErr)
	}
	// R1: a live turn ends on a TURN boundary and the session stays alive for the next Prompt,
	// so what proves the turn completed is the boundary payload, not a session terminal.
	if len(events) == 0 || events[len(events)-1].Terminal == nil {
		t.Fatalf("live session did not reach a turn boundary")
	}
	if events[len(events)-1].IsTerminal() {
		t.Errorf("the live turn ended the SESSION (kind %s); a success `result` is a TURN boundary",
			events[len(events)-1].Kind)
	}
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], token)
	}
}

// TestIntegration_LiveClaude_PermissionRoundTrip is the load-bearing live arm for slice 5b: it
// drives a REAL claude turn that requests an OUT-OF-GRANT tool (a Bash command with NO Bash
// grant, permission-mode default) and proves the NATIVE control-channel round-trip:
//
//	(a) a real EventPermissionRequest is emitted (NOT an opaque EventExtension) — claude's
//	    can_use_tool control_request was parsed onto the Eden taxonomy;
//	(b) on Resolve(allow) the tool actually RUNS — observable as a Bash EventToolStart/ToolEnd
//	    in the stream after the decision (the decision rode the control_response, not a user turn);
//	(c) on Resolve(deny) claude is told no and does NOT run the tool — no successful Bash ToolEnd,
//	    and the model surfaces the denial.
//
// It asserts the credential never leaks. SKIPPED without CLAUDEADAPTER_LIVE_TOKEN.
func TestIntegration_LiveClaude_PermissionRoundTrip(t *testing.T) {
	t.Parallel()
	token := liveTokenOrSkip(t)

	t.Run("allow_runs_the_tool", func(t *testing.T) {
		t.Parallel()
		runLivePermissionArm(t, token, true)
	})
	t.Run("deny_blocks_the_tool", func(t *testing.T) {
		t.Parallel()
		runLivePermissionArm(t, token, false)
	})
}

// runLivePermissionArm opens a real claude session whose ONLY grant is Read (so Bash is
// out-of-grant and the default-mode + stdio control gate engages), prompts for a
// non-statically-safe Bash command (a curl with a redirect — claude cannot auto-validate it as
// safe, so it MUST ask), observes the real EventPermissionRequest, resolves it allow/deny, and
// asserts the tool ran (allow) or was blocked (deny).
func runLivePermissionArm(t *testing.T, token string, allow bool) {
	t.Helper()
	pool := newLivePool(t, token)
	// OnPermission nil == the chat HUMAN path: the request surfaces as an event we Resolve
	// out-of-band. The Read-only grant drives default mode + the stdio control sentinel.
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-read", Tool: "Read", ReadOnly: true}},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	})
	if err != nil {
		t.Fatalf("live Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	prompt := "Use the Bash tool to run exactly this command and nothing else: " +
		"curl -s https://example.com -o /tmp/eden-live-test.txt . " +
		"If you are denied permission, reply with exactly DENIED and stop."
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: prompt}); err != nil {
		t.Fatalf("live Prompt: %v", err)
	}

	// One home for the number: the ctx deadline and the bound drainStreamTo names in its failure
	// message are the same value, so a message can never quote a deadline the drain did not run under.
	const armBound = 90 * time.Second
	ctx, cancel := context.WithTimeout(context.Background(), armBound)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))

	// Phase 1: read until the REAL permission request surfaces (a genuine EventPermissionRequest,
	// not an opaque Extension — the (a) assertion, enforced inside awaitLivePermissionRequest).
	requestID, preDecision := awaitLivePermissionRequest(t, ctx, stream)

	// Phase 2: resolve the decision over the NATIVE control channel.
	decision := agentsession.Decision{Allow: allow, By: "user-live-test"}
	if _, err := session.Resolve(context.Background(), requestID, decision); err != nil {
		t.Fatalf("Resolve(allow=%v): %v", allow, err)
	}

	// Phase 3: drain to the terminal and inspect the outcome.
	rest := drainStreamTo(t, ctx, stream, armBound)
	all := append(preDecision, rest...) //nolint:gocritic // intentional fresh slice of the full event log for assertions
	for i := range all {
		agentsessiontest.AssertNoSecretInEvent(t, all[i], token)
	}

	bashRan := bashToolSucceeded(all)
	if allow {
		// (b) ALLOW: the Bash tool actually ran (a non-error tool_end) after the decision.
		if !bashRan {
			t.Errorf("on Resolve(allow) the Bash tool did not run successfully; kinds=%v", kindsOf(all))
		}
	} else {
		// (c) DENY: the Bash tool did NOT run successfully; the deny was delivered to the model.
		if bashRan {
			t.Errorf("on Resolve(deny) the Bash tool ran anyway (the deny did not reach claude); kinds=%v", kindsOf(all))
		}
	}
}

// awaitLivePermissionRequest reads the live stream until the REAL permission request surfaces,
// returning its request id plus the events seen before the decision (for the no-secret-leak
// sweep). It enforces the (a) assertion inline: a can_use_tool that leaked as an opaque
// EventExtension is the pre-fix bug and fails the test. Extracted from runLivePermissionArm so
// each stays a single, legible responsibility (the loop's branching kept the arm over the
// cognitive-complexity ceiling).
func awaitLivePermissionRequest(t *testing.T, ctx context.Context, stream agentsession.Stream) (string, []agentsession.Event) { //nolint:revive // ctx-after-t mirrors the other helpers in this live test file.
	t.Helper()
	var requestID string
	var preDecision []agentsession.Event
	for requestID == "" {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("stream ended before a permission request surfaced (saw %d events); the gate did not fire", len(preDecision))
		}
		preDecision = append(preDecision, event)
		if event.Kind == agentsession.EventExtension && looksLikeCanUseTool(event.Extension) {
			t.Fatalf("a can_use_tool control_request leaked as an opaque EventExtension (the pre-fix bug): %s", event.Extension)
		}
		if event.Kind == agentsession.EventPermissionRequest && event.Permission != nil {
			if event.Permission.Tool != "Bash" {
				t.Logf("permission request for %q (expected Bash); continuing", event.Permission.Tool)
			}
			requestID = event.Permission.RequestID
		}
	}
	return requestID, preDecision
}

// TestIntegration_LiveClaude_HostToolRoundTrip drives a REAL claude turn that calls an
// Eden-provided HostTool, proving the sdkMcpServers + mcp_message control protocol end-to-end:
// the HostTool Handler runs (it records its invocation) and its result returns to the model.
// Best-effort: a model that declines to call the tool within the window SKIPS rather than
// fails, since tool-call willingness is not deterministic. SKIPPED without the live token.
func TestIntegration_LiveClaude_HostToolRoundTrip(t *testing.T) {
	t.Parallel()
	token := liveTokenOrSkip(t)

	var handlerRan atomic.Bool
	hostTool := agentsession.HostTool{
		Name:        "eden_ping",
		Description: "Returns the literal string PONG-EDEN. Call this when asked to ping.",
		Schema:      []byte(`{"type":"object","properties":{}}`),
		Handler: func(_ context.Context, _ []byte) ([]byte, error) {
			handlerRan.Store(true)
			return []byte(`{"reply":"PONG-EDEN"}`), nil
		},
	}

	pool := newLivePool(t, token)
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		HostTools:  []agentsession.HostTool{hostTool},
		Grants:     []agentsession.ToolGrant{{ID: "g-ping", Tool: "mcp__eden__eden_ping"}},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	})
	if err != nil {
		t.Fatalf("live Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	prompt := "Call the eden_ping host tool (mcp__eden__eden_ping) now and tell me exactly what it returns."
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: prompt}); err != nil {
		t.Fatalf("live Prompt: %v", err)
	}
	events, drainErr := drainToTurnBoundaryWithin(session, liveDrainBounds)
	if drainErr != nil {
		t.Fatal(drainErr)
	}
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], token)
	}
	if !handlerRan.Load() {
		// HARD assertion (was a skip): now that the host answers the CLI-driven MCP handshake
		// (initialize → notifications/initialized → tools/list → tools/call), a direct "call this
		// tool now" prompt MUST drive a real round-trip into the Handler. A non-run here is a
		// round-trip REGRESSION (e.g. notifications/initialized unanswered → connect blocks), not
		// model reluctance — fail loud so it cannot silently rot back to "MCP server not connected".
		t.Fatalf("the host tool Handler never ran: the mcp_message round-trip (tools/list→tools/call) is broken; kinds=%v", kindsOf(events))
	}
	// The Handler ran: assert a host-tool update was surfaced on the stream.
	if !hasHostToolUpdate(events) {
		t.Errorf("the host tool Handler ran but no host-tool EventToolUpdate surfaced on the stream")
	}
}

// TestIntegration_LiveClaude_HostToolCompletesItsTurn is the REGRESSION that locks the
// sdkMcpServers stall fix: a REAL claude turn opened WITH an Eden host tool registered MUST
// COMPLETE ITS TURN. The pre-fix code advertised sdkMcpServers as a JSON ARRAY, which made claude
// complete the MCP `initialize` + `notifications/initialized` then STALL before `tools/list` — so
// the turn never ended (the eden_commit_transition supervisor stall). Unlike HostToolRoundTrip
// this does NOT skip on a non-call: reaching the turn boundary is the HARD assertion (the array
// form never reaches one within the window → fails; the object form processes the turn → passes).
// The session mirrors the supervisor's breadth (a host tool + a multi-grant allowlist). SKIPPED
// without the live token.
//
// Re-pinned for contract revision R1: the stall this locks is the ABSENCE of a turn boundary, so
// the assertion reads the boundary payload — the same event before and after R1 — instead of a
// session terminal, which a healthy multi-turn session no longer emits until it is Closed.
func TestIntegration_LiveClaude_HostToolCompletesItsTurn(t *testing.T) {
	t.Parallel()
	token := liveTokenOrSkip(t)

	hostTool := agentsession.HostTool{
		Name:        "eden_commit_transition",
		Description: `Commit the current FSM transition. Call with {"fsm":"<from>-><to>"}.`,
		Schema:      []byte(`{"type":"object","properties":{"fsm":{"type":"string"}},"required":["fsm"]}`),
		Handler: func(_ context.Context, _ []byte) ([]byte, error) {
			return []byte(`{"committed":true}`), nil
		},
	}

	pool := newLivePool(t, token)
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace: t.TempDir(),
		Routing:   agentsession.RouteKey{Role: "assistant"},
		HostTools: []agentsession.HostTool{hostTool},
		// A representative multi-grant allowlist so the session shape matches the supervisor's
		// breadth (the stall reproduced under exactly this kind of session), not a one-grant minimal.
		Grants: []agentsession.ToolGrant{
			{ID: "g-commit", Tool: "mcp__eden__eden_commit_transition"},
			{ID: "g-read", Tool: "Read"},
			{ID: "g-glob", Tool: "Glob"},
			{ID: "g-grep", Tool: "Grep"},
			{ID: "g-lsdir", Tool: "Bash(ls)"},
			{ID: "g-gitstatus", Tool: "Bash(git status)"},
		},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	})
	if err != nil {
		t.Fatalf("live Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	prompt := `Call the eden_commit_transition host tool with {"fsm":"init->charter"}, then tell me exactly what it returned.`
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: prompt}); err != nil {
		t.Fatalf("live Prompt: %v", err)
	}

	// One home for the number: the ctx deadline and the bound drainStreamTo names in its failure
	// message are the same value, so a message can never quote a deadline the drain did not run under.
	const armBound = liveDrainTotal
	ctx, cancel := context.WithTimeout(context.Background(), armBound)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	// A deadline now fails INSIDE drainStreamTo and names the clock, so reaching this line means
	// the stream genuinely ended. The stall diagnosis below is therefore about a missing boundary
	// on a finished stream, which is what the array form actually produced — never about a timeout.
	events := drainStreamTo(t, ctx, stream, armBound)
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], token)
	}
	if len(events) == 0 || events[len(events)-1].Terminal == nil {
		t.Fatalf("the stream ended with no turn boundary under a registered host tool (the sdkMcpServers array stall) — kinds: %v", kindsOf(events))
	}
	if events[len(events)-1].IsTerminal() {
		t.Errorf("the live turn ended the SESSION (kind %s); a success `result` is a TURN boundary",
			events[len(events)-1].Kind)
	}
}

// newLivePool builds a Pool whose route carries an EMPTY model, so buildArguments omits
// --model and the live claude uses its own default (a REAL model). The stub-fable model the
// other integration pools use is a fake the real CLI rejects ("model may not exist"), so the
// live arms must NOT reuse it. The provider resolves the credential to the operator token.
func newLivePool(t *testing.T, token string) *agentsession.Pool {
	t.Helper()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "claude-code", Model: ""}, // empty == claude's default real model
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": claudeadapter.MustNewForTest(t, claudeadapter.Config{})},
			Secrets:    secretstest.New(map[string]string{"vault://eden/anthropic#setup-token": token}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      integrationClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}

// liveTokenOrSkip returns the operator-supplied live token, or skips the test. It NEVER mints
// a token, launches auth, or reads ~/.claude.
func liveTokenOrSkip(t *testing.T) string {
	t.Helper()
	token := os.Getenv("CLAUDEADAPTER_LIVE_TOKEN")
	if token == "" {
		t.Skip("CLAUDEADAPTER_LIVE_TOKEN not set: the live authenticated claude run is gated and skipped")
	}
	if _, err := exec.LookPath("claude"); err != nil {
		t.Skip("claude binary not on PATH: skipping the live arm")
	}
	return token
}

// drainStreamTo reads a live stream to the end of its turn over a stream the CALLER already
// opened, and FAILS the test when the caller's ctx expires. Re-pinned for contract revision R1:
// it stops on the boundary PAYLOAD, the same event on both sides of the revision — otherwise a
// healthy post-R1 session, which emits no terminal until it is Closed, would drain for the whole
// ctx deadline.
//
// It used to `return events` on ctx expiry with no error and no clock, so both live callers read
// a TIMEOUT as a missing boundary and reported it as the sdkMcpServers normalizer stall — a
// misdiagnosis of exactly the class this change exists to end, in this very file. bound is the
// deadline the caller put on ctx; it is named here only so the message can carry it, and it is
// routed through the SAME drainFault the main drainer uses so there is one wording, not two.
//
// It keeps an ABSOLUTE bound and no idle window: these arms legitimately go silent for minutes
// on a permission dialog, and claude's normalizer drops keep_alive (see liveDrainTotal), so an
// inactivity clock here would be blind and wrong.
func drainStreamTo(t *testing.T, ctx context.Context, stream agentsession.Stream, bound time.Duration) []agentsession.Event { //nolint:revive // ctx-after-t is fine for this bounded test drainer
	t.Helper()
	started := time.Now()
	progress := drainProgress{started: started, lastEvent: started}
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			// A bound or a stream fault is named here and FAILS. A clean end of stream is not an
			// error, and returning it lets the caller report its own missing-boundary diagnosis.
			if err := drainFault(ctx, stream, false, drainBounds{Total: bound}, progress); err != nil {
				t.Fatal(err)
			}
			return progress.events
		}
		progress.events = append(progress.events, event)
		progress.lastEvent = time.Now()
		if event.Terminal != nil || event.IsTerminal() {
			return progress.events
		}
	}
}

// bashToolSucceeded reports whether a Bash tool ran to a NON-error completion in the stream — a
// Bash EventToolStart paired with an EventToolEnd whose outcome is OK.
func bashToolSucceeded(events []agentsession.Event) bool {
	bashCalls := map[string]bool{}
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventToolStart && ev.Tool != nil && ev.Tool.Name == "Bash" {
			bashCalls[ev.Tool.CallID] = true
		}
	}
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventToolEnd && ev.Tool != nil && bashCalls[ev.Tool.CallID] &&
			ev.Tool.Outcome == agentsession.ToolOutcomeOK {
			return true
		}
	}
	return false
}

// looksLikeCanUseTool reports whether a raw Extension frame is a can_use_tool control_request —
// used to fail loudly if the permission ask regressed to leaking as an opaque Extension.
func looksLikeCanUseTool(raw []byte) bool {
	return bytes.Contains(raw, []byte("control_request")) && bytes.Contains(raw, []byte("can_use_tool"))
}

// kindsOf projects the event kinds for failure diagnostics.
func kindsOf(events []agentsession.Event) []agentsession.EventKind {
	out := make([]agentsession.EventKind, len(events))
	for i := range events {
		out[i] = events[i].Kind
	}
	return out
}

// buildStub compiles the stub harness binary into t.TempDir() and returns its path. The
// build uses the workspace so the stub's module resolves; it is reaped with TempDir.
func buildStub(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	binary := filepath.Join(dir, "stubharness")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	source := stubSourceDir(t)
	// #nosec G204 -- fixed `go build` of the in-repo stub; binary/source are test-derived paths, not user input.
	build := exec.Command("go", "build", "-o", binary, ".")
	build.Dir = source
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
	return newPoolWithToken(t, adapter, fakeCanary)
}

// newPoolWithToken constructs a Pool whose provider resolves the credential reference to
// the given token (a fake canary in the stub arm; the operator-supplied token in the gated
// live arm — never minted here).
func newPoolWithToken(t *testing.T, adapter agentsession.Adapter, token string) *agentsession.Pool {
	t.Helper()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "claude-code", Model: "stub-fable"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": adapter},
			Secrets:    secretstest.New(map[string]string{"vault://eden/anthropic#setup-token": token}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      integrationClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}

// integrationClock is a deterministic clock for the integration pools.
type integrationClock struct{}

func (integrationClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// drainDeadline bounds the STUB arm's drain. A scripted stub is instant or broken, so one
// absolute bound is the whole story there and no inactivity window is needed. Exceeding it is a
// FAILURE that says so, never a quiet return of a partial event list. The LIVE arms do NOT use
// it — they carry liveDrainBounds below.
const drainDeadline = 15 * time.Second

// liveDrainTotal is claude's live bound, and it is ABSOLUTE. This is a DELIBERATE, STATED
// asymmetry with the ompadapter twin, which carries an IDLE window as well: the two-clock
// MECHANISM (drainBounds, nextWithin, drainFault) is shared and proven identically on both sides
// by the four tests below, but the TUNING is applied only where the defect was MEASURED, and the
// measured defect is omp-only. claude's live arms are green; giving them an idle bound would
// narrow a green arm on an unmeasured assumption, which is the same mistake as raising a constant.
//
// It is also unsound here today. The idle clock ticks on NORMALIZED Events, and claudeadapter's
// normalizer DROPS the one frame whose entire purpose is to signal liveness during a silence —
// see normalize.go: `case "control_response", "control_cancel_request", "keep_alive": return nil`.
// So a real claude turn that goes quiet except for heartbeats is INVISIBLE to an idle clock, and
// a 60s idle bound would report "the harness stopped producing" about a harness that was
// producing. ompadapter's normalizer preserves every unmodeled frame as an extension, so its idle
// clock can see omp's liveness and the bound is sound there.
//
// claude adopts the idle bound the day its normalizer surfaces a liveness signal. Until then this
// value is exactly what the live arms already ran under, so this change alters NO claude behavior.
const liveDrainTotal = 120 * time.Second

// liveDrainBounds is the live arm's bound, cited by every live call site. Idle is left zero —
// DISABLED on purpose, for the reason documented on liveDrainTotal.
var liveDrainBounds = drainBounds{Total: liveDrainTotal}

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
// (`event.Terminal != nil`), which is the SAME event on both sides of the revision — a success
// `result` today, and the non-terminal turn-end it becomes once a session survives its own
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
		UsageMeter: agentsession.UsageMeter{Harness: "claude-code", Cumulative: true},
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
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
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
// harness that is streaming steadily from one that is dead. CI proved it twice on the sibling omp
// arm, both times in the EDEN monorepo (`gophersys/eden`, not this repository): eden run
// 32935203884 died at 60s with 18 events seen, and after the constant was raised, eden run
// 32998558460 died at 120s with 27. Both harnesses were PROGRESSING. An INACTIVITY bound reads
// the gap between CONSECUTIVE events instead, so a turn that runs many multiples of the window
// survives as long as events keep arriving — and raising a constant stops being the fix.
//
// This package proves the MECHANISM, not the tuning: claude's own live arms stay Total-only, for
// the reason on liveDrainTotal. A shared helper with an untested copy is a copy that drifts.
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
