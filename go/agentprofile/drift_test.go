package agentprofile_test

import (
	"context"
	"io/fs"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
	"github.com/gophersys/libs/go/errors"
)

// DivergenceExtraneous is the reason a committed file under the emission's own subtree that the
// RENDER NO LONGER PRODUCES must be reported with. It is spelled here as a string literal, not as a
// library constant, precisely because the library declares no such constant at 436d7f7 — naming the
// third reason is the implementer's call, and this test states the requirement without pre-empting
// it or breaking the package's compilation. The two shipped reasons cannot express it: "missing" is
// rendered-but-not-committed and "content-differs" is committed-with-other-bytes, and this case is
// committed-but-not-rendered, whose remedy is DELETE rather than re-render.
const DivergenceExtraneous agentprofile.DivergenceReason = "extraneous"

// TestDrift_ReportsAnExtraneousCommittedFile is RED FIRST — the behaviour is genuinely absent, not
// broken. Drift iterates the RENDER's files and asks the tree about each, so a file the render no
// longer produces is invisible to it: delete a role or a rule from the document, re-render, and the
// stale artifact sits in the tree forever with Drift reporting a clean verdict. Detecting it needs a
// reverse sweep — a List over the emission prefix — which the one-method Tree port cannot do.
//
// The assertion is driven through Compiler.Drift and fails on the OUTCOME (zero divergences over a
// tree that carries a stale file), never on a missing method, so it proves behaviour rather than
// compilation. It goes green the moment the port grows the sweep and Drift reports the stale path.
func TestDrift_ReportsAnExtraneousCommittedFile(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())

	// The tree holds the whole render PLUS one stale artifact under the very same emission subtree —
	// the shape a deleted rule leaves behind.
	stale := "profiles/" + string(agentprofiletest.CanonicalRole) + "/claude-code/.claude/rules/deleted-rule.md"
	tree := agentprofiletest.NewTree().WithFileSet(rendered).With(stale, []byte("a rule the document no longer declares"))

	divergences := driftCanonicalCell(t, document, tree)

	for _, divergence := range divergences {
		if divergence.Path == stale {
			if divergence.Reason != DivergenceExtraneous {
				t.Errorf("the stale file %q was reported with Reason %q, want %q", stale, divergence.Reason, DivergenceExtraneous)
			}
			return
		}
	}
	t.Fatalf("Drift reported %d divergence(s) and NONE named the stale committed file %q; a render-only sweep cannot see a file the render no longer produces, so the drift gate passes over it forever",
		len(divergences), stale)
}

// TestDrift_RefusesASymlinkAtARenderedPath is RED FIRST for the same reason. os.ReadFile FOLLOWS a
// symlink, so a drift check built only on ReadFile compares the LINK TARGET's bytes and reports a
// clean tree — which is exactly the hole the estate's workflow-twins check closes by refusing a
// symlink outright ("cmp follows a symlink"). Deciding that a path IS a link needs a Stat that
// reports a mode; the one-method Tree port has none.
//
// The fake models the hazard faithfully: the link's target holds the rendered bytes verbatim, so
// today Drift reads them, finds them equal, and reports zero divergences over a tree where a
// rendered file has been replaced by a link. The assertion is on that OUTCOME.
func TestDrift_RefusesASymlinkAtARenderedPath(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	linked := rendered[0].Path
	elsewhere := "somewhere-else/planted.md"

	// Everything is committed correctly EXCEPT that one rendered path is a symlink whose target
	// happens to hold the right bytes. Byte comparison alone cannot tell the two apart.
	tree := agentprofiletest.NewTree().
		WithFileSet(rendered[1:]).
		With(elsewhere, rendered[0].Content).
		WithSymlink(linked, elsewhere)

	compiler := compileCell(t, document, tree)
	divergences, err := compiler.Drift(context.Background(), agentprofile.Target{
		Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode,
	})

	// The requirement is that the symlink is SURFACED, loudly. Whether it surfaces as a typed error
	// or as a divergence at that path is the implementer's call; silence is not on the menu, because
	// a link is how a committed artifact is made to lie about its own bytes.
	if err != nil {
		if !strings.Contains(err.Error(), linked) {
			t.Errorf("Drift refused the tree but its error does not name the symlinked path %q: %v", linked, err)
		}
		return
	}
	for _, divergence := range divergences {
		if divergence.Path == linked {
			return
		}
	}
	t.Fatalf("Drift returned a nil error and %d divergence(s), none naming %q, over a tree where that rendered path is a SYMLINK to %q; a byte comparison follows the link and reports a clean gate over a file that is not there",
		len(divergences), linked, elsewhere)
}

// TestDrift_MissingNamesEveryRenderedPath asserts the DivergenceMissing arm on a wholly empty tree:
// one divergence per rendered file, each carrying THAT file's path and a Diff that says what to do.
// The per-path identity is the load-bearing half — a report that said "5 files differ" without
// saying which would leave a human to diff the whole subtree by hand.
func TestDrift_MissingNamesEveryRenderedPath(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	divergences := driftCanonicalCell(t, document, agentprofiletest.NewTree())

	if len(divergences) != len(rendered) {
		t.Fatalf("Drift over an empty tree reported %d divergence(s), want %d (one per rendered file)", len(divergences), len(rendered))
	}
	for i, divergence := range divergences {
		if divergence.Reason != agentprofile.DivergenceMissing {
			t.Errorf("divergence %d Reason = %q, want %q", i, divergence.Reason, agentprofile.DivergenceMissing)
		}
		if divergence.Path != rendered[i].Path {
			t.Errorf("divergence %d Path = %q, want %q", i, divergence.Path, rendered[i].Path)
		}
		if !strings.Contains(divergence.Diff, "absent from the committed tree") {
			t.Errorf("divergence %d Diff = %q, want it to say the file is absent", i, divergence.Diff)
		}
		if !strings.Contains(divergence.Diff, "re-render") {
			t.Errorf("divergence %d Diff = %q, want it to end in the instruction that resolves it", i, divergence.Diff)
		}
	}
}

// TestDrift_ContentDiffersIdentifiesTheEditedFileOnly asserts the DivergenceContentDiffers arm: a
// single edited byte in ONE committed file yields exactly ONE divergence, naming that file, and the
// Diff carries BOTH content addresses and BOTH lengths so a reader can tell which side is stale
// without opening either.
func TestDrift_ContentDiffersIdentifiesTheEditedFileOnly(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())

	edited := rendered[len(rendered)-1]
	tree := agentprofiletest.NewTree().
		WithFileSet(rendered).
		With(edited.Path, append(append([]byte(nil), edited.Content...), '!'))

	divergences := driftCanonicalCell(t, document, tree)
	if len(divergences) != 1 {
		t.Fatalf("a one-byte edit produced %d divergence(s), want exactly 1: %+v", len(divergences), divergences)
	}
	if divergences[0].Reason != agentprofile.DivergenceContentDiffers {
		t.Errorf("Reason = %q, want %q", divergences[0].Reason, agentprofile.DivergenceContentDiffers)
	}
	if divergences[0].Path != edited.Path {
		t.Errorf("Path = %q, want the edited file %q", divergences[0].Path, edited.Path)
	}
	diff := divergences[0].Diff
	if !strings.Contains(diff, "committed sha256:") || !strings.Contains(diff, "rendered sha256:") {
		t.Errorf("Diff = %q, want both content addresses so a reader can tell the two sides apart", diff)
	}
	if !strings.Contains(diff, "bytes") {
		t.Errorf("Diff = %q, want the lengths of both sides", diff)
	}
}

// TestDrift_CleanTreeReportsZeroDivergences asserts the ONLY clean verdict is reachable. A check
// that could never report clean is as useless as one that could never report dirty.
func TestDrift_CleanTreeReportsZeroDivergences(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	divergences := driftCanonicalCell(t, document, agentprofiletest.NewTree().WithFileSet(rendered))
	if len(divergences) != 0 {
		t.Errorf("Drift over a tree holding exactly the render reported %d divergence(s), want 0: %+v", len(divergences), divergences)
	}
}

// TestDrift_TreeFaultPropagatesAndNamesThePath asserts a NON-absent read failure is propagated as an
// error rather than folded into a divergence: an unreadable tree is not the same fact as an unwritten
// file, and reporting it as "missing" would tell a human to re-render when the real remedy is to fix
// the tree. The error carries the path so the operator knows which read failed.
func TestDrift_TreeFaultPropagatesAndNamesThePath(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())

	fault := errors.New(errors.KindUnavailable, "the committed tree is unreadable")
	tree := agentprofiletest.NewTree().WithFileSet(rendered).FailWith(rendered[0].Path, fault)

	compiler := compileCell(t, document, tree)
	divergences, err := compiler.Drift(context.Background(), agentprofile.Target{
		Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode,
	})
	if err == nil {
		t.Fatalf("Drift over an unreadable tree returned nil error with %d divergence(s); an unreadable tree is not an unwritten file", len(divergences))
	}
	if divergences != nil {
		t.Errorf("Drift returned %d divergence(s) alongside its error, want nil", len(divergences))
	}
	if !errors.Is(err, fault) {
		t.Errorf("the read fault is not reachable through the chain: %v", err)
	}
	if kind := errors.KindOf(err); kind != errors.KindUnavailable {
		t.Errorf("KindOf = %v, want KindUnavailable (the Tree's own classification, preserved across the boundary)", kind)
	}
	if !strings.Contains(err.Error(), rendered[0].Path) {
		t.Errorf("the error %q does not name the path whose read failed (%q)", err.Error(), rendered[0].Path)
	}
}

// TestDrift_AbsentIsDistinguishedFromUnreadable pins the discrimination the two arms above rest on:
// an fs.ErrNotExist read becomes a divergence, and any OTHER read failure becomes an error. A Tree
// that reported absence as a generic failure would turn every un-rendered profile into a hard error,
// and a Drift that treated every failure as absence would turn an outage into "re-render and commit".
func TestDrift_AbsentIsDistinguishedFromUnreadable(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())

	absent := agentprofiletest.NewTree().WithFileSet(rendered[1:])
	divergences := driftCanonicalCell(t, document, absent)
	if len(divergences) != 1 || divergences[0].Reason != agentprofile.DivergenceMissing {
		t.Fatalf("an fs.ErrNotExist read yielded %+v, want exactly one DivergenceMissing", divergences)
	}

	unreadable := agentprofiletest.NewTree().
		WithFileSet(rendered).
		FailWith(rendered[0].Path, &fs.PathError{Op: "read", Path: rendered[0].Path, Err: fs.ErrPermission})
	compiler := compileCell(t, document, unreadable)
	if _, err := compiler.Drift(context.Background(), agentprofile.Target{
		Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode,
	}); err == nil {
		t.Error("a permission-denied read was folded into a divergence instead of surfacing as an error")
	}
}

// compileCell builds a Compiler over document with the canonical overlay, the real ClaudeRenderer,
// and the given tree.
func compileCell(t *testing.T, document []byte, tree agentprofile.Tree) *agentprofile.Compiler {
	t.Helper()
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: document, Repository: agentprofiletest.CanonicalOverlay},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}}, Tree: tree},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return compiler
}

// renderCanonicalCell renders the canonical cell through the real ClaudeRenderer.
func renderCanonicalCell(t *testing.T, document []byte, tree agentprofile.Tree) agentprofile.FileSet {
	t.Helper()
	files, err := compileCell(t, document, tree).Render(context.Background(), agentprofile.Target{
		Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode,
	})
	if err != nil {
		t.Fatalf("Render: %v", err)
	}
	return files
}

// driftCanonicalCell drifts the canonical cell against tree, failing the test on a transport error.
func driftCanonicalCell(t *testing.T, document []byte, tree agentprofile.Tree) []agentprofile.Divergence {
	t.Helper()
	divergences, err := compileCell(t, document, tree).Drift(context.Background(), agentprofile.Target{
		Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode,
	})
	if err != nil {
		t.Fatalf("Drift: %v", err)
	}
	return divergences
}
