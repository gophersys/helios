package agentprofiletest

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/errors"
)

// CanonicalRole is the one role the conformance document declares. It is a fixed HNS-1 slug so a
// binding can name the emission subtree it expects without re-deriving it.
const CanonicalRole agentprofile.Role = "reviewer"

// CanonicalOverlay is the repository overlay the conformance document declares and the suite
// selects, so every property is proven with the FULL precedence chain applied (defaults < role <
// overlay) rather than only the base matrix.
const CanonicalOverlay = "eden"

// The fragment bodies the precedence property discriminates on. Each layer declares a fragment named
// "precedence" with a DIFFERENT body, so the composed emission proves which layer won and — because
// the losing bodies must be absent — proves the higher layer REPLACED the lower one rather than
// merging with it.
const (
	defaultsPrecedenceBody = "the defaults precedence body"
	rolePrecedenceBody     = "the role precedence body"
	overlayPrecedenceBody  = "the overlay precedence body"

	defaultsInstruction = "the defaults instruction"
	roleInstruction     = "the role instruction"

	defaultsSkillBody = "the defaults deep research body"
	overlaySkillBody  = "the overlay deep research body"

	sharedRuleBody = "the shared fail loudly body"
	variedRuleBody = "the VARIED fail loudly body"
)

// TreeFactory builds a read-only agentprofile.Tree that holds EXACTLY the committed file set — the
// seam that lets one suite run over an in-memory Tree and over a real directory on the host
// filesystem without the suite knowing which. A nil or empty set means an empty tree.
type TreeFactory func(committed agentprofile.FileSet) (agentprofile.Tree, error)

// RunRendererSuite asserts the agentprofile Renderer port contract, and the Compiler behaviour that
// rides on it, against a freshly-constructed Renderer. It is the ONE entry point every binding is
// proven through — the in-memory fake, the real ClaudeRenderer, and the real-filesystem integration
// arm all run these same cases, which is what makes substitutability EXECUTED rather than asserted.
//
// newRenderer returns a Renderer claiming the harness the suite renders for; the suite reads
// Harness() to build its own Target, so a binding cannot mis-wire the cell. newTree builds the
// committed tree the drift properties compare against.
//
// Each property is a self-contained parallel subtest that constructs its own Compiler, so the cases
// are independent and share no mutable state.
//
//nolint:thelper // RunRendererSuite IS the suite entrypoint; subtests carry t directly.
func RunRendererSuite(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Run("RenderIsDeterministic", func(t *testing.T) {
		t.Parallel()
		assertRenderIsDeterministic(t, newRenderer, newTree)
	})
	t.Run("EmissionIsNeverEmpty", func(t *testing.T) {
		t.Parallel()
		assertEmissionIsNeverEmpty(t, newRenderer, newTree)
	})
	t.Run("EmissionPathsAreSortedUniqueAndRelative", func(t *testing.T) {
		t.Parallel()
		assertEmissionPathsAreSortedUniqueAndRelative(t, newRenderer, newTree)
	})
	t.Run("DigestIsStableAcrossCompilers", func(t *testing.T) {
		t.Parallel()
		assertDigestIsStableAcrossCompilers(t, newRenderer, newTree)
	})
	t.Run("DigestChangesWithContent", func(t *testing.T) {
		t.Parallel()
		assertDigestChangesWithContent(t, newRenderer, newTree)
	})
	t.Run("PrecedenceReplacesAndIsDocumentOrderIndependent", func(t *testing.T) {
		t.Parallel()
		assertPrecedenceReplaces(t, newRenderer, newTree)
	})
	t.Run("UnknownRoleIsNotFound", func(t *testing.T) {
		t.Parallel()
		assertUnknownRoleIsNotFound(t, newRenderer, newTree)
	})
	t.Run("UnclaimedHarnessIsNotFound", func(t *testing.T) {
		t.Parallel()
		assertUnclaimedHarnessIsNotFound(t, newRenderer, newTree)
	})
	t.Run("DriftReportsMissingOnAnEmptyTree", func(t *testing.T) {
		t.Parallel()
		assertDriftReportsMissing(t, newRenderer, newTree)
	})
	t.Run("DriftIsCleanWhenTheTreeHoldsTheRender", func(t *testing.T) {
		t.Parallel()
		assertDriftIsCleanOnAMatchingTree(t, newRenderer, newTree)
	})
	t.Run("DriftReportsContentDiffersAfterAnEdit", func(t *testing.T) {
		t.Parallel()
		assertDriftReportsContentDiffers(t, newRenderer, newTree)
	})
}

// AssertLoudlyUnbuilt is the suite arm for a DECLARED-BUT-UNBUILT harness renderer. It asserts the
// failure is LOUD in exactly the way the library exists to guarantee: an error, typed as
// NotImplementedError and naming the harness in its Harness field, classified KindInternal — and
// NEVER an empty FileSet, because a silent nothing would let a drift check pass over a profile that
// was never written.
func AssertLoudlyUnbuilt(t *testing.T, renderer agentprofile.Renderer) {
	t.Helper()

	harness := renderer.Harness()
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: canonicalDocument(harness), Repository: CanonicalOverlay},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{renderer}, Tree: NewTree()},
	)
	if err != nil {
		t.Fatalf("New for the unbuilt %s renderer: %v", harness, err)
	}

	files, err := compiler.Render(context.Background(), agentprofile.Target{Role: CanonicalRole, Harness: harness})
	if err == nil {
		t.Fatalf("Render for the unbuilt harness %s returned nil error with %d file(s) — a silent nothing is the failure this library prevents", harness, len(files))
	}
	if files != nil {
		t.Errorf("Render for the unbuilt harness %s returned a non-nil FileSet (%d file(s)) alongside its error; it must emit nothing", harness, len(files))
	}
	if kind := errors.KindOf(err); kind != errors.KindInternal {
		t.Errorf("Render for the unbuilt harness %s: KindOf = %v, want KindInternal (an unbuilt renderer is our gap, not the caller's bad input)", harness, kind)
	}
	unbuilt, matched := errors.AsType[agentprofile.NotImplementedError](err)
	if !matched {
		t.Fatalf("Render for the unbuilt harness %s: error does not unwrap to NotImplementedError: %v", harness, err)
	}
	if unbuilt.Harness != harness {
		t.Errorf("NotImplementedError.Harness = %q, want %q — the typed cause must name WHICH renderer is unbuilt", unbuilt.Harness, harness)
	}
}

// compileCanonical builds a Compiler over the canonical document for the renderer's own harness,
// with the overlay selected, and the tree the factory produces from committed.
func compileCanonical(
	t *testing.T,
	newRenderer func() agentprofile.Renderer,
	newTree TreeFactory,
	document []byte,
	committed agentprofile.FileSet,
) (*agentprofile.Compiler, agentprofile.Target) {
	t.Helper()
	renderer := newRenderer()
	tree, err := newTree(committed)
	if err != nil {
		t.Fatalf("TreeFactory: %v", err)
	}
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: document, Repository: CanonicalOverlay},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{renderer}, Tree: tree},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return compiler, agentprofile.Target{Role: CanonicalRole, Harness: renderer.Harness()}
}

// renderCanonical builds a Compiler over document and renders the canonical cell, failing on error.
func renderCanonical(
	t *testing.T,
	newRenderer func() agentprofile.Renderer,
	newTree TreeFactory,
	document []byte,
) agentprofile.FileSet {
	t.Helper()
	compiler, target := compileCanonical(t, newRenderer, newTree, document, nil)
	files, err := compiler.Render(context.Background(), target)
	if err != nil {
		t.Fatalf("Render(%v): %v", target, err)
	}
	return files
}

// assertRenderIsDeterministic: two Renders through ONE Compiler produce byte-identical FileSets and
// equal Digests. This is the library's central guarantee — a committed emission whose expectation
// moved between runs would make the drift check meaningless.
func assertRenderIsDeterministic(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	compiler, target := compileCanonical(t, newRenderer, newTree, canonicalDocument(harness), nil)
	ctx := context.Background()

	first, err := compiler.Render(ctx, target)
	if err != nil {
		t.Fatalf("first Render: %v", err)
	}
	second, err := compiler.Render(ctx, target)
	if err != nil {
		t.Fatalf("second Render: %v", err)
	}
	assertFileSetsEqual(t, "second Render", first, second)
	if first.Digest() != second.Digest() {
		t.Errorf("Digest drifted between two Renders of one input: %s then %s", first.Digest(), second.Digest())
	}
}

// assertEmissionIsNeverEmpty: a successful Render yields at least one file. An empty emission would
// make the drift check vacuous, so the library refuses it rather than returning it.
func assertEmissionIsNeverEmpty(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	files := renderCanonical(t, newRenderer, newTree, canonicalDocument(newRenderer().Harness()))
	if len(files) == 0 {
		t.Fatal("Render returned an empty FileSet with a nil error — a vacuous drift check")
	}
}

// assertEmissionPathsAreSortedUniqueAndRelative: paths come back STRICTLY ascending (so sorted and
// duplicate-free in one assertion) and every one is writable under a repository root.
func assertEmissionPathsAreSortedUniqueAndRelative(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	files := renderCanonical(t, newRenderer, newTree, canonicalDocument(newRenderer().Harness()))
	for i := range files {
		path := files[i].Path
		if i > 0 && path <= files[i-1].Path {
			t.Errorf("emission is not strictly ascending by Path at index %d: %q follows %q", i, path, files[i-1].Path)
		}
		if path == "" || strings.HasPrefix(path, "/") || strings.Contains(path, `\`) {
			t.Errorf("emitted path %q is not a repository-relative, slash-separated contract string", path)
		}
		for _, element := range strings.Split(path, "/") {
			if element == "" || element == "." || element == ".." {
				t.Errorf("emitted path %q carries the unusable element %q", path, element)
			}
		}
		if files[i].Mode == 0 {
			t.Errorf("emitted file %q carries a zero Mode; a consumer would write it unreadable", path)
		}
	}
}

// assertDigestIsStableAcrossCompilers: two INDEPENDENTLY constructed Compilers over the same
// document bytes produce the same Digest. That is the process-run stability the profileRef depends
// on — a digest that varied per Compiler would address nothing.
func assertDigestIsStableAcrossCompilers(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	document := canonicalDocument(newRenderer().Harness())
	first := renderCanonical(t, newRenderer, newTree, document)
	second := renderCanonical(t, newRenderer, newTree, document)
	assertFileSetsEqual(t, "an independently constructed Compiler", first, second)
	if first.Digest() != second.Digest() {
		t.Errorf("Digest is not stable across Compilers: %s then %s", first.Digest(), second.Digest())
	}
}

// assertDigestChangesWithContent: editing one fragment body changes the Digest. A digest that
// survived a content change would let a drifted profile address as an unchanged one.
func assertDigestChangesWithContent(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	base := renderCanonical(t, newRenderer, newTree, canonicalDocument(harness))
	varied := renderCanonical(t, newRenderer, newTree, variedDocument(harness))
	if base.Digest() == varied.Digest() {
		t.Errorf("Digest %s survived a fragment-body change; it does not address the content", base.Digest())
	}
}

// assertPrecedenceReplaces: the highest layer that declares a fragment name WINS and the lower
// layers' bodies are ABSENT (replace, never merge), the instruction follows the same rule, and the
// composition is INDEPENDENT of the order the document happened to list its fragments in — the
// invariant that keeps two orderings of one document byte-identical.
func assertPrecedenceReplaces(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	files := renderCanonical(t, newRenderer, newTree, canonicalDocument(harness))
	emitted := concatContents(files)

	for _, want := range []string{overlayPrecedenceBody, overlaySkillBody, roleInstruction} {
		if !strings.Contains(emitted, want) {
			t.Errorf("the winning layer's text %q is absent from the emission", want)
		}
	}
	for _, unwanted := range []string{rolePrecedenceBody, defaultsPrecedenceBody, defaultsSkillBody, defaultsInstruction} {
		if strings.Contains(emitted, unwanted) {
			t.Errorf("a LOWER layer's text %q survived into the emission; a higher layer must REPLACE it, never merge with it", unwanted)
		}
	}

	shuffled := renderCanonical(t, newRenderer, newTree, shuffledDocument(harness))
	assertFileSetsEqual(t, "the same document with its fragment arrays reordered", files, shuffled)
	if files.Digest() != shuffled.Digest() {
		t.Errorf("reordering the document's fragment arrays changed the Digest (%s then %s); composition must be sorted by name, so precedence decides WHICH fragment wins and never WHERE it lands",
			files.Digest(), shuffled.Digest())
	}
}

// assertUnknownRoleIsNotFound: a Target naming a role the document does not declare is KindNotFound
// with a nil FileSet — never an empty emission a drift check would pass over.
func assertUnknownRoleIsNotFound(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	compiler, _ := compileCanonical(t, newRenderer, newTree, canonicalDocument(harness), nil)
	files, err := compiler.Render(context.Background(), agentprofile.Target{Role: "no-such-role", Harness: harness})
	if err == nil {
		t.Fatalf("Render of an undeclared role returned nil error with %d file(s)", len(files))
	}
	if files != nil {
		t.Errorf("Render of an undeclared role returned a non-nil FileSet alongside its error")
	}
	if kind := errors.KindOf(err); kind != errors.KindNotFound {
		t.Errorf("Render of an undeclared role: KindOf = %v, want KindNotFound", kind)
	}
}

// assertUnclaimedHarnessIsNotFound: a Target whose harness no injected Renderer claims is
// KindNotFound. This is the wiring mistake that must never resolve to a silent empty emission.
func assertUnclaimedHarnessIsNotFound(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	compiler, _ := compileCanonical(t, newRenderer, newTree, canonicalDocument(harness), nil)
	unclaimed := agentprofile.HarnessCodex
	if harness == unclaimed {
		unclaimed = agentprofile.HarnessOMP
	}
	files, err := compiler.Render(context.Background(), agentprofile.Target{Role: CanonicalRole, Harness: unclaimed})
	if err == nil {
		t.Fatalf("Render for the unclaimed harness %s returned nil error with %d file(s)", unclaimed, len(files))
	}
	if kind := errors.KindOf(err); kind != errors.KindNotFound {
		t.Errorf("Render for the unclaimed harness %s: KindOf = %v, want KindNotFound", unclaimed, kind)
	}
}

// assertDriftReportsMissing: against an EMPTY tree every rendered file is reported, each with reason
// DivergenceMissing and each naming its own path.
func assertDriftReportsMissing(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	document := canonicalDocument(harness)
	rendered := renderCanonical(t, newRenderer, newTree, document)

	compiler, target := compileCanonical(t, newRenderer, newTree, document, nil)
	divergences, err := compiler.Drift(context.Background(), target)
	if err != nil {
		t.Fatalf("Drift against an empty tree: %v", err)
	}
	if len(divergences) != len(rendered) {
		t.Fatalf("Drift against an empty tree reported %d divergence(s), want one per rendered file (%d)", len(divergences), len(rendered))
	}
	for i, divergence := range divergences {
		if divergence.Reason != agentprofile.DivergenceMissing {
			t.Errorf("divergence %d Reason = %q, want %q", i, divergence.Reason, agentprofile.DivergenceMissing)
		}
		if divergence.Path != rendered[i].Path {
			t.Errorf("divergence %d Path = %q, want the rendered path %q", i, divergence.Path, rendered[i].Path)
		}
		if divergence.Diff == "" {
			t.Errorf("divergence %d for %q carries an empty Diff; the report must say what to do about it", i, divergence.Path)
		}
	}
}

// assertDriftIsCleanOnAMatchingTree: a tree holding EXACTLY the render reports zero divergences.
// This is the only clean verdict, and a check that could never reach it would be no check.
func assertDriftIsCleanOnAMatchingTree(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	document := canonicalDocument(harness)
	rendered := renderCanonical(t, newRenderer, newTree, document)

	compiler, target := compileCanonical(t, newRenderer, newTree, document, rendered)
	divergences, err := compiler.Drift(context.Background(), target)
	if err != nil {
		t.Fatalf("Drift against a tree holding the render: %v", err)
	}
	if len(divergences) != 0 {
		t.Errorf("Drift against a tree holding the render reported %d divergence(s), want 0: %+v", len(divergences), divergences)
	}
}

// assertDriftReportsContentDiffers: a ONE-BYTE edit to a single committed file yields exactly one
// divergence, reason DivergenceContentDiffers, naming THAT file and no other.
func assertDriftReportsContentDiffers(t *testing.T, newRenderer func() agentprofile.Renderer, newTree TreeFactory) {
	t.Helper()
	harness := newRenderer().Harness()
	document := canonicalDocument(harness)
	rendered := renderCanonical(t, newRenderer, newTree, document)
	if len(rendered) == 0 {
		t.Fatal("Render returned no files; the edit case has nothing to edit")
	}

	edited := make(agentprofile.FileSet, len(rendered))
	copy(edited, rendered)
	target := len(edited) - 1
	edited[target].Content = append(append([]byte(nil), rendered[target].Content...), '!')

	compiler, cell := compileCanonical(t, newRenderer, newTree, document, edited)
	divergences, err := compiler.Drift(context.Background(), cell)
	if err != nil {
		t.Fatalf("Drift against an edited tree: %v", err)
	}
	if len(divergences) != 1 {
		t.Fatalf("a one-byte edit to %q produced %d divergence(s), want exactly 1: %+v", rendered[target].Path, len(divergences), divergences)
	}
	if divergences[0].Reason != agentprofile.DivergenceContentDiffers {
		t.Errorf("Reason = %q, want %q", divergences[0].Reason, agentprofile.DivergenceContentDiffers)
	}
	if divergences[0].Path != rendered[target].Path {
		t.Errorf("Path = %q, want the edited file %q — the report must identify WHICH file diverged", divergences[0].Path, rendered[target].Path)
	}
}

// assertFileSetsEqual fails t unless two emissions are equal file by file — path, mode, and every
// content byte, in order. Hand-written because this repository ships no assertion library and
// depguard permits none.
func assertFileSetsEqual(t *testing.T, label string, want, got agentprofile.FileSet) {
	t.Helper()
	if len(want) != len(got) {
		t.Fatalf("%s emitted %d file(s), want %d", label, len(got), len(want))
	}
	for i := range want {
		if got[i].Path != want[i].Path {
			t.Errorf("%s: file %d Path = %q, want %q", label, i, got[i].Path, want[i].Path)
			continue
		}
		if got[i].Mode != want[i].Mode {
			t.Errorf("%s: file %d (%s) Mode = %v, want %v", label, i, want[i].Path, got[i].Mode, want[i].Mode)
		}
		if string(got[i].Content) != string(want[i].Content) {
			t.Errorf("%s: file %d (%s) content differs\n got: %q\nwant: %q", label, i, want[i].Path, got[i].Content, want[i].Content)
		}
	}
}

// concatContents joins every emitted file's bytes into one haystack, for presence/absence assertions
// that must hold across a whole emission regardless of which harness laid it out.
func concatContents(files agentprofile.FileSet) string {
	var joined strings.Builder
	for i := range files {
		joined.Write(files[i].Content)
		joined.WriteByte('\n')
	}
	return joined.String()
}
