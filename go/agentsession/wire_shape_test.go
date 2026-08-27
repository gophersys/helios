package agentsession_test

import (
	"encoding"
	"encoding/json"
	"reflect"
	"strings"
	"testing"
	"unicode"

	"github.com/gophersys/libs/go/agentsession"
)

// THE WIRE SHAPE (slice F1). Everything this library puts on a fleet message — the Event
// stream, the turn-taking controls, the permission round-trip, and the session Spec — is
// serialized by encoding/json. Today NOT ONE of those structs carries a json tag, so the
// wire keys are the Go field names ("SessionID", "Kind") and every closed enum rides as a
// BARE INTEGER. A frozen fleet header would freeze exactly that, forever.
//
// This file is the assertion that makes the fix COMPLETE rather than partial, and that keeps
// it complete: it walks the type graph with reflect from the wire ROOTS and fails naming the
// exact Type.Field for anything that is missing its tag. A struct added to the graph later,
// or a field added to one of them, is covered with NO edit to this file — which is the whole
// point of deriving the set by reachability instead of listing it.
//
// The three rules it pins, and why each is mechanical rather than a judgement call:
//
//   - THE NAME is the camelCase rendering of the Go field name, with an initialism treated
//     as an ordinary word (SessionID -> "sessionId", MsgID -> "msgId", StateRoot ->
//     "stateRoot"). One pure function, expectedWireName, is its ONE home; the golden fixture
//     and the token assertions cite the same function, so the three can never disagree.
//   - A NIL-ABLE field (pointer, slice, map) carries ",omitempty"; every other field does
//     not. An Event carries exactly one of eight payload pointers, so without this every
//     text delta ships seven "null" keys, and a consumer cannot tell an absent payload from
//     a present-but-empty one.
//   - A FUNC-typed exported field carries `json:"-"`. encoding/json cannot marshal a func at
//     all — not even a nil one — so Spec.OnPermission and HostTool.Handler make the whole
//     Spec unmarshalable until they are excluded by name.

// wireRoots are the types that CROSS the wire. Reachability is computed from these and
// nothing else, so a type that never leaves the process is never gated here.
//
//	Event              agent -> bus (the normalized instrumentation stream)
//	Command, Decision  control -> agent (turn-taking, permission answer)
//	Ack                agent -> control (the seq a control was admitted at)
//	PermissionRequest  agent -> policy decider (the out-of-grant ask)
//	Spec               orchestrator -> agent (the immutable per-session input)
func wireRoots() []reflect.Type {
	return []reflect.Type{
		reflect.TypeOf(agentsession.Event{}),
		reflect.TypeOf(agentsession.Command{}),
		reflect.TypeOf(agentsession.Decision{}),
		reflect.TypeOf(agentsession.Ack{}),
		reflect.TypeOf(agentsession.PermissionRequest{}),
		reflect.TypeOf(agentsession.Spec{}),
	}
}

// wirePackagePath is the import path whose types this library OWNS the tags of. The walk
// stops at any other package: time.Time, time.Duration and secrets.Reference are leaves,
// because their rendering belongs to the library that declares them.
func wirePackagePath() string { return reflect.TypeOf(agentsession.Event{}).PkgPath() }

// ── the reachability walk ────────────────────────────────────────────────────────────────.

// walkWireGraph returns every struct and every enum reachable from wireRoots, in a
// deterministic breadth-first order (roots in order, then fields in declaration order). It
// is the ONE derivation of the covered set; every test in this file and its two siblings
// reads it rather than re-listing types by hand.
func walkWireGraph(t *testing.T) (structures, enumerations []reflect.Type) {
	t.Helper()
	seen := make(map[reflect.Type]bool)
	queue := wireRoots()
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		if seen[current] {
			continue
		}
		seen[current] = true
		if current.Kind() == reflect.Struct {
			structures = append(structures, current)
			for i := range current.NumField() {
				queue = append(queue, wireConstituents(current.Field(i).Type)...)
			}
			continue
		}
		if isWireEnumKind(current.Kind()) {
			enumerations = append(enumerations, current)
			continue
		}
		t.Fatalf("wire graph reached %s, a %s — the walk only understands structs and integer enums",
			current.String(), current.Kind())
	}
	return structures, enumerations
}

// wireConstituents unwraps a field type down to the wire-package types it carries. A named
// type declared in this library is a DESTINATION (returned as-is); a container is unwrapped
// (a map yields both its key and its element); anything else is a leaf and yields nothing.
func wireConstituents(typ reflect.Type) []reflect.Type {
	if typ.Name() != "" && typ.PkgPath() == wirePackagePath() {
		return []reflect.Type{typ}
	}
	if typ.Kind() == reflect.Pointer || typ.Kind() == reflect.Slice || typ.Kind() == reflect.Array {
		return wireConstituents(typ.Elem())
	}
	if typ.Kind() == reflect.Map {
		return append(wireConstituents(typ.Key()), wireConstituents(typ.Elem())...)
	}
	return nil
}

// isWireEnumKind reports whether kind is one of the unsigned integer kinds this library
// declares its closed taxonomies as (every one of them is a uint8).
func isWireEnumKind(kind reflect.Kind) bool {
	return kind == reflect.Uint8 || kind == reflect.Uint16 || kind == reflect.Uint32 || kind == reflect.Uint64
}

// ── the naming rule ──────────────────────────────────────────────────────────────────────.

// expectedWireName renders a Go field name as its canonical camelCase wire key: the first
// word entirely lowercase, every later word capitalized then lowercased, so an initialism is
// an ordinary word. SessionID -> "sessionId", MsgID -> "msgId", IsHostTool -> "isHostTool",
// ID -> "id", StateRoot -> "stateRoot". This is the ONE home of the naming rule.
func expectedWireName(goFieldName string) string {
	words := splitIdentifierWords(goFieldName)
	var rendered strings.Builder
	rendered.WriteString(strings.ToLower(words[0]))
	for _, word := range words[1:] {
		runes := []rune(word)
		rendered.WriteString(string(unicode.ToUpper(runes[0])))
		rendered.WriteString(strings.ToLower(string(runes[1:])))
	}
	return rendered.String()
}

// splitIdentifierWords splits a MixedCaps Go identifier into words, treating a run of
// capitals as one word up to the capital that starts the next word (SessionID -> Session,ID;
// IDToken -> ID,Token).
func splitIdentifierWords(name string) []string {
	runes := []rune(name)
	var words []string
	start := 0
	for i := 1; i < len(runes); i++ {
		upper := unicode.IsUpper(runes[i])
		startsWord := upper && !unicode.IsUpper(runes[i-1])
		startsRun := upper && unicode.IsUpper(runes[i-1]) && i+1 < len(runes) && unicode.IsLower(runes[i+1])
		if startsWord || startsRun {
			words = append(words, string(runes[start:i]))
			start = i
		}
	}
	return append(words, string(runes[start:]))
}

// expectedWireTag renders the ENTIRE json tag one field must carry, so a failure names the
// exact literal to paste. A func field is excluded by name; a nil-able field is omitted when
// empty; everything else is always present on the wire.
//
//nolint:gocritic // reflect.StructField is the stdlib's own value record; the walk passes what reflect hands it.
func expectedWireTag(field reflect.StructField) string {
	if field.Type.Kind() == reflect.Func {
		return "-"
	}
	name := expectedWireName(field.Name)
	nilable := field.Type.Kind() == reflect.Pointer ||
		field.Type.Kind() == reflect.Slice ||
		field.Type.Kind() == reflect.Map
	if nilable {
		return name + ",omitempty"
	}
	return name
}

// ── the assertions ───────────────────────────────────────────────────────────────────────.

// TestWireShape_EveryExportedFieldCarriesItsCamelCaseJSONTag is the completeness gate: every
// exported field of every struct reachable from the wire roots declares the exact json tag
// the naming rule derives. A field with no tag serializes under its Go name, which is the
// defect this slice exists to remove before a byte is frozen.
func TestWireShape_EveryExportedFieldCarriesItsCamelCaseJSONTag(t *testing.T) {
	t.Parallel()
	structures, _ := walkWireGraph(t)
	assertWireGraphIsNotVacuous(t, structures)
	for _, structure := range structures {
		for i := range structure.NumField() {
			assertFieldTag(t, structure, structure.Field(i))
		}
	}
}

// assertFieldTag checks one field against the naming rule. An embedded field is the one
// legitimate untagged case: encoding/json promotes its fields onto the parent object, which
// is the wire shape TokenLedger already has and keeps.
//
//nolint:gocritic // reflect.StructField is the stdlib's own value record; the walk passes what reflect hands it.
func assertFieldTag(t *testing.T, structure reflect.Type, field reflect.StructField) {
	t.Helper()
	if field.PkgPath != "" {
		return // unexported: encoding/json never sees it.
	}
	tag, tagged := field.Tag.Lookup("json")
	if field.Anonymous {
		if tagged {
			t.Errorf("%s.%s: the embedded field carries json:%q — leave it UNTAGGED so its fields promote inline onto the parent object",
				structure.Name(), field.Name, tag)
		}
		return
	}
	want := expectedWireTag(field)
	if !tagged {
		t.Errorf("%s.%s has NO json tag: it serializes under the Go field name %q. want `json:%q`",
			structure.Name(), field.Name, field.Name, want)
		return
	}
	if tag != want {
		t.Errorf("%s.%s carries json:%q, want json:%q", structure.Name(), field.Name, tag, want)
	}
}

// TestWireShape_EveryReachableEnumIsATextMarshaler asserts each closed taxonomy on the wire
// renders as its stable token rather than as an integer, in BOTH directions. It reaches the
// contract through encoding.TextMarshaler / encoding.TextUnmarshaler, which is what
// encoding/json itself consults — so what is asserted is the behavior a consumer gets, not
// the presence of a method name.
func TestWireShape_EveryReachableEnumIsATextMarshaler(t *testing.T) {
	t.Parallel()
	_, enumerations := walkWireGraph(t)
	if len(enumerations) < 8 {
		t.Fatalf("the wire walk found %d enums (%s); it found fewer than the eight closed taxonomies the Event and control graphs are known to carry, so this assertion would be near-vacuous",
			len(enumerations), typeNames(enumerations))
	}
	for _, enumeration := range enumerations {
		value := reflect.New(enumeration).Elem().Interface()
		if _, ok := value.(encoding.TextMarshaler); !ok {
			t.Errorf("%s does not implement encoding.TextMarshaler: encoding/json renders it as a BARE INTEGER on the wire, so a frozen header would freeze the ordinal instead of the stable token",
				enumeration.Name())
		}
		pointer := reflect.New(enumeration).Interface()
		if _, ok := pointer.(encoding.TextUnmarshaler); !ok {
			t.Errorf("*%s does not implement encoding.TextUnmarshaler: a decoder cannot read the stable token back, and an UNKNOWN token would land as the zero value — which is a MEANINGFUL member of every taxonomy here",
				enumeration.Name())
		}
	}
}

// TestWireShape_SpecCarriesTheStateRootSeam pins the typed per-session harness state root.
// It reads the field through reflect deliberately: a literal agentsession.Spec{StateRoot: …}
// would not COMPILE today, and a build failure proves nothing about the contract. This way
// the failure is "the field is absent", which is the fact the slice is about.
func TestWireShape_SpecCarriesTheStateRootSeam(t *testing.T) {
	t.Parallel()
	specification := reflect.TypeOf(agentsession.Spec{})
	field, found := specification.FieldByName("StateRoot")
	if !found {
		t.Fatalf("agentsession.Spec has no field StateRoot; its fields today are %s. want a `StateRoot string` carrying the per-session harness state root as a TYPED seam",
			fieldNames(specification))
	}
	if field.Type.Kind() != reflect.String {
		t.Errorf("Spec.StateRoot is a %s, want a string (a filesystem path the harness roots its per-session state at)", field.Type)
	}
	if got, want := field.Tag.Get("json"), "stateRoot"; got != want {
		t.Errorf("Spec.StateRoot carries json:%q, want json:%q", got, want)
	}
}

// TestWireShape_SpecMarshalsWithoutItsFunctionFields proves the Spec can reach the wire at
// all. encoding/json refuses a func-typed field outright — a NIL one too — so until
// OnPermission and HostTool.Handler are excluded by name, no orchestrator can serialize a
// session request.
func TestWireShape_SpecMarshalsWithoutItsFunctionFields(t *testing.T) {
	t.Parallel()
	encoded, err := json.Marshal(agentsession.Spec{Workspace: "/workspace", Name: "planner"})
	if err != nil {
		t.Fatalf("json.Marshal(agentsession.Spec{}) failed: %v\nthe func-typed exported fields must carry `json:\"-\"`", err)
	}
	if len(encoded) == 0 {
		t.Fatal("json.Marshal(agentsession.Spec{}) produced no bytes")
	}
}

// TestWireShape_SpecRoundTripsTheStateRoot drives the field through a real encode/decode. It
// sets and reads StateRoot through reflect for the same reason the test above uses
// FieldByName: the suite must COMPILE against today's code and fail on behavior.
func TestWireShape_SpecRoundTripsTheStateRoot(t *testing.T) {
	t.Parallel()
	const want = "/var/lib/eden/sessions/planner"

	sent := agentsession.Spec{Workspace: "/workspace", Name: "planner"}
	field := reflect.ValueOf(&sent).Elem().FieldByName("StateRoot")
	if !field.IsValid() {
		t.Fatalf("agentsession.Spec has no field StateRoot; its fields today are %s",
			fieldNames(reflect.TypeOf(agentsession.Spec{})))
	}
	field.SetString(want)

	encoded, err := json.Marshal(sent)
	if err != nil {
		t.Fatalf("json.Marshal(Spec): %v", err)
	}
	var received agentsession.Spec
	if err := json.Unmarshal(encoded, &received); err != nil {
		t.Fatalf("json.Unmarshal(Spec): %v (encoded: %s)", err, encoded)
	}
	if got := reflect.ValueOf(received).FieldByName("StateRoot").String(); got != want {
		t.Errorf("Spec.StateRoot did not survive the round trip: got %q, want %q (encoded: %s)", got, want, encoded)
	}
}

// ── non-vacuity anchors ──────────────────────────────────────────────────────────────────.

// assertWireGraphIsNotVacuous pins the structs the graph is KNOWN to reach today. Without
// it a walk that silently found nothing — a root removed, wireConstituents stopping one
// level too early — would let the completeness loop above pass over an empty set.
func assertWireGraphIsNotVacuous(t *testing.T, structures []reflect.Type) {
	t.Helper()
	known := []string{
		"Event", "StatePayload", "MessagePayload", "ToolPayload", "PermissionPayload",
		"UsageMeter", "TerminalPayload", "TokenLedger", "PeerMessage", "SubagentMessage",
		"Command", "Decision", "Ack", "PermissionRequest",
		"Spec", "RouteKey", "ToolGrant", "HostTool", "Budget",
	}
	reached := make(map[string]bool, len(structures))
	for _, structure := range structures {
		reached[structure.Name()] = true
	}
	for _, name := range known {
		if !reached[name] {
			t.Fatalf("the wire walk did not reach %s; it reached %s. The walk is broken, so every assertion built on it would be vacuous",
				name, typeNames(structures))
		}
	}
}

// typeNames renders a type list for a failure message.
func typeNames(types []reflect.Type) string {
	names := make([]string, 0, len(types))
	for _, typ := range types {
		names = append(names, typ.Name())
	}
	return "[" + strings.Join(names, " ") + "]"
}

// fieldNames renders a struct's exported field names for a failure message.
func fieldNames(structure reflect.Type) string {
	names := make([]string, 0, structure.NumField())
	for i := range structure.NumField() {
		if field := structure.Field(i); field.PkgPath == "" {
			names = append(names, field.Name)
		}
	}
	return "[" + strings.Join(names, " ") + "]"
}
