package agentprofile_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// The DETERMINISM half of the contract. FileSet.Digest addresses a whole emission as
// "sha256:<hex>" over a canonical serialization: for each file, Path, then NUL, then the mode in
// OCTAL, then NUL, then the content LENGTH in decimal, then NUL, then the content bytes. NUL cannot
// occur in a path or a decimal length, so no content can forge a component boundary, and the
// length field is what makes the boundary unforgeable even when it could.
//
// The goldens below are HARDCODED. They were computed OUTSIDE this library, by transcribing the
// serialization above and hashing it, so they are an independent check rather than a photograph of
// whatever the code produced. There is deliberately NO -update flag: a golden a test can rewrite for
// itself agrees with every change and therefore checks nothing. Regenerating one is a manual,
// reviewed act, and a change to either value means the profileRef of every committed emission in the
// estate has moved — which is exactly the event that must not happen quietly.

// goldenTwoFileDigest is the digest of the two-file emission built by goldenTwoFileSet. The bytes it
// hashes are, verbatim:
//
//	"a.md" NUL "644" NUL "5" NUL "alpha" "b/c.md" NUL "600" NUL "0" NUL
//
// A change to this constant means one of: the hash algorithm, the prefix, the field order, the
// separator, or the octal/decimal rendering of a component. Every one of those is a wire-visible
// break for anything holding a profileRef.
const goldenTwoFileDigest = "sha256:53128d6c567529f2d8f2134e16d3048b8941408be45831761daf889f45046d73"

// goldenEmptyDigest is the digest of an EMPTY FileSet: the SHA-256 of zero bytes. Render refuses to
// return an empty emission, so this value can never address a real profile — pinning it is what
// proves that, if one ever escaped, it would carry the universally recognisable empty-input hash
// rather than something that looked like content.
const goldenEmptyDigest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

// goldenTwoFileSet is the fixture both digest goldens are written against: two files with different
// modes, one of them empty, so the mode field and the zero-length case are both inside the hash.
func goldenTwoFileSet() agentprofile.FileSet {
	return agentprofile.FileSet{
		{Path: "a.md", Content: []byte("alpha"), Mode: 0o644},
		{Path: "b/c.md", Content: []byte(""), Mode: 0o600},
	}
}

// TestDigest_MatchesThePinnedGolden asserts the content address of a known emission is exactly the
// pinned value. This is the cross-process, cross-host, cross-build stability claim: the same bytes
// address the same way forever, or a committed profileRef stops pointing at what it named.
func TestDigest_MatchesThePinnedGolden(t *testing.T) {
	t.Parallel()
	if got := goldenTwoFileSet().Digest(); got != goldenTwoFileDigest {
		t.Errorf("Digest() = %s\nwant the pinned golden %s\n(the canonical serialization or the algorithm moved; every committed profileRef in the estate now points at nothing)",
			got, goldenTwoFileDigest)
	}
	var empty agentprofile.FileSet
	if got := empty.Digest(); got != goldenEmptyDigest {
		t.Errorf("the empty FileSet's Digest() = %s, want %s", got, goldenEmptyDigest)
	}
}

// TestDigest_IsSelfDescribingAndWellFormed asserts the shape callers parse: the algorithm prefix,
// then exactly 64 lowercase hex characters. The prefix is what makes a future algorithm change a
// visible change rather than a silent reinterpretation of the same-looking hex.
func TestDigest_IsSelfDescribingAndWellFormed(t *testing.T) {
	t.Parallel()
	digest := goldenTwoFileSet().Digest()
	if !strings.HasPrefix(digest, "sha256:") {
		t.Fatalf("Digest() = %q, want the sha256: algorithm prefix", digest)
	}
	hexadecimal := strings.TrimPrefix(digest, "sha256:")
	if len(hexadecimal) != 64 {
		t.Errorf("Digest() carries %d hex characters, want 64", len(hexadecimal))
	}
	for i := range len(hexadecimal) {
		character := hexadecimal[i]
		isDigit := character >= '0' && character <= '9'
		isLowerHex := character >= 'a' && character <= 'f'
		if !isDigit && !isLowerHex {
			t.Fatalf("Digest() carries the non-lowercase-hex character %q at %d: %q", character, i, digest)
		}
	}
}

// TestDigest_DistinguishesEveryComponent asserts each component of the canonical serialization is
// actually IN the hash: a renamed file, a mode change, an edited byte and a reordering must every one
// produce a different address. A digest blind to any of them would let that class of drift pass a
// gate that compared only profileRefs.
func TestDigest_DistinguishesEveryComponent(t *testing.T) {
	t.Parallel()
	base := goldenTwoFileSet().Digest()

	renamed := goldenTwoFileSet()
	renamed[0].Path = "renamed.md"

	remoded := goldenTwoFileSet()
	remoded[0].Mode = 0o600

	edited := goldenTwoFileSet()
	edited[0].Content = []byte("alphb")

	lengthened := goldenTwoFileSet()
	lengthened[0].Content = []byte("alpha!")

	reordered := agentprofile.FileSet{goldenTwoFileSet()[1], goldenTwoFileSet()[0]}

	for name, variant := range map[string]agentprofile.FileSet{
		"a renamed file":            renamed,
		"a mode change":             remoded,
		"one edited byte":           edited,
		"one appended byte":         lengthened,
		"the same files reordered":  reordered,
		"a file removed altogether": goldenTwoFileSet()[:1],
	} {
		if got := variant.Digest(); got == base {
			t.Errorf("%s did not change the Digest (%s); that component is not inside the hash", name, got)
		}
	}
}

// TestDigest_ContentCannotForgeAComponentBoundary asserts the length field does the work the doc
// claims: two DIFFERENT emissions whose components would concatenate to the same bytes under a naive
// scheme must still address differently. Without the lengths, "ab" + "x" and "a" + "bx" collide, and
// a crafted file content could impersonate a second file.
func TestDigest_ContentCannotForgeAComponentBoundary(t *testing.T) {
	t.Parallel()
	left := agentprofile.FileSet{{Path: "ab", Content: []byte("x"), Mode: 0o644}}
	right := agentprofile.FileSet{{Path: "a", Content: []byte("bx"), Mode: 0o644}}
	if left.Digest() == right.Digest() {
		t.Errorf("two distinct emissions collide on %s; a component boundary can be forged from content", left.Digest())
	}

	// The sharper case: content that CONTAINS the NUL separator must not be able to fabricate a
	// second component, because the length is read before the bytes are.
	withSeparator := agentprofile.FileSet{{Path: "a", Content: []byte("x\x00644\x001\x00y"), Mode: 0o644}}
	twoFiles := agentprofile.FileSet{
		{Path: "a", Content: []byte("x"), Mode: 0o644},
		{Path: "644", Content: []byte("y"), Mode: 0o644},
	}
	if withSeparator.Digest() == twoFiles.Digest() {
		t.Errorf("a NUL inside a file's content forged a component boundary; both addressed as %s", withSeparator.Digest())
	}
}

// TestRender_IsByteIdenticalAcrossRepeatedCalls is the library's central promise, asserted directly
// on the production ClaudeRenderer: the same document and the same Target render byte-identical
// output, so a committed emission's expectation never moves under it. Ten renders, one expectation.
func TestRender_IsByteIdenticalAcrossRepeatedCalls(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	first := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	if len(first) == 0 {
		t.Fatal("Render returned an empty emission")
	}
	want := first.Digest()
	for attempt := 1; attempt < 10; attempt++ {
		again := renderCanonicalCell(t, document, agentprofiletest.NewTree())
		if len(again) != len(first) {
			t.Fatalf("render %d emitted %d file(s), want %d", attempt, len(again), len(first))
		}
		for i := range first {
			if again[i].Path != first[i].Path {
				t.Fatalf("render %d file %d Path = %q, want %q", attempt, i, again[i].Path, first[i].Path)
			}
			if string(again[i].Content) != string(first[i].Content) {
				t.Fatalf("render %d file %d (%s) content drifted:\n got: %q\nwant: %q",
					attempt, i, first[i].Path, again[i].Content, first[i].Content)
			}
			if again[i].Mode != first[i].Mode {
				t.Fatalf("render %d file %d (%s) Mode = %v, want %v", attempt, i, first[i].Path, again[i].Mode, first[i].Mode)
			}
		}
		if got := again.Digest(); got != want {
			t.Fatalf("render %d addressed as %s, want %s", attempt, got, want)
		}
	}
}

// TestRender_DocumentOrderNeverReachesTheEmission asserts the composition is sorted by fragment NAME,
// so precedence decides WHICH fragment wins and never WHERE it lands. Two documents that list the
// identical fragments in opposite order must render byte-identically. This is the assertion that
// catches an accidental reordering: an implementation that leaked the document's listing order — or
// a Go map's iteration order — into the emission fails it.
func TestRender_DocumentOrderNeverReachesTheEmission(t *testing.T) {
	t.Parallel()
	const forward = `{"schemaVersion":1,"defaults":{"instruction":"i","rules":[` +
		`{"name":"alpha","body":"A"},{"name":"beta","body":"B"},{"name":"gamma","body":"C"}` +
		`],"skills":[{"name":"one","body":"1"},{"name":"two","body":"2"}]},` +
		`"roles":{"reviewer":{"harnesses":["claude-code"]}}}`
	const backward = `{"schemaVersion":1,"defaults":{"instruction":"i","rules":[` +
		`{"name":"gamma","body":"C"},{"name":"beta","body":"B"},{"name":"alpha","body":"A"}` +
		`],"skills":[{"name":"two","body":"2"},{"name":"one","body":"1"}]},` +
		`"roles":{"reviewer":{"harnesses":["claude-code"]}}}`

	forwardFiles := renderDocument(t, []byte(forward), "")
	backwardFiles := renderDocument(t, []byte(backward), "")

	if forwardFiles.Digest() != backwardFiles.Digest() {
		t.Fatalf("reordering the document's fragment arrays changed the emission: %s vs %s\nforward: %s\nbackward: %s",
			forwardFiles.Digest(), backwardFiles.Digest(), pathsOf(forwardFiles), pathsOf(backwardFiles))
	}
	// And the emitted order is the NAME order, not either document's order.
	wantRuleOrder := []string{"alpha", "beta", "gamma"}
	emitted := make([]string, 0, len(wantRuleOrder))
	for i := range forwardFiles {
		if name, isRule := ruleNameOf(forwardFiles[i].Path); isRule {
			emitted = append(emitted, name)
		}
	}
	if len(emitted) != len(wantRuleOrder) {
		t.Fatalf("emitted %d rule file(s) (%q), want %d", len(emitted), emitted, len(wantRuleOrder))
	}
	for i := range wantRuleOrder {
		if !strings.Contains(emitted[i], wantRuleOrder[i]) {
			t.Errorf("rule %d emitted as %q, want it to be %q — composition is sorted by name", i, emitted[i], wantRuleOrder[i])
		}
	}
}

// TestRender_PrecedenceIsTotalAndReplaces asserts the documented chain — defaults < role < overlay —
// resolves to exactly ONE winner per fragment name, with the losing bodies ABSENT. Replace, never
// merge, and never append: a merged emission would carry two conflicting versions of one rule, which
// is worse than either.
func TestRender_PrecedenceIsTotalAndReplaces(t *testing.T) {
	t.Parallel()
	const document = `{"schemaVersion":1,` +
		`"defaults":{"instruction":"DEFAULTS-INSTRUCTION","rules":[{"name":"shared","body":"DEFAULTS-BODY"},{"name":"only-defaults","body":"ONLY-DEFAULTS"}]},` +
		`"roles":{"reviewer":{"instruction":"ROLE-INSTRUCTION","harnesses":["claude-code"],"rules":[{"name":"shared","body":"ROLE-BODY"}]}},` +
		`"overlays":{"eden":{"rules":[{"name":"shared","body":"OVERLAY-BODY"}]}}}`

	cases := []struct {
		name       string
		repository string
		wantWinner string
		wantGone   []string
	}{
		{"BaseMatrixTakesTheRole", "", "ROLE-BODY", []string{"DEFAULTS-BODY", "OVERLAY-BODY"}},
		{"OverlayOutranksTheRole", "eden", "OVERLAY-BODY", []string{"DEFAULTS-BODY", "ROLE-BODY"}},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			files := renderDocument(t, []byte(document), testCase.repository)
			emitted := concatEmission(files)
			if !strings.Contains(emitted, testCase.wantWinner) {
				t.Errorf("the winning body %q is absent from the emission", testCase.wantWinner)
			}
			for _, gone := range testCase.wantGone {
				if strings.Contains(emitted, gone) {
					t.Errorf("the losing body %q survived; a higher layer must REPLACE a same-named fragment, never merge with it", gone)
				}
			}
			// A layer that declares nothing overrides nothing: the defaults-only rule and the role's
			// instruction both survive at every layer.
			if !strings.Contains(emitted, "ONLY-DEFAULTS") {
				t.Error("the defaults-only rule was dropped; a higher layer overrides only the names it declares")
			}
			if !strings.Contains(emitted, "ROLE-INSTRUCTION") || strings.Contains(emitted, "DEFAULTS-INSTRUCTION") {
				t.Error("the instruction did not follow the precedence chain: the highest layer declaring a non-empty one wins")
			}
			// Exactly ONE file carries the shared rule — precedence resolves, it does not accumulate.
			if got := countRuleFiles(files, "shared"); got != 1 {
				t.Errorf("%d emitted file(s) carry the rule %q, want exactly 1", got, "shared")
			}
		})
	}
}

// ruleNameOf extracts the fragment name from an emitted rule path, and reports whether the path is a
// rule file at all. It tolerates an ordering prefix so the assertion survives the NN- prefix landing.
func ruleNameOf(path string) (string, bool) {
	const marker = "/.claude/rules/"
	index := strings.Index(path, marker)
	if index < 0 {
		return "", false
	}
	return strings.TrimSuffix(path[index+len(marker):], ".md"), true
}

// countRuleFiles counts the emitted rule files whose name contains fragment.
func countRuleFiles(files agentprofile.FileSet, fragment string) int {
	count := 0
	for i := range files {
		if name, isRule := ruleNameOf(files[i].Path); isRule && strings.Contains(name, fragment) {
			count++
		}
	}
	return count
}

// concatEmission joins every emitted file's bytes into one haystack for presence/absence assertions.
func concatEmission(files agentprofile.FileSet) string {
	var joined strings.Builder
	for i := range files {
		joined.Write(files[i].Content)
		joined.WriteByte('\n')
	}
	return joined.String()
}
