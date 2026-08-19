// The `--mode rpc` FRAME-CONTRACT lane: one long-lived omp session driven over its real NDJSON
// transport, with the frames replayed verbatim from the credential-free 17.3.7 probe captures in
// testdata/rpc-17.3.7-*.jsonl. It is a fast unit lane — no process, no substrate, no network: the
// conn is built over an in-memory transport (RPCConnForTest), which is the SAME conn Spawn wraps
// around the child's stdout/stdin pipes.
//
// What the four properties here defend, each measured on the real omp before it was written down:
//
//	Ready       — `ready` is omp's ONLY readiness signal (rpc-mode.ts:690). Synthesizing one at
//	              spawn is the silent-bad-token trap: the library's Open would return a live
//	              session for a child that never came up.
//	host tools  — host_tool_result correlates on the RPC frame `id`, never on the model's
//	              `toolCallId`, and result.content MUST be an array or the frame is dropped.
//	the dialog  — a `select` extension_ui_request carries NO timeout field and omp arms no timer
//	              (rpc-mode.ts:640), so an unanswered dialog waits FOREVER: q3-probe5 measured 45s
//	              of wall clock with no agent_end. Answering is not a courtesy, it is the only
//	              thing that ends the turn.
//	Close       — stdin EOF makes omp reject its pending requests, drain and exit 0; on this side
//	              every caller — the one blocked in flight and every one after — must get the
//	              same typed sentinel, mirroring the sticky #closedError of omp's own bridge.
package ompadapter_test

import (
	"bufio"
	"context"
	"encoding/json"
	stderrors "errors"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

const (
	// rpcDeadline bounds every wait for one frame or one event. It is the 2 seconds the
	// stall-deadlock pin is written against: the dialog omp never times out must be answered
	// well inside it, and a wait that runs out is a FAILURE naming what never arrived — never a
	// quiet return.
	rpcDeadline = 2 * time.Second

	// readyGrace is how long a freshly built conn is watched for a PREMATURE Ready before any
	// frame has been written on omp's stdout. It only has to be long enough to catch a Ready
	// that is signaled unconditionally at construction, which is instant.
	readyGrace = 250 * time.Millisecond

	// rpcPoll is the granularity of the wait loops.
	rpcPoll = 5 * time.Millisecond

	// contractPackage is the ONE package whose error types a caller outside this adapter can
	// branch on. ompadapter exports no error type of its own and must not start: its
	// .apibaseline section stays byte-identical across this rewrite.
	contractPackage = "github.com/gophersys/libs/go/agentsession"
)

// The three captured frame files and the identifiers inside them the assertions correlate on.
const (
	handshakeFixture = "rpc-17.3.7-handshake.jsonl"
	hostToolFixture  = "rpc-17.3.7-hosttool.jsonl"
	approvalFixture  = "rpc-17.3.7-approval-select.jsonl"

	// hostToolFrameID is the `id` of the captured host_tool_call — the RPC correlation id the
	// host MUST echo (host-tools.ts resolves #pendingCalls.get(frame.id)).
	hostToolFrameID = "155cddcf9981ec56"
	// modelToolCallID is the SAME frame's `toolCallId` — the model's id, which correlates
	// nothing on this channel. Answering with it strands the call.
	modelToolCallID = "call_stub_1"
	// selectFrameID is the `id` of the captured no-timeout approval dialog.
	selectFrameID = "155cde478590975d"
)

// dialogDismissField is the dismissal variant's field name in RpcExtensionUIResponse
// (rpc-types.ts:535), spelled as omp spells it on the wire. The test reads the answer by the key
// that actually resolves a dialog, so it must carry omp's spelling and not this repository's.
//
//nolint:misspell // the double-L is omp's wire spelling of this field, not prose; it mirrors rpc.go's answerCancelField.
const dialogDismissField = "cancelled"

// TestRPC_ReadyWaitsForTheReadyFrame proves the readiness handshake is MEASURED, not assumed: no
// Ready is published while omp has said nothing, and the host answers the `ready` frame by
// negotiating protocol 2 on stdin.
//
// The pre-rewrite conn signaled Initializing->Ready from a goroutine started inside Spawn,
// before any process existed — so the library's Open returned a live session for a harness that
// might never have started. omp's `ready` is unconditional and FIRST (rpc-mode.ts:690), which is
// exactly why it is a usable readiness signal and a synthesized one is not.
func TestRPC_ReadyWaitsForTheReadyFrame(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{})
	frames := rpcFixture(t, handshakeFixture)

	// Nothing has been written on omp's stdout: a real omp has not announced itself yet.
	time.Sleep(readyGrace)
	if event, found := harness.findEvent(isReady); found {
		t.Fatalf("Ready was published %s before omp emitted its `ready` frame (%+v) — a session that is ready by assumption is the silent-bad-token trap",
			readyGrace, event.State)
	}
	if frame, found := harness.stdin.find(hasType("negotiate_protocol")); found {
		t.Fatalf("the host negotiated the protocol before omp announced itself: %v", frame)
	}

	harness.emit(frames[0]) // the `ready` frame, alone

	negotiate := harness.waitFrame("negotiate_protocol", hasType("negotiate_protocol"))
	if !numberIs(negotiate["protocolVersion"], 2) {
		t.Errorf("negotiate_protocol protocolVersion = %v, want 2 — 1 is what omp runs until the host negotiates, and the rpc wire schema is byte-identical 17.2.5<->17.3.7, so 2 is safe on the pin",
			negotiate["protocolVersion"])
	}
	if id := stringField(negotiate, "id"); id == "" {
		t.Errorf("negotiate_protocol carries no id; omp correlates its response on it (captured: id \"1\"): %v", negotiate)
	}

	harness.emit(frames[1:]...) // setWidget, available_commands_update, the negotiate response
	harness.waitEvent("the Initializing->Ready transition", isReady)
}

// TestRPC_HostToolResultCorrelatesOnTheFrameID proves the host-tool channel: the tools are
// registered on the LIVE session with set_host_tools, the turn text rides a stdin `prompt` frame
// (never argv), and the answer to a host_tool_call correlates on the RPC frame `id` with an
// ARRAY result.content.
//
// Both halves are drop-on-the-floor failures rather than errors, which is why they are pinned:
// host-tools.ts resolves the pending call with #pendingCalls.get(frame.id), so an answer keyed on
// the model's toolCallId matches nothing and is silently discarded; and isRpcHostToolResult
// accepts the frame ONLY when Array.isArray(result.content) holds, so a bare string result is
// discarded the same way. In both cases the model waits forever for a tool that already ran.
func TestRPC_HostToolResultCorrelatesOnTheFrameID(t *testing.T) {
	t.Parallel()
	const promptText = "Call eden_ping with payload hello-eden."
	const handlerResult = "pong from eden host"
	arguments := make(chan string, 1)

	harness := newRPCHarness(t, agentsession.Spec{HostTools: []agentsession.HostTool{{
		Name:        "eden_ping",
		Description: "Ping the Eden host message plane.",
		Schema:      []byte(`{"type":"object","properties":{"payload":{"type":"string"}},"required":["payload"]}`),
		Handler: func(_ context.Context, args []byte) ([]byte, error) {
			arguments <- string(args)
			return []byte(handlerResult), nil
		},
	}}})
	harness.completeHandshake()

	register := harness.waitFrame("set_host_tools", hasType("set_host_tools"))
	assertRegistersEdenPing(t, register)

	if err := harness.conn.Send(t.Context(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: promptText}); err != nil {
		t.Fatalf("Prompt on the live rpc session: %v", err)
	}
	prompt := harness.waitFrame("prompt", hasType("prompt"))
	if message := stringField(prompt, "message"); message != promptText {
		t.Errorf("prompt frame message = %q, want %q — under rpc the turn text is a stdin frame on the LIVING session, never a positional argv on a fresh process",
			message, promptText)
	}

	harness.emit(rpcFixture(t, hostToolFixture)...)

	answer := harness.waitFrame("host_tool_result", hasType("host_tool_result"))
	if id := stringField(answer, "id"); id != hostToolFrameID {
		t.Errorf("host_tool_result id = %q, want %q (the host_tool_call's RPC `id`)%s", id, hostToolFrameID, wrongIDHint(id))
	}
	assertContentIsAnArray(t, answer, handlerResult)

	select {
	case got := <-arguments:
		if !strings.Contains(got, "hello-eden") {
			t.Errorf("the HostTool handler was called with %q, want the frame's arguments {\"payload\":\"hello-eden\"}", got)
		}
	case <-time.After(rpcDeadline):
		t.Errorf("the HostTool handler was never called within %s of the host_tool_call", rpcDeadline)
	}
}

// TestRPC_SelectDialogIsAnsweredWithoutATimeout is the stall-deadlock regression pin.
//
// The captured `select` dialog carries NO timeout field, and requestRpcDialog arms a timer only
// when opts.timeout !== undefined (rpc-mode.ts:640) — so omp waits forever. q3-probe5 measured
// exactly that: 45 seconds of wall clock, no agent_end, the child killed by the driver. There is
// no deciding policy on this Spec and nobody will Resolve, and the answer must arrive ANYWAY:
// unconditional is the only rule that cannot deadlock.
//
// It must also not be an approval. An unattended session that answers "Approve" to a dialog
// nobody decided has invented an authorization — the ungated-bash defect with extra steps.
//
// The setWidget frame ahead of it is fire-and-forget (rpc-mode.ts:824): omp never waits for it.
// Answering it too is permitted; BLOCKING on it is not, and this test would starve if the conn
// did — the select behind it would never be read.
func TestRPC_SelectDialogIsAnsweredWithoutATimeout(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{}) // no OnPermission: nobody is deciding
	harness.completeHandshake()
	frames := rpcFixture(t, approvalFixture)

	harness.emit(frames[0], frames[1]) // fire-and-forget setWidget, then the no-timeout select

	answer := harness.waitFrame("extension_ui_response", hasType("extension_ui_response"))
	if id := stringField(answer, "id"); id != selectFrameID {
		t.Errorf("extension_ui_response id = %q, want %q — omp resolves the dialog by id and ignores an answer to anything else", id, selectFrameID)
	}
	assertLegalDialogAnswer(t, answer)
	if value := stringField(answer, "value"); strings.EqualFold(value, "approve") {
		t.Errorf("a dialog nobody decided was answered %q: an unattended session must never authorize the tool it was asked about", value)
	}

	// The turn proceeds past the answered dialog rather than stalling on it.
	harness.emit(frames[2], frames[3])
	harness.waitEvent("the tool outcome past the dialog", func(event *agentsession.Event) bool {
		return event.Kind == agentsession.EventToolEnd
	})
}

// TestRPC_CloseFailsEveryCallerWithOneTypedError proves the close contract on both sides of the
// boundary: the caller blocked in flight when Close lands, and every caller after it, get the
// SAME typed sentinel.
//
// It mirrors what omp does on its side of the same event: on stdin EOF the host-tool bridge
// closes with a sticky #closedError that rejects every pending call AND every future one (q4 §5).
// The pre-rewrite conn answered a post-close Send with an inline errors.New carrying only a
// message — nothing to branch on but the string, which rule 12 forbids — and had no notion of a
// caller pending at Close at all, since a turn WAS the process.
func TestRPC_CloseFailsEveryCallerWithOneTypedError(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{})
	harness.completeHandshake()

	harness.stdin.blockNextWrite()
	pending := make(chan error, 1)
	go func() {
		// context.Background, not t.Context: this caller must be released by CLOSE, so a context
		// that a cancellation could release instead would prove the wrong thing.
		pending <- harness.conn.Send(context.Background(),
			agentsession.Command{Kind: agentsession.CommandPrompt, Text: "the turn that never reached omp"})
	}()
	harness.stdin.awaitBlockedWrite(t)

	if err := harness.conn.Close(t.Context()); err != nil {
		t.Fatalf("Close with a caller blocked on omp's stdin: %v", err)
	}

	var pendingErr error
	select {
	case pendingErr = <-pending:
	case <-time.After(rpcDeadline):
		t.Fatalf("the Send blocked on omp's stdin was still blocked %s after Close returned — Close owes omp its EOF and every blocked caller an error", rpcDeadline)
	}
	postErr := harness.conn.Send(t.Context(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "a turn after the close"})

	if pendingErr == nil {
		t.Fatalf("the Send pending at Close returned nil: the caller believes a turn omp never received was accepted")
	}
	if postErr == nil {
		t.Fatalf("a Send after Close returned nil: the caller believes a closed session took a turn")
	}
	assertSameSentinel(t, pendingErr, postErr)
}

// TestRPC_ManifestPromotionsAreMeasuredNotDeclared is the capability-truthfulness pin: the two
// promotions this rewrite claims are asserted in the SAME test as the round trips that earn
// them, on ONE conn, so neither half can go green alone. Editing the manifest map without wiring
// the plane fails here on the round trip; wiring the plane without promoting the manifest fails
// here on the manifest.
//
//   - CapHostTools Partial->Full: an in-process Handler is invoked by the agent and its result is
//     returned on the wire — a real callback round trip, not data the adapter declines.
//   - CapPermissionPrompt Partial->Full: the approval dialog SURFACES as an
//     EventPermissionRequest the library's resolution chain can act on, and is answered on the
//     wire. A one-way stream that only reports the ask is what Partial meant.
func TestRPC_ManifestPromotionsAreMeasuredNotDeclared(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{HostTools: []agentsession.HostTool{{
		Name:        "eden_ping",
		Description: "Ping the Eden host message plane.",
		Handler:     func(context.Context, []byte) ([]byte, error) { return []byte("pong from eden host"), nil },
	}}})
	harness.completeHandshake()

	if err := harness.conn.Send(t.Context(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "Call eden_ping with payload hello-eden."}); err != nil {
		t.Fatalf("Prompt on the live rpc session: %v", err)
	}

	// (1) the host-tool round trip, earning CapHostTools.
	harness.emit(rpcFixture(t, hostToolFixture)...)
	answer := harness.waitFrame("host_tool_result", hasType("host_tool_result"))
	if id := stringField(answer, "id"); id != hostToolFrameID {
		t.Errorf("host_tool_result id = %q, want %q%s", id, hostToolFrameID, wrongIDHint(id))
	}
	assertContentIsAnArray(t, answer, "pong from eden host")

	// (2) the permission round trip, earning CapPermissionPrompt: it is SURFACED and ANSWERED.
	approval := rpcFixture(t, approvalFixture)
	harness.emit(approval[1])
	ask := harness.waitEvent("an EventPermissionRequest for the approval dialog", func(event *agentsession.Event) bool {
		return event.Kind == agentsession.EventPermissionRequest
	})
	assertAskIsActionable(t, ask)
	harness.waitFrame("extension_ui_response", hasType("extension_ui_response"))

	// (3) only now, the claim.
	manifest := ompadapter.MustNewForTest(t, ompadapter.Config{}).Manifest()
	for _, capability := range []agentsession.Capability{agentsession.CapHostTools, agentsession.CapPermissionPrompt} {
		if status := manifest.Status(capability); status != agentsession.CapFull {
			t.Errorf("Manifest %s = %v, want CapFull — the round trip above is wired, and a manifest that under-claims it makes the library degrade a capability it has",
				capability, status)
		}
	}
}

// ── assertions ───────────────────────────────────────────────────────────────────────────────.

// assertRegistersEdenPing proves the set_host_tools frame carries the Spec's HostTool by name in
// the `tools` array RpcHostToolDefinition describes (name + description + parameters).
func assertRegistersEdenPing(t *testing.T, frame map[string]any) {
	t.Helper()
	tools, ok := frame["tools"].([]any)
	if !ok || len(tools) == 0 {
		t.Fatalf("set_host_tools carries no `tools` array: %v", frame)
	}
	first, ok := tools[0].(map[string]any)
	if !ok {
		t.Fatalf("set_host_tools tools[0] is %T, want an object: %v", tools[0], frame)
	}
	if name := stringField(first, "name"); name != "eden_ping" {
		t.Errorf("set_host_tools registered %q, want eden_ping (the Spec's HostTool)", name)
	}
	if description := stringField(first, "description"); description == "" {
		t.Errorf("set_host_tools sent no description; it is a required field of RpcHostToolDefinition: %v", first)
	}
}

// assertContentIsAnArray proves the ONLY structural requirement omp enforces on a host tool
// answer: isAgentToolResult accepts result.content ONLY when Array.isArray holds. A string
// result is not an error — the frame is dropped and the model waits for a tool that already ran.
func assertContentIsAnArray(t *testing.T, frame map[string]any, wantText string) {
	t.Helper()
	result, ok := frame["result"].(map[string]any)
	if !ok {
		t.Fatalf("host_tool_result carries result %T, want an object: %v", frame["result"], frame)
	}
	content, ok := result["content"].([]any)
	if !ok {
		t.Fatalf("host_tool_result result.content is %T, want a JSON ARRAY — isRpcHostToolResult drops the frame unless Array.isArray(result.content): %v",
			result["content"], frame)
	}
	if len(content) == 0 {
		t.Fatalf("host_tool_result result.content is empty; the handler's output is lost: %v", frame)
	}
	if rendered := renderJSON(t, content); !strings.Contains(rendered, wantText) {
		t.Errorf("host_tool_result content = %s, want it to carry the HostTool handler's output %q", rendered, wantText)
	}
}

// assertLegalDialogAnswer proves the answer is one of the three RpcExtensionUIResponse variants
// (rpc-types.ts:535): a `value` for select/input/editor, a `confirmed` boolean for confirm, or the
// dismissal field (dialogDismissField, spelled omp's way) set true. A frame outside that union
// does not resolve the dialog.
func assertLegalDialogAnswer(t *testing.T, frame map[string]any) {
	t.Helper()
	_, hasValue := frame["value"].(string)
	_, hasConfirmed := frame["confirmed"].(bool)
	if !hasValue && !hasConfirmed && !boolField(frame, dialogDismissField) {
		t.Errorf("extension_ui_response is none of the three variants (value | confirmed | %s:true) and resolves nothing: %v",
			dialogDismissField, frame)
	}
	if value, ok := frame["value"].(string); ok && !isDialogOption(value) {
		t.Errorf("extension_ui_response value = %q, want one of the dialog's own options [\"Approve\",\"Deny\"] — the value is matched against them", value)
	}
}

// isDialogOption reports whether the answer names one of the captured dialog's own option labels.
// omp matches the value against the `options` array, so anything else resolves nothing; the
// comparison is case-insensitive because the adapter answers with the label VERBATIM from the
// frame and a future capture may spell it differently.
func isDialogOption(value string) bool {
	return strings.EqualFold(value, "approve") || strings.EqualFold(value, "deny")
}

// assertAskIsActionable proves the surfaced permission request is one a decider can act on: it
// carries the dialog's id (an answer is correlated by it) and names the tool being asked about.
// omp puts the tool name in the dialog title's first line ("Allow tool: bash"), which is the only
// place it appears on this frame family.
func assertAskIsActionable(t *testing.T, ask *agentsession.Event) {
	t.Helper()
	if ask.Permission == nil {
		t.Fatalf("EventPermissionRequest carries no PermissionPayload: %+v", ask)
	}
	if ask.Permission.RequestID != selectFrameID {
		t.Errorf("permission RequestID = %q, want the dialog id %q — a decision that cannot be correlated cannot be delivered",
			ask.Permission.RequestID, selectFrameID)
	}
	if !strings.Contains(ask.Permission.Tool, "bash") && !strings.Contains(ask.Permission.Reason, "bash") {
		t.Errorf("the ask names no tool (Tool=%q Reason=%q); a policy cannot decide what it cannot identify",
			ask.Permission.Tool, ask.Permission.Reason)
	}
}

// assertSameSentinel proves the close error is STICKY by IDENTITY, not by value: the caller
// pending at Close and the caller after it must receive the SAME error — one declared sentinel
// handed out twice — exactly as omp's own bridge stores ONE #closedError and rejects the pending
// call and every future one with it (q4 §5).
//
// Comparing the extracted typed CAUSE by value was too weak: two errors each freshly wrapping an
// equal State{From:Completed,Op:"Send"} would compare equal and pass, so a per-call constructed
// error — precisely what a "sticky sentinel" must NOT be — would slip through. This compares the
// original errors by interface identity (same dynamic pointer), which a per-call construction
// cannot satisfy. Each must also carry a contract-typed cause so a caller can branch on it
// (rule 12); a sentinel that is one value but only a bare message is still unbranchable.
func assertSameSentinel(t *testing.T, pendingErr, postErr error) {
	t.Helper()
	contractTypedCause(t, pendingErr, "the Send pending at Close")
	contractTypedCause(t, postErr, "the Send after Close")
	if pendingErr != postErr {
		t.Errorf("the close error is not ONE sticky sentinel by identity: pending caller got %#v, later caller got %#v — a per-call constructed error, even one whose typed cause is value-equal, is not the shared sentinel omp's bridge model requires (q4 §5)",
			pendingErr, postErr)
	}
}

// contractTypedCause returns the first cause in err's chain whose type is declared by the
// agentsession contract package — the only error vocabulary a caller OUTSIDE this adapter can
// branch on (rule 12: inspect by type, never by string). ompadapter exports no error type of its
// own and must not start one: its .apibaseline section is frozen byte-identical by this rewrite.
func contractTypedCause(t *testing.T, err error, what string) any {
	t.Helper()
	for cause := err; cause != nil; cause = stderrors.Unwrap(cause) {
		value := reflect.ValueOf(cause)
		for value.Kind() == reflect.Pointer && !value.IsNil() {
			value = value.Elem()
		}
		if value.Type().PkgPath() == contractPackage {
			return value.Interface()
		}
	}
	t.Fatalf("%s returned an error with no typed cause from %s: %v (%T) — a caller can only match its message text, which rule 12 forbids",
		what, contractPackage, err, err)
	return nil
}

// ── the in-memory omp transport ──────────────────────────────────────────────────────────────.

// rpcHarness drives one rpc conn over an in-memory transport: frames written with emit are what
// omp would print on ITS stdout, and everything the conn writes to omp's stdin is recorded by
// stdin. Every event the conn publishes is drained continuously, exactly as the library's pump
// does, so the conn is never blocked on a reader that is not there.
type rpcHarness struct {
	t      *testing.T
	conn   agentsession.HarnessConn
	stdout *io.PipeWriter
	stdin  *recordingStdin

	mu      sync.Mutex
	events  []agentsession.Event
	drained chan struct{}
}

// newRPCHarness builds the conn over the in-memory transport and reaps it (and the transport) at
// cleanup, asserting the event channel is closed — a conn whose pump outlives Close is a leak the
// package's goleak TestMain would report against whichever test ran last.
func newRPCHarness(t *testing.T, spec agentsession.Spec) *rpcHarness { //nolint:gocritic // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
	t.Helper()
	reader, writer := io.Pipe()
	harness := &rpcHarness{t: t, stdout: writer, stdin: &recordingStdin{}, drained: make(chan struct{})}
	harness.conn = ompadapter.RPCConnForTest(spec, reader, harness.stdin)
	go harness.drain()
	t.Cleanup(func() {
		_ = harness.conn.Close(context.Background()) //nolint:errcheck // best-effort reap; Close is idempotent and this second call also exercises that.
		_ = writer.Close()                           //nolint:errcheck // releases any test-side write still blocked on the conn's reader.
		_ = reader.Close()                           //nolint:errcheck // ends the conn's read pump if Close did not.
		select {
		case <-harness.drained:
		case <-time.After(rpcDeadline):
			t.Errorf("the conn's event channel was still open %s after Close: the pump outlives the session", rpcDeadline)
		}
	})
	return harness
}

// drain consumes the conn's event channel for the whole test, recording every event.
func (h *rpcHarness) drain() {
	defer close(h.drained)
	for event := range h.conn.Events() {
		h.mu.Lock()
		h.events = append(h.events, event)
		h.mu.Unlock()
	}
}

// emit writes frames on omp's stdout, one NDJSON line each. A write the conn never reads is a
// FAILURE naming the frames it stopped at, never a hang.
func (h *rpcHarness) emit(frames ...string) {
	h.t.Helper()
	written := make(chan error, 1)
	go func() {
		_, err := io.WriteString(h.stdout, strings.Join(frames, "\n")+"\n")
		written <- err
	}()
	select {
	case err := <-written:
		if err != nil {
			h.t.Fatalf("write %d frame(s) on omp's stdout: %v", len(frames), err)
		}
	case <-time.After(rpcDeadline):
		h.t.Fatalf("the conn did not read %d frame(s) from omp's stdout within %s; it stopped reading at: %s",
			len(frames), rpcDeadline, frames[0])
	}
}

// completeHandshake drives the captured startup exchange to Ready: the `ready` frame, the host's
// negotiate_protocol, then the rest of the captured startup burst.
func (h *rpcHarness) completeHandshake() {
	h.t.Helper()
	frames := rpcFixture(h.t, handshakeFixture)
	h.emit(frames[0])
	h.waitFrame("negotiate_protocol", hasType("negotiate_protocol"))
	h.emit(frames[1:]...)
	h.waitEvent("the Initializing->Ready transition", isReady)
}

// waitFrame returns the first frame the conn wrote on omp's stdin that matches, or FAILS naming
// what never arrived and everything that did.
func (h *rpcHarness) waitFrame(what string, match func(map[string]any) bool) map[string]any {
	h.t.Helper()
	deadline := time.Now().Add(rpcDeadline)
	for {
		if frame, found := h.stdin.find(match); found {
			return frame
		}
		if time.Now().After(deadline) {
			h.t.Fatalf("no %s frame on omp's stdin within %s; the conn wrote: %s", what, rpcDeadline, h.stdin.render())
		}
		time.Sleep(rpcPoll)
	}
}

// waitEvent returns the first published event that matches, or FAILS naming what never arrived.
func (h *rpcHarness) waitEvent(what string, match func(*agentsession.Event) bool) *agentsession.Event {
	h.t.Helper()
	deadline := time.Now().Add(rpcDeadline)
	for {
		if event, found := h.findEvent(match); found {
			return event
		}
		if time.Now().After(deadline) {
			h.t.Fatalf("no event matching %s within %s; the conn published: %s", what, rpcDeadline, h.renderEvents())
		}
		time.Sleep(rpcPoll)
	}
}

// findEvent reports the first published event that matches, without waiting.
func (h *rpcHarness) findEvent(match func(*agentsession.Event) bool) (*agentsession.Event, bool) {
	h.mu.Lock()
	defer h.mu.Unlock()
	for i := range h.events {
		if match(&h.events[i]) {
			found := h.events[i]
			return &found, true
		}
	}
	return nil, false
}

// renderEvents lists the published event kinds for a failure message.
func (h *rpcHarness) renderEvents() string {
	h.mu.Lock()
	defer h.mu.Unlock()
	if len(h.events) == 0 {
		return "(nothing)"
	}
	kinds := make([]string, 0, len(h.events))
	for i := range h.events {
		kinds = append(kinds, h.events[i].Kind.String())
	}
	return strings.Join(kinds, ", ")
}

// recordingStdin is omp's stdin as the test sees it: every frame the conn writes is decoded and
// kept, and a write never blocks the conn — except when the test deliberately gates one to hold a
// caller in flight across Close. Close is the EOF the conn owes omp, and it releases the gate.
type recordingStdin struct {
	mu      sync.Mutex
	partial []byte
	frames  []map[string]any
	closed  bool

	gate    chan struct{} // armed by blockNextWrite; closed by Close
	blocked chan struct{} // closed once a write is actually parked on the gate
}

// Write records whole NDJSON frames, parking first when the test has gated the next write.
func (s *recordingStdin) Write(p []byte) (int, error) {
	if err := s.park(); err != nil {
		return 0, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return 0, io.ErrClosedPipe
	}
	s.partial = append(s.partial, p...)
	for {
		index := strings.IndexByte(string(s.partial), '\n')
		if index < 0 {
			break
		}
		line := strings.TrimSpace(string(s.partial[:index]))
		s.partial = s.partial[index+1:]
		if line == "" {
			continue
		}
		var frame map[string]any
		if err := json.Unmarshal([]byte(line), &frame); err != nil {
			frame = map[string]any{"type": "<not json>", "raw": line}
		}
		s.frames = append(s.frames, frame)
	}
	return len(p), nil
}

// park blocks the caller when a gate is armed, until the gate is released or stdin is closed.
func (s *recordingStdin) park() error {
	s.mu.Lock()
	gate, blocked := s.gate, s.blocked
	s.mu.Unlock()
	if gate == nil {
		return nil
	}
	close(blocked)
	<-gate
	return io.ErrClosedPipe
}

// Close is the stdin EOF: on the real transport it is what makes omp reject its pending
// requests, drain the accepted commands and exit 0. It releases any parked writer.
func (s *recordingStdin) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return nil
	}
	s.closed = true
	if s.gate != nil {
		close(s.gate)
		s.gate = nil
	}
	return nil
}

// blockNextWrite arms the gate so the next frame the conn writes parks until Close.
func (s *recordingStdin) blockNextWrite() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.gate = make(chan struct{})
	s.blocked = make(chan struct{})
}

// awaitBlockedWrite waits until a write is actually parked, so the test never races Close ahead
// of the caller it means to catch in flight.
func (s *recordingStdin) awaitBlockedWrite(t *testing.T) {
	t.Helper()
	s.mu.Lock()
	blocked := s.blocked
	s.mu.Unlock()
	select {
	case <-blocked:
	case <-time.After(rpcDeadline):
		t.Fatalf("no frame was written on omp's stdin within %s of the Prompt, so no caller is pending at Close", rpcDeadline)
	}
}

// find reports the first recorded frame that matches, without waiting.
func (s *recordingStdin) find(match func(map[string]any) bool) (map[string]any, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, frame := range s.frames {
		if match(frame) {
			return frame, true
		}
	}
	return nil, false
}

// render lists the recorded frame types for a failure message.
func (s *recordingStdin) render() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.frames) == 0 {
		return "(nothing)"
	}
	types := make([]string, 0, len(s.frames))
	for _, frame := range s.frames {
		types = append(types, stringField(frame, "type"))
	}
	return strings.Join(types, ", ")
}

// ── fixtures and small predicates ────────────────────────────────────────────────────────────.

// rpcFixture reads one captured frame file, returning its JSON lines in wire order. The `#` lines
// are the provenance header (which probe capture each frame came from, and whether it was
// truncated there) and are not frames.
func rpcFixture(t *testing.T, name string) []string {
	t.Helper()
	file, err := os.Open(filepath.Join("testdata", name)) //nolint:gosec // a fixed test fixture path.
	if err != nil {
		t.Fatalf("open fixture %s: %v", name, err)
	}
	t.Cleanup(func() { _ = file.Close() }) //nolint:errcheck // best-effort fixture-file close.

	var frames []string
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 8<<20)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		frames = append(frames, line)
	}
	if err := scanner.Err(); err != nil {
		t.Fatalf("scan fixture %s: %v", name, err)
	}
	if len(frames) == 0 {
		t.Fatalf("fixture %s carries no frames", name)
	}
	return frames
}

// hasType matches a written frame by its top-level `type`.
func hasType(name string) func(map[string]any) bool {
	return func(frame map[string]any) bool { return stringField(frame, "type") == name }
}

// stringField reads a decoded frame's string field, returning "" when the key is absent or
// carries another JSON type. A frame is decoded into map[string]any, so every read is a type
// assertion; going through one checked reader keeps the assertion honest at every call site
// (errcheck's check-type-assertions) instead of discarding the ok bit eleven times.
func stringField(frame map[string]any, name string) string {
	value, ok := frame[name].(string)
	if !ok {
		return ""
	}
	return value
}

// boolField reads a decoded frame's boolean field, returning false when the key is absent or
// carries another JSON type.
func boolField(frame map[string]any, name string) bool {
	value, ok := frame[name].(bool)
	if !ok {
		return false
	}
	return value
}

// isReady matches the Initializing->Ready handshake event.
func isReady(event *agentsession.Event) bool {
	return event.Kind == agentsession.EventSessionState && event.State != nil && event.State.To == agentsession.StateReady
}

// numberIs reports whether a decoded JSON number equals want (encoding/json decodes into
// float64 when the target is any).
func numberIs(value any, want float64) bool {
	number, ok := value.(float64)
	return ok && number == want
}

// wrongIDHint names the specific mis-correlation when the answer echoed the model's tool-call id.
func wrongIDHint(got string) string {
	if got == modelToolCallID {
		return " — that is the MODEL's toolCallId; #pendingCalls is keyed by the RPC frame id, so this answer resolves nothing and the model waits forever"
	}
	return ""
}

// renderJSON renders a decoded value back to compact JSON for a substring assertion.
func renderJSON(t *testing.T, value any) string {
	t.Helper()
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("marshal %v: %v", value, err)
	}
	return string(encoded)
}
