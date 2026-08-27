package agentprofiletest

import (
	"encoding/json"

	"github.com/gophersys/libs/go/agentprofile"
)

// The wire shapes below mirror the profile document's JSON exactly. The library keeps its own
// parsed shape unexported (the document's public surface is its JSON), so the suite writes the JSON
// it means rather than reaching for an internal type — which is also what makes an accidental schema
// change visible here as a parse failure instead of hiding behind a shared struct.
type wireFragment struct {
	Name string `json:"name"`
	Body string `json:"body"`
}

// wireLayer is one contributor to a cell: the defaults or a repository overlay.
type wireLayer struct {
	Instruction string         `json:"instruction,omitempty"`
	Rules       []wireFragment `json:"rules,omitempty"`
	Skills      []wireFragment `json:"skills,omitempty"`
}

// wireRole is one row of the matrix: a layer plus the harnesses that row may be rendered for. The
// layer's fields are spelled out rather than embedded so the emitted JSON key set is explicit — the
// parser refuses unknown fields, so a stray key is a hard failure, not a silent omission.
type wireRole struct {
	Instruction string                 `json:"instruction,omitempty"`
	Rules       []wireFragment         `json:"rules,omitempty"`
	Skills      []wireFragment         `json:"skills,omitempty"`
	Harnesses   []agentprofile.Harness `json:"harnesses"`
}

// wireDocument is the whole profile document.
type wireDocument struct {
	SchemaVersion int                  `json:"schemaVersion"`
	Defaults      wireLayer            `json:"defaults"`
	Roles         map[string]wireRole  `json:"roles"`
	Overlays      map[string]wireLayer `json:"overlays"`
}

// CanonicalDocument is the conformance profile document, declaring CanonicalRole for the given
// harnesses and exercising the FULL precedence chain: a fragment named "precedence" is declared at
// all three layers with a different body each, an instruction at two, and a skill at two. It is
// exported so a binding outside this package builds the same fixture the suite does, rather than
// hand-rolling a document whose drift from this one would be invisible.
func CanonicalDocument(harnesses ...agentprofile.Harness) []byte {
	return marshalDocument(buildDocument(sharedRuleBody, false, harnesses...))
}

// canonicalDocument is the package-internal spelling the suite bodies use.
func canonicalDocument(harnesses ...agentprofile.Harness) []byte {
	return CanonicalDocument(harnesses...)
}

// variedDocument is canonicalDocument with exactly ONE fragment body changed. Everything else — the
// key set, the names, the harnesses — is identical, so a Digest that fails to distinguish the two
// is failing on content and nothing else.
func variedDocument(harnesses ...agentprofile.Harness) []byte {
	return marshalDocument(buildDocument(variedRuleBody, false, harnesses...))
}

// shuffledDocument is canonicalDocument with every fragment ARRAY reversed. It carries the identical
// fragment set, so the composition — which sorts by name — must produce a byte-identical emission.
// A renderer or a composer that leaked the document's listing order into the output fails on it.
func shuffledDocument(harnesses ...agentprofile.Harness) []byte {
	return marshalDocument(buildDocument(sharedRuleBody, true, harnesses...))
}

// buildDocument assembles the conformance document. failLoudlyBody is the one body the varied
// variant changes; reversed flips every fragment array so the order-independence property has a
// counterpart to compare against.
func buildDocument(failLoudlyBody string, reversed bool, harnesses ...agentprofile.Harness) wireDocument {
	defaults := wireLayer{
		Instruction: defaultsInstruction,
		Rules: reverseIf(reversed, []wireFragment{
			{Name: "precedence", Body: defaultsPrecedenceBody},
			{Name: "fail-loudly", Body: failLoudlyBody},
		}),
		Skills: []wireFragment{{Name: "deep-research", Body: defaultsSkillBody}},
	}
	role := wireRole{
		Instruction: roleInstruction,
		Rules:       []wireFragment{{Name: "precedence", Body: rolePrecedenceBody}},
		Harnesses:   harnesses,
	}
	overlay := wireLayer{
		Rules:  []wireFragment{{Name: "precedence", Body: overlayPrecedenceBody}},
		Skills: []wireFragment{{Name: "deep-research", Body: overlaySkillBody}},
	}
	return wireDocument{
		SchemaVersion: 1,
		Defaults:      defaults,
		Roles:         map[string]wireRole{string(CanonicalRole): role},
		Overlays:      map[string]wireLayer{CanonicalOverlay: overlay},
	}
}

// reverseIf returns fragments reversed when reversed is true, and unchanged otherwise. It copies, so
// the caller's slice is never mutated.
func reverseIf(reversed bool, fragments []wireFragment) []wireFragment {
	if !reversed {
		return fragments
	}
	flipped := make([]wireFragment, len(fragments))
	for i := range fragments {
		flipped[len(fragments)-1-i] = fragments[i]
	}
	return flipped
}

// marshalDocument renders the document to JSON. encoding/json sorts map keys, so the bytes are
// deterministic. A marshal failure here is impossible for these fixed shapes; it is turned into a
// clear panic rather than an error return, because a suite that could not build its own fixture has
// nothing meaningful to report.
func marshalDocument(document wireDocument) []byte {
	raw, err := json.Marshal(document)
	if err != nil {
		panic("agentprofiletest: the conformance document is not marshalable: " + err.Error())
	}
	return raw
}
