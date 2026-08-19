// The PERMISSION-ROUTING contract (Mateo's ruling, 2026-08-19): the omp adapter does NOT decide
// permissions from the session's grants. It surfaces omp's approval dialog as an
// EventPermissionRequest carrying the command, routes it THROUGH the library's permission chain
// (grants -> scope-check -> risk-class clamp -> advisor/human), and writes to the wire whatever
// the library resolved — never a verdict it derived itself from bare tool-name membership.
//
// Two of these tests drive the REAL agentsession library end to end (a Pool over an in-memory omp
// transport), because the security case is exactly the interaction between the adapter's ask and
// the library's clamp: a stub-only path would prove nothing about whose verdict reaches the wire.
package ompadapter_test

import (
	"context"
	"encoding/json"
	"io"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

const (
	// permVaultReference and permCanary are this file's OWN credential fixtures (distinct names so
	// they do not collide with harness_helpers_test.go's when the integration lane compiles both).
	permVaultReference = "vault://eden/openrouter#api-key"
	permCanary         = "STUB-OPENROUTER-KEY-do-not-leak"
)

// dialogID is the correlation id the routing tests drive their dialog on — the captured select
// frame's id (rpc_test.go selectFrameID), reused so the wire answer correlates on omp's own id.
const dialogID = selectFrameID

// unitClock is a deterministic clock for the fast-lane library harness (integrationClock lives
// behind a build tag and is not compiled here).
type unitClock struct{}

func (unitClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// selectDialogFrame renders omp's approval `select` frame VERBATIM in the captured shape
// (q3-probe5-always-ask.txt:10): the tool rides the title's first line, the command its second,
// and the options are the labels an answer names. The command is the test's own case (the F1
// ruling is about a destructive command a scoped grant must not auto-approve), not a probe
// capture — the SHAPE is captured, the command is the security case under test.
func selectDialogFrame(t *testing.T, id, tool, command string) string {
	t.Helper()
	frame := map[string]any{
		"type":    "extension_ui_request",
		"id":      id,
		"method":  "select",
		"title":   "Allow tool: " + tool + "\nCommand: " + command,
		"options": []string{"Approve", "Deny"},
	}
	line, err := json.Marshal(frame)
	if err != nil {
		t.Fatalf("marshal select dialog: %v", err)
	}
	return string(line)
}

// TestRPC_DialogAskCarriesTheCommand is F1 CORE: the surfaced EventPermissionRequest must carry
// the COMMAND (the dialog title's 2nd line), not just the tool name.
//
// The command is the only thing that distinguishes `bash ls` from `bash rm -rf /`, so a decider
// that never sees it cannot apply a scope check or a risk class — the library's whole permission
// chain is blind. omp folds the command onto the title's second line; the adapter must fold it
// into the payload as the tool's SCOPE, in the "Tool(scope)" shape the library's grant-match and
// risk-class machinery already consume (the claudeadapter Skill(name)/Bash(go test) precedent).
//
// Today the adapter puts the tool name alone in Permission.Tool and the command only in Reason
// (a digest), where no scope check can reach it — RED.
func TestRPC_DialogAskCarriesTheCommand(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{})
	harness.completeHandshake()

	const command = "rm -rf /"
	harness.emit(selectDialogFrame(t, dialogID, "bash", command))

	ask := harness.waitEvent("the EventPermissionRequest for the approval dialog", func(event *agentsession.Event) bool {
		return event.Kind == agentsession.EventPermissionRequest
	})
	if ask.Permission == nil {
		t.Fatalf("EventPermissionRequest carried no payload: %+v", ask)
	}
	if ask.Permission.RequestID != dialogID {
		t.Errorf("ask RequestID = %q, want the dialog id %q", ask.Permission.RequestID, dialogID)
	}
	if !strings.Contains(ask.Permission.Tool, command) {
		t.Errorf("ask Tool = %q does NOT carry the command %q — the command reached only Reason=%q, where no scope check can act on it",
			ask.Permission.Tool, command, ask.Permission.Reason)
	}
	base, scope := toolBaseAndScope(ask.Permission.Tool)
	if base != "bash" {
		t.Errorf("ask Tool base = %q, want bash (the folded shape must stay grant-matchable)", base)
	}
	if scope != command {
		t.Errorf("ask Tool scope = %q, want the command %q folded as Tool(scope) so the library derives the scope from it", scope, command)
	}
}

// TestRPC_WireAnswerFollowsLibraryDeny is F1 WIRE-FROM-RESOLVE, the security case, driven through
// the REAL library: a grant scoped to `ls *` must NOT auto-approve `rm -rf /`.
//
// The session grants bash("ls *") and runs the autonomous chain with an advisor that (as a
// prompt-injection would) votes Allow. The library denies anyway — the scoped grant does not
// cover `rm -rf /`, and the risk-class clamp overrides the advisor's allow on a high-risk command
// (session.go clampToRisk). The wire answer must be that DENY.
//
// Today the adapter answers the dialog itself from bare "bash" membership (which IS in --tools),
// writes "Approve" on the wire, and DROPS the library's tunneled deny — the ungated-bash defect.
// RED: the wire carries Approve where the library resolved Deny.
func TestRPC_WireAnswerFollowsLibraryDeny(t *testing.T) {
	t.Parallel()
	harness := newLibraryHarness(t, agentsession.Spec{
		Routing:              agentsession.RouteKey{Role: "assistant"},
		Credential:           secrets.Ref(permVaultReference),
		Grants:               []agentsession.ToolGrant{{ID: "g-bash-ls", Tool: "bash", Scopes: []string{"ls *"}}},
		PermissionResolution: agentsession.ResolveAutonomousAdvisor,
	}, allowingAdvisor{})

	harness.emit(selectDialogFrame(t, dialogID, "bash", "rm -rf /"))

	value := harness.awaitWireAnswer(dialogID)
	if !strings.EqualFold(value, "Deny") {
		t.Errorf("wire answer = %q, want Deny — a grant scoped to \"ls *\" must not auto-approve \"rm -rf /\"; the library's risk-clamped deny must reach the wire, not the adapter's bare-name Approve",
			value)
	}
}

// TestRPC_WireAnswerFollowsLibraryAllow is F3's positive arm, driven through the REAL library: a
// human Session.Resolve(Allow) for an out-of-grant tool must reach the wire as "Approve".
//
// The session grants nothing, so the dialog is out-of-grant and the human chain records it and
// waits for Resolve. The test resolves Allow; the library forwards it, and the adapter must map
// that allow to the wire.
//
// Today the adapter answers "Deny" itself the instant the dialog arrives (bare "bash" is not in an
// empty --tools set) and DROPS the human's allow. RED: the wire carries Deny where the human
// resolved Allow.
func TestRPC_WireAnswerFollowsLibraryAllow(t *testing.T) {
	t.Parallel()
	harness := newLibraryHarness(t, agentsession.Spec{
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(permVaultReference),
		// No grants and no advisor: the request surfaces for a human Resolve (the chat chain).
	}, nil)

	harness.emit(selectDialogFrame(t, dialogID, "bash", "ls -la"))

	ask := harness.awaitAsk()
	if _, err := harness.session.Resolve(context.Background(), ask.Permission.RequestID, agentsession.Decision{
		Allow: true, By: "user:test", Scope: agentsession.ScopeOnce,
	}); err != nil {
		t.Fatalf("Resolve(Allow) for the pending request: %v", err)
	}

	value := harness.awaitWireAnswer(dialogID)
	if !strings.EqualFold(value, "Approve") {
		t.Errorf("wire answer = %q, want Approve — a human Resolve(Allow) must reach the wire, not the adapter's own bare-name Deny", value)
	}
}

// TestRPC_PermissionDecisionSteerNeverReachesOmpAsText is F2: the guard that keeps a tunneled
// permission decision off omp's conversation channel is load-bearing.
//
// The library forwards every resolved decision as a steer-shaped Command (session.go
// forwardDecision). That internal frame answers a dialog; it must NEVER reach omp as a `prompt`
// or `steer` message, where the model would read "eden:permission:...:deny:..." as user text. A
// GENUINE steer, by contrast, MUST reach omp.
//
// This holds today (the guard drops the decision) and after the rewrite (the guard maps it to a
// wire answer instead) — so the assertion is future-proof. Non-vacuity is proven separately:
// disabling the guard on a scratch build sends the decision text out as a steer and fails here.
func TestRPC_PermissionDecisionSteerNeverReachesOmpAsText(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{})
	harness.completeHandshake()

	decision := controlframe.EncodePermission(dialogID, false, "policy:risk-clamp", "high-risk tool")
	if err := harness.conn.Send(t.Context(), agentsession.Command{Kind: agentsession.CommandSteer, Text: decision}); err != nil {
		t.Fatalf("Send the tunneled decision steer: %v", err)
	}
	// A genuine interjection, which MUST reach omp as a steer (so the test is not vacuously
	// "no steer ever").
	const genuine = "focus on the failing test"
	if err := harness.conn.Send(t.Context(), agentsession.Command{Kind: agentsession.CommandSteer, Text: genuine}); err != nil {
		t.Fatalf("Send the genuine steer: %v", err)
	}

	harness.waitFrame("the genuine steer", func(frame map[string]any) bool {
		return stringField(frame, "type") == "steer" && stringField(frame, "message") == genuine
	})
	if frame, found := harness.stdin.find(carriesDecisionText); found {
		t.Errorf("a tunneled permission decision reached omp as conversation text: %v — the model would read the eden:permission frame as user input", frame)
	}
}

// carriesDecisionText reports whether a written frame smuggled the eden:permission decision text
// onto a conversation channel (a prompt or steer message).
func carriesDecisionText(frame map[string]any) bool {
	switch stringField(frame, "type") {
	case "prompt", "steer":
		return strings.Contains(stringField(frame, "message"), controlframe.PermissionPrefix)
	default:
		return false
	}
}

// toolBaseAndScope splits a folded "Tool(scope)" permission tool into its base name and scope,
// mirroring the library's own grant-match/risk-class parse (baseToolName + scopesFromTool). A
// bare tool name yields an empty scope.
func toolBaseAndScope(tool string) (base, scope string) {
	open := strings.IndexByte(tool, '(')
	if open < 0 || !strings.HasSuffix(strings.TrimSpace(tool), ")") {
		return strings.TrimSpace(tool), ""
	}
	base = strings.TrimSpace(tool[:open])
	scope = strings.TrimSpace(tool[open+1 : strings.LastIndexByte(tool, ')')])
	return base, scope
}

// allowingAdvisor is the adversarial advisor for the security case: it always votes Allow, as a
// prompt injection convincing the reasoning subagent would. The library's risk-class clamp — not
// the advisor — is what must stop the destructive command, so this vote must NOT reach the wire.
type allowingAdvisor struct{}

func (allowingAdvisor) Advise(context.Context, agentsession.PermissionRequest, agentsession.AdviceContext) (agentsession.Decision, error) {
	return agentsession.Decision{Allow: true, By: "advisor:test", Rationale: "the injected prose argued for it"}, nil
}

// ── the library-driven harness: a real Pool over an in-memory omp transport ────────────────────.

// libraryHarness drives the REAL agentsession library against the REAL omp rpc conn, with omp's
// stdout/stdin replaced by an in-memory transport: the test writes omp's frames with emit, reads
// the wire omp would receive from stdin, and reads the session's events from the library's own
// fan-out stream. No process, no substrate — the permission chain is exercised for real.
type libraryHarness struct {
	t       *testing.T
	session agentsession.Session
	stream  agentsession.Stream
	ctx     context.Context //nolint:containedctx // the stream ctx is bounded and reaped in cleanup; holding it keeps the await helpers to one argument.
	stdout  *io.PipeWriter
	stdin   *recordingStdin
}

// newLibraryHarness opens a real session over the in-memory transport and drives the handshake to
// Ready, so the caller starts from a live session exactly as Open returns one.
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the harness mirrors Open's by-value seam.
func newLibraryHarness(t *testing.T, spec agentsession.Spec, advisor agentsession.PermissionAdvisor) *libraryHarness {
	t.Helper()
	reader, writer := io.Pipe()
	stdin := &recordingStdin{}
	adapter := &inMemoryOmpAdapter{
		fromOMP:  reader,
		toOMP:    stdin,
		manifest: ompadapter.MustNewForTest(t, ompadapter.Config{}).Manifest(),
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "omp", Model: "stub"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"omp": adapter},
			Secrets:    secretstest.New(map[string]string{permVaultReference: permCanary}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      unitClock{},
			Advisor:    advisor,
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}

	harness := &libraryHarness{t: t, stdout: writer, stdin: stdin}
	opened := make(chan error, 1)
	go func() {
		// context.Background: Open is released by the handshake the test feeds, not by a ctx.
		session, openErr := pool.Open(context.Background(), spec)
		harness.session = session
		opened <- openErr
	}()
	// Feed omp's `ready` — its only readiness signal — so the adapter negotiates and the library's
	// Open completes.
	harness.emit(rpcFixture(t, handshakeFixture)[0])
	select {
	case openErr := <-opened:
		if openErr != nil {
			t.Fatalf("Open over the in-memory omp transport: %v", openErr)
		}
	case <-time.After(rpcDeadline):
		t.Fatalf("Open did not reach Ready within %s after the ready frame", rpcDeadline)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	harness.ctx = ctx
	harness.stream = harness.session.Events(ctx, agentsession.FromSeq(0))
	t.Cleanup(func() {
		_ = writer.Close() //nolint:errcheck // EOF ends the conn pump so Close can drain; an already-closed writer is fine.
		closeCtx, closeCancel := context.WithTimeout(context.Background(), rpcDeadline)
		defer closeCancel()
		_ = harness.session.Close(closeCtx) //nolint:errcheck // best-effort reap; Close is idempotent.
		_ = reader.Close()                  //nolint:errcheck // releases the pump if it is still parked on the reader.
		cancel()
	})
	return harness
}

// emit writes one omp frame on the transport, failing (never hanging) if the conn stops reading.
func (h *libraryHarness) emit(frame string) {
	h.t.Helper()
	written := make(chan error, 1)
	go func() { _, err := io.WriteString(h.stdout, frame+"\n"); written <- err }()
	select {
	case err := <-written:
		if err != nil {
			h.t.Fatalf("write omp frame on the transport: %v", err)
		}
	case <-time.After(rpcDeadline):
		h.t.Fatalf("the conn did not read the omp frame within %s: %s", rpcDeadline, frame)
	}
}

// awaitAsk reads the library's fan-out stream up to the EventPermissionRequest, or fails naming
// what never arrived.
func (h *libraryHarness) awaitAsk() agentsession.Event { //nolint:gocritic // Event is the contract's copyable value record (§2); returned by value.
	h.t.Helper()
	for {
		event, ok := h.stream.Next(h.ctx)
		if !ok {
			h.t.Fatalf("the stream ended before an EventPermissionRequest: %v", h.stream.Err())
		}
		if event.Kind == agentsession.EventPermissionRequest && event.Permission != nil {
			return event
		}
	}
}

// awaitWireAnswer returns the value of the extension_ui_response the adapter wrote for the given
// dialog id, or fails naming what the conn wrote instead.
func (h *libraryHarness) awaitWireAnswer(id string) string {
	h.t.Helper()
	deadline := time.Now().Add(rpcDeadline)
	for {
		if frame, found := h.stdin.find(isDialogResponse(id)); found {
			return stringField(frame, "value")
		}
		if time.Now().After(deadline) {
			h.t.Fatalf("no extension_ui_response for dialog %q within %s; the conn wrote: %s", id, rpcDeadline, h.stdin.render())
		}
		time.Sleep(rpcPoll)
	}
}

// isDialogResponse matches the extension_ui_response written for one dialog id.
func isDialogResponse(id string) func(map[string]any) bool {
	return func(frame map[string]any) bool {
		return stringField(frame, "type") == "extension_ui_response" && stringField(frame, "id") == id
	}
}

// inMemoryOmpAdapter is a test Adapter whose Spawn returns the REAL omp rpc conn over the test's
// in-memory transport, so a real Pool drives the real adapter with no process. Manifest mirrors
// the real adapter's so the library sees the true capability set.
type inMemoryOmpAdapter struct {
	fromOMP  io.Reader
	toOMP    io.WriteCloser
	manifest agentsession.CapabilityManifest
}

//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the frozen lower seam.
func (a *inMemoryOmpAdapter) Spawn(_ context.Context, spec agentsession.Spec, _ agentsession.Route, _ agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	return ompadapter.RPCConnForTest(spec, a.fromOMP, a.toOMP), nil
}

func (a *inMemoryOmpAdapter) Manifest() agentsession.CapabilityManifest { return a.manifest }

// compile-time assertion: the test adapter satisfies the port the library drives.
var _ agentsession.Adapter = (*inMemoryOmpAdapter)(nil)
