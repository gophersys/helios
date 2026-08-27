package agentprofile_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// ADR-0020 dimension (f), the SeededCanary no-leak property. The needle is
// agentprofiletest.SeededCanary — a high-entropy, self-labeling token seeded into a profile document.
//
// The claim under test is precise, and its boundary matters. A rendered file's CONTENT legitimately
// carries the document's own text: emitting the instruction an author wrote is the whole job, so the
// emission is not a leak surface. The leak surfaces are the artifacts the library SYNTHESISES about
// that content and hands to an operator, a log or a CI annotation:
//
//   - every error message on every failure path;
//   - Divergence.Diff — the sharpest one, because a diff of file contents is exactly where a careless
//     implementation would quote the bytes it found, and a drift report is printed into CI logs by
//     construction. The library summarises with a content ADDRESS and a length instead, which reveals
//     nothing a log should not carry;
//   - the Digest and everything adjacent to it;
//   - a neighbouring cell's emission, since a renderer sees only its own Resolved.
//
// One leak fails the lane.

// seededCanary is the needle, taken from the shipped test-helper package so the fake, the suite and
// this lane all point at ONE value rather than three that could drift apart.
const seededCanary = agentprofiletest.SeededCanary

// canaryDocument is a valid document whose reviewer role carries the canary in a rule body, and whose
// SECOND role (auditor) carries it in an instruction. Rendering the reviewer cell must surface it
// nowhere synthesised, and the auditor's copy must not cross into the reviewer's emission at all.
const canaryDocument = `{"schemaVersion":1,` +
	`"defaults":{"instruction":"the default instruction"},` +
	`"roles":{` +
	`"reviewer":{"instruction":"the reviewer instruction","harnesses":["claude-code"],` +
	`"rules":[{"name":"secret-bearing","body":"` + seededCanary + `"}]},` +
	`"auditor":{"instruction":"auditor ` + seededCanary + ` instruction","harnesses":["claude-code"]}` +
	`}}`

// TestCanary_NeverLeaksThroughADivergenceDiff is the load-bearing case. A drift report is printed
// into CI logs by construction, and Divergence.Diff is the field a naive implementation would fill
// with the bytes it compared. Both reasons are exercised — MISSING (nothing committed) and
// CONTENT-DIFFERS (committed with other bytes) — because the two build their summaries separately and
// a leak in either is a leak.
func TestCanary_NeverLeaksThroughADivergenceDiff(t *testing.T) {
	t.Parallel()
	rendered := renderCanaryCell(t, agentprofiletest.NewTree())

	// MISSING: an empty tree, so every rendered file is reported absent.
	missing := driftCanaryCell(t, agentprofiletest.NewTree())
	assertNoCanary(t, "DivergenceMissing", diffsOf(missing))

	// CONTENT-DIFFERS: the tree holds the render with one file's bytes replaced by other
	// canary-bearing bytes, so BOTH sides of the comparison carry the needle.
	edited := agentprofiletest.NewTree().WithFileSet(rendered).
		With(rendered[0].Path, []byte("committed "+seededCanary+" bytes"))
	differs := driftCanaryCell(t, edited)
	if len(differs) == 0 {
		t.Fatal("the edited tree reported no divergence; the content-differs half was never exercised")
	}
	assertNoCanary(t, "DivergenceContentDiffers", diffsOf(differs))

	// The Path field names the file and is loggable; assert it never became a content field.
	for _, divergence := range append(missing, differs...) {
		if strings.Contains(divergence.Path, seededCanary) {
			t.Errorf("the canary leaked into Divergence.Path: %q", divergence.Path)
		}
	}
}

// TestCanary_NeverLeaksThroughADigest asserts the content address and everything the library prints
// beside it stay free of the bytes they address. A digest reveals nothing a log should not carry —
// that is the entire reason Drift summarises with one instead of a line-level diff.
func TestCanary_NeverLeaksThroughADigest(t *testing.T) {
	t.Parallel()
	rendered := renderCanaryCell(t, agentprofiletest.NewTree())
	if !strings.Contains(concatEmission(rendered), seededCanary) {
		t.Fatal("the canary is not in the emission; this lane would be asserting over nothing")
	}
	if digest := rendered.Digest(); strings.Contains(digest, seededCanary) {
		t.Errorf("the canary leaked into the Digest: %q", digest)
	}
	for i := range rendered {
		if strings.Contains(rendered[i].Path, seededCanary) {
			t.Errorf("the canary leaked into an emitted PATH: %q", rendered[i].Path)
		}
	}
}

// TestCanary_NeverLeaksThroughAnErrorMessage walks the failure paths a canary-bearing document can
// reach — a parse fault over raw bytes that contain the needle, an unaddressable cell, an unbuilt
// harness, a renderer fault, and an unreadable tree — and asserts none of their messages carries it.
// A parser that echoed the raw document, or a wrapper that interpolated the content it was handed,
// would surface it here.
func TestCanary_NeverLeaksThroughAnErrorMessage(t *testing.T) {
	t.Parallel()

	// A MALFORMED document whose bytes contain the needle: the parse fault must name a position, not
	// quote the file.
	malformed := `{"schemaVersion":1,"roles":{"reviewer":{"instruction":"` + seededCanary + `",}}}`
	if _, err := newOverDocument(malformed); err == nil {
		t.Error("the malformed canary document parsed cleanly")
	} else {
		assertNoCanary(t, "parse fault", []string{err.Error()})
	}

	compiler := compileCanary(t, agentprofiletest.NewTree())
	ctx := context.Background()

	// An unaddressable cell.
	if _, err := compiler.Render(ctx, agentprofile.Target{Role: "no-such-role", Harness: agentprofile.HarnessClaudeCode}); err == nil {
		t.Error("Render of an undeclared role returned nil error")
	} else {
		assertNoCanary(t, "not-found fault", []string{err.Error()})
	}

	// An UNBUILT harness, whose typed cause names the harness and nothing else.
	unbuilt, err := agentprofile.New(
		agentprofile.Config{Document: []byte(canaryDocument)},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{agentprofile.OMPRenderer{}}, Tree: agentprofiletest.NewTree()},
	)
	if err != nil {
		t.Fatalf("New with the omp renderer: %v", err)
	}
	if _, renderErr := unbuilt.Render(ctx, agentprofile.Target{Role: "reviewer", Harness: agentprofile.HarnessOMP}); renderErr == nil {
		t.Error("the unbuilt omp renderer returned nil error")
	} else {
		assertNoCanary(t, "not-implemented fault", []string{renderErr.Error()})
	}

	// A renderer fault whose own message carries the needle: the wrap must not be the thing that
	// widens the blast radius, but the cause is the renderer's own and is reported as it stands. The
	// assertion here is on the FIELDS the library adds, which must stay content-free.
	rendered := renderCanaryCell(t, agentprofiletest.NewTree())
	unreadable := agentprofiletest.NewTree().WithFileSet(rendered).
		FailWith(rendered[0].Path, &canaryFreeFault{})
	if _, driftErr := compileCanary(t, unreadable).Drift(ctx, canaryTarget()); driftErr == nil {
		t.Error("Drift over an unreadable tree returned nil error")
	} else {
		assertNoCanary(t, "tree fault", []string{driftErr.Error()})
	}
}

// TestCanary_NeverCrossesIntoANeighbouringCell asserts the projection boundary: a renderer sees ONLY
// its own Resolved, so the auditor role's canary-bearing instruction cannot appear in the reviewer's
// emission. A composer that handed the whole document to every renderer would surface it here — and
// that is the class of bug that turns one role's private instruction into every role's.
func TestCanary_NeverCrossesIntoANeighbouringCell(t *testing.T) {
	t.Parallel()
	const auditorMarker = "auditor " + seededCanary + " instruction"
	files := renderCanaryCell(t, agentprofiletest.NewTree())
	if emitted := concatEmission(files); strings.Contains(emitted, auditorMarker) {
		t.Errorf("the auditor role's instruction crossed into the reviewer's emission; a renderer must see only its own Resolved")
	}
}

// ── helpers ─────────────────────────────────────────────────────────────────────────────────────

// canaryFreeFault is a tree failure whose message carries no needle, so the assertion above measures
// what the LIBRARY adds to a wrapped error rather than what the port's own message already said.
type canaryFreeFault struct{}

func (*canaryFreeFault) Error() string { return "the committed tree could not be read" }

// canaryTarget is the cell every case in this lane addresses.
func canaryTarget() agentprofile.Target {
	return agentprofile.Target{Role: "reviewer", Harness: agentprofile.HarnessClaudeCode}
}

// compileCanary builds a Compiler over the canary document with the real ClaudeRenderer.
func compileCanary(t *testing.T, tree agentprofile.Tree) *agentprofile.Compiler {
	t.Helper()
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: []byte(canaryDocument)},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}}, Tree: tree},
	)
	if err != nil {
		t.Fatalf("New over the canary document: %v", err)
	}
	return compiler
}

// renderCanaryCell renders the reviewer cell of the canary document.
func renderCanaryCell(t *testing.T, tree agentprofile.Tree) agentprofile.FileSet {
	t.Helper()
	files, err := compileCanary(t, tree).Render(context.Background(), canaryTarget())
	if err != nil {
		t.Fatalf("Render: %v", err)
	}
	return files
}

// driftCanaryCell drifts the reviewer cell of the canary document against tree.
func driftCanaryCell(t *testing.T, tree agentprofile.Tree) []agentprofile.Divergence {
	t.Helper()
	divergences, err := compileCanary(t, tree).Drift(context.Background(), canaryTarget())
	if err != nil {
		t.Fatalf("Drift: %v", err)
	}
	return divergences
}

// diffsOf collects every Divergence.Diff for a bulk absence assertion.
func diffsOf(divergences []agentprofile.Divergence) []string {
	diffs := make([]string, 0, len(divergences))
	for _, divergence := range divergences {
		diffs = append(diffs, divergence.Diff)
	}
	return diffs
}

// assertNoCanary fails t if the needle appears verbatim in any of the surfaces.
func assertNoCanary(t *testing.T, surface string, rendered []string) {
	t.Helper()
	if len(rendered) == 0 {
		t.Fatalf("%s: nothing was captured, so this assertion checked nothing", surface)
	}
	for i, line := range rendered {
		if strings.Contains(line, seededCanary) {
			t.Errorf("the canary leaked through %s (%d): %q", surface, i, line)
		}
	}
}
