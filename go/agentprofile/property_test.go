package agentprofile_test

import (
	"encoding/json"
	"strings"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
	"github.com/gophersys/libs/go/errors"
)

// ADR-0020 dimension (a). The `property` ctl.sh verb sets RAPID_CHECKS in the environment (1000
// iterations per property; rapid reads it directly) and runs the whole suite under -race, so rapid's
// shrinking still observes data races.
//
// These properties state the library's guarantees over the whole INPUT SPACE rather than over a
// fixture. Determinism, digest sensitivity, order-independence and precedence-totality are exactly
// the claims a single hand-picked document cannot establish: a fixture proves the code works on that
// document, and the whole point of the contract is that it works on every document.

// layerNames is the fixed pool the precedence property draws its fragment names from. The names are
// EQUAL-LENGTH and mutually non-prefixing, so a substring search for one layer's body can never
// accidentally match another's.
//
//nolint:gochecknoglobals // a generator's fixed draw pool; package-level so every property shares one.
var layerNames = []string{"aa", "bb", "cc", "dd"}

// drawSlug draws an HNS-1 slug (rule 11): one to three words of [a-z][a-z0-9]*, hyphen-joined.
func drawSlug(rt *rapid.T, label string) string {
	words := rapid.SliceOfN(rapid.StringMatching(`[a-z][a-z0-9]{0,4}`), 1, 3).Draw(rt, label)
	return strings.Join(words, "-")
}

// drawFragments draws a set of uniquely-named fragments with non-empty bodies — the shape the
// validator admits, so a generated document exercises the render path rather than the reject path.
func drawFragments(rt *rapid.T, label string) []wireFragment {
	count := rapid.IntRange(0, 4).Draw(rt, label+"-count")
	seen := make(map[string]bool, count)
	fragments := make([]wireFragment, 0, count)
	for i := range count {
		name := drawSlug(rt, label+"-name")
		if seen[name] {
			continue
		}
		seen[name] = true
		body := rapid.StringMatching(`[A-Za-z0-9 .]{1,24}`).Draw(rt, label+"-body")
		fragments = append(fragments, wireFragment{Name: name, Body: body + "-" + name + "-" + itoa(i)})
	}
	return fragments
}

// drawDocument draws a well-formed, renderable profile document for the claude-code harness.
func drawDocument(rt *rapid.T) wireDocument {
	return wireDocument{
		SchemaVersion: 1,
		Defaults: wireLayer{
			Instruction: rapid.StringMatching(`[A-Za-z ]{1,20}`).Draw(rt, "defaults-instruction"),
			Rules:       drawFragments(rt, "defaults-rules"),
			Skills:      drawFragments(rt, "defaults-skills"),
		},
		Roles: map[string]wireRole{
			"reviewer": {
				Instruction: rapid.StringMatching(`[A-Za-z ]{1,20}`).Draw(rt, "role-instruction"),
				Rules:       drawFragments(rt, "role-rules"),
				Skills:      drawFragments(rt, "role-skills"),
				Harnesses:   []agentprofile.Harness{agentprofile.HarnessClaudeCode},
			},
		},
	}
}

// TestProperty_RenderIsDeterministic asserts the central guarantee over the whole document space:
// for ANY well-formed document, two renders of one cell are byte-identical and address identically.
// A fixture proves it for one document; this proves it for the space.
func TestProperty_RenderIsDeterministic(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		document := marshalWire(rt, drawDocument(rt))
		first := renderForProperty(rt, document, "")
		second := renderForProperty(rt, document, "")
		if len(first) != len(second) {
			rt.Fatalf("two renders emitted %d and %d file(s)", len(first), len(second))
		}
		for i := range first {
			if first[i].Path != second[i].Path || string(first[i].Content) != string(second[i].Content) || first[i].Mode != second[i].Mode {
				rt.Fatalf("render drifted at file %d: %q/%q vs %q/%q", i, first[i].Path, first[i].Content, second[i].Path, second[i].Content)
			}
		}
		if first.Digest() != second.Digest() {
			rt.Fatalf("Digest drifted: %s then %s", first.Digest(), second.Digest())
		}
	})
}

// TestProperty_EmissionInvariantsHoldForAnyDocument asserts the guards the library enforces on every
// emission hold for ANY document: at least one file, strictly ascending unique paths, every path
// repository-relative and free of a traversal element, and every mode non-zero.
func TestProperty_EmissionInvariantsHoldForAnyDocument(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		files := renderForProperty(rt, marshalWire(rt, drawDocument(rt)), "")
		if len(files) == 0 {
			rt.Fatal("an empty emission escaped the guard")
		}
		for i := range files {
			path := files[i].Path
			if i > 0 && path <= files[i-1].Path {
				rt.Fatalf("emission is not strictly ascending at %d: %q follows %q", i, path, files[i-1].Path)
			}
			if path == "" || strings.HasPrefix(path, "/") || strings.Contains(path, `\`) {
				rt.Fatalf("emitted path %q is not repository-relative and slash-separated", path)
			}
			for _, element := range strings.Split(path, "/") {
				if element == "" || element == "." || element == ".." {
					rt.Fatalf("emitted path %q carries the unusable element %q", path, element)
				}
			}
			if files[i].Mode == 0 {
				rt.Fatalf("emitted file %q carries a zero Mode", path)
			}
		}
	})
}

// TestProperty_DocumentOrderNeverReachesTheEmission asserts order-independence over the space: for
// ANY document, reversing every fragment array renders the IDENTICAL bytes. Composition is sorted by
// name, so precedence decides WHICH fragment wins and never WHERE it lands — and a Go map's
// iteration order can never leak into a committed artifact.
func TestProperty_DocumentOrderNeverReachesTheEmission(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		document := drawDocument(rt)
		forward := renderForProperty(rt, marshalWire(rt, document), "")

		reversed := document
		reversed.Defaults.Rules = reverseFragments(document.Defaults.Rules)
		reversed.Defaults.Skills = reverseFragments(document.Defaults.Skills)
		role := document.Roles["reviewer"]
		role.Rules = reverseFragments(role.Rules)
		role.Skills = reverseFragments(role.Skills)
		reversed.Roles = map[string]wireRole{"reviewer": role}

		backward := renderForProperty(rt, marshalWire(rt, reversed), "")
		if forward.Digest() != backward.Digest() {
			rt.Fatalf("reversing every fragment array changed the emission: %s vs %s", forward.Digest(), backward.Digest())
		}
	})
}

// TestProperty_DigestChangesWhenAnyBodyChanges asserts digest sensitivity over the space: append one
// byte to ANY drawn fragment body and the address must move. A digest that survived a content change
// would let a drifted profile address as an unchanged one, which is the failure a content address
// exists to make impossible.
func TestProperty_DigestChangesWhenAnyBodyChanges(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// The edited rule is seeded at the ROLE layer under a name drawSlug can never produce (its
		// words are at most five characters, so "property" is unreachable) and no drawn rule can
		// shadow it. Editing a fragment a HIGHER layer replaces would be invisible in the emission by
		// design, and asserting otherwise would contradict the precedence contract rather than test it.
		const seededName = "zzz-property-seed"
		const seededBody = "the property-seeded rule body"

		document := drawDocument(rt)
		role := document.Roles["reviewer"]
		role.Rules = append(append([]wireFragment(nil), role.Rules...), wireFragment{Name: seededName, Body: seededBody})
		document.Roles = map[string]wireRole{"reviewer": role}
		base := renderForProperty(rt, marshalWire(rt, document), "")

		editedRole := role
		editedRules := append([]wireFragment(nil), role.Rules...)
		editedRules[len(editedRules)-1].Body = seededBody + "!"
		editedRole.Rules = editedRules
		edited := document
		edited.Roles = map[string]wireRole{"reviewer": editedRole}

		changed := renderForProperty(rt, marshalWire(rt, edited), "")
		if base.Digest() == changed.Digest() {
			rt.Fatalf("appending a byte to the winning rule %q left the Digest at %s", seededName, base.Digest())
		}
	})
}

// TestProperty_PrecedenceIsTotal asserts precedence is a TOTAL order over the layers: for any
// assignment of a fixed name pool across defaults, role and overlay, the emitted body for each name
// is EXACTLY the highest declaring layer's, and no lower layer's body survives anywhere. Totality is
// what makes the composition well-defined — a partial order would leave a pair whose winner depended
// on an accident of iteration.
func TestProperty_PrecedenceIsTotal(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		declared := make([][]bool, 3)
		for layer := range declared {
			declared[layer] = make([]bool, len(layerNames))
			for name := range layerNames {
				declared[layer][name] = rapid.Bool().Draw(rt, "declared")
			}
		}
		document := wireDocument{
			SchemaVersion: 1,
			Defaults:      wireLayer{Instruction: "i", Rules: fragmentsFor(0, declared[0])},
			Roles: map[string]wireRole{"reviewer": {
				Rules:     fragmentsFor(1, declared[1]),
				Harnesses: []agentprofile.Harness{agentprofile.HarnessClaudeCode},
			}},
			Overlays: map[string]wireLayer{"eden": {Rules: fragmentsFor(2, declared[2])}},
		}

		emitted := concatEmission(renderForProperty(rt, marshalWire(rt, document), "eden"))
		for name := range layerNames {
			winner := -1
			for layer := range declared {
				if declared[layer][name] {
					winner = layer
				}
			}
			for layer := range declared {
				body := bodyFor(layer, name)
				present := strings.Contains(emitted, body)
				if layer == winner && !present {
					rt.Fatalf("layer %d declares %q and is the highest to do so, but its body %q is absent", layer, layerNames[name], body)
				}
				if layer != winner && present {
					rt.Fatalf("layer %d's body %q survived though layer %d won %q; a higher layer must REPLACE, never merge", layer, body, winner, layerNames[name])
				}
			}
		}
	})
}

// TestProperty_SlugGrammarAcceptsExactlyTheHNS1Language asserts the role-name gate accepts every
// generated HNS-1 slug and rejects any string carrying a character the grammar does not admit. The
// grammar is also the traversal guard — it admits no dot, no slash and no separator — so a hole in it
// would be a hole in the write path, not merely a naming inconsistency.
func TestProperty_SlugGrammarAcceptsExactlyTheHNS1Language(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		valid := drawSlug(rt, "valid-role")
		if _, err := newOverDocument(documentNamingRole(valid)); err != nil {
			rt.Fatalf("the HNS-1 slug %q was rejected as a role name: %v", valid, err)
		}

		// Splice in one character the grammar cannot admit, at a drawn position.
		intruder := rapid.SampledFrom([]string{"A", "_", ".", "/", " ", "Z", "\\"}).Draw(rt, "intruder")
		position := rapid.IntRange(0, len(valid)).Draw(rt, "position")
		invalid := valid[:position] + intruder + valid[position:]
		_, err := newOverDocument(documentNamingRole(invalid))
		if err == nil {
			rt.Fatalf("the non-slug role name %q was accepted", invalid)
		}
		if errors.KindOf(err) != errors.KindInvalid {
			rt.Fatalf("the non-slug role name %q yielded kind %v, want KindInvalid", invalid, errors.KindOf(err))
		}
	})
}

// ── generators and helpers ──────────────────────────────────────────────────────────────────────

// wireFragment, wireLayer, wireRole and wireDocument mirror the profile document's JSON. The library
// keeps its parsed shape unexported, so a black-box property test writes the JSON it means.
type wireFragment struct {
	Name string `json:"name"`
	Body string `json:"body"`
}

// wireLayer is one contributor to a cell.
type wireLayer struct {
	Instruction string         `json:"instruction,omitempty"`
	Rules       []wireFragment `json:"rules,omitempty"`
	Skills      []wireFragment `json:"skills,omitempty"`
}

// wireRole is one row of the matrix.
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
	Overlays      map[string]wireLayer `json:"overlays,omitempty"`
}

// marshalWire renders a drawn document to JSON, failing the property on an impossible marshal error.
func marshalWire(rt *rapid.T, document wireDocument) []byte {
	raw, err := json.Marshal(document)
	if err != nil {
		rt.Fatalf("marshalling the drawn document: %v", err)
	}
	return raw
}

// renderForProperty renders the reviewer/claude-code cell through the real ClaudeRenderer, failing
// the property on any construction or render error — a drawn document is well-formed by
// construction, so an error here is a real falsification, not a bad draw.
func renderForProperty(rt *rapid.T, document []byte, repository string) agentprofile.FileSet {
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: document, Repository: repository},
		agentprofile.Deps{
			Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}},
			Tree:      agentprofiletest.NewTree(),
		},
	)
	if err != nil {
		rt.Fatalf("New over a well-formed drawn document: %v (document: %s)", err, document)
	}
	files, err := compiler.Render(rt.Context(), agentprofile.Target{
		Role: "reviewer", Harness: agentprofile.HarnessClaudeCode,
	})
	if err != nil {
		rt.Fatalf("Render over a well-formed drawn document: %v (document: %s)", err, document)
	}
	return files
}

// fragmentsFor builds the fragments one layer declares, given which names it declares.
func fragmentsFor(layer int, declared []bool) []wireFragment {
	fragments := make([]wireFragment, 0, len(declared))
	for name := range declared {
		if declared[name] {
			fragments = append(fragments, wireFragment{Name: layerNames[name], Body: bodyFor(layer, name)})
		}
	}
	return fragments
}

// bodyFor is the unique, mutually non-substring body layer `layer` gives name `name`.
func bodyFor(layer, name int) string {
	return "LAYER" + itoa(layer) + "-NAME-" + layerNames[name] + "-END"
}

// reverseFragments returns a reversed copy.
func reverseFragments(fragments []wireFragment) []wireFragment {
	flipped := make([]wireFragment, len(fragments))
	for i := range fragments {
		flipped[len(fragments)-1-i] = fragments[i]
	}
	return flipped
}

// itoa renders a small non-negative int without pulling strconv into the generator's hot path.
func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	digits := ""
	for n > 0 {
		digits = string(rune('0'+n%10)) + digits
		n /= 10
	}
	return digits
}
