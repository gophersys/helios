package claudeadapter_test

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// The NATIVE cross-session messaging binding, proven against the committed captures.
//
// The execution-proven contract (memory claude-cross-session-headless-contract, corrected by
// measurement on 2026-08-24 over all three captures): `result.origin` is the ONLY inbound form
// on `-p --output-format stream-json` stdout. There are ZERO <cross-session-message> wrappers
// and ZERO type:"user" delivery events on that stream — the wrapped user turn exists only in
// the session JSONL on disk. So the binding PARSES origin and NEVER scrapes text, and the
// fixtures in testdata/peer-*.jsonl are the capture lines themselves.

// The identifiers measured inside the committed captures. They are the correlation the whole
// design turns on: the SENDER's receipt msg_id EQUALS the RECEIVER's origin.msg_id, so an
// end-to-end assertion needs no text matching at all.
const (
	// peerOriginMsgID is origin.msg_id on the delivery-triggered result line of
	// claude-peer-receive.stream.jsonl, and ALSO the msg_id in the sender's SendMessage
	// receipt in claude-peer-send.json — the same message seen from both ends.
	peerOriginMsgID = "de781fd3-d875-42be-8ae1-8ede89ad6f20"
	peerOriginFrom  = "p2-control-fe"
	peerOriginBody  = "PROBE-P2-CONTROL hello from sender"

	// The sender-side receipt measured in claude-peer-send.stream.jsonl lines 24-25.
	peerSendToolUseID = "toolu_016nE4bVR49k4zJ5ydpeftxg"
	peerSendTo        = "p1-unnamed-f7"
	peerSendBody      = "PROBE-P2-NARROW"
	peerSendMsgID     = "43ee0075-2af2-49d2-a9b8-fbd7d7964d89"
)

// peerFixture names the committed capture fixtures (testdata/), each carrying a "#" header
// that cites the capture it was copied from and what was measured in it.
const (
	fixtureReceiveOrigin  = "peer-receive-origin.jsonl"
	fixtureReceiveHeld    = "peer-receive-held.jsonl"
	fixtureReceiveBypass  = "peer-receive-bypass-accept.jsonl"
	fixtureSendReceipt    = "peer-send-receipt.jsonl"
	fixtureSendNoMsgID    = "peer-send-receipt-no-msgid.jsonl"
	fixtureSendUnreadable = "peer-send-unreachable.jsonl"
)

// bypassAcceptMsgIDs are the FOUR distinct origin.msg_ids measured across the five result lines
// of claude-peer-receive-bypass-accept.stream.jsonl. The fifth result line carries no origin at
// all and must yield nothing.
var bypassAcceptMsgIDs = []string{
	"148f9cd7-3985-4093-882b-17812a7a37d4",
	"20003737-948f-42c2-822e-a54a4d4cdb46",
	"fca52186-1dec-41fd-8684-98d4156bc124",
	"3034ac92-5c69-4743-8a6b-0b1368c54343",
}

// TestPeerNormalize_OriginBecomesPeerMessageBeforeTurnEnd is test 1. The delivery-triggered
// turn of the receiver capture must yield exactly one EventPeerMessage carrying origin's
// msg_id / name / body, marked Verified (the CLI reported verifiedPeerPid, a kernel fact the
// sender cannot forge), and it must be emitted IMMEDIATELY BEFORE the EventTurnEnd the SAME
// result line produces — the arrival is part of the turn that the arrival caused.
//
// FALSIFICATION: an implementation that emits the peer event after the turn boundary hands the
// consumer a message that arrived "after" the turn it triggered, and a UI that renders on
// EventTurnEnd shows the turn without ever showing what caused it.
func TestPeerNormalize_OriginBecomesPeerMessageBeforeTurnEnd(t *testing.T) {
	t.Parallel()
	lines := peerFixtureLines(t, fixtureReceiveOrigin)
	events := normalizePeerStream(t, lines)

	peers := eventsOfKind(events, agentsession.EventPeerMessage)
	if len(peers) != 1 {
		t.Fatalf("the delivery-triggered turn must yield exactly 1 EventPeerMessage, got %d; kinds: %s",
			len(peers), renderKinds(events))
	}
	message := peers[0].Peer
	if message == nil {
		t.Fatalf("EventPeerMessage carried a nil Peer payload")
	}
	if message.MsgID != peerOriginMsgID {
		t.Errorf("Peer.MsgID = %q, want %q (origin.msg_id — the id the sender's receipt also carries)",
			message.MsgID, peerOriginMsgID)
	}
	if message.From != peerOriginFrom {
		t.Errorf("Peer.From = %q, want %q (origin.name)", message.From, peerOriginFrom)
	}
	if message.Body != peerOriginBody {
		t.Errorf("Peer.Body = %q, want %q (origin.body, verbatim)", message.Body, peerOriginBody)
	}
	if message.To != "" {
		t.Errorf("Peer.To = %q, want \"\" — an inbound message is addressed to THIS session", message.To)
	}
	if !message.Verified {
		t.Errorf("Peer.Verified = false; origin.verifiedPeerPid=40509 is the kernel-verified sender pid, so the binding must stamp Verified")
	}

	// Ordering across the whole turn: the arrival precedes the boundary.
	peerAt, peerFound := indexOfKind(events, agentsession.EventPeerMessage)
	endAt, endFound := indexOfKind(events, agentsession.EventTurnEnd)
	if !endFound {
		t.Fatalf("the capture's result line must still yield one EventTurnEnd; kinds: %s", renderKinds(events))
	}
	if !peerFound || peerAt >= endAt {
		t.Errorf("EventPeerMessage at %d must precede EventTurnEnd at %d; kinds: %s", peerAt, endAt, renderKinds(events))
	}

	// The SAME result line produces both, adjacently and in that order.
	fromResultLine := claudeadapter.NormalizeLineForTest(lines[len(lines)-1])
	if len(fromResultLine) != 2 ||
		fromResultLine[0].Kind != agentsession.EventPeerMessage ||
		fromResultLine[1].Kind != agentsession.EventTurnEnd {
		t.Errorf("the origin-bearing result line must yield exactly [EventPeerMessage, EventTurnEnd], got %s",
			renderKinds(fromResultLine))
	}
}

// TestPeerNormalize_HeldCaptureYieldsNoPeerMessage is test 2 — THE ADVERSARIAL CASE, and it is
// a CONTROL, not a red: it passes before the feature exists (nothing emits EventPeerMessage
// today) and must keep passing after. Its whole value is that it is the one capture where a
// text-scraping normalizer goes green on the positive case and RED here.
//
// The receiver ran with crossSessionInbound="hold": the message was never delivered, so its one
// result line carries NO origin — while the turn itself completed normally and must still yield
// exactly one EventTurnEnd.
//
// FALSIFICATION: an implementation that greps the assistant prose, or that infers a delivery
// from the shape of a turn rather than from the presence of origin, invents a peer message here
// out of a message that was never delivered.
func TestPeerNormalize_HeldCaptureYieldsNoPeerMessage(t *testing.T) {
	t.Parallel()
	events := normalizePeerStream(t, peerFixtureLines(t, fixtureReceiveHeld))

	if peers := eventsOfKind(events, agentsession.EventPeerMessage); len(peers) != 0 {
		t.Errorf("the HELD capture carries no origin anywhere, so it must yield ZERO EventPeerMessage, got %d", len(peers))
	}
	if ends := eventsOfKind(events, agentsession.EventTurnEnd); len(ends) != 1 {
		t.Errorf("the HELD capture's turn completed normally: want exactly 1 EventTurnEnd, got %d; kinds: %s",
			len(ends), renderKinds(events))
	}
}

// TestPeerNormalize_BypassAcceptYieldsFourDistinctMessages is test 3. Five concatenated receiver
// sessions, five result lines: four carry origin and one does not. The whole capture must yield
// exactly 4 EventPeerMessage with 4 DISTINCT MsgIDs, and every origin-less result line in it
// must yield none.
//
// FALSIFICATION: an implementation that keys on the presence of a result line, or that carries
// a msg_id across lines in normalizer state, produces five events or four identical ids — and a
// consumer deduping on MsgID would then silently drop three real messages.
func TestPeerNormalize_BypassAcceptYieldsFourDistinctMessages(t *testing.T) {
	t.Parallel()
	lines := peerFixtureLines(t, fixtureReceiveBypass)
	events := normalizePeerStream(t, lines)

	peers := eventsOfKind(events, agentsession.EventPeerMessage)
	if len(peers) != len(bypassAcceptMsgIDs) {
		t.Fatalf("the bypass-accept capture carries %d origin-bearing result lines, so it must yield %d EventPeerMessage, got %d",
			len(bypassAcceptMsgIDs), len(bypassAcceptMsgIDs), len(peers))
	}
	seen := make(map[string]int, len(peers))
	for i := range peers {
		if peers[i].Peer == nil {
			t.Fatalf("EventPeerMessage %d carried a nil Peer payload", i)
		}
		seen[peers[i].Peer.MsgID]++
	}
	if len(seen) != len(bypassAcceptMsgIDs) {
		t.Errorf("want %d DISTINCT MsgIDs, got %d: %v", len(bypassAcceptMsgIDs), len(seen), seen)
	}
	for _, want := range bypassAcceptMsgIDs {
		if seen[want] != 1 {
			t.Errorf("MsgID %q emitted %d times, want exactly 1", want, seen[want])
		}
	}

	// The origin-less result lines of this capture yield no peer message at all.
	originless := originlessResultLines(t, lines)
	if len(originless) == 0 {
		t.Fatal("the fixture must retain at least one origin-less result line: it is the negative control inside the positive capture")
	}
	for _, line := range originless {
		for _, event := range claudeadapter.NormalizeLineForTest(line) {
			if event.Kind == agentsession.EventPeerMessage {
				t.Errorf("an origin-less result line yielded an EventPeerMessage: %s", truncateForFailure(line))
			}
		}
	}
}

// TestPeerBuildArguments_NameEnablesNativeInbound is test 4. A Spec.Name turns the session into
// an addressable peer on claude's NATIVE plane, which needs exactly two argv additions:
// `--name <name>` and `--settings <json>` with crossSessionInbound=accept. The settings JSON is
// ONE RAW argv element — exec.Command passes argv straight to execve, so a shell-quoted
// '{"crossSessionInbound":"accept"}' would reach the CLI WITH the quote characters and fail to
// parse. The four tokens are adjacent so the flag and its value cannot be split by a later edit.
//
// The empty-Name arm is the no-regression pin: a session with no peer address must produce argv
// BYTE-IDENTICAL to today's, so wiring the peer plane cannot change how every existing
// non-peer session is spawned.
//
// FALSIFICATION: shell-quoting the settings value, splitting it across argv elements, or
// emitting --name unconditionally (which would make every existing session addressable and
// collide on the host's socket namespace).
func TestPeerBuildArguments_NameEnablesNativeInbound(t *testing.T) {
	t.Parallel()
	route := agentsession.Route{Harness: "claude-code", Model: "claude-fable-5"}
	grants := []agentsession.ToolGrant{{ID: "g-write", Tool: "Write"}}

	// today's argv, recorded from the merged buildArguments for this exact spec.
	todaysArguments := []string{
		"-p",
		"--output-format", "stream-json",
		"--verbose",
		"--input-format", "stream-json",
		"--include-partial-messages",
		"--model", "claude-fable-5",
		"--allowedTools", "Write",
		"--permission-mode", "default",
		"--permission-prompt-tool", "stdio",
	}

	withoutName := claudeadapter.BuildArgumentsForTest(
		agentsession.Spec{Grants: grants}, route)
	if strings.Join(withoutName, "\x00") != strings.Join(todaysArguments, "\x00") {
		t.Errorf("Spec.Name empty must leave argv BYTE-IDENTICAL to today's.\n got: %#v\nwant: %#v", withoutName, todaysArguments)
	}

	withName := claudeadapter.BuildArgumentsForTest(
		agentsession.Spec{Grants: grants, Name: "impl-a"}, route)

	nameAt := indexOfArg(withName, "--name")
	if nameAt < 0 || nameAt+1 >= len(withName) {
		t.Fatalf("Spec.Name set must add `--name <name>`; argv: %#v", withName)
	}
	if withName[nameAt+1] != "impl-a" {
		t.Errorf("argv[%d] = %q, want %q adjacent to --name", nameAt+1, withName[nameAt+1], "impl-a")
	}

	settingsAt := indexOfArg(withName, "--settings")
	if settingsAt < 0 || settingsAt+1 >= len(withName) {
		t.Fatalf("Spec.Name set must add `--settings <json>` (crossSessionInbound=accept); argv: %#v", withName)
	}
	settings := withName[settingsAt+1]
	if settings != `{"crossSessionInbound":"accept"}` {
		t.Errorf("argv[%d] = %q, want the settings object as ONE RAW argv element %q — exec.Command does no shell parsing, so any quoting reaches the CLI verbatim",
			settingsAt+1, settings, `{"crossSessionInbound":"accept"}`)
	}
	var decoded map[string]string
	if err := json.Unmarshal([]byte(settings), &decoded); err != nil {
		t.Errorf("the --settings argv element must be raw parseable JSON, got %q: %v", settings, err)
	} else if decoded["crossSessionInbound"] != "accept" {
		t.Errorf("--settings crossSessionInbound = %q, want \"accept\" (hold/refuse never deliver — the HELD capture is what that looks like)",
			decoded["crossSessionInbound"])
	}

	// Nothing else about the spawn changed: today's argv is still a prefix-preserved subset.
	for i := 0; i+1 < len(todaysArguments); i++ {
		if !argPairPresent(withName, todaysArguments[i], todaysArguments[i+1]) && !argPresent(withName, todaysArguments[i]) {
			t.Errorf("adding a peer name dropped %q from argv: %#v", todaysArguments[i], withName)
		}
	}
}

// TestPeerNormalize_SendReceiptBecomesPeerSent is test 5. The sender side has TWO lines and
// neither is sufficient alone: the assistant `tool_use` carries the destination (input.to) and
// no id, the user `tool_result` carries the minted msg_id and no destination. The binding
// correlates them by tool_use_id and emits ONE EventPeerSent carrying both.
//
// The second arm is the loudness guarantee: a receipt whose msg_id cannot be parsed is NEVER a
// dropped event. It becomes EventPeerSent{Accepted:false, Detail:"send-receipt-unparsed"}, so
// the model's send stays visible on the stream even when the correlation is lost.
//
// FALSIFICATION: emitting on the tool_use alone (a send that failed would look accepted), or
// dropping an unparseable receipt (the send disappears from the transcript entirely).
func TestPeerNormalize_SendReceiptBecomesPeerSent(t *testing.T) {
	t.Parallel()

	t.Run("parsed receipt correlates to Accepted", func(t *testing.T) {
		t.Parallel()
		events := normalizePeerStream(t, peerFixtureLines(t, fixtureSendReceipt))
		sent := eventsOfKind(events, agentsession.EventPeerSent)
		if len(sent) != 1 {
			t.Fatalf("the tool_use/tool_result pair must yield exactly 1 EventPeerSent, got %d; kinds: %s",
				len(sent), renderKinds(events))
		}
		message := sent[0].Peer
		if message == nil {
			t.Fatalf("EventPeerSent carried a nil Peer payload")
		}
		if message.MsgID != peerSendMsgID {
			t.Errorf("Peer.MsgID = %q, want %q (the minted id in the tool_result — the receiver's origin.msg_id)",
				message.MsgID, peerSendMsgID)
		}
		if message.To != peerSendTo {
			t.Errorf("Peer.To = %q, want %q (input.to on the tool_use, correlated by tool_use_id %s)",
				message.To, peerSendTo, peerSendToolUseID)
		}
		if !message.Accepted {
			t.Errorf("Peer.Accepted = false; the receipt says success:true and carries a msg_id, so it was accepted for routing")
		}
		if message.Detail != "" {
			t.Errorf("Peer.Detail = %q, want \"\" on an accepted send", message.Detail)
		}
	})

	t.Run("unparsed receipt is never a dropped event", func(t *testing.T) {
		t.Parallel()
		events := normalizePeerStream(t, peerFixtureLines(t, fixtureSendNoMsgID))
		sent := eventsOfKind(events, agentsession.EventPeerSent)
		if len(sent) != 1 {
			t.Fatalf("a receipt with no msg_id must STILL yield exactly 1 EventPeerSent (never a dropped event), got %d; kinds: %s",
				len(sent), renderKinds(events))
		}
		message := sent[0].Peer
		if message == nil {
			t.Fatalf("EventPeerSent carried a nil Peer payload")
		}
		if message.Accepted {
			t.Errorf("Peer.Accepted = true for a receipt carrying no msg_id; nothing corroborates acceptance")
		}
		if message.Detail != "send-receipt-unparsed" {
			t.Errorf("Peer.Detail = %q, want %q — the redacted reason a consumer branches on", message.Detail, "send-receipt-unparsed")
		}
		if message.MsgID != "" {
			t.Errorf("Peer.MsgID = %q, want \"\": there was no id to correlate on", message.MsgID)
		}
	})
}

// ── fixture + assertion helpers ───────────────────────────────────────────────────────────────.

// peerFixtureLines reads a committed peer capture fixture, SKIPPING its "#" header. The header
// is what cites which capture each line was copied from and what was measured in it, so it
// lives in the fixture file rather than only in this test.
func peerFixtureLines(t *testing.T, name string) [][]byte {
	t.Helper()
	file, err := os.Open(filepath.Join("testdata", name)) //nolint:gosec // a fixed committed test fixture path
	if err != nil {
		t.Fatalf("open peer fixture %s: %v", name, err)
	}
	t.Cleanup(func() { _ = file.Close() }) //nolint:errcheck // best-effort fixture-file close on test cleanup.
	var lines [][]byte
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 8<<20)
	for scanner.Scan() {
		text := scanner.Text()
		if strings.TrimSpace(text) == "" || strings.HasPrefix(text, "#") {
			continue
		}
		line := make([]byte, len(scanner.Bytes()))
		copy(line, scanner.Bytes())
		lines = append(lines, line)
	}
	if err := scanner.Err(); err != nil {
		t.Fatalf("scan peer fixture %s: %v", name, err)
	}
	if len(lines) == 0 {
		t.Fatalf("peer fixture %s carried no capture lines (only a header): the assertion would be vacuous", name)
	}
	return lines
}

// normalizePeerStream drives the REAL stateful stream normalizer over every fixture line, in
// order — exactly as the live conn's scanner does, so cross-line state (model attribution, the
// tool_use -> tool_result correlation) is threaded the way a real session threads it.
func normalizePeerStream(t *testing.T, lines [][]byte) []agentsession.Event {
	t.Helper()
	normalize := claudeadapter.StreamNormalizerForTest()
	var events []agentsession.Event
	for _, line := range lines {
		events = append(events, normalize(line)...)
	}
	return events
}

// originlessResultLines returns the capture's `result` lines that carry NO `origin` key — the
// negative control that lives inside the positive capture.
func originlessResultLines(t *testing.T, lines [][]byte) [][]byte {
	t.Helper()
	var out [][]byte
	for _, line := range lines {
		var envelope map[string]json.RawMessage
		if err := json.Unmarshal(line, &envelope); err != nil {
			continue
		}
		var kind string
		if err := json.Unmarshal(envelope["type"], &kind); err != nil || kind != "result" {
			continue
		}
		if _, hasOrigin := envelope["origin"]; !hasOrigin {
			out = append(out, line)
		}
	}
	return out
}

// eventsOfKind returns every event of one kind, by value.
func eventsOfKind(events []agentsession.Event, kind agentsession.EventKind) []agentsession.Event {
	var out []agentsession.Event
	for i := range events {
		if events[i].Kind == kind {
			out = append(out, events[i])
		}
	}
	return out
}

// indexOfKind returns the index of the first event of a kind.
func indexOfKind(events []agentsession.Event, kind agentsession.EventKind) (int, bool) {
	for i := range events {
		if events[i].Kind == kind {
			return i, true
		}
	}
	return -1, false
}

// indexOfArg returns the index of an argv token, or -1.
func indexOfArg(args []string, want string) int {
	for i := range args {
		if args[i] == want {
			return i
		}
	}
	return -1
}

// renderKinds lists event kinds for a failure message, so a failure names what DID arrive.
func renderKinds(events []agentsession.Event) string {
	if len(events) == 0 {
		return "(nothing)"
	}
	kinds := make([]string, 0, len(events))
	for i := range events {
		kinds = append(kinds, events[i].Kind.String())
	}
	return strings.Join(kinds, ", ")
}

// truncateForFailure bounds a capture line quoted in a failure message.
func truncateForFailure(line []byte) string {
	const bound = 200
	if len(line) <= bound {
		return string(line)
	}
	return string(line[:bound]) + "…"
}
