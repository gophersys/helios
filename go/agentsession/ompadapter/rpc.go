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
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/errors"
)

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

	// name is this session's peer address; "" == not addressable. A conn that does not know
	// its own name cannot tell a delivery meant for it from one that is not.
	name string

	// fallback bounds how long a surfaced dialog waits for the library to resolve it before the
	// adapter answers Deny itself, so omp's timerless `select` (rpc-mode.ts:640) cannot stall.
	fallback time.Duration

	events chan agentsession.Event

	writeMu sync.Mutex   // serializes whole NDJSON frames onto omp's stdin
	frameID atomic.Int64 // the host-chosen correlation ids ("1", "2", "3", ... as captured)

	// dialogMu guards the pending-dialog set: the ask surfaced for each open select, keyed by its
	// frame id, with the options the wire answer must name and the deny-on-timeout timer.
	dialogMu sync.Mutex
	dialogs  map[string]*pendingDialog

	// resolved carries the EventPermissionResolved a settled dialog produces, from resolveDialog
	// (the library's Send goroutine, or the fallback timer) to the pump — the ONE events sender.
	// Buffered so a resolution never blocks its caller; the pump is the only reader.
	resolved chan agentsession.Event

	// peerEvents carries an inbound delivery's EventPeerMessage from Send to the pump, for the
	// same reason and on the same terms as resolved.
	peerEvents chan agentsession.Event

	mu      sync.Mutex
	closed  bool
	command *exec.Cmd // the child to reap; nil on the in-memory transport seam

	done      chan struct{} // closed at Close: releases a pump blocked publishing
	drained   chan struct{} // closed when the pump has read omp's stdout to its end
	closeOnce sync.Once
	reapOnce  sync.Once
}

// pendingDialog is one surfaced approval dialog awaiting a resolution. options are the labels the
// wire answer must name (omp matches the answer's value against them); timer is the deny-on-timeout
// fallback; resolved is the first-wins guard so a library decision and the fallback cannot both
// answer the same dialog.
type pendingDialog struct {
	options  []string
	timer    *time.Timer
	resolved bool
}

// dialogResolveBuffer bounds the resolution hand-off channel. A session has at most one open
// approval dialog at a time in plain rpc, but the buffer is generous so a burst never blocks the
// library's decision goroutine on the pump.
const dialogResolveBuffer = 8

// defaultDialogFallback is the production deny-on-timeout window. It is longer than the library's
// own default permission window (agentsession defaultPermissionTimeout, 5 minutes) on purpose: in
// normal operation the library ALWAYS resolves first — grant, advisor, or its own timeout->deny —
// and that decision reaches the wire. This blunt adapter deny is the last-resort safety net for a
// library that never forwards at all (the session torn down mid-flight, the decision Send dropped),
// so it must not pre-empt the library's own richer resolution.
const defaultDialogFallback = 6 * time.Minute

// newRPCConn builds the conn with the production deny-on-timeout window.
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
func newRPCConn(spec agentsession.Spec, fromOMP io.Reader, toOMP io.WriteCloser) *rpcConn {
	return newRPCConnWithFallback(spec, fromOMP, toOMP, defaultDialogFallback)
}

// newRPCConnWithFallback builds the conn over an already-open transport and starts pumping
// immediately, so omp's `ready` frame is read the moment it arrives. toOMP is a WriteCloser because
// the stdin EOF is load-bearing rather than incidental: closing it is what makes omp reject its
// pending requests, drain the accepted commands, dispose the session and exit 0. fallback is the
// deny-on-timeout window (the test injects a short one; production uses defaultDialogFallback).
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
func newRPCConnWithFallback(spec agentsession.Spec, fromOMP io.Reader, toOMP io.WriteCloser, fallback time.Duration) *rpcConn {
	conn := &rpcConn{
		fromOMP:    fromOMP,
		toOMP:      toOMP,
		normalizer: newNormalizer(),
		digest:     defaultDigester,
		name:       spec.Name,
		fallback:   fallback,
		events:     make(chan agentsession.Event),
		dialogs:    make(map[string]*pendingDialog),
		resolved:   make(chan agentsession.Event, dialogResolveBuffer),
		peerEvents: make(chan agentsession.Event, peerDeliveryBuffer),
		done:       make(chan struct{}),
		drained:    make(chan struct{}),
	}
	conn.hostTools = newHostToolRouter(spec.HostTools, conn.writeFrame)
	go conn.pump()
	return conn
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
		if requestID, allow, by, _, isDecision := controlframe.DecodePermission(command.Text); isDecision {
			// A resolved permission decision, tunneled as a steer by the library (forwardDecision).
			// It answers a surfaced dialog on the WIRE — mapped to that dialog's own options and
			// correlated by id — never as conversation text: omp would read the internal
			// eden:permission frame as user input. The F2 guard is exactly this early return; the
			// genuine-steer path below never sees a decision.
			c.resolveDialog(requestID, allow, by)
			return nil
		}
		// The library's deliver goroutine steers an inbound peer message into a RUNNING turn,
		// so the delivery path is on both turn-taking verbs, not only Prompt. It is UNWRAPPED
		// here: the internal frame never reaches the model.
		if delivery, isPeer := decodePeerDelivery(command.Text); isPeer {
			return c.deliverPeer("steer", &delivery)
		}
		return c.writeFrame(map[string]any{"id": c.nextFrameID(), "type": "steer", "message": command.Text})
	case agentsession.CommandPrompt:
		if delivery, isPeer := decodePeerDelivery(command.Text); isPeer {
			return c.deliverPeer("prompt", &delivery)
		}
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
		c.cancelDialogs()
		c.hostTools.closeAll()
		close(c.done)
		_ = c.toOMP.Close() //nolint:errcheck // the EOF is the signal; an already-closed stdin is the desired state.
	})
	c.reap(ctx)
	return nil
}

// pump is the SOLE sender on the events channel. It reads omp's stdout frames off a reader
// goroutine and interleaves them with the permission RESOLUTIONS the library hands back through
// resolveDialog: each omp line is serviced (the rpc control plane — readiness, host tools, the
// dialog ask) and then normalized onto the taxonomy, while a resolved dialog publishes the
// EventPermissionResolved that moves the session out of StateAwaitingPermission. omp emits no
// resolved frame of its own (it just proceeds with the tool), so the adapter is the harness that
// "emits the EventPermissionResolved record" the library's state machine waits for. On EOF it
// closes the events channel: the library reads a closed channel with no terminal as a transport
// failure, and one with no Ready as the silent-bad-token trap.
func (c *rpcConn) pump() {
	defer c.finish()
	lines := make(chan []byte)
	go c.readLines(lines)
	for {
		pending, alive := c.publishPending()
		if !alive {
			return
		}
		if pending {
			continue
		}
		select {
		case resolved := <-c.resolved:
			if !c.publish([]agentsession.Event{resolved}) {
				return
			}
		case delivered := <-c.peerEvents:
			if !c.publish([]agentsession.Event{delivered}) {
				return
			}
		case line, ok := <-lines:
			if !ok {
				return
			}
			if !c.publishLine(line) {
				return
			}
		case <-c.done:
			return
		}
	}
}

// publishPending fans out a resolution or a peer delivery that is ALREADY waiting, ahead of
// omp's own frames. A ready resolution goes out FIRST so the session leaves
// StateAwaitingPermission before the tool frames that follow the answer — a turn_end reached
// while still awaiting a permission would strand the session there. An inbound peer delivery
// takes the same priority, so the arrival precedes the frames of the turn it caused.
//
// pending reports whether one went out; alive is false once Close ended the session, so the pump
// returns instead of blocking on a stream nobody will read.
func (c *rpcConn) publishPending() (pending, alive bool) {
	select {
	case resolved := <-c.resolved:
		return true, c.publish([]agentsession.Event{resolved})
	case delivered := <-c.peerEvents:
		return true, c.publish([]agentsession.Event{delivered})
	default:
		return false, true
	}
}

// publishLine services one omp frame (the rpc control plane — readiness, host tools, the dialog
// ask) and then normalizes it onto the taxonomy, fanning out what each produced. It reports
// false when Close ended the session first.
func (c *rpcConn) publishLine(line []byte) bool {
	if !c.publish(c.service(line)) {
		return false
	}
	return c.publish(c.normalizer.normalize(line))
}

// readLines scans omp's stdout into whole NDJSON lines and hands COPIES to the pump (the scanner
// reuses its buffer), closing the channel on EOF so the pump ends the session.
func (c *rpcConn) readLines(lines chan<- []byte) {
	defer close(lines)
	scanner := bufio.NewScanner(c.fromOMP)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	for scanner.Scan() {
		line := make([]byte, len(scanner.Bytes()))
		copy(line, scanner.Bytes())
		select {
		case lines <- line:
		case <-c.done:
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
// (rpc-mode.ts:690) — by registering the session's host tools and publishing the
// Initializing->Ready transition the library's Open blocks on. Readiness is therefore MEASURED: a
// child that never came up publishes nothing, and Open fails rather than returning a live session
// for a harness that is not there.
//
// It deliberately negotiates NO protocol. omp's RpcFrameEncoder defaults to protocol 1
// (rpc-frame.ts:265) and flips to 2 only on a `success===true` negotiate response
// (rpc-mode.ts:701-702), so writing nothing IS protocol 1 — the state omp already starts in.
// Protocol 2 is the ONE thing that licenses omp to split an over-1-MiB logical frame into
// `rpc_chunk` lines (rpc-frame.ts:284), and this package reassembles none of them: a chunked
// `agent_end` would dissolve into EventExtension and the turn would never end. omp's own
// reference host treats the two as one indivisible capability — rpc-client.ts:409-419 enables
// chunk reassembly BEFORE it sends the negotiate, and rpc-client.ts:345-346 throws
// "RPC chunk received before protocol negotiation" on a chunk that arrives without it.
//
// Sending `protocolVersion: 1` is NOT the alternative: rpc-mode.ts:979-983 answers any version
// other than 2 with `success:false`, buying an error frame on the wire for the same outcome.
//
// FOLLOW-UP: re-enable the negotiate in the SAME change that adds the `rpc_chunk` reassembler
// (the Go twin of rpc-frame.ts:136-189) — never before it, and never in a change of its own.
func (c *rpcConn) handshake() []agentsession.Event {
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

// dialog SURFACES an approval `select` as an EventPermissionRequest and routes it through the
// library's permission chain — it does NOT decide. Mateo's ruling (2026-08-19): the adapter is
// not a permission authority; it hands the library what the library needs to decide and writes
// back whatever the library resolved (resolveDialog, driven by the tunneled decision in Send).
//
// The command is load-bearing. omp folds the tool onto the title's first line ("Allow tool: bash")
// and the command onto its second ("Command: rm -rf /"). The command is the only thing that
// distinguishes `bash ls` from `bash rm -rf /`, so the adapter folds it into Permission.Tool as
// the "Tool(scope)" shape the library's grant-match and risk-class machinery already consume
// (baseToolName + scopesFromTool) — without it the whole chain is blind and a scoped grant would
// auto-approve a destructive command.
//
// A pending entry is recorded BEFORE the ask is published, because the autonomous chain resolves
// synchronously on receipt: the decision Send arrives while this call's event is still being
// delivered, and resolveDialog must find the entry. The deny-on-timeout timer is armed here
// because the adapter cannot count on omp arming one: a `select` CAN carry a timeout
// (rpc-mode.ts:640), but that is the raising caller's choice, and the approval dialog this adapter
// receives under `--approval-mode always-ask` arrives without one — MEASURED in q3-probe5 (45s,
// no agent_end), not assumed. An ask the library never resolves would stall the turn.
//
// The other three BLOCKING verbs are dismissed on arrival instead. They are not permission asks,
// so the permission chain holds no verdict for them and a headless session has no human to raise
// them to; arming the fallback would only buy minutes of stalled turn for a decision that can
// never arrive. Dismissal fails safe on every one of them, each verified on its own omp code path:
// confirm returns false (rpc-mode.ts:767-774), select and input return undefined
// (parseValueDialogResponse, rpc-mode.ts:521-531), editor calls finish(undefined) (the resolver in
// requestRpcEditor, rpc-mode.ts:586-594).
//
// The routing rule is a CLOSED ALLOWLIST, and that is the point: every other method — notify
// (rpc-mode.ts:798), setStatus (:809), setWidget (:824), setTitle (:847), set_editor_text (:868),
// the cancel WITHDRAWAL (:628, :574), and anything omp adds later — is fire-and-forget, registers
// no pending request, and stays unanswered BY CONSTRUCTION rather than by being excluded one at a
// time. An unsolicited extension_ui_response correlates with nothing on omp's side.
func (c *rpcConn) dialog(frame *rpcFrame) []agentsession.Event {
	switch frame.Method {
	case dialogSelect:
		c.recordDialog(frame.ID, frame.Options)
		return []agentsession.Event{{
			Kind: agentsession.EventPermissionRequest,
			Permission: &agentsession.PermissionPayload{
				RequestID: frame.ID,
				Tool:      foldToolScope(dialogTool(frame.Title), dialogCommand(frame.Title)),
				Reason:    c.digest([]byte(frame.Title)),
			},
		}}
	case dialogConfirm, dialogInput, dialogEditor:
		//nolint:errcheck // best-effort dismissal: a transport that cannot take the answer has already ended the session, and the block it would otherwise cause is what this write exists to prevent.
		_ = c.writeFrame(dismissAnswer(frame.ID))
		return nil
	default:
		return nil
	}
}

// The four extension-UI verbs omp BLOCKS on, and the whole of what dialog answers. Each registers
// a pending request that settles when a matching `extension_ui_response` arrives
// (dispatchRpcControlFrame, rpc-mode.ts:280-284 — an id with no pending entry resolves nothing).
//
// Every OTHER settlement is omp's to trigger, never the host's, so the host can rely on none of
// them: an abort on the raising caller's signal (rpc-mode.ts:628-637, and :574-582 for editor),
// and a timeout. select, confirm and input alike route through requestRpcDialog, whose ONE
// setTimeout (rpc-mode.ts:640-646) arms iff the caller that raised the dialog set
// dialogOptions.timeout (select :745-756, confirm :761-775, input :783-790) — a choice made on
// omp's side by the tool or extension behind the dialog, which the host neither makes nor sees in
// advance. `editor` goes through requestRpcEditor (rpc-mode.ts:544-606) and arms no timer on ANY
// path. The last resort is rejectAll (rpc-mode.ts:81), whose sole call site is the stdin-closed
// path at rpc-mode.ts:1507 — session teardown.
const (
	dialogSelect  = "select"  // rpc-mode.ts:740
	dialogConfirm = "confirm" // rpc-mode.ts:760
	dialogInput   = "input"   // rpc-mode.ts:778
	dialogEditor  = "editor"  // rpc-mode.ts:884
)

// fallbackDenyBy is the deciding identity the adapter stamps on a deny-on-timeout resolution — the
// last-resort safety net, distinct from any library verdict so the audit record shows the library
// never resolved this one.
const fallbackDenyBy = "policy:adapter-timeout-deny"

// recordDialog registers a surfaced dialog and arms its deny-on-timeout fallback. A conn already
// closed records nothing (its dialogs were canceled and no answer can go out).
func (c *rpcConn) recordDialog(id string, options []string) {
	c.dialogMu.Lock()
	defer c.dialogMu.Unlock()
	if c.dialogs == nil {
		return
	}
	entry := &pendingDialog{options: options}
	entry.timer = time.AfterFunc(c.fallback, func() { c.resolveDialog(id, false, fallbackDenyBy) })
	c.dialogs[id] = entry
}

// resolveDialog answers a surfaced dialog once — first writer wins between the library's tunneled
// decision and the deny-on-timeout fallback. It marks the dialog resolved under the lock, stops the
// timer, writes the wire answer mapped to the dialog's own options, and hands the pump the
// EventPermissionResolved that moves the session out of StateAwaitingPermission. A decision for an
// id with no pending dialog (one that raced Close, or one for a dialog this conn never surfaced)
// does nothing — there is no ask to resolve and no state to recover.
func (c *rpcConn) resolveDialog(id string, allow bool, by string) {
	c.dialogMu.Lock()
	entry, ok := c.dialogs[id]
	if !ok || entry.resolved {
		c.dialogMu.Unlock()
		return
	}
	entry.resolved = true
	if entry.timer != nil {
		entry.timer.Stop()
	}
	options := entry.options
	delete(c.dialogs, id)
	c.dialogMu.Unlock()

	_ = c.writeFrame(wireAnswer(id, options, allow)) //nolint:errcheck // best-effort: a transport that cannot take the answer has already ended the session, and the stall it would otherwise cause is what this write exists to prevent.
	c.publishResolved(id, allow, by)
}

// publishResolved hands the pump the resolution record. It is buffered and done-guarded so the
// library's decision goroutine never blocks on the pump, and a resolution that lands after Close
// (the pump already gone) is harmlessly dropped.
func (c *rpcConn) publishResolved(id string, allow bool, by string) {
	decision := agentsession.GrantDenied
	if allow {
		decision = agentsession.GrantAllowed
	}
	event := agentsession.Event{
		Kind: agentsession.EventPermissionResolved,
		Permission: &agentsession.PermissionPayload{
			RequestID: id,
			Decision:  decision,
			By:        by,
		},
	}
	select {
	case c.resolved <- event:
	case <-c.done:
	}
}

// cancelDialogs stops every pending fallback timer at Close and drops the set, so no timer fires
// after the transport is gone and no dialog goroutine outlives the session (goleak).
func (c *rpcConn) cancelDialogs() {
	c.dialogMu.Lock()
	defer c.dialogMu.Unlock()
	for _, entry := range c.dialogs {
		entry.resolved = true
		if entry.timer != nil {
			entry.timer.Stop()
		}
	}
	c.dialogs = nil
}

// wireAnswer renders the VALUE variant of RpcExtensionUIResponse for a resolved select
// (rpc-types.ts:536): the library's verdict mapped to the dialog's OWN option label (omp matches
// the answer's value against its options array). When the expected label is absent it falls back to
// dismissAnswer, which fails safe — a dismissed dialog is a denial, never a fabricated approval.
func wireAnswer(id string, options []string, allow bool) map[string]any {
	want := denyOption
	if allow {
		want = approveOption
	}
	option, found := optionLabeled(options, want)
	if !found {
		return dismissAnswer(id)
	}
	return map[string]any{"type": "extension_ui_response", "id": id, "value": option}
}

// dismissAnswer renders the DISMISSAL variant of RpcExtensionUIResponse (rpc-types.ts:538) — the
// one variant of the three that carries no verdict, and the ONE home for the shape. It is the whole
// answer to a blocking verb Eden cannot decide, and wireAnswer's fail-safe when a select's options
// carry no matching label. `timedOut` is deliberately absent: setting it would fire omp's own
// onTimeout hook (rpc-mode.ts:526, :769), and this is a dismissal, not an expiry.
func dismissAnswer(id string) map[string]any {
	return map[string]any{"type": "extension_ui_response", "id": id, answerDismissField: true}
}

// The two option labels omp's approval dialog offers, matched case-insensitively against the
// dialog's own options because the answer's `value` is compared to them.
const (
	approveOption = "approve"
	denyOption    = "deny"
)

// answerDismissField is the dismissal variant's field name, spelled as omp spells it on the wire
// (rpc-types.ts:538). An answer whose key does not match resolves no dialog.
//
//nolint:misspell // the double-L is omp's wire spelling of this field, not this repository's prose; the US-locale linter flags the only spelling that resolves the dialog.
const answerDismissField = "cancelled"

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

// foldToolScope renders the "Tool(scope)" shape the library's grant-match/risk-class machinery
// consumes: the command as the tool's scope (e.g. bash + "rm -rf /" -> "bash(rm -rf /)"). A dialog
// with no command line yields the bare tool name, which for a shell the library already treats as
// unbounded (RiskHigh).
func foldToolScope(tool, command string) string {
	if command == "" {
		return tool
	}
	return tool + "(" + command + ")"
}

// dialogTool reads the tool name from an approval dialog's title first line ("Allow tool: bash").
func dialogTool(title string) string {
	first, _, _ := strings.Cut(title, "\n")
	if _, name, found := strings.Cut(first, ":"); found {
		return strings.TrimSpace(name)
	}
	return strings.TrimSpace(first)
}

// dialogCommand reads the command from an approval dialog's title second line ("Command: rm -rf /").
// A title with no second line (a dialog that names only a tool) yields "".
func dialogCommand(title string) string {
	_, rest, found := strings.Cut(title, "\n")
	if !found {
		return ""
	}
	line, _, _ := strings.Cut(rest, "\n")
	if _, command, ok := strings.Cut(line, ":"); ok {
		return strings.TrimSpace(command)
	}
	return strings.TrimSpace(line)
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
// response frame ("1" for set_host_tools, "2" for the first prompt — the probe captures carry
// the ids one higher, from the negotiate this host no longer sends: see handshake()).
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
