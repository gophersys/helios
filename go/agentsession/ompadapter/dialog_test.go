// The `--mode rpc` TRANSPORT + DIALOG contract, derived from the PINNED harness source
// (omp 17.2.5, src/modes/rpc/). Three measured defects are pinned here:
//
//	D1 chunking  — the adapter negotiates protocol 2 (rpc.go:346-348) and then cannot decode what
//	               protocol 2 licenses omp to send. rpc-frame.ts:284 makes protocol 2 the ONLY
//	               thing that turns an over-1-MiB logical frame into `rpc_chunk` lines, and this
//	               package has no reassembler (the Go twin of rpc-frame.ts:136-189), so an
//	               oversized `agent_end` — the frame that ENDS THE TURN — dissolves into
//	               EventExtension and the turn never ends.
//	D2/D3 dialog — only `select` is answered (rpc.go:381). `confirm` and `input` ride
//	               requestRpcDialog (rpc-mode.ts:609), whose promise settles solely on a matching
//	               `extension_ui_response` (rpc-mode.ts:279-284) and whose timer is armed ONLY
//	               when the request carries a `timeout` field (rpc-mode.ts:640) — the adapter's
//	               asks never do. `editor` rides requestRpcEditor (rpc-mode.ts:544-606), which
//	               arms no timer on ANY path. An unanswered one of those three blocks omp until
//	               the client disconnects (rejectAll, rpc-mode.ts:81) — i.e. session teardown.
//
// The oversize proof does not hand-write a chunk stream. It drives a MIRROR of omp's own
// RpcFrameEncoder (rpc-frame.ts:263-316) that reads the conn's stdin recorder and branches on
// what the ADAPTER asked for, exactly as the real encoder branches on what it was told — so the
// same test proves the defect today and the fix tomorrow, without either side being scripted.
package ompadapter_test

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// omp's transport constants, spelled as rpc-frame.ts spells them so a pin bump that moves one is
// a one-line diff here rather than an arithmetic hunt.
const (
	// maxRPCFrameBytes is MAX_RPC_FRAME_BYTES (rpc-frame.ts:6): the utf-8 ceiling on ONE
	// newline-delimited physical frame, INCLUDING the newline.
	maxRPCFrameBytes = 1024 * 1024

	// maxRPCReassembledBytes is MAX_RPC_REASSEMBLED_BYTES (rpc-frame.ts:8): the ceiling on one
	// LOGICAL frame rebuilt from chunks.
	maxRPCReassembledBytes = 64 * 1024 * 1024

	// rpcChunkPayloadBytes is RPC_CHUNK_PAYLOAD_BYTES (rpc-frame.ts:10): the RAW slice each
	// `rpc_chunk` carries, before base64 inflates it by ~4/3.
	rpcChunkPayloadBytes = 256 * 1024

	// stringElisionReserve is STRING_ELISION_RESERVE (rpc-frame.ts:39): the room shrinkString
	// keeps for its own elision marker inside the cap.
	stringElisionReserve = 80
)

// oversizeAssistantTextBytes sizes the final assistant text so the `agent_end` frame still clears
// MAX_RPC_FRAME_BYTES AFTER compaction has removed the already-streamed half (rpc-frame.ts:191-215).
// The 200 KiB of headroom is deliberate: a fixture that merely grazes the ceiling would let the
// branch under test flip on an encoding detail rather than on the defect.
const oversizeAssistantTextBytes = maxRPCFrameBytes + 200<<10

// TestRPC_OversizeAgentEndStillEndsTheTurn is D1: a turn whose terminal frame is over the
// transport ceiling must still END, whatever omp's encoder does with it.
//
// The branch is not the test's to choose. omp's RpcFrameEncoder defaults to protocol 1
// (rpc-frame.ts:265) and flips to 2 ONLY on a success negotiate response (rpc-mode.ts:701-702),
// so the mirror below reads the conn's stdin and takes the arm the ADAPTER earned:
//
//   - negotiate_protocol{protocolVersion:2} written -> the v2 arm: `rpc_chunk` lines
//     (rpc-frame.ts:93-117), which this package's normalizer maps to EventExtension because it has
//     no reassembler — the turn boundary is inside a frame nobody rebuilds;
//   - nothing written -> protocol 1, omp's own default: compact, then the SHRINK_PASSES ladder
//     (rpc-frame.ts:29-37, :46-50), and exactly ONE parseable line — still `type:"agent_end"`,
//     still carrying an assistant message, so normalize.go:155 yields EventTurnEnd.
//
// Today the adapter negotiates, so the mirror chunks and no turn boundary is ever published.
func TestRPC_OversizeAgentEndStillEndsTheTurn(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{})
	harness.completeHandshake()

	encoder := newOMPFrameEncoder(t, harness)

	// The streamed half of the turn: a small assistant message omp already put on the wire as
	// message_start/message_end. It gives the normalizer a lastMsg (normalize.go:225) and it gives
	// the encoder its #streamedMessages entry (rpc-frame.ts:299-306), which is what compaction
	// slices off the terminal aggregate.
	streamed := assistantMessageValue("Read the build log; summarizing it now.", false)
	harness.emit(encoder.encodeFrames(ompFrameLine(t, map[string]any{
		"type": "message_start", "message": streamed,
	}))...)
	harness.emit(encoder.encodeFrames(ompFrameLine(t, map[string]any{
		"type": "message_end", "message": streamed,
	}))...)

	// The terminal aggregate: the streamed message plus the un-streamed message that blew the
	// ceiling. Compaction removes the first and keeps the second, so the frame is over the limit
	// on BOTH arms and neither is reached by accident.
	oversize := ompFrameLine(t, map[string]any{
		"type": "agent_end",
		"messages": []any{
			streamed,
			assistantMessageValue(oversizeAssistantText(), true),
		},
	})

	lines := encoder.encodeFrames(oversize)
	t.Logf("omp's encoder mirror took the %s: %d line(s), %d bytes on the wire", encoder.arm, len(lines), wireBytes(lines))
	harness.emit(lines...)

	harness.waitEvent("an EventTurnEnd for the oversized agent_end (omp's encoder took the "+encoder.arm+")", isTurnEnd)
}

// TestRPC_HandshakeClaimsNoProtocolItCannotDecode is D1's cause, pinned on its own: the host must
// not claim a protocol whose frames it cannot rebuild.
//
// The gate is the Initializing->Ready event, not a sleep: handshake() (rpc.go:344) returns that
// event AFTER its writes, so observing it orders this assertion behind every frame the host emits
// on `ready`.
func TestRPC_HandshakeClaimsNoProtocolItCannotDecode(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{})
	harness.completeHandshake()

	if frame, found := harness.stdin.find(hasType("negotiate_protocol")); found {
		t.Fatalf("the host negotiated a protocol on omp's `ready`: %v — protocol 2 is the ONLY thing that turns an over-1-MiB logical frame into `rpc_chunk` lines (rpc-frame.ts:284), and this package ships no reassembler, so a chunked agent_end never becomes a turn boundary. Writing NOTHING is protocol 1: omp's encoder defaults to it (rpc-frame.ts:265) and flips to 2 only on a success negotiate response (rpc-mode.ts:701-702). Sending protocolVersion 1 is not the fix either — rpc-mode.ts:979-983 answers any version other than 2 with success:false, buying an error frame for the same outcome",
			frame)
	}
}

// TestRPC_EveryBlockingDialogVerbIsAnswered is D2/D3: every extension-UI verb omp BLOCKS on must
// come back answered, not just `select`.
//
// The dismissal shape is one field for all four verbs, verified per verb rather than assumed
// shared: `select` and `input` read it in parseValueDialogResponse (rpc-mode.ts:521-531), `confirm`
// in its own inline parser (rpc-mode.ts:767-774), `editor` in the resolver inside requestRpcEditor
// (rpc-mode.ts:586-594). All four test `"cancelled" in response && response.cancelled` and all four
// fail SAFE on it — no value, not confirmed. It is the third variant of RpcExtensionUIResponse
// (rpc-types.ts:536-538).
//
// Today rpc.go:381 returns nil for every method that is not `select`, so nothing is written back.
func TestRPC_EveryBlockingDialogVerbIsAnswered(t *testing.T) {
	t.Parallel()
	for _, dialog := range blockingDialogs() {
		t.Run(dialog.method, func(t *testing.T) {
			t.Parallel()
			harness := newRPCHarness(t, agentsession.Spec{})
			harness.completeHandshake()

			harness.emit(dialog.frame(t))

			answer := harness.waitFrame("extension_ui_response dismissing the blocking `"+dialog.method+"` dialog ("+dialog.blocks+")",
				isDialogAnswerFor(dialog.id))
			assertLegalDialogAnswer(t, answer)
			assertDismissal(t, answer, dialog)
		})
	}
}

// TestRPC_FireAndForgetVerbsAreNeverAnswered is the other half of the closed allowlist: a verb omp
// never awaits must draw NO frame back. omp's fire-and-forget verbs return void and register no
// pending request (notify rpc-mode.ts:798-807, setStatus :809-818, setWidget :824-837, setTitle
// :847-856, set_editor_text :868-876) and `cancel` WITHDRAWS a presentation the host already
// answered or abandoned (rpc-mode.ts:628-634, :574-582). An unsolicited extension_ui_response for
// one of those resolves nothing on omp's side and is noise on a correlated channel.
//
// The guard is NON-VACUOUS by construction, not by a sleep: each case emits a `select` on the SAME
// conn AFTER the fire-and-forget frame, and waits for the answer the adapter DOES owe it. Frames
// are serviced in wire order (rpc.go:289 publishLine), and an inline answer is written inside that
// same service call, so any answer to the fire-and-forget verb would already be recorded by the
// time the control's answer lands. The window is therefore bounded by an event that HAPPENED.
func TestRPC_FireAndForgetVerbsAreNeverAnswered(t *testing.T) {
	t.Parallel()
	for _, verb := range fireAndForgetVerbs() {
		t.Run(verb.method, func(t *testing.T) {
			t.Parallel()
			harness := newRPCHarnessWithFallback(t, agentsession.Spec{}, controlDialogFallback)
			harness.completeHandshake()

			harness.emit(verb.frame(t))
			// The positive control: a `select`, which the adapter answers through the injected
			// short fallback (permission_fallback_test.go's F1 TIMEOUT contract).
			harness.emit(selectDialogFrame(t, dialogID, "bash", "ls -la"))
			harness.waitFrame("positive-control fallback deny for the `select` dialog", isDialogAnswerFor(dialogID))

			if frame, found := harness.stdin.find(isDialogAnswerFor(verb.id)); found {
				t.Errorf("the adapter answered the fire-and-forget `%s` request: %v — omp registered no pending request for it (%s), so this frame correlates with nothing and is noise on the extension-UI channel",
					verb.method, frame, verb.source)
			}
		})
	}
}

// TestRPC_NonPermissionVerbsAnswerWithoutTheFallbackWindow proves the bound on the three new
// answers is IMMEDIATE, not the deny-on-timeout net.
//
// defaultDialogFallback (rpc.go:126) exists to give THE LIBRARY time to decide, and only `select`
// has a decider — confirm/input/editor are not permission asks and the permission chain holds no
// verdict for them. Arming a window for them would buy minutes of stalled turn for a decision that
// can never arrive. The conn here is built with a one-HOUR window, so an answer that rode the
// fallback cannot arrive inside rpcDeadline and this test would time out on it.
func TestRPC_NonPermissionVerbsAnswerWithoutTheFallbackWindow(t *testing.T) {
	t.Parallel()
	for _, dialog := range blockingDialogs() {
		t.Run(dialog.method, func(t *testing.T) {
			t.Parallel()
			harness := newRPCHarnessWithFallback(t, agentsession.Spec{}, unreachableFallback)
			harness.completeHandshake()

			harness.emit(dialog.frame(t))

			harness.waitFrame("IMMEDIATE extension_ui_response dismissing `"+dialog.method+"` on a conn whose deny-on-timeout window is "+unreachableFallback.String(),
				isDialogAnswerFor(dialog.id))
		})
	}
}

// unreachableFallback is a deny-on-timeout window no test can wait out, so an answer observed
// inside rpcDeadline PROVES the answer did not ride the fallback.
const unreachableFallback = time.Hour

// controlDialogFallback is the short window the fire-and-forget guard's positive control rides. It
// only has to be well inside rpcDeadline, so the control's answer bounds the observation window
// long before the wait would fail.
const controlDialogFallback = 100 * time.Millisecond

// ── the verb tables ──────────────────────────────────────────────────────────────────────────.

// blockingDialog is one extension-UI verb whose omp-side call BLOCKS until a matching
// `extension_ui_response` arrives. fields are the verb's OWN request keys, spelled as
// RpcExtensionUIContext spells them.
type blockingDialog struct {
	method string
	id     string
	fields map[string]any
	blocks string
}

// blockingDialogs is the set this change must start answering: the blocking verbs OTHER than
// `select`, which is already routed through the library's permission chain (rpc.go:380-393).
func blockingDialogs() []blockingDialog {
	return []blockingDialog{
		{
			method: "confirm",
			id:     "155cde478590b001",
			fields: map[string]any{
				"title":   "Overwrite eden.yaml?",
				"message": "The file already exists in the workspace.",
			},
			blocks: "rpc-mode.ts:760-776 -> requestRpcDialog, whose timer is armed only for a request carrying `timeout` (rpc-mode.ts:640) and this one carries none",
		},
		{
			method: "input",
			id:     "155cde478590b002",
			fields: map[string]any{
				"title":       "Name the release branch",
				"placeholder": "release/2026-08",
			},
			blocks: "rpc-mode.ts:778-791 -> requestRpcDialog, same timerless path as confirm",
		},
		{
			method: "editor",
			id:     "155cde478590b003",
			fields: map[string]any{
				"title":       "Edit the commit message",
				"prefill":     "fix(ompadapter): answer every blocking dialog verb",
				"promptStyle": true,
			},
			blocks: "rpc-mode.ts:884-891 -> requestRpcEditor (rpc-mode.ts:544-606), which arms NO timer on any path — an unanswered editor blocks unconditionally",
		},
	}
}

// frame renders this dialog as the `extension_ui_request` line omp would print.
func (d blockingDialog) frame(t *testing.T) string {
	t.Helper()
	return ompFrameLine(t, extensionUIRequest(d.method, d.id, d.fields))
}

// fireAndForgetVerb is one extension-UI verb omp never awaits.
type fireAndForgetVerb struct {
	method string
	id     string
	fields map[string]any
	source string
}

// fireAndForgetVerbs is every non-blocking `extension_ui_request` method omp 17.2.5 can print.
func fireAndForgetVerbs() []fireAndForgetVerb {
	return []fireAndForgetVerb{
		{
			method: "notify",
			id:     "155cde478590c001",
			fields: map[string]any{"message": "The scan finished.", "notifyType": "info"},
			source: "rpc-mode.ts:798-807, a void method",
		},
		{
			method: "setStatus",
			id:     "155cde478590c002",
			fields: map[string]any{"statusKey": "scan", "statusText": "3 findings"},
			source: "rpc-mode.ts:809-818, a void method",
		},
		{
			method: "setWidget",
			id:     "155cde478590c003",
			fields: map[string]any{"widgetKey": "autoresearch", "widgetLines": []any{"line one"}},
			source: "rpc-mode.ts:824-837, a void method",
		},
		{
			method: "setTitle",
			id:     "155cde478590c004",
			fields: map[string]any{"title": "eden — ompadapter"},
			source: "rpc-mode.ts:847-856, a void method behind PI_RPC_EMIT_TITLE",
		},
		{
			method: "set_editor_text",
			id:     "155cde478590c005",
			fields: map[string]any{"text": "go test ./..."},
			source: "rpc-mode.ts:868-876, a void method",
		},
		{
			method: "cancel",
			id:     "155cde478590c006",
			fields: map[string]any{"targetId": "155cde478590b001"},
			source: "rpc-mode.ts:628-634 and :574-582 — a WITHDRAWAL of a presentation, never a question",
		},
	}
}

// frame renders this verb as the `extension_ui_request` line omp would print.
func (v fireAndForgetVerb) frame(t *testing.T) string {
	t.Helper()
	return ompFrameLine(t, extensionUIRequest(v.method, v.id, v.fields))
}

// ── assertions and small predicates ──────────────────────────────────────────────────────────.

// assertDismissal proves the answer is the DISMISSAL variant and nothing else: omp reads
// `cancelled` first on every one of the four blocking paths, and a `value` or `confirmed` riding
// alongside it would be a verdict the adapter has no standing to give — it is dismissing a
// question nobody in Eden can answer, not answering it.
func assertDismissal(t *testing.T, answer map[string]any, dialog blockingDialog) {
	t.Helper()
	if !boolField(answer, dialogDismissField) {
		t.Errorf("the `%s` answer does not carry %s:true (%v) — that field is what every one of omp's four blocking parsers tests first, and it is the only variant that fails SAFE",
			dialog.method, dialogDismissField, answer)
	}
	if _, carries := answer["value"]; carries {
		t.Errorf("the `%s` dismissal also carries a `value` (%v) — a dismissal is not a verdict, and RpcExtensionUIResponse (rpc-types.ts:536-538) is a union of three variants, not a merge",
			dialog.method, answer)
	}
	if _, carries := answer["confirmed"]; carries {
		t.Errorf("the `%s` dismissal also carries a `confirmed` (%v) — the adapter must not confirm a question the library never saw",
			dialog.method, answer)
	}
}

// isDialogAnswerFor matches the `extension_ui_response` written back for one request id. omp
// resolves pendingRequests.get(id) (rpc-mode.ts:279-284), so an answer on another id resolves
// nothing.
func isDialogAnswerFor(id string) func(map[string]any) bool {
	return func(frame map[string]any) bool {
		return stringField(frame, "type") == "extension_ui_response" && stringField(frame, "id") == id
	}
}

// isTurnEnd matches the turn boundary normalize.go:155 derives from a clean `agent_end`.
func isTurnEnd(event *agentsession.Event) bool {
	return event.Kind == agentsession.EventTurnEnd
}

// extensionUIRequest assembles one `extension_ui_request` from its verb-specific fields.
func extensionUIRequest(method, id string, fields map[string]any) map[string]any {
	request := map[string]any{"type": "extension_ui_request", "id": id, "method": method}
	for key, value := range fields {
		request[key] = value
	}
	return request
}

// ompFrameLine renders one omp frame as the single NDJSON line the harness emits.
func ompFrameLine(t *testing.T, frame map[string]any) string {
	t.Helper()
	line, err := json.Marshal(frame)
	if err != nil {
		t.Fatalf("marshal an omp frame: %v", err)
	}
	return string(line)
}

// assistantMessageValue renders one omp assistant message snapshot in the captured shape
// (testdata/partial-stream.jsonl). terminal adds the usage + duration block the terminal
// aggregate's final message carries.
func assistantMessageValue(text string, terminal bool) map[string]any {
	message := map[string]any{
		"role":       "assistant",
		"content":    []any{map[string]any{"type": "text", "text": text}},
		"model":      "deepseek/deepseek-v4-flash",
		"stopReason": "stop",
	}
	if terminal {
		message["usage"] = map[string]any{
			"input": 120, "output": 8, "cacheRead": 0, "cacheWrite": 0,
			"cost": map[string]any{"total": 0},
		}
		message["duration"] = 900
	}
	return message
}

// oversizeAssistantText builds the ASCII filler that pushes the terminal aggregate over the
// transport ceiling. It carries no character JSON escapes, so its serialized length is its byte
// length and the fixture's size is the size the encoder sees.
func oversizeAssistantText() string {
	const filler = "the assistant transcribed another chunk of the build log. "
	text := strings.Repeat(filler, oversizeAssistantTextBytes/len(filler)+1)
	return text[:oversizeAssistantTextBytes]
}

// wireBytes totals what a set of physical lines costs on the transport, newlines included.
func wireBytes(lines []string) int {
	total := 0
	for _, line := range lines {
		total += serializedFrameBytes(line)
	}
	return total
}

// ── the mirror of omp's RpcFrameEncoder (rpc-frame.ts:263-316) ───────────────────────────────.

// ompFrameEncoder reproduces omp's stateful frame encoder for the test side of the transport, so
// the oversize proof drives what the REAL harness would put on the wire instead of a hand-written
// stream that could flatter either the defect or the fix.
//
// Faithfulness is enforced, not assumed: every line it emits is checked against
// MAX_RPC_FRAME_BYTES, and every branch of the real encoder this fixture does not traverse FAILS
// the test naming the omp source it would have to reproduce. A mirror that guesses is worse than
// no mirror, because its red would be imaginary.
type ompFrameEncoder struct {
	t *testing.T

	// protocolVersion is fixed from the conn's OWN stdin, not chosen by the test.
	protocolVersion int

	// streamedMessages is RpcFrameEncoder#streamedMessages (rpc-frame.ts:264): the message
	// snapshots already delivered, which compaction slices off the terminal aggregate.
	streamedMessages []any

	// chunkCounter is #chunkCounter (rpc-frame.ts:266), the `rpc-N` chunkId source.
	chunkCounter int

	// arm names the branch the last encodeFrames took, so a failure says WHICH omp behaviour it
	// was measured against.
	arm string
}

// newOMPFrameEncoder fixes the mirror's protocol from what the adapter negotiated on this conn.
// omp's encoder defaults to 1 (rpc-frame.ts:265) and setProtocolVersion(2) runs only when a
// `response` to negotiate_protocol carries success===true (rpc-mode.ts:701-702); since
// rpc-mode.ts:979-983 answers any version other than 2 with success:false, a negotiate for 2 is
// the ONE host frame that can move it.
func newOMPFrameEncoder(t *testing.T, harness *rpcHarness) *ompFrameEncoder {
	t.Helper()
	version := 1
	if frame, found := harness.stdin.find(hasType("negotiate_protocol")); found && numberIs(frame["protocolVersion"], 2) {
		version = 2
	}
	return &ompFrameEncoder{t: t, protocolVersion: version}
}

// encodeFrames is RpcFrameEncoder#encodeFrames (rpc-frame.ts:279-309): it turns ONE logical frame
// into the physical NDJSON lines omp would print, and keeps the streamed-message bookkeeping that
// compaction depends on.
func (e *ompFrameEncoder) encodeFrames(frameJSON string) []string {
	e.t.Helper()
	frame := e.decode(frameJSON)
	if ompFrameType(frame) == "agent_start" {
		e.streamedMessages = nil
	}

	encoded := e.encode(frame)
	var lines []string
	var singleFrame string
	switch {
	case e.protocolVersion == 2 && serializedFrameBytes(encoded) > maxRPCFrameBytes:
		compacted := e.compactTerminalFrame(frame)
		compactedJSON := e.encode(compacted)
		if serializedFrameBytes(compactedJSON) > maxRPCFrameBytes {
			e.chunkCounter++
			lines = e.encodeChunkedRPCFrames(compactedJSON, fmt.Sprintf("rpc-%d", e.chunkCounter))
			e.arm = fmt.Sprintf("protocol-2 CHUNKED arm (rpc-frame.ts:284-289): %d rpc_chunk lines", len(lines))
			break
		}
		singleFrame = compactedJSON
		lines = []string{singleFrame}
		e.arm = "protocol-2 single-line arm (rpc-frame.ts:290-293): compaction fit under the ceiling"
	default:
		singleFrame = e.encodeRPCFrame(frame)
		lines = []string{singleFrame}
		e.arm = fmt.Sprintf("protocol-%d single-line arm (rpc-frame.ts:295: encodeRpcFrame)", e.protocolVersion)
	}

	e.recordStreamed(frame, singleFrame)
	e.assertWithinTransportLimit(lines)
	return lines
}

// encodeRPCFrame is encodeRpcFrame (rpc-frame.ts:243-260), the protocol-1 path: compact the
// terminal aggregate, then walk the SHRINK_PASSES ladder, and ALWAYS return exactly one parseable
// line.
func (e *ompFrameEncoder) encodeRPCFrame(frame any) string {
	e.t.Helper()
	encoded := e.encode(frame)
	if serializedFrameBytes(encoded) <= maxRPCFrameBytes {
		return encoded
	}
	if ompFrameType(frame) == "response" {
		e.unreachableArm("the `response` overflow arm (rpc-frame.ts:246-248)")
	}

	compacted := e.compactTerminalFrame(frame)
	encoded = e.encode(compacted)
	if serializedFrameBytes(encoded) <= maxRPCFrameBytes {
		return encoded
	}
	for _, pass := range ompShrinkPasses() {
		encoded = e.encode(e.shrinkValue(compacted, pass))
		if serializedFrameBytes(encoded) <= maxRPCFrameBytes {
			return encoded
		}
	}
	e.unreachableArm("the overflowFrame arm (rpc-frame.ts:259) — the whole SHRINK_PASSES ladder failed to fit this fixture")
	return ""
}

// encodeChunkedRPCFrames is encodeChunkedRpcFrames (rpc-frame.ts:93-117): the pre-serialized
// logical frame sliced into RPC_CHUNK_PAYLOAD_BYTES of RAW utf-8 per chunk, base64'd, with
// byteLength carrying the WHOLE logical frame's length on every chunk.
func (e *ompFrameEncoder) encodeChunkedRPCFrames(frameJSON, chunkID string) []string {
	e.t.Helper()
	raw := []byte(frameJSON)
	if len(raw) > maxRPCReassembledBytes {
		e.unreachableArm("the reassembly-overflow arm (rpc-frame.ts:95-98)")
	}
	count := (len(raw) + rpcChunkPayloadBytes - 1) / rpcChunkPayloadBytes
	lines := make([]string, 0, count)
	for index := range count {
		end := min((index+1)*rpcChunkPayloadBytes, len(raw))
		lines = append(lines, e.encode(map[string]any{
			"type":       "rpc_chunk",
			"chunkId":    chunkID,
			"index":      index,
			"count":      count,
			"byteLength": len(raw),
			"data":       base64.StdEncoding.EncodeToString(raw[index*rpcChunkPayloadBytes : end]),
		}))
	}
	return lines
}

// compactTerminalFrame is compactTerminalFrame (rpc-frame.ts:191-215) as the encoder calls it —
// always WITH the streamed snapshots, so the streamed prefix is recomputed by deep comparison
// rather than trusted from a count. The jsonSnapshot round trip (rpc-frame.ts:75-78) is the
// identity here because every value already came from JSON.
func (e *ompFrameEncoder) compactTerminalFrame(frame any) any {
	record, isRecord := frame.(map[string]any)
	if !isRecord || ompFrameType(frame) != "agent_end" {
		return frame
	}
	messages, isArray := record["messages"].([]any)
	if !isArray {
		return frame
	}
	streamed := 0
	limit := min(len(e.streamedMessages), len(messages))
	for streamed < limit && reflect.DeepEqual(e.streamedMessages[streamed], messages[streamed]) {
		streamed++
	}
	compacted := make(map[string]any, len(record)+1)
	for key, value := range record {
		compacted[key] = value
	}
	compacted["messages"] = messages[streamed:]
	compacted["messageCount"] = len(messages)
	return compacted
}

// recordStreamed is the encoder's post-emit bookkeeping (rpc-frame.ts:299-307). Protocol 2 remembers
// the message VERBATIM; protocol 1 remembers what it actually PUT ON THE WIRE, which is why a
// shrunken message never matches the terminal aggregate's copy and compaction stops before it.
func (e *ompFrameEncoder) recordStreamed(frame any, singleFrame string) {
	e.t.Helper()
	record, isRecord := frame.(map[string]any)
	if !isRecord {
		return
	}
	switch ompFrameType(frame) {
	case "message_end":
		message, carries := record["message"]
		if e.protocolVersion == 2 && carries {
			e.streamedMessages = append(e.streamedMessages, message)
			return
		}
		if singleFrame == "" {
			return
		}
		emitted, isEmittedRecord := e.decode(singleFrame).(map[string]any)
		if !isEmittedRecord || ompFrameType(emitted) != "message_end" {
			return
		}
		if streamed, emittedCarries := emitted["message"]; emittedCarries {
			e.streamedMessages = append(e.streamedMessages, streamed)
		}
	case "agent_end":
		if record["willContinue"] != true {
			e.streamedMessages = nil
		}
	}
}

// assertWithinTransportLimit is the mirror's own guard: omp NEVER puts a line over
// MAX_RPC_FRAME_BYTES on the wire, so a mirror that did would produce a red the real harness could
// not.
func (e *ompFrameEncoder) assertWithinTransportLimit(lines []string) {
	e.t.Helper()
	for index, line := range lines {
		if size := serializedFrameBytes(line); size > maxRPCFrameBytes {
			e.t.Fatalf("the omp encoder mirror emitted line %d/%d at %d bytes, over MAX_RPC_FRAME_BYTES (%d, rpc-frame.ts:6) on the %s — real omp never writes such a line, so any red read from it would be imaginary",
				index+1, len(lines), size, maxRPCFrameBytes, e.arm)
		}
	}
}

// unreachableArm fails the test rather than guessing at a branch of omp's encoder this fixture was
// not built to traverse. Reproducing an unexercised arm from reading alone is how a mirror starts
// lying about the harness it mirrors.
func (e *ompFrameEncoder) unreachableArm(what string) {
	e.t.Helper()
	e.t.Fatalf("the omp encoder mirror reached %s, which this fixture must never need — the mirror does not reproduce it, so fix the fixture rather than trusting an unexercised branch", what)
}

// shrinkPass is one rung of SHRINK_PASSES (rpc-frame.ts:23-27).
type shrinkPass struct {
	stringCap   int
	arrayLimit  int
	objectLimit int
}

// ompShrinkPasses is SHRINK_PASSES verbatim (rpc-frame.ts:29-37), in order.
func ompShrinkPasses() []shrinkPass {
	return []shrinkPass{
		{stringCap: 256 * 1024, arrayLimit: 512, objectLimit: 512},
		{stringCap: 64 * 1024, arrayLimit: 256, objectLimit: 256},
		{stringCap: 16 * 1024, arrayLimit: 128, objectLimit: 128},
		{stringCap: 4 * 1024, arrayLimit: 64, objectLimit: 64},
		{stringCap: 1024, arrayLimit: 32, objectLimit: 32},
		{stringCap: 256, arrayLimit: 8, objectLimit: 16},
		{stringCap: 64, arrayLimit: 1, objectLimit: 8},
	}
}

// shrinkValue is shrinkValue (rpc-frame.ts:52-73). The object arm is the one place a Go mirror
// cannot be faithful — omp keeps the FIRST objectLimit entries in JS insertion order, which a Go
// map does not carry — so a record that would be elided FAILS the test instead of being guessed.
func (e *ompFrameEncoder) shrinkValue(value any, pass shrinkPass) any {
	e.t.Helper()
	switch typed := value.(type) {
	case string:
		return shrinkString(typed, pass.stringCap)
	case []any:
		keep := min(len(typed), pass.arrayLimit)
		output := make([]any, 0, keep+1)
		for index := range keep {
			output = append(output, e.shrinkValue(typed[index], pass))
		}
		if keep < len(typed) {
			output = append(output, fmt.Sprintf("…[%d items elided for RPC frame]", len(typed)-keep))
		}
		return output
	case map[string]any:
		if len(typed) > pass.objectLimit {
			e.unreachableArm(fmt.Sprintf("the OBJECT elision arm (rpc-frame.ts:61-71): a %d-key record met objectLimit %d, and omp keeps the first entries in JS insertion order", len(typed), pass.objectLimit))
		}
		output := make(map[string]any, len(typed))
		for key, item := range typed {
			output[key] = e.shrinkValue(item, pass)
		}
		return output
	default:
		return value
	}
}

// shrinkString is shrinkString (rpc-frame.ts:46-50). omp measures in UTF-16 code units
// (String#length); this measures runes, which agree for the BMP text these fixtures carry, and the
// emitted line is size-checked regardless.
func shrinkString(value string, stringCap int) string {
	runes := []rune(value)
	if len(runes) <= stringCap {
		return value
	}
	headLength := max(0, stringCap-stringElisionReserve)
	return fmt.Sprintf("%s\n…[%d chars elided for RPC frame]", string(runes[:headLength]), len(runes)-headLength)
}

// serializedFrameBytes is serializedFrameBytes (rpc-frame.ts:42-44): the line's utf-8 length PLUS
// the newline that delimits it.
func serializedFrameBytes(line string) int { return len(line) + 1 }

// ompFrameType reads a decoded frame's top-level `type`, returning "" for anything that is not a
// record with a string type — isRecord(value) && value.type in omp's terms.
func ompFrameType(value any) string {
	record, isRecord := value.(map[string]any)
	if !isRecord {
		return ""
	}
	return stringField(record, "type")
}

// encode is JSON.stringify: HTML escaping is off because JSON.stringify does not escape < > &, and
// a mirror that inflated a frame differently from omp would measure the ceiling against the wrong
// bytes.
func (e *ompFrameEncoder) encode(value any) string {
	e.t.Helper()
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		e.t.Fatalf("mirror-encode an omp frame: %v", err)
	}
	return strings.TrimSuffix(buffer.String(), "\n")
}

// decode is JSON.parse: every frame the mirror handles is decoded first, so numbers, strings and
// records compare by the SAME representation omp's structural equality sees.
func (e *ompFrameEncoder) decode(line string) any {
	e.t.Helper()
	var value any
	if err := json.Unmarshal([]byte(line), &value); err != nil {
		e.t.Fatalf("mirror-decode an omp frame: %v", err)
	}
	return value
}
