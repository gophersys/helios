package agentsession_test

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// THE GOLDEN WIRE DOCUMENTS. testdata/event-wire.golden.json carries ONE canonical Event per
// EventKind and testdata/control-wire.golden.json carries the four control-plane values, both
// in the shape a fleet message header freezes: camelCase keys, lower-kebab enum tokens, and a
// payload key present only when its payload is.
//
// The comparison is SEMANTIC (both sides decoded to any, then walked) rather than a byte
// diff, because JSON key order is not a wire contract and pinning it would fail a build for a
// field reordering that changes nothing a consumer sees.
//
// Each golden is checked for INTERNAL SOUNDNESS before it is compared, against the real Go
// type graph: every key must be a key the naming rule derives, every non-omitempty field must
// be present, every enum value must be one of that taxonomy's tokens, and every leaf must be
// the JSON kind its Go type produces. A hand-authored fixture with a typo would otherwise
// fail the comparison for a reason that has nothing to do with the feature — a fixture fault
// dressed as evidence.

// ── the canonical values ─────────────────────────────────────────────────────────────────.

const (
	goldenSessionID = "session-canonical"
	goldenTurnID    = "turn-1"
)

// goldenTime is the one stamp every canonical Event carries, so the fixture is reproducible.
var goldenTime = time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)

// goldenUsage is the four-token meter every usage tick and every ledger in the fixture uses.
func goldenUsage() agentsession.UsageMeter {
	return agentsession.UsageMeter{
		Model: "fake-fable-5", Harness: "fake",
		InputTokens: 100, OutputTokens: 40, CacheReadTokens: 60, CacheCreationTokens: 20,
		CostMicros: 1500, Cumulative: true,
	}
}

// goldenLedger is the authoritative aggregate every terminal Event in the fixture carries.
func goldenLedger() agentsession.TokenLedger {
	return agentsession.TokenLedger{
		UsageMeter:     goldenUsage(),
		Turns:          1,
		ToolUses:       1,
		WallTime:       12 * time.Millisecond,
		ToolUsesByName: map[string]int32{"Write": 1},
	}
}

// canonicalWireEvents builds ONE Event per EventKind, in ordinal order, each carrying the
// payload its kind populates. Covering every kind is what makes the golden a complete
// statement of the Event wire shape rather than a sample of it.
//
//nolint:funlen // one literal per EventKind: the length IS the coverage.
func canonicalWireEvents() []agentsession.Event {
	events := []agentsession.Event{
		{
			Kind:  agentsession.EventSessionState,
			State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
		},
		{
			Kind:    agentsession.EventMessageStart,
			Message: &agentsession.MessagePayload{Role: "assistant"},
		},
		{
			Kind:    agentsession.EventThinkingDelta,
			Message: &agentsession.MessagePayload{Role: "assistant", Delta: "weighing the request"},
		},
		{
			Kind:    agentsession.EventTextDelta,
			Message: &agentsession.MessagePayload{Role: "assistant", Delta: "Hello, world"},
		},
		{Kind: agentsession.EventMessageEnd},
		{
			Kind: agentsession.EventToolStart,
			Tool: &agentsession.ToolPayload{
				CallID: "call-1", Name: "Write", GrantID: "grant-write", ArgsSummary: "path=note.txt",
			},
		},
		{
			Kind: agentsession.EventToolUpdate,
			Tool: &agentsession.ToolPayload{
				CallID: "call-1", Name: "Write", GrantID: "grant-write", PartialDigest: "wrote 6 of 12 bytes",
			},
		},
		{
			Kind: agentsession.EventToolEnd,
			Tool: &agentsession.ToolPayload{
				CallID: "call-1", Name: "Write", GrantID: "grant-write",
				Outcome: agentsession.ToolOutcomeOK, ResultDigest: "wrote 12 bytes", Duration: 5 * time.Millisecond,
			},
		},
		{
			Kind: agentsession.EventPermissionRequest,
			Permission: &agentsession.PermissionPayload{
				RequestID: "request-1", Tool: "Bash", Reason: "run the test suite",
				Decision: agentsession.GrantPending,
			},
		},
		{
			Kind: agentsession.EventPermissionResolved,
			Permission: &agentsession.PermissionPayload{
				RequestID: "request-1", Tool: "Bash", Reason: "run the test suite",
				Decision: agentsession.GrantAllowed, By: "user:mateo",
			},
		},
		{Kind: agentsession.EventUsage, Usage: pointerTo(goldenUsage())},
		{
			Kind: agentsession.EventResult,
			Terminal: &agentsession.TerminalPayload{
				Outcome: agentsession.TurnCompleted, Ledger: goldenLedger(),
				ResultText: "Hello, world", StopReason: "end_turn",
			},
		},
		{
			Kind: agentsession.EventFailed,
			Terminal: &agentsession.TerminalPayload{
				Outcome: agentsession.TurnFailed, Ledger: goldenLedger(), StopReason: "error",
				Reason: agentsession.ReasonRateLimit, Detail: "the provider throttled the request",
			},
		},
		{
			Kind: agentsession.EventAborted,
			Terminal: &agentsession.TerminalPayload{
				Outcome: agentsession.TurnAborted, Ledger: goldenLedger(), StopReason: "abort",
				By: "user:mateo",
			},
		},
		{Kind: agentsession.EventExtension, Extension: []byte(`{"type":"rate_limit_event"}`)},
		{
			Kind:    agentsession.EventThinkingProgress,
			Message: &agentsession.MessagePayload{Role: "assistant", Tokens: 512},
		},
		{
			Kind: agentsession.EventTurnEnd,
			Terminal: &agentsession.TerminalPayload{
				Outcome: agentsession.TurnCompleted, Ledger: goldenLedger(),
				ResultText: "Hello, world", StopReason: "end_turn",
			},
		},
		{
			Kind: agentsession.EventPeerMessage,
			Peer: &agentsession.PeerMessage{
				MsgID: "msg-1", From: "planner", Body: "what is the current state?", Verified: true,
			},
		},
		{
			Kind: agentsession.EventPeerSent,
			Peer: &agentsession.PeerMessage{
				MsgID: "msg-2", From: "implementer", To: "planner", ReplyTo: "msg-1",
				Body: "the suite is green", Accepted: true,
			},
		},
		{
			Kind: agentsession.EventSubagentMessage,
			Subagent: &agentsession.SubagentMessage{
				SubagentID: "subagent-1", ParentTurn: goldenTurnID, ToChild: true, Digest: "read the plan",
			},
		},
	}
	for i := range events {
		events[i].SessionID = goldenSessionID
		events[i].TurnID = goldenTurnID
		events[i].Seq = uint64(i + 1) //nolint:gosec // a bounded fixture index.
		events[i].Turn = 1
		events[i].Time = goldenTime
	}
	return events
}

// pointerTo boxes a value so an Event payload pointer can be built inline.
//
//nolint:gocritic // UsageMeter is the contract's copyable value record; the helper takes it by value.
func pointerTo(meter agentsession.UsageMeter) *agentsession.UsageMeter { return &meter }

// wireControlDocument bundles the four control-plane values into one comparable document.
// Its own keys are this fixture's; the keys INSIDE each value are the library's contract.
type wireControlDocument struct {
	Ack               agentsession.Ack               `json:"ack"`
	Command           agentsession.Command           `json:"command"`
	Decision          agentsession.Decision          `json:"decision"`
	PermissionRequest agentsession.PermissionRequest `json:"permissionRequest"`
}

// canonicalControlDocument is the control-plane half of the wire: the turn-taking command,
// the permission answer, the admission receipt, and the out-of-grant ask.
func canonicalControlDocument() wireControlDocument {
	return wireControlDocument{
		Ack:     agentsession.Ack{Seq: 42},
		Command: agentsession.Command{Kind: agentsession.CommandSteer, Text: "focus on the failing test"},
		Decision: agentsession.Decision{
			Allow: true, By: "user:mateo", Scope: agentsession.ScopeSession,
			Rationale: "in-workspace write, reversible",
		},
		PermissionRequest: agentsession.PermissionRequest{
			RequestID: "request-1", Tool: "Bash",
			Input:  []byte(`{"command":"go test ./..."}`),
			Reason: "run the test suite",
		},
	}
}

// ── the golden assertions ────────────────────────────────────────────────────────────────.

// TestWireGolden_EveryEventKindMatchesTheCommittedGolden marshals one canonical Event per
// EventKind and compares it against the committed golden document. This is the spine
// assertion of the slice: it pins the exact wire shape a fleet message header freezes.
func TestWireGolden_EveryEventKindMatchesTheCommittedGolden(t *testing.T) {
	t.Parallel()
	events := canonicalWireEvents()
	assertFixtureCoversEveryEventKind(t, events)

	eventType := reflect.TypeOf(agentsession.Event{})
	golden := readGoldenDocument(t, "event-wire.golden.json")
	goldenEvents, isArray := golden.([]any)
	if !isArray {
		t.Fatalf("testdata/event-wire.golden.json is a %T, want a JSON array of events", golden)
	}
	if len(goldenEvents) != len(events) {
		t.Fatalf("testdata/event-wire.golden.json holds %d events, the fixture builds %d", len(goldenEvents), len(events))
	}
	for i := range goldenEvents {
		assertGoldenNodeIsSound(t, fmt.Sprintf("golden[%d]", i), goldenEvents[i], eventType)
	}

	produced := marshalToTree(t, events)
	if difference := firstWireDifference("events", produced, golden); difference != "" {
		t.Fatalf("the encoded Event stream does not match testdata/event-wire.golden.json:\n  %s", difference)
	}
}

// TestWireGolden_TheControlPlaneMatchesTheCommittedGolden does the same for the four values
// that travel the other way: Command, Decision, Ack and PermissionRequest.
func TestWireGolden_TheControlPlaneMatchesTheCommittedGolden(t *testing.T) {
	t.Parallel()
	golden := readGoldenDocument(t, "control-wire.golden.json")
	object, isObject := golden.(map[string]any)
	if !isObject {
		t.Fatalf("testdata/control-wire.golden.json is a %T, want a JSON object", golden)
	}
	document := canonicalControlDocument()
	documentType := reflect.TypeOf(document)
	for i := range documentType.NumField() {
		field := documentType.Field(i)
		key := field.Tag.Get("json")
		part, present := object[key]
		if !present {
			t.Fatalf("testdata/control-wire.golden.json has no %q member; it carries %v", key, sortedKeys(object))
		}
		assertGoldenNodeIsSound(t, "golden."+key, part, field.Type)
	}

	produced := marshalToTree(t, document)
	if difference := firstWireDifference("control", produced, golden); difference != "" {
		t.Fatalf("the encoded control plane does not match testdata/control-wire.golden.json:\n  %s", difference)
	}
}

// TestWireGolden_TheGoldenDocumentDecodesBackIntoEvents drives the CONSUMER direction: a
// fleet member receives the committed document and must recover the same typed values. The
// producer half above cannot prove this — a library that only encoded correctly would leave
// every reader of the stream decoding tokens into the zero member.
func TestWireGolden_TheGoldenDocumentDecodesBackIntoEvents(t *testing.T) {
	t.Parallel()
	raw, err := os.ReadFile(filepath.Join("testdata", "event-wire.golden.json")) //nolint:gosec // a fixed committed test fixture path
	if err != nil {
		t.Fatalf("read the golden fixture: %v", err)
	}
	var decoded []agentsession.Event
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatalf("the golden Event document does not decode into []agentsession.Event: %v", err)
	}
	if len(decoded) != len(canonicalWireEvents()) {
		t.Fatalf("decoded %d events from the golden document, want %d", len(decoded), len(canonicalWireEvents()))
	}
	for ordinal := range decoded {
		if int(decoded[ordinal].Kind) != ordinal {
			t.Errorf("golden event %d decoded with Kind %d (%s), want ordinal %d — the kind token did not decode",
				ordinal, decoded[ordinal].Kind, decoded[ordinal].Kind, ordinal)
		}
		if decoded[ordinal].SessionID != goldenSessionID {
			t.Errorf("golden event %d decoded SessionID %q, want %q", ordinal, decoded[ordinal].SessionID, goldenSessionID)
		}
	}
	assertDecodedEnum(t, "event[0].state.to", int(payloadState(t, decoded, 0).To), int(agentsession.StateReady))
	assertDecodedEnum(t, "event[7].tool.outcome", int(payloadTool(t, decoded, 7).Outcome), int(agentsession.ToolOutcomeOK))
	assertDecodedEnum(t, "event[9].permission.decision", int(payloadPermission(t, decoded, 9).Decision), int(agentsession.GrantAllowed))
	assertDecodedEnum(t, "event[12].terminal.reason", int(payloadTerminal(t, decoded, 12).Reason), int(agentsession.ReasonRateLimit))
	assertDecodedEnum(t, "event[13].terminal.outcome", int(payloadTerminal(t, decoded, 13).Outcome), int(agentsession.TurnAborted))
}

// assertDecodedEnum reports a taxonomy member that did not survive the decode.
func assertDecodedEnum(t *testing.T, path string, got, want int) {
	t.Helper()
	if got != want {
		t.Errorf("%s decoded as ordinal %d, want %d — the stable token did not decode back into its member", path, got, want)
	}
}

// payloadState returns the decoded state payload at ordinal, or fails naming what arrived.
func payloadState(t *testing.T, decoded []agentsession.Event, ordinal int) agentsession.StatePayload {
	t.Helper()
	if decoded[ordinal].State == nil {
		t.Fatalf("golden event %d decoded with a nil State payload", ordinal)
	}
	return *decoded[ordinal].State
}

// payloadTool returns the decoded tool payload at ordinal, or fails naming what arrived.
func payloadTool(t *testing.T, decoded []agentsession.Event, ordinal int) agentsession.ToolPayload {
	t.Helper()
	if decoded[ordinal].Tool == nil {
		t.Fatalf("golden event %d decoded with a nil Tool payload", ordinal)
	}
	return *decoded[ordinal].Tool
}

// payloadPermission returns the decoded permission payload at ordinal, or fails naming what arrived.
func payloadPermission(t *testing.T, decoded []agentsession.Event, ordinal int) agentsession.PermissionPayload {
	t.Helper()
	if decoded[ordinal].Permission == nil {
		t.Fatalf("golden event %d decoded with a nil Permission payload", ordinal)
	}
	return *decoded[ordinal].Permission
}

// payloadTerminal returns the decoded terminal payload at ordinal, or fails naming what arrived.
func payloadTerminal(t *testing.T, decoded []agentsession.Event, ordinal int) agentsession.TerminalPayload {
	t.Helper()
	if decoded[ordinal].Terminal == nil {
		t.Fatalf("golden event %d decoded with a nil Terminal payload", ordinal)
	}
	return *decoded[ordinal].Terminal
}

// TestWireEncoding_EnumsAreTokensNotIntegers decodes the ENCODED canonical events back into
// generic JSON and asserts every closed-taxonomy field arrived as its stable token string. It
// asserts on the decoded shape, never on a substring of the document, so a token that merely
// appears somewhere in the bytes cannot satisfy it.
func TestWireEncoding_EnumsAreTokensNotIntegers(t *testing.T) {
	t.Parallel()
	events := canonicalWireEvents()
	assertFixtureCoversEveryEventKind(t, events)
	eventType := reflect.TypeOf(agentsession.Event{})

	encoded, isArray := marshalToTree(t, events).([]any)
	if !isArray {
		t.Fatal("the encoded Event stream is not a JSON array")
	}
	var faults []string
	for i := range encoded {
		faults = append(faults, describeEnumFaults(fmt.Sprintf("event[%d]", i), encoded[i], eventType)...)
	}
	if len(faults) > 0 {
		t.Fatalf("%d closed-taxonomy fields do not carry their stable token:\n  %s",
			len(faults), strings.Join(faults, "\n  "))
	}
}

// TestWireEncoding_TheTokenDetectorRejectsABareInteger is the NON-VACUITY anchor for the
// assertion above, and it passes today by design: it guards the DETECTOR, not the feature.
// It feeds describeEnumFaults a document whose keys are already camelCase but whose enums are
// still bare ordinals — the exact half-finished state a fix that adds json tags WITHOUT
// MarshalText would produce — and requires every one of them to be reported. Without this,
// that half-finished state would encode integers under correct keys and the token assertion
// would go quietly green.
func TestWireEncoding_TheTokenDetectorRejectsABareInteger(t *testing.T) {
	t.Parallel()
	halfFixed := map[string]any{
		"sessionId": "session-canonical",
		"turnId":    "turn-1",
		"seq":       float64(1),
		"turn":      float64(1),
		"time":      "2026-06-13T12:00:00Z",
		"kind":      float64(3),
		"state":     map[string]any{"from": float64(0), "to": float64(1)},
	}
	faults := describeEnumFaults("event", halfFixed, reflect.TypeOf(agentsession.Event{}))
	if len(faults) != 3 {
		t.Fatalf("the bare-integer detector reported %d faults %v, want 3 (event.kind, event.state.from, event.state.to)",
			len(faults), faults)
	}
	joined := strings.Join(faults, "\n")
	for _, wanted := range []string{"event.kind", "event.state.from", "event.state.to"} {
		if !strings.Contains(joined, wanted) {
			t.Errorf("the bare-integer detector did not name %s; it reported:\n%s", wanted, joined)
		}
	}
	if !strings.Contains(joined, "float64") {
		t.Errorf("the fault text does not say what the value actually was, so a failure would not be diagnosable:\n%s", joined)
	}
}

// ── fixture soundness ────────────────────────────────────────────────────────────────────.

// assertFixtureCoversEveryEventKind pins the canonical set to the EventKind const block read
// from the package source. Without it, a kind appended later would simply go untested by
// every golden assertion above.
func assertFixtureCoversEveryEventKind(t *testing.T, events []agentsession.Event) {
	t.Helper()
	members := declaredMembers(t, "types.go", "EventKind")
	if len(events) != len(members) {
		t.Fatalf("the canonical fixture builds %d events but EventKind declares %d members %v — every kind needs a canonical Event",
			len(events), len(members), members)
	}
	for ordinal := range members {
		if int(events[ordinal].Kind) != ordinal {
			t.Fatalf("canonical event %d carries Kind %v (ordinal %d), want %s — the fixture is out of ordinal order",
				ordinal, events[ordinal].Kind, events[ordinal].Kind, members[ordinal])
		}
	}
}

// readGoldenDocument reads and decodes a committed golden fixture.
func readGoldenDocument(t *testing.T, name string) any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", name)) //nolint:gosec // a fixed committed test fixture path
	if err != nil {
		t.Fatalf("read the golden fixture: %v", err)
	}
	var document any
	if err := json.Unmarshal(raw, &document); err != nil {
		t.Fatalf("testdata/%s is not valid JSON: %v", name, err)
	}
	return document
}

// marshalToTree encodes a value with encoding/json and decodes it back into generic JSON, so
// the produced document can be compared key by key rather than byte by byte.
func marshalToTree(t *testing.T, value any) any {
	t.Helper()
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("json.Marshal: %v", err)
	}
	var tree any
	if err := json.Unmarshal(encoded, &tree); err != nil {
		t.Fatalf("json.Unmarshal of the encoded document: %v (encoded: %s)", err, encoded)
	}
	return tree
}

// assertGoldenNodeIsSound fails when a committed fixture does not describe the real Go type
// graph. It guards the FIXTURE, not the feature — a hand-authored typo must surface as its
// own failure rather than as a comparison mismatch that reads like a defect in the code.
func assertGoldenNodeIsSound(t *testing.T, path string, node any, goType reflect.Type) {
	t.Helper()
	if faults := describeShapeFaults(path, node, goType); len(faults) > 0 {
		t.Fatalf("the committed golden fixture is not a faithful description of %s:\n  %s",
			goType.Name(), strings.Join(faults, "\n  "))
	}
}

// ── the walkers ──────────────────────────────────────────────────────────────────────────.

// describeShapeFaults validates a decoded JSON node against a Go type: every key known, every
// required key present, every enum a legal token, every leaf the JSON kind its Go type
// produces.
func describeShapeFaults(path string, node any, goType reflect.Type) []string {
	goType = derefWireType(goType)
	if isWireEnumType(goType) {
		return describeTokenFault(path, node, goType)
	}
	if !isWireStructType(goType) {
		return describeLeafFault(path, node, goType)
	}
	object, isObject := node.(map[string]any)
	if !isObject {
		return []string{fmt.Sprintf("%s: is a %T, want a JSON object for %s", path, node, goType.Name())}
	}
	fields := wireFields(goType)
	var faults []string
	for _, key := range sortedKeys(object) {
		field, known := fields[key]
		if !known {
			faults = append(faults, fmt.Sprintf("%s.%s: no such field on %s (its wire keys are %v)",
				path, key, goType.Name(), sortedFieldKeys(fields)))
			continue
		}
		faults = append(faults, describeShapeFaults(path+"."+key, object[key], field.Type)...)
	}
	for _, key := range sortedFieldKeys(fields) {
		if _, present := object[key]; present {
			continue
		}
		if !strings.Contains(expectedWireTag(fields[key]), ",omitempty") {
			faults = append(faults, fmt.Sprintf("%s.%s: missing; %s.%s is always present on the wire",
				path, key, goType.Name(), fields[key].Name))
		}
	}
	return faults
}

// describeEnumFaults reports every closed-taxonomy field that did NOT arrive as its stable
// token. It descends only into keys the document actually carries, so an omitted payload is
// not a fault — an enum field that is absent or numeric is.
func describeEnumFaults(path string, node any, goType reflect.Type) []string {
	goType = derefWireType(goType)
	if isWireEnumType(goType) {
		return describeTokenFault(path, node, goType)
	}
	if goType.Kind() == reflect.Slice && isWireStructType(derefWireType(goType.Elem())) {
		return describeEnumFaultsInArray(path, node, derefWireType(goType.Elem()))
	}
	if !isWireStructType(goType) {
		return nil
	}
	object, isObject := node.(map[string]any)
	if !isObject {
		return []string{fmt.Sprintf("%s: is a %T, want a JSON object for %s", path, node, goType.Name())}
	}
	fields := wireFields(goType)
	var faults []string
	for _, key := range sortedFieldKeys(fields) {
		child, present := object[key]
		if !present {
			if isWireEnumType(derefWireType(fields[key].Type)) {
				faults = append(faults, fmt.Sprintf("%s.%s: ABSENT from the encoded %s, which carries %v instead",
					path, key, goType.Name(), sortedKeys(object)))
			}
			continue
		}
		faults = append(faults, describeEnumFaults(path+"."+key, child, fields[key].Type)...)
	}
	return faults
}

// describeEnumFaultsInArray applies the token check to each element of a JSON array.
func describeEnumFaultsInArray(path string, node any, elementType reflect.Type) []string {
	elements, isArray := node.([]any)
	if !isArray {
		return []string{fmt.Sprintf("%s: is a %T, want a JSON array", path, node)}
	}
	var faults []string
	for i := range elements {
		faults = append(faults, describeEnumFaults(fmt.Sprintf("%s[%d]", path, i), elements[i], elementType)...)
	}
	return faults
}

// describeTokenFault reports a closed-taxonomy value that is not one of its stable tokens —
// the BARE INTEGER case included, which is what encoding/json produces with no TextMarshaler.
func describeTokenFault(path string, node any, goType reflect.Type) []string {
	tokens, tabled := wireEnumTokens()[goType.Name()]
	if !tabled {
		return []string{fmt.Sprintf("%s: %s has no row in wireEnumSpecs, so its tokens are unasserted", path, goType.Name())}
	}
	token, isString := node.(string)
	if !isString {
		return []string{fmt.Sprintf("%s: encoded as %T (%v), want one of the %s tokens %v",
			path, node, node, goType.Name(), tokens)}
	}
	for _, known := range tokens {
		if token == known {
			return nil
		}
	}
	return []string{fmt.Sprintf("%s: encoded as %q, which is not a %s token %v", path, token, goType.Name(), tokens)}
}

// describeLeafFault reports a leaf whose JSON kind does not match what its Go type produces.
func describeLeafFault(path string, node any, goType reflect.Type) []string {
	want := jsonKindOfType(goType)
	if want == "" {
		return nil
	}
	if got := jsonKindOfValue(node); got != want {
		return []string{fmt.Sprintf("%s: is a JSON %s, but %s encodes as a JSON %s", path, got, goType, want)}
	}
	return nil
}

// firstWireDifference returns a description of the FIRST place the produced document departs
// from the golden, or "" when the two describe the same wire document.
func firstWireDifference(path string, produced, golden any) string {
	switch expected := golden.(type) {
	case map[string]any:
		return firstObjectDifference(path, produced, expected)
	case []any:
		return firstArrayDifference(path, produced, expected)
	default:
		if !reflect.DeepEqual(produced, golden) {
			return fmt.Sprintf("%s: produced %#v, golden has %#v", path, produced, golden)
		}
		return ""
	}
}

// firstObjectDifference compares one JSON object against the golden's.
func firstObjectDifference(path string, produced any, expected map[string]any) string {
	actual, isObject := produced.(map[string]any)
	if !isObject {
		return fmt.Sprintf("%s: produced a %T, golden has a JSON object", path, produced)
	}
	for _, key := range sortedKeys(expected) {
		child, present := actual[key]
		if !present {
			return fmt.Sprintf("%s.%s: ABSENT from the produced document, which carries the keys %v",
				path, key, sortedKeys(actual))
		}
		if difference := firstWireDifference(path+"."+key, child, expected[key]); difference != "" {
			return difference
		}
	}
	for _, key := range sortedKeys(actual) {
		if _, wanted := expected[key]; !wanted {
			return fmt.Sprintf("%s.%s: the produced document carries this key (value %v); the golden does not",
				path, key, actual[key])
		}
	}
	return ""
}

// firstArrayDifference compares one JSON array against the golden's.
func firstArrayDifference(path string, produced any, expected []any) string {
	actual, isArray := produced.([]any)
	if !isArray {
		return fmt.Sprintf("%s: produced a %T, golden has a JSON array", path, produced)
	}
	if len(actual) != len(expected) {
		return fmt.Sprintf("%s: produced %d elements, golden has %d", path, len(actual), len(expected))
	}
	for i := range expected {
		if difference := firstWireDifference(fmt.Sprintf("%s[%d]", path, i), actual[i], expected[i]); difference != "" {
			return difference
		}
	}
	return ""
}

// ── small shared helpers ─────────────────────────────────────────────────────────────────.

// derefWireType strips one pointer level.
func derefWireType(goType reflect.Type) reflect.Type {
	if goType.Kind() == reflect.Pointer {
		return goType.Elem()
	}
	return goType
}

// isWireEnumType reports whether goType is one of this library's closed integer taxonomies.
func isWireEnumType(goType reflect.Type) bool {
	return goType.PkgPath() == wirePackagePath() && isWireEnumKind(goType.Kind())
}

// isWireStructType reports whether goType is a struct this library declares.
func isWireStructType(goType reflect.Type) bool {
	return goType.Kind() == reflect.Struct && goType.PkgPath() == wirePackagePath()
}

// wireFields maps a struct's wire keys to their fields, PROMOTING the fields of an embedded
// struct exactly as encoding/json does, and dropping func fields (which never reach the wire).
func wireFields(structure reflect.Type) map[string]reflect.StructField {
	fields := make(map[string]reflect.StructField)
	for i := range structure.NumField() {
		field := structure.Field(i)
		if field.PkgPath != "" || field.Type.Kind() == reflect.Func {
			continue
		}
		if field.Anonymous && field.Type.Kind() == reflect.Struct {
			for key, promoted := range wireFields(field.Type) {
				fields[key] = promoted
			}
			continue
		}
		fields[expectedWireName(field.Name)] = field
	}
	return fields
}

// jsonKindOfType names the JSON kind a Go type encodes as, or "" when it is not pinned.
func jsonKindOfType(goType reflect.Type) string {
	if goType == reflect.TypeOf(time.Time{}) {
		return "string"
	}
	if goType.Kind() == reflect.Slice && goType.Elem().Kind() == reflect.Uint8 {
		return "string" // encoding/json base64-encodes a byte slice.
	}
	if goType.Kind() == reflect.String {
		return "string"
	}
	if goType.Kind() == reflect.Bool {
		return "boolean"
	}
	if isNumericKind(goType.Kind()) {
		return "number"
	}
	if goType.Kind() == reflect.Slice || goType.Kind() == reflect.Array {
		return "array"
	}
	if goType.Kind() == reflect.Map {
		return "object"
	}
	return ""
}

// isNumericKind reports whether kind encodes as a JSON number.
func isNumericKind(kind reflect.Kind) bool {
	return kind >= reflect.Int && kind <= reflect.Float64
}

// jsonKindOfValue names the JSON kind a decoded value came back as.
func jsonKindOfValue(node any) string {
	switch node.(type) {
	case nil:
		return "null"
	case string:
		return "string"
	case bool:
		return "boolean"
	case float64:
		return "number"
	case []any:
		return "array"
	case map[string]any:
		return "object"
	default:
		return fmt.Sprintf("%T", node)
	}
}

// sortedKeys returns a JSON object's keys in a stable order.
func sortedKeys(object map[string]any) []string {
	keys := make([]string, 0, len(object))
	for key := range object {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

// sortedFieldKeys returns a wire-field map's keys in a stable order.
func sortedFieldKeys(fields map[string]reflect.StructField) []string {
	keys := make([]string, 0, len(fields))
	for key := range fields {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
