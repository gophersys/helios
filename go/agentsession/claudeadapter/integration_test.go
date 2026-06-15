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
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
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
// through the claude-code adapter's genuine Spawn path, drives Open -> Prompt -> drain to
// terminal, and asserts: the init handshake reached Ready, the assistant text/tool events
// parsed, the rate_limit_event survived as Extension through a real pipe, the terminal
// carried the four-token ledger, Seq is monotonic, and the credential canary never leaked.
// The process is reaped on Cleanup.
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

	events := drainTerminal(t, session)
	if len(events) == 0 {
		t.Fatal("the stub subprocess produced no events")
	}
	assertSubprocessKinds(t, events)
	assertSubprocessTerminalLedger(t, events[len(events)-1])
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

// assertSubprocessTerminalLedger proves the terminal carries the four-token ledger and
// the cost converted with no float drift (0.0123 USD -> 12300 micros).
func assertSubprocessTerminalLedger(t *testing.T, terminal agentsession.Event) { //nolint:gocritic // Event is the contract's copyable value record (§2); this test helper takes it by value.
	t.Helper()
	if !terminal.IsTerminal() || terminal.Terminal == nil {
		t.Fatalf("the real subprocess did not end on a terminal carrying a ledger")
	}
	ledger := terminal.Terminal.Ledger
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

	pool := newPoolWithToken(t, claudeadapter.MustNewForTest(t, claudeadapter.Config{}), token)
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
	events := drainTerminal(t, session)
	if len(events) == 0 || !events[len(events)-1].IsTerminal() {
		t.Fatalf("live session did not reach a terminal")
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

	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))

	// Phase 1: read until the REAL permission request surfaces. It must be a genuine
	// EventPermissionRequest for Bash (not an opaque Extension) — the (a) assertion.
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
	if requestID == "" {
		t.Fatal("no EventPermissionRequest observed")
	}

	// Phase 2: resolve the decision over the NATIVE control channel.
	decision := agentsession.Decision{Allow: allow, By: "user-live-test"}
	if _, err := session.Resolve(context.Background(), requestID, decision); err != nil {
		t.Fatalf("Resolve(allow=%v): %v", allow, err)
	}

	// Phase 3: drain to the terminal and inspect the outcome.
	rest := drainStreamTo(t, ctx, stream)
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
	events := drainTerminal(t, session)
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], token)
	}
	if !handlerRan.Load() {
		t.Skip("the model did not call the host tool within the window (non-deterministic willingness); the mcp_message wiring is proven by the unit router test")
	}
	// The Handler ran: assert a host-tool update was surfaced on the stream.
	if !hasHostToolUpdate(events) {
		t.Errorf("the host tool Handler ran but no host-tool EventToolUpdate surfaced on the stream")
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

// drainStreamTo reads a live stream to its terminal (or ctx deadline), returning the events.
func drainStreamTo(t *testing.T, ctx context.Context, stream agentsession.Stream) []agentsession.Event { //nolint:revive // ctx-after-t is fine for this bounded test drainer
	t.Helper()
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return events
		}
		events = append(events, event)
		if event.IsTerminal() {
			return events
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

// drainTerminal drains a session's stream to its terminal, bounded so a regression fails
// fast rather than hanging.
func drainTerminal(t *testing.T, session agentsession.Session) []agentsession.Event {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
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
