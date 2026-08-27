package agentprofiletest_test

import (
	"context"
	"io/fs"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
	"github.com/gophersys/libs/go/errors"
)

// TestTree_ZeroValueReadsNothing asserts the documented zero-value behaviour: an unseeded Tree
// reports EVERY path absent, with an error satisfying errors.Is(err, fs.ErrNotExist) — the shape the
// Tree port requires so Drift can tell "never written" from "could not read". A fake whose zero
// value returned empty bytes instead would make a forgotten seed look like a clean drift check.
func TestTree_ZeroValueReadsNothing(t *testing.T) {
	t.Parallel()
	var tree agentprofiletest.Tree
	content, err := tree.ReadFile(context.Background(), "profiles/reviewer/claude-code/CLAUDE.md")
	if content != nil {
		t.Errorf("the zero Tree returned %d byte(s) for an unseeded path, want nil", len(content))
	}
	if !errors.Is(err, fs.ErrNotExist) {
		t.Fatalf("the zero Tree's error does not satisfy errors.Is(err, fs.ErrNotExist): %v", err)
	}
}

// TestTree_RecordsEveryReadInOrder asserts the append-only Read recorder captures each path in call
// order, which is what lets a test prove the drift check actually looked at a file rather than
// short-circuiting past it.
func TestTree_RecordsEveryReadInOrder(t *testing.T) {
	t.Parallel()
	tree := agentprofiletest.NewTree().With("one.md", []byte("1")).With("two.md", []byte("2"))
	ctx := context.Background()
	for _, path := range []string{"two.md", "one.md", "absent.md"} {
		//nolint:errcheck // the recorder, not the result, is the subject here; the result arms have their own tests.
		_, _ = tree.ReadFile(ctx, path)
	}
	want := []string{"two.md", "one.md", "absent.md"}
	if len(tree.Read) != len(want) {
		t.Fatalf("Read recorded %d path(s) (%q), want %d", len(tree.Read), tree.Read, len(want))
	}
	for i := range want {
		if tree.Read[i] != want[i] {
			t.Errorf("Read[%d] = %q, want %q", i, tree.Read[i], want[i])
		}
	}
}

// TestTree_SeedIsCopiedNotAliased asserts With copies the caller's bytes: mutating the caller's
// slice afterwards must not change what the tree reports. A fake that aliased its seed would let one
// test silently rewrite another's expectation.
func TestTree_SeedIsCopiedNotAliased(t *testing.T) {
	t.Parallel()
	seed := []byte("original")
	tree := agentprofiletest.NewTree().With("f.md", seed)
	seed[0] = 'X'
	got, err := tree.ReadFile(context.Background(), "f.md")
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	if string(got) != "original" {
		t.Errorf("ReadFile = %q, want %q — With must copy the seed, not alias it", got, "original")
	}
}

// TestTree_SymlinkIsFollowedByReadFile pins the HAZARD the fake exists to model: ReadFile follows a
// symlink and returns the TARGET's bytes, exactly as os.ReadFile does. A drift check built only on
// ReadFile therefore cannot tell a file from a link to one — which is why the port needs a Stat.
// IsSymlink reports the truth ReadFile hides.
func TestTree_SymlinkIsFollowedByReadFile(t *testing.T) {
	t.Parallel()
	tree := agentprofiletest.NewTree().
		With("real.md", []byte("the real bytes")).
		WithSymlink("link.md", "real.md")

	got, err := tree.ReadFile(context.Background(), "link.md")
	if err != nil {
		t.Fatalf("ReadFile through the symlink: %v", err)
	}
	if string(got) != "the real bytes" {
		t.Errorf("ReadFile through the symlink = %q, want the target's bytes %q", got, "the real bytes")
	}
	if !tree.IsSymlink("link.md") {
		t.Error("IsSymlink(link.md) = false; the fake must record the link ReadFile silently followed")
	}
	if tree.IsSymlink("real.md") {
		t.Error("IsSymlink(real.md) = true for a plain file")
	}
}

// TestTree_FailWithPropagatesTheTransportFault asserts a forced failure comes back verbatim and is
// NOT mistaken for an absent path — the arm Drift must propagate rather than fold into a divergence.
func TestTree_FailWithPropagatesTheTransportFault(t *testing.T) {
	t.Parallel()
	fault := errors.New(errors.KindUnavailable, "the tree is unreadable")
	tree := agentprofiletest.NewTree().FailWith("f.md", fault)
	_, err := tree.ReadFile(context.Background(), "f.md")
	if !errors.Is(err, fault) {
		t.Fatalf("ReadFile error = %v, want the forced fault", err)
	}
	if errors.Is(err, fs.ErrNotExist) {
		t.Error("a forced transport fault must not satisfy fs.ErrNotExist; Drift would report it as a missing file")
	}
}

// TestTree_PathsAreSortedAndComplete asserts Paths returns every seeded path — files AND symlinks —
// in sorted order. That is the data a Tree port grown a List method would read, and it is how a test
// can state the extraneous-committed-file requirement without this package inventing the Entry type
// the library must own.
func TestTree_PathsAreSortedAndComplete(t *testing.T) {
	t.Parallel()
	tree := agentprofiletest.NewTree().
		With("b.md", []byte("b")).
		With("a.md", []byte("a")).
		WithSymlink("c.md", "a.md")
	want := []string{"a.md", "b.md", "c.md"}
	got := tree.Paths()
	if len(got) != len(want) {
		t.Fatalf("Paths = %q, want %q", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Paths[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

// TestRenderer_RecordsTheResolvedProjection asserts the fake records exactly what the Compiler handed
// it: the resolved cell, the applied overlay, the schema version, and the COMPOSED fragment sets in
// name order. This is the seam that proves precedence ran before the renderer saw anything — the
// renderer never reads the raw document, so what it recorded IS the projection.
func TestRenderer_RecordsTheResolvedProjection(t *testing.T) {
	t.Parallel()
	renderer := agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode)
	compiler := compileWithFake(t, renderer)

	if _, err := compiler.Render(context.Background(), agentprofile.Target{
		Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode,
	}); err != nil {
		t.Fatalf("Render: %v", err)
	}

	if len(renderer.Resolved) != 1 {
		t.Fatalf("Resolved recorded %d projection(s), want 1", len(renderer.Resolved))
	}
	resolved := renderer.Resolved[0]
	if resolved.Target.Role != agentprofiletest.CanonicalRole {
		t.Errorf("Resolved.Target.Role = %q, want %q", resolved.Target.Role, agentprofiletest.CanonicalRole)
	}
	if resolved.Target.Harness != agentprofile.HarnessClaudeCode {
		t.Errorf("Resolved.Target.Harness = %q, want %q", resolved.Target.Harness, agentprofile.HarnessClaudeCode)
	}
	if resolved.Repository != agentprofiletest.CanonicalOverlay {
		t.Errorf("Resolved.Repository = %q, want %q", resolved.Repository, agentprofiletest.CanonicalOverlay)
	}
	if resolved.SchemaVersion != 1 {
		t.Errorf("Resolved.SchemaVersion = %d, want 1", resolved.SchemaVersion)
	}
	wantRules := []string{"fail-loudly", "precedence"}
	if len(resolved.Rules) != len(wantRules) {
		t.Fatalf("Resolved.Rules = %+v, want %d fragment(s) named %q", resolved.Rules, len(wantRules), wantRules)
	}
	for i := range wantRules {
		if resolved.Rules[i].Name != wantRules[i] {
			t.Errorf("Resolved.Rules[%d].Name = %q, want %q (composition is sorted by name)", i, resolved.Rules[i].Name, wantRules[i])
		}
	}
}

// TestRenderer_FailWithTakesPrecedenceOverEmitting asserts the scripted failure wins over a scripted
// emission: a renderer that fails emits nothing. Without that, a test could script a contradiction
// and read whichever half the fake happened to check first.
func TestRenderer_FailWithTakesPrecedenceOverEmitting(t *testing.T) {
	t.Parallel()
	fault := errors.New(errors.KindInternal, "scripted renderer fault")
	renderer := agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode).
		Emitting(agentprofile.FileSet{{Path: "x.md", Content: []byte("x"), Mode: 0o644}}).
		FailWith(fault)

	files, err := renderer.Render(context.Background(), agentprofile.Resolved{})
	if !errors.Is(err, fault) {
		t.Fatalf("Render error = %v, want the scripted fault", err)
	}
	if files != nil {
		t.Errorf("Render returned %d file(s) alongside its error, want nil", len(files))
	}
}

// TestRenderer_DefaultEmissionIsDeterministic asserts the fake's own default layout is byte-stable
// across calls. The conformance suite proves determinism THROUGH the fake, so a non-deterministic
// fake would make that proof circular.
func TestRenderer_DefaultEmissionIsDeterministic(t *testing.T) {
	t.Parallel()
	renderer := agentprofiletest.NewRenderer(agentprofile.HarnessOMP)
	resolved := agentprofile.Resolved{
		SchemaVersion: 1,
		Target:        agentprofile.Target{Role: "reviewer", Harness: agentprofile.HarnessOMP},
		Instruction:   "an instruction",
		Rules:         []agentprofile.Fragment{{Name: "a", Body: "A"}, {Name: "b", Body: "B"}},
		Skills:        []agentprofile.Fragment{{Name: "s", Body: "S"}},
	}
	first, err := renderer.Render(context.Background(), resolved)
	if err != nil {
		t.Fatalf("first Render: %v", err)
	}
	second, err := renderer.Render(context.Background(), resolved)
	if err != nil {
		t.Fatalf("second Render: %v", err)
	}
	if first.Digest() != second.Digest() {
		t.Fatalf("the fake's default emission is not deterministic: %s then %s", first.Digest(), second.Digest())
	}
	if len(first) != 4 {
		t.Errorf("the default emission carries %d file(s), want 4 (profile + 2 rules + 1 skill)", len(first))
	}
}

// TestConformance_FakeRendererOverInMemoryTree runs the exported suite over the two fakes. It proves
// the fake binding is substitutable BEFORE the real one is asked the same questions, which is the
// two-binding closure's fake half (08 §2).
func TestConformance_FakeRendererOverInMemoryTree(t *testing.T) {
	t.Parallel()
	agentprofiletest.RunRendererSuite(t,
		func() agentprofile.Renderer { return agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode) },
		func(committed agentprofile.FileSet) (agentprofile.Tree, error) {
			return agentprofiletest.NewTree().WithFileSet(committed), nil
		},
	)
}

// compileWithFake builds a Compiler over the conformance document for the renderer's harness with
// the canonical overlay selected and an empty in-memory tree.
func compileWithFake(t *testing.T, renderer *agentprofiletest.Renderer) *agentprofile.Compiler {
	t.Helper()
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: agentprofiletest.CanonicalDocument(renderer.Harness()), Repository: agentprofiletest.CanonicalOverlay},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{renderer}, Tree: agentprofiletest.NewTree()},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return compiler
}
