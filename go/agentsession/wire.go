package agentsession

import (
	"github.com/gophersys/libs/go/errors"
)

// This file is the WIRE ENCODING of every closed taxonomy that crosses a fleet message. A
// bare uint8 rides encoding/json as its ORDINAL, so a frozen fleet header would freeze the
// iota position rather than the stable token, and appending a member later would renumber
// what every consumer already decoded. encoding.TextMarshaler / encoding.TextUnmarshaler are
// the seam encoding/json itself consults, so implementing them puts the token on the wire in
// BOTH directions with no per-struct marshaler.
//
// Go cannot generate a method set, so each of the nine taxonomies still declares its own
// MarshalText/UnmarshalText pair — but each pair is one line over the shared wireTokens
// below, so the table lookup, the range guard and the typed decode fault have ONE home.

// wireTokens binds one closed taxonomy's members to their stable tokens and holds both
// directions of its wire encoding.
type wireTokens[Member ~uint8] struct {
	// taxonomy names the type in a fault, so a rejected token says WHICH vocabulary did not
	// contain it.
	taxonomy string

	// tokens holds each member's stable lower-kebab token, indexed by the member's value. It
	// is the SAME table the type's String() reads where the type ships one — one vocabulary,
	// never a second.
	tokens []string

	// render is the taxonomy's own String(), passed as a method expression, for the five
	// types that already ship one. Where it is set, marshal DELEGATES to it, so the wire
	// token and the rendered token are identical by construction rather than by inspection —
	// including for a value outside the declared set, which String() promises to render
	// totally (EventKind renders "extension", CommandKind renders "command").
	//
	// nil for a taxonomy that makes no such promise. Every member of those four is
	// meaningful (ToolOutcomeOK, GrantPending, TurnCompleted, ReasonUnknown), so there is no
	// member an out-of-range value could honestly borrow: encoding one is a typed fault, not
	// a token that claims something untrue.
	render func(Member) string
}

// marshal renders member as its stable token.
func (w wireTokens[Member]) marshal(member Member) ([]byte, error) {
	if w.render != nil {
		return []byte(w.render(member)), nil
	}
	if int(member) < len(w.tokens) {
		return []byte(w.tokens[member]), nil
	}
	return nil, errors.New(errors.KindInvalid, "agentsession: cannot encode a value outside the declared taxonomy").
		WithField("taxonomy", w.taxonomy).
		WithField("ordinal", int(member))
}

// unmarshal resolves token to the member that declares it, and fails typed (KindInvalid) on
// any other token. The fault is the load-bearing half of this file: ordinal 0 is a MEANINGFUL
// member of every taxonomy here — EventSessionState, StateInitializing, CommandPrompt,
// ScopeOnce, ToolOutcomeOK, GrantPending, TurnCompleted, ReasonUnknown,
// ResolveChatHumanThenAdvisor — so a decoder that fell back to the zero value would silently
// turn an event kind this build does not know into a valid session-state event, and a tool it
// cannot classify into a successful one. A peer that speaks a newer vocabulary must be
// reported, never guessed at.
func (w wireTokens[Member]) unmarshal(token []byte, member *Member) error {
	text := string(token)
	var candidate Member
	for _, known := range w.tokens {
		if known == text {
			*member = candidate
			return nil
		}
		candidate++
	}
	return errors.New(errors.KindInvalid, "agentsession: unknown wire token").
		WithField("taxonomy", w.taxonomy).
		WithField("token", text)
}

// The wire encoding of each closed taxonomy, citing the token table the type already declares.
var (
	stateWire         = wireTokens[State]{taxonomy: "State", tokens: stateTokens[:], render: State.String}
	commandKindWire   = wireTokens[CommandKind]{taxonomy: "CommandKind", tokens: commandTokens[:], render: CommandKind.String}
	decisionScopeWire = wireTokens[DecisionScope]{taxonomy: "DecisionScope", tokens: decisionScopeTokens[:], render: DecisionScope.String}
	eventKindWire     = wireTokens[EventKind]{taxonomy: "EventKind", tokens: eventKindTokens[:], render: EventKind.String}
	toolOutcomeWire   = wireTokens[ToolOutcome]{taxonomy: "ToolOutcome", tokens: toolOutcomeTokens[:]}
	grantDecisionWire = wireTokens[GrantDecision]{taxonomy: "GrantDecision", tokens: grantDecisionTokens[:]}
	turnOutcomeWire   = wireTokens[TurnOutcome]{taxonomy: "TurnOutcome", tokens: turnOutcomeTokens[:]}
	errorReasonWire   = wireTokens[ErrorReason]{taxonomy: "ErrorReason", tokens: errorReasonTokens[:]}
	resolutionWire    = wireTokens[PermissionResolution]{taxonomy: "PermissionResolution", tokens: resolutionTokens[:], render: PermissionResolution.String}
)

// MarshalText renders the State as its stable token (encoding.TextMarshaler).
func (s State) MarshalText() ([]byte, error) { return stateWire.marshal(s) }

// UnmarshalText reads a stable token back into a State; an unknown token is a typed fault.
func (s *State) UnmarshalText(token []byte) error { return stateWire.unmarshal(token, s) }

// MarshalText renders the CommandKind as its stable token (encoding.TextMarshaler).
func (k CommandKind) MarshalText() ([]byte, error) { return commandKindWire.marshal(k) }

// UnmarshalText reads a stable token back into a CommandKind; an unknown token is a typed fault.
func (k *CommandKind) UnmarshalText(token []byte) error { return commandKindWire.unmarshal(token, k) }

// MarshalText renders the DecisionScope as its stable token (encoding.TextMarshaler).
func (s DecisionScope) MarshalText() ([]byte, error) { return decisionScopeWire.marshal(s) }

// UnmarshalText reads a stable token back into a DecisionScope; an unknown token is a typed fault.
func (s *DecisionScope) UnmarshalText(token []byte) error {
	return decisionScopeWire.unmarshal(token, s)
}

// MarshalText renders the EventKind as its stable token (encoding.TextMarshaler).
func (k EventKind) MarshalText() ([]byte, error) { return eventKindWire.marshal(k) }

// UnmarshalText reads a stable token back into an EventKind; an unknown token is a typed fault.
func (k *EventKind) UnmarshalText(token []byte) error { return eventKindWire.unmarshal(token, k) }

// MarshalText renders the ToolOutcome as its stable token (encoding.TextMarshaler).
func (o ToolOutcome) MarshalText() ([]byte, error) { return toolOutcomeWire.marshal(o) }

// UnmarshalText reads a stable token back into a ToolOutcome; an unknown token is a typed fault.
func (o *ToolOutcome) UnmarshalText(token []byte) error { return toolOutcomeWire.unmarshal(token, o) }

// MarshalText renders the GrantDecision as its stable token (encoding.TextMarshaler).
func (d GrantDecision) MarshalText() ([]byte, error) { return grantDecisionWire.marshal(d) }

// UnmarshalText reads a stable token back into a GrantDecision; an unknown token is a typed fault.
func (d *GrantDecision) UnmarshalText(token []byte) error {
	return grantDecisionWire.unmarshal(token, d)
}

// MarshalText renders the TurnOutcome as its stable token (encoding.TextMarshaler).
func (o TurnOutcome) MarshalText() ([]byte, error) { return turnOutcomeWire.marshal(o) }

// UnmarshalText reads a stable token back into a TurnOutcome; an unknown token is a typed fault.
func (o *TurnOutcome) UnmarshalText(token []byte) error { return turnOutcomeWire.unmarshal(token, o) }

// MarshalText renders the ErrorReason as its stable token (encoding.TextMarshaler).
func (r ErrorReason) MarshalText() ([]byte, error) { return errorReasonWire.marshal(r) }

// UnmarshalText reads a stable token back into an ErrorReason; an unknown token is a typed fault.
func (r *ErrorReason) UnmarshalText(token []byte) error { return errorReasonWire.unmarshal(token, r) }

// MarshalText renders the PermissionResolution as its stable token (encoding.TextMarshaler).
func (r PermissionResolution) MarshalText() ([]byte, error) { return resolutionWire.marshal(r) }

// UnmarshalText reads a stable token back into a PermissionResolution; an unknown token is a typed fault.
func (r *PermissionResolution) UnmarshalText(token []byte) error {
	return resolutionWire.unmarshal(token, r)
}
