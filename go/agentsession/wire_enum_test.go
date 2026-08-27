package agentsession_test

import (
	"encoding"
	"strings"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// THE TOKEN VOCABULARY of every closed taxonomy that crosses the wire. Each member rides as
// its stable lower-kebab token, in BOTH directions, or the ordinal is what a frozen fleet
// header freezes.
//
// The UNKNOWN-token half is the load-bearing one. Ordinal 0 is a MEANINGFUL member of every
// taxonomy here — EventSessionState, StateInitializing, ToolOutcomeOK, GrantPending,
// TurnCompleted, ReasonUnknown, CommandPrompt, ScopeOnce, ResolveChatHumanThenAdvisor — so a
// decoder that fell back to the zero value on an unrecognized token would silently turn a
// kind it does not know into a valid session-state event, and a tool it cannot classify into
// a successful one. That is a silent corruption, and it is why an unknown token must be a
// TYPED error rather than a default.
//
// Five of the nine taxonomies already spell their tokens through String() (State,
// CommandKind, DecisionScope, EventKind, PermissionResolution) and the table below is
// asserted EQUAL to those — one vocabulary, not two. FOUR of them (ToolOutcome,
// GrantDecision, TurnOutcome, ErrorReason) have NO String() method at all today, so this
// table is the first place their tokens are written down. They follow the house rule the
// other five already obey: drop the type's constant prefix, lower-kebab the remainder
// (ToolOutcomeDenied -> "denied", TurnBudgetExceeded -> "budget-exceeded",
// ReasonHarnessError -> "harness-error").

// wireEnumSpec binds one closed taxonomy's SOURCE declaration to its RUNTIME text encoding.
// The member set is read from the const block by declaredMembers (types_tokens_test.go), so
// a member appended without a token row fails the coverage anchor instead of rotting.
type wireEnumSpec struct {
	typeName   string
	sourceFile string
	tokens     []string

	// member boxes the taxonomy member at ordinal, so the text-marshaling contract is
	// reached through an interface assertion rather than through a method call that would
	// not compile until the feature lands.
	member func(ordinal int) any

	// target returns a pointer to a fresh zero member plus a reader for its ordinal — the
	// decode half of the round trip.
	target func() (pointer any, ordinal func() int)

	// existingToken renders the member through the String() the type already ships, or is
	// nil for a taxonomy that has no String() method yet.
	existingToken func(ordinal int) string
}

// wireEnumSpecs is the guarded set: every closed taxonomy reachable from the wire roots.
// TestWireEnums_TheTableCoversEveryEnumTheWireWalkReaches proves it is neither short nor
// stale, so adding a taxonomy to the graph forces a row here.
//
//nolint:funlen // one row per taxonomy; the length IS the coverage, and splitting it hides what is covered.
func wireEnumSpecs() []wireEnumSpec {
	return []wireEnumSpec{
		{
			typeName: "EventKind", sourceFile: "types.go",
			tokens: []string{
				"session-state", "message-start", "thinking-delta", "text-delta", "message-end",
				"tool-start", "tool-update", "tool-end", "permission-request", "permission-resolved",
				"usage", "result", "failed", "aborted", "extension", "thinking-progress", "turn-end",
				"peer-message", "peer-sent", "subagent-message",
			},
			member: func(ordinal int) any { return agentsession.EventKind(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.EventKind
				return &decoded, func() int { return int(decoded) }
			},
			existingToken: func(ordinal int) string { return agentsession.EventKind(ordinal).String() }, //nolint:gosec // a bounded source-derived index
		},
		{
			typeName: "State", sourceFile: "types.go",
			tokens: []string{
				"initializing", "ready", "running", "awaiting-input", "awaiting-permission",
				"completed", "failed", "aborted",
			},
			member: func(ordinal int) any { return agentsession.State(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.State
				return &decoded, func() int { return int(decoded) }
			},
			existingToken: func(ordinal int) string { return agentsession.State(ordinal).String() }, //nolint:gosec // a bounded source-derived index
		},
		{
			typeName: "CommandKind", sourceFile: "types.go",
			tokens: []string{"prompt", "steer", "abort"},
			member: func(ordinal int) any { return agentsession.CommandKind(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.CommandKind
				return &decoded, func() int { return int(decoded) }
			},
			existingToken: func(ordinal int) string { return agentsession.CommandKind(ordinal).String() }, //nolint:gosec // a bounded source-derived index
		},
		{
			typeName: "DecisionScope", sourceFile: "types.go",
			tokens: []string{"once", "session"},
			member: func(ordinal int) any { return agentsession.DecisionScope(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.DecisionScope
				return &decoded, func() int { return int(decoded) }
			},
			existingToken: func(ordinal int) string { return agentsession.DecisionScope(ordinal).String() }, //nolint:gosec // a bounded source-derived index
		},
		{
			typeName: "PermissionResolution", sourceFile: "permission.go",
			tokens: []string{"chat-human-then-advisor", "autonomous-advisor"},
			member: func(ordinal int) any { return agentsession.PermissionResolution(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.PermissionResolution
				return &decoded, func() int { return int(decoded) }
			},
			existingToken: func(ordinal int) string { return agentsession.PermissionResolution(ordinal).String() }, //nolint:gosec // a bounded source-derived index
		},
		{
			// No String() today: these four tokens are minted here, by the house rule.
			typeName: "ToolOutcome", sourceFile: "types.go",
			tokens: []string{"ok", "error", "denied"},
			member: func(ordinal int) any { return agentsession.ToolOutcome(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.ToolOutcome
				return &decoded, func() int { return int(decoded) }
			},
		},
		{
			typeName: "GrantDecision", sourceFile: "types.go",
			tokens: []string{"pending", "allowed", "denied"},
			member: func(ordinal int) any { return agentsession.GrantDecision(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.GrantDecision
				return &decoded, func() int { return int(decoded) }
			},
		},
		{
			typeName: "TurnOutcome", sourceFile: "types.go",
			tokens: []string{"completed", "aborted", "failed", "max-turns", "budget-exceeded"},
			member: func(ordinal int) any { return agentsession.TurnOutcome(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.TurnOutcome
				return &decoded, func() int { return int(decoded) }
			},
		},
		{
			typeName: "ErrorReason", sourceFile: "types.go",
			tokens: []string{
				"unknown", "auth", "rate-limit", "budget", "max-turns", "transport", "harness-error",
			},
			member: func(ordinal int) any { return agentsession.ErrorReason(ordinal) }, //nolint:gosec // a bounded source-derived index
			target: func() (any, func() int) {
				var decoded agentsession.ErrorReason
				return &decoded, func() int { return int(decoded) }
			},
		},
	}
}

// wireEnumTokens indexes the token table by type name, for the fixture and path checks in
// the sibling wire test files.
func wireEnumTokens() map[string][]string {
	byName := make(map[string][]string)
	for _, spec := range wireEnumSpecs() {
		byName[spec.typeName] = spec.tokens
	}
	return byName
}

// ── the fixture anchors (these pass today: they guard the TABLE, not the feature) ─────────.

// TestWireEnums_TheTableCoversEveryEnumTheWireWalkReaches pins the token table to the
// reachability walk. A taxonomy that enters the wire graph without a row here would be
// silently unasserted by every property below — the blind-gate shape this repository has
// already shipped four times.
func TestWireEnums_TheTableCoversEveryEnumTheWireWalkReaches(t *testing.T) {
	t.Parallel()
	_, enumerations := walkWireGraph(t)
	tabled := wireEnumTokens()
	for _, enumeration := range enumerations {
		if _, covered := tabled[enumeration.Name()]; !covered {
			t.Errorf("%s is reachable from the wire roots but has NO row in wireEnumSpecs, so its tokens are asserted nowhere",
				enumeration.Name())
		}
	}
	if len(tabled) != len(enumerations) {
		t.Errorf("the token table has %d taxonomies, the wire walk reaches %d (%s) — the table has drifted from the graph",
			len(tabled), len(enumerations), typeNames(enumerations))
	}
}

// TestWireEnums_TheTokenTableMatchesTheDeclaredMembers reads each taxonomy's member list
// from its const block in the package SOURCE and asserts the table has exactly one token per
// member, in order — so a member appended without a token fails here rather than encoding as
// a neighbor's token. Where a String() already exists, the table must repeat it EXACTLY:
// one vocabulary, never a second.
func TestWireEnums_TheTokenTableMatchesTheDeclaredMembers(t *testing.T) {
	t.Parallel()
	for _, spec := range wireEnumSpecs() {
		t.Run(spec.typeName, func(t *testing.T) {
			t.Parallel()
			members := declaredMembers(t, spec.sourceFile, spec.typeName)
			if len(members) != len(spec.tokens) {
				t.Fatalf("%s declares %d members %v but the token table lists %d %v",
					spec.typeName, len(members), members, len(spec.tokens), spec.tokens)
			}
			seen := make(map[string]string, len(spec.tokens))
			for ordinal := range spec.tokens {
				assertTokenRow(t, &spec, members, seen, ordinal)
			}
		})
	}
}

// assertTokenRow checks one taxonomy member's token: distinct, lower-kebab, and identical to
// the String() the type already ships when it ships one.
func assertTokenRow(t *testing.T, spec *wireEnumSpec, members []string, seen map[string]string, ordinal int) {
	t.Helper()
	token := spec.tokens[ordinal]
	if previous, clash := seen[token]; clash {
		t.Errorf("%s: %s and %s share the token %q", spec.typeName, previous, members[ordinal], token)
	}
	seen[token] = members[ordinal]
	if token == "" || token != strings.ToLower(token) || strings.ContainsAny(token, " _") {
		t.Errorf("%s: %s has token %q, which is not the stable lower-kebab wire form",
			spec.typeName, members[ordinal], token)
	}
	if spec.existingToken == nil {
		return
	}
	if existing := spec.existingToken(ordinal); existing != token {
		t.Errorf("%s: %s.String() is %q but the token table says %q — the wire encoding must reuse the vocabulary that already exists, not invent a second one",
			spec.typeName, members[ordinal], existing, token)
	}
}

// ── the assertions the feature must satisfy ──────────────────────────────────────────────.

// TestWireEnums_MarshalTextRendersTheStableToken walks every member of every wire taxonomy
// and asserts its text encoding is the stable token. It is the deterministic, total
// companion to the rapid property below: rapid samples, this one covers.
func TestWireEnums_MarshalTextRendersTheStableToken(t *testing.T) {
	t.Parallel()
	for _, spec := range wireEnumSpecs() {
		t.Run(spec.typeName, func(t *testing.T) {
			t.Parallel()
			marshalers := assertEnumSpeaksText(t, &spec)
			for ordinal, want := range spec.tokens {
				encoded, err := marshalers.marshal(ordinal)
				if err != nil {
					t.Errorf("%s(%d).MarshalText: %v", spec.typeName, ordinal, err)
					continue
				}
				if string(encoded) != want {
					t.Errorf("%s(%d).MarshalText = %q, want %q", spec.typeName, ordinal, encoded, want)
				}
			}
		})
	}
}

// TestProperty_WireEnumTextRoundTrip is the ADR-0020 dimension (a) property: for EVERY
// member of every wire taxonomy, token -> value -> token is the identity. A drift here is a
// wire break, because the token is what a frozen fleet header carries.
func TestProperty_WireEnumTextRoundTrip(t *testing.T) {
	t.Parallel()
	for _, spec := range wireEnumSpecs() {
		t.Run(spec.typeName, func(t *testing.T) {
			t.Parallel()
			marshalers := assertEnumSpeaksText(t, &spec)
			rapid.Check(t, func(rt *rapid.T) {
				ordinal := rapid.IntRange(0, len(spec.tokens)-1).Draw(rt, "ordinal")
				encoded, err := marshalers.marshal(ordinal)
				if err != nil {
					rt.Fatalf("%s(%d).MarshalText: %v", spec.typeName, ordinal, err)
				}
				decoded, err := marshalers.unmarshal(encoded)
				if err != nil {
					rt.Fatalf("%s.UnmarshalText(%q): %v", spec.typeName, encoded, err)
				}
				if decoded != ordinal {
					rt.Fatalf("%s round trip drifted: %s(%d) encoded as %q decoded back as ordinal %d",
						spec.typeName, spec.typeName, ordinal, encoded, decoded)
				}
			})
		})
	}
}

// TestProperty_WireEnumRejectsAnUnknownToken is the half that keeps a fleet honest: a token
// this build does not know is a TYPED error, never a default. Ordinal 0 is a meaningful
// member of every taxonomy here, so a silent fallback would rename an unrecognized event
// into a valid one instead of reporting that the peer speaks a newer vocabulary.
func TestProperty_WireEnumRejectsAnUnknownToken(t *testing.T) {
	t.Parallel()
	for _, spec := range wireEnumSpecs() {
		t.Run(spec.typeName, func(t *testing.T) {
			t.Parallel()
			marshalers := assertEnumSpeaksText(t, &spec)
			known := make(map[string]bool, len(spec.tokens))
			for _, token := range spec.tokens {
				known[token] = true
			}
			rapid.Check(t, func(rt *rapid.T) {
				candidate := rapid.String().Filter(func(drawn string) bool { return !known[drawn] }).Draw(rt, "unknownToken")
				decoded, err := marshalers.unmarshal([]byte(candidate))
				if err == nil {
					rt.Fatalf("%s.UnmarshalText(%q) accepted an unknown token and produced ordinal %d — an unrecognized token must be an error, never a silent member",
						spec.typeName, candidate, decoded)
				}
				if kind := errors.KindOf(err); kind != errors.KindInvalid {
					rt.Fatalf("%s.UnmarshalText(%q) returned Kind %v, want %v: a wire decode fault is branchable by Kind, never by message text",
						spec.typeName, candidate, kind, errors.KindInvalid)
				}
			})
		})
	}
}

// ── reaching the contract without a compile dependency on it ──────────────────────────────.

// enumTextCodec is the pair of closures the assertions drive. Reaching MarshalText /
// UnmarshalText through encoding.TextMarshaler and encoding.TextUnmarshaler is deliberate:
// it is exactly the seam encoding/json itself consults, and it lets this suite COMPILE
// against a build where the methods do not exist yet, so the failure is the missing
// contract rather than a broken build.
type enumTextCodec struct {
	marshal   func(ordinal int) ([]byte, error)
	unmarshal func(token []byte) (ordinal int, err error)
}

// assertEnumSpeaksText fails the subtest when the taxonomy does not implement the two text
// interfaces, and otherwise returns the codec bound to them.
func assertEnumSpeaksText(t *testing.T, spec *wireEnumSpec) enumTextCodec {
	t.Helper()
	if _, ok := spec.member(0).(encoding.TextMarshaler); !ok {
		t.Fatalf("%s does not implement encoding.TextMarshaler: encoding/json renders every member as a BARE INTEGER, so the wire carries the ordinal instead of the stable token",
			spec.typeName)
	}
	pointer, _ := spec.target()
	if _, ok := pointer.(encoding.TextUnmarshaler); !ok {
		t.Fatalf("*%s does not implement encoding.TextUnmarshaler: the token cannot be decoded back, and an unknown token would land on the meaningful zero member",
			spec.typeName)
	}
	return enumTextCodec{
		marshal: func(ordinal int) ([]byte, error) {
			marshaler, ok := spec.member(ordinal).(encoding.TextMarshaler)
			if !ok {
				return nil, errors.New(errors.KindInternal, "agentsession_test: member is not a TextMarshaler")
			}
			return marshaler.MarshalText() //nolint:wrapcheck // the assertion reports the raw contract error.
		},
		unmarshal: func(token []byte) (int, error) {
			fresh, readOrdinal := spec.target()
			unmarshaler, ok := fresh.(encoding.TextUnmarshaler)
			if !ok {
				return 0, errors.New(errors.KindInternal, "agentsession_test: target is not a TextUnmarshaler")
			}
			if err := unmarshaler.UnmarshalText(token); err != nil {
				return readOrdinal(), err //nolint:wrapcheck // the assertion branches on the raw contract error's Kind.
			}
			return readOrdinal(), nil
		},
	}
}
