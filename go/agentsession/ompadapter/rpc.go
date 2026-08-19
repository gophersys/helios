package ompadapter

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/errors"
)

// rpcProtocolVersion is the protocol the host negotiates on the `ready` frame. omp runs
// protocol 1 until the host asks for another and offers [1,2] in supportedProtocolVersions;
// the rpc wire schema is byte-identical across 17.2.5 and 17.3.7 (rpc-types.ts, sha1
// f3a62ed4), so 2 is safe on the pinned harness.
const rpcProtocolVersion = 2

// errRPCSessionClosed is the ONE sticky error every caller of a closed session gets — the one
// blocked in flight when Close landed and every one after it. It mirrors what omp does on its
// side of the same event: on stdin EOF its host-tool bridge closes with a sticky #closedError
// that rejects every pending call AND every future one. The typed cause is agentsession's, the
// only error vocabulary a caller outside this adapter can branch on (rule 12).
//
//nolint:gochecknoglobals // a sticky sentinel MUST be one value: two callers that construct their own are not the same error.
var errRPCSessionClosed = errors.Wrap(errors.KindUnavailable, "ompadapter: rpc session closed",
	agentsession.StateError{From: agentsession.StateCompleted, Op: "Send"})

// rpcFrame is the omp `--mode rpc` envelope, decoded far enough to route a frame. Everything
// the adapter does NOT act on still reaches the normalizer, which preserves it verbatim.
type rpcFrame struct {
	Type   string `json:"type"`
	ID     string `json:"id"`
	Method string `json:"method"` // extension_ui_request: the dialog/widget verb

	// extension_ui_request (select): the tool name rides the title's first line, and an answer
	// names one of these options.
	Title   string   `json:"title"`
	Options []string `json:"options"`

	// host_tool_call / host_tool_cancel.
	ToolName  string          `json:"toolName"`
	Arguments json.RawMessage `json:"arguments"`
	TargetID  string          `json:"targetId"`
}

// rpcConn is the HarnessConn for ONE long-lived `omp --mode rpc` session. It owns the frame
// pump (omp's stdout -> normalized Events) and the command writer (Prompt/Steer/Abort ->
// NDJSON frames on omp's stdin); the process itself is attached by Spawn and reaped by Close.
//
// Concurrency: one pump goroutine owns the reader and the events channel; every stdin write is
// serialized under writeMu; Close is idempotent via closeOnce and takes NO write lock, so it
// can hand omp its EOF while a caller is still blocked writing.
type rpcConn struct {
	fromOMP    io.Reader
	toOMP      io.WriteCloser
	normalizer *normalizer
	hostTools  *hostToolRouter
	digest     digester

	// granted is the tool set this session launched with (the same names that ride --tools).
	// It is the standing authorization the approval dialog is answered from.
	granted map[string]struct{}

	events chan agentsession.Event

	writeMu sync.Mutex   // serializes whole NDJSON frames onto omp's stdin
	frameID atomic.Int64 // the host-chosen correlation ids ("1", "2", "3", ... as captured)

	mu      sync.Mutex
	closed  bool
	command *exec.Cmd // the child to reap; nil on the in-memory transport seam

	done      chan struct{} // closed at Close: releases a pump blocked publishing
	drained   chan struct{} // closed when the pump has read omp's stdout to its end
	closeOnce sync.Once
	reapOnce  sync.Once
}

// newRPCConn builds the conn over an already-open transport and starts pumping immediately, so
// omp's `ready` frame is read the moment it arrives. toOMP is a WriteCloser because the stdin
// EOF is load-bearing rather than incidental: closing it is what makes omp reject its pending
// requests, drain the accepted commands, dispose the session and exit 0.
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
func newRPCConn(spec agentsession.Spec, fromOMP io.Reader, toOMP io.WriteCloser) *rpcConn {
	conn := &rpcConn{
		fromOMP:    fromOMP,
		toOMP:      toOMP,
		normalizer: newNormalizer(),
		digest:     defaultDigester,
		granted:    grantedTools(spec.Grants),
		events:     make(chan agentsession.Event),
		done:       make(chan struct{}),
		drained:    make(chan struct{}),
	}
	conn.hostTools = newHostToolRouter(spec.HostTools, conn.writeFrame)
	go conn.pump()
	return conn
}

// grantedTools indexes the tool names the session launched with — the same set toolArguments
// renders into --tools, so the approval dialog and the tool allowlist cannot disagree.
func grantedTools(grants []agentsession.ToolGrant) map[string]struct{} {
	names := toolNames(grants)
	index := make(map[string]struct{}, len(names))
	for _, name := range names {
		index[name] = struct{}{}
	}
	return index
}

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *rpcConn) Events() <-chan agentsession.Event { return c.events }

// Send writes one control frame on omp's stdin. Under rpc a turn is a FRAME on the living
// session — never a positional argv on a fresh process — so Prompt/Steer are non-blocking
// writes and Abort is omp's own `abort` command rather than a kill.
func (c *rpcConn) Send(ctx context.Context, command agentsession.Command) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	if err := c.closedError(); err != nil {
		return err
	}
	switch command.Kind {
	case agentsession.CommandAbort:
		return c.writeFrame(map[string]any{"id": c.nextFrameID(), "type": "abort"})
	case agentsession.CommandSteer:
		if _, _, _, _, isDecision := controlframe.DecodePermission(command.Text); isDecision {
			// A resolved permission decision, tunneled as a steer by the library. The dialog it
			// answers was resolved on the wire the instant it arrived — omp arms no timer on a
			// `select` (rpc-mode.ts:640), so a dialog held open for an out-of-band decision stalls
			// the turn forever, and an answer to a dialog omp has already resolved matches nothing.
			// The decision is the library's record; what must never happen is this internal frame
			// reaching omp as conversation text, which the steer below would do.
			return nil
		}
		return c.writeFrame(map[string]any{"id": c.nextFrameID(), "type": "steer", "message": command.Text})
	case agentsession.CommandPrompt:
		return c.writeFrame(map[string]any{"id": c.nextFrameID(), "type": "prompt", "message": command.Text})
	default:
		return errors.New(errors.KindInvalid, "ompadapter: unknown control kind")
	}
}

// Close ends the session: it marks the conn closed (so the caller blocked in flight and every
// caller after it get the same sticky error), then hands omp the stdin EOF that makes it reject
// its pending requests, drain the accepted commands and exit 0, then reaps the child. It is
// idempotent, and it takes no write lock — a Close that waited for an in-flight write could
// never deliver the EOF that releases it.
func (c *rpcConn) Close(ctx context.Context) error {
	c.closeOnce.Do(func() {
		c.mu.Lock()
		c.closed = true
		c.mu.Unlock()
		c.hostTools.closeAll()
		close(c.done)
		_ = c.toOMP.Close() //nolint:errcheck // the EOF is the signal; an already-closed stdin is the desired state.
	})
	c.reap(ctx)
	return nil
}

// pump reads omp's stdout frame by frame for the whole session: each line is serviced (the rpc
// control plane — readiness, host tools, dialogs) and then normalized onto the Event taxonomy,
// so a frame the adapter acts on is still surfaced rather than swallowed. On EOF it closes the
// events channel: the library reads a closed channel with no terminal as a transport failure,
// and one with no Ready as the silent-bad-token trap.
func (c *rpcConn) pump() {
	defer c.finish()
	scanner := bufio.NewScanner(c.fromOMP)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	for scanner.Scan() {
		line := scanner.Bytes()
		if !c.publish(c.service(line)) {
			return
		}
		if !c.publish(c.normalizer.normalize(line)) {
			return
		}
	}
}

// service acts on the rpc control frames and returns the Events that servicing produced. A line
// that is not one of them (or is not JSON at all) produces nothing here and is left to the
// normalizer.
func (c *rpcConn) service(line []byte) []agentsession.Event {
	var frame rpcFrame
	if err := json.Unmarshal(line, &frame); err != nil {
		return nil
	}
	switch frame.Type {
	case "ready":
		return c.handshake()
	case "extension_ui_request":
		return c.dialog(&frame)
	case "host_tool_call":
		c.hostTools.call(frame.ID, frame.ToolName, frame.Arguments)
		return nil
	case "host_tool_cancel":
		// The bridge rejects a canceled call locally and does not wait for the host to
		// acknowledge it (q4 §5), so there is no frame to write back.
		c.hostTools.cancel(frame.TargetID)
		return nil
	default:
		return nil
	}
}

// handshake answers omp's `ready` — its ONLY readiness signal, unconditional and first
// (rpc-mode.ts:690) — by negotiating the protocol, registering the session's host tools, and
// publishing the Initializing->Ready transition the library's Open blocks on. Readiness is
// therefore MEASURED: a child that never came up publishes nothing, and Open fails rather than
// returning a live session for a harness that is not there.
func (c *rpcConn) handshake() []agentsession.Event {
	//nolint:errcheck // best-effort handshake: a transport that cannot take these frames ends the pump, and the missing Ready is the actionable outcome.
	_ = c.writeFrame(map[string]any{
		"id": c.nextFrameID(), "type": "negotiate_protocol", "protocolVersion": rpcProtocolVersion,
	})
	if definitions := c.hostTools.definitions(); len(definitions) > 0 {
		//nolint:errcheck // best-effort registration; an unregistered host tool surfaces as a failed call, not a broken transport.
		_ = c.writeFrame(map[string]any{
			"id": c.nextFrameID(), "type": "set_host_tools", "tools": definitions,
		})
	}
	return []agentsession.Event{{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}}
}

// dialog answers an extension_ui_request and surfaces the round trip as the ask AND its
// resolution, in that order.
//
// Answering is not a courtesy. A `select` carries no timeout field and requestRpcDialog arms a
// timer only when opts.timeout is set (rpc-mode.ts:640), so an unanswered dialog waits FOREVER:
// q3-probe5 measured 45 seconds of wall clock with no agent_end and had to kill the child. The
// answer is therefore written on arrival, from the only authorization the session holds — its
// standing grant, the same tool set that rides --tools. A tool outside it is refused, so an
// unattended session can never authorize what nobody granted.
//
// Both events are published because the answer has ALREADY happened: the ask alone would park
// the session at StateAwaitingPermission waiting for a resolution that is on the wire, and the
// resolution alone would hide the ask from the audit record.
//
// The widget/status/notify verbs are fire-and-forget (rpc-mode.ts:824) and are NOT answered:
// omp never waits for them, and an answer to one would be a frame nobody asked for.
func (c *rpcConn) dialog(frame *rpcFrame) []agentsession.Event {
	tool := dialogTool(frame.Title)
	allowed := c.isGranted(tool)
	answer, isDialog := dialogAnswer(frame, allowed)
	if !isDialog {
		return nil
	}
	_ = c.writeFrame(answer) //nolint:errcheck // best-effort: a transport that cannot take the answer has already ended the session, and the stall it would otherwise cause is what this write exists to prevent.
	ask := agentsession.PermissionPayload{
		RequestID: frame.ID,
		Tool:      tool,
		Reason:    c.digest([]byte(frame.Title)),
	}
	resolved := ask
	resolved.Decision, resolved.By = agentsession.GrantDenied, "policy:default-deny"
	if allowed {
		resolved.Decision, resolved.By = agentsession.GrantAllowed, "grant:session"
	}
	return []agentsession.Event{
		{Kind: agentsession.EventPermissionRequest, Permission: &ask},
		{Kind: agentsession.EventPermissionResolved, Permission: &resolved},
	}
}

// dialogAnswer renders the RpcExtensionUIResponse for one dialog (rpc-types.ts:535): a value
// naming one of the dialog's own options for select, a confirmed boolean for confirm, and the
// cancel variant for anything else — including a select whose options this host does not
// recognize, where canceling is the only answer that cannot invent a verdict. isDialog is
// false for the fire-and-forget verbs, which carry no response at all.
func dialogAnswer(frame *rpcFrame, approve bool) (map[string]any, bool) {
	answer := map[string]any{"type": "extension_ui_response", "id": frame.ID}
	switch frame.Method {
	case "select":
		verdict := denyOption
		if approve {
			verdict = approveOption
		}
		option, found := optionLabeled(frame.Options, verdict)
		if !found {
			answer[answerCancelField] = true
			return answer, true
		}
		answer["value"] = option
		return answer, true
	case "confirm":
		answer["confirmed"] = approve
		return answer, true
	case "input", "editor":
		// A free-text dialog has no verdict to give: an unattended host has nothing to type.
		answer[answerCancelField] = true
		return answer, true
	default:
		return nil, false
	}
}

// The two option labels omp's approval dialog offers, matched case-insensitively against the
// dialog's own options because the answer's `value` is compared to them.
const (
	approveOption = "approve"
	denyOption    = "deny"
)

// answerCancelField is the cancel variant's field name, spelled as omp spells it on the wire
// (rpc-types.ts:535). An answer whose key does not match resolves no dialog.
//
//nolint:misspell // the double-L is omp's wire spelling of this field, not this repository's prose; the US-locale linter flags the only spelling that resolves the dialog.
const answerCancelField = "cancelled"

// optionLabeled finds the dialog option carrying the wanted verdict, returning it verbatim (the
// label is matched against the options array, so the exact spelling is what must ride back).
func optionLabeled(options []string, want string) (string, bool) {
	for _, option := range options {
		if strings.EqualFold(strings.TrimSpace(option), want) {
			return option, true
		}
	}
	return "", false
}

// dialogTool reads the tool name out of an approval dialog's title. omp writes it on the first
// line ("Allow tool: bash", with the command on the next), which is the only place it appears
// on this frame family.
func dialogTool(title string) string {
	first, _, _ := strings.Cut(title, "\n")
	if _, name, found := strings.Cut(first, ":"); found {
		return strings.TrimSpace(name)
	}
	return strings.TrimSpace(first)
}

// isGranted reports whether a tool is in the set this session launched with.
func (c *rpcConn) isGranted(tool string) bool {
	_, found := c.granted[tool]
	return found
}

// writeFrame marshals one command frame and writes it as a single NDJSON line. A write that
// fails after the session was closed reports the sticky close error rather than the transport's
// own — the caller blocked in flight when Close landed and the one that arrives afterwards must
// see the same thing.
func (c *rpcConn) writeFrame(frame any) error {
	line, err := json.Marshal(frame)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "ompadapter: marshal rpc frame", err)
	}
	line = append(line, '\n')

	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	if closedErr := c.closedError(); closedErr != nil {
		return closedErr
	}
	if _, writeErr := c.toOMP.Write(line); writeErr != nil {
		if closedErr := c.closedError(); closedErr != nil {
			return closedErr
		}
		return errors.Wrap(errors.KindUnavailable, "ompadapter: write rpc frame", writeErr)
	}
	return nil
}

// nextFrameID returns the next host-chosen correlation id. omp echoes it on the matching
// response frame ("1" for the negotiate, "2" for set_host_tools, "3" for the first prompt — the
// ids the probe captures carry).
func (c *rpcConn) nextFrameID() string {
	return strconv.FormatInt(c.frameID.Add(1), 10)
}

// closedError returns the sticky close error once the session is closed, nil before that.
func (c *rpcConn) closedError() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.closed {
		return errRPCSessionClosed
	}
	return nil
}

// publish fans events onto the channel, reporting false when Close ended the session first so
// the pump returns instead of blocking on a stream nobody will read.
func (c *rpcConn) publish(events []agentsession.Event) bool {
	for i := range events {
		select {
		case c.events <- events[i]:
		case <-c.done:
			return false
		}
	}
	return true
}

// finish closes the event stream and reports the drain, which is what lets Close reap the child
// without truncating the tail of its output.
func (c *rpcConn) finish() {
	close(c.events)
	close(c.drained)
}

// compile-time assertion: *rpcConn is an agentsession.HarnessConn.
var _ agentsession.HarnessConn = (*rpcConn)(nil)
