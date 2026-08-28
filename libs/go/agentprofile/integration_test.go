//go:build integration

package agentprofile_test

import (
	"context"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// ADR-0020 dimension (d) — the host-leveraging lane, REAL substrate, never a mock.
//
// agentprofile provisions no daemon: a profile renders to BYTES, so there is no container or cluster
// to stand up, and EDEN_INTEGRATION_CMDS is "go". Its real substrate is the FILESYSTEM. That is not a
// technicality — the whole point of this library is that its emission is COMMITTED to a working tree
// and later compared against what is on disk, so every fact that only the real filesystem can settle
// lives here: that a slash-separated contract path maps onto real nested directories, that the bytes
// survive a write-then-read round trip unchanged, that a real os.ReadFile-backed Tree satisfies the
// port's fs.ErrNotExist requirement without anyone hand-rolling it, and that a real symlink behaves
// the way the in-memory fake models it.
//
// So the SAME exported conformance suite runs over a real directory, with every file written by
// os.WriteFile and read back by os.ReadFile. Nothing is mocked. Everything is reaped by t.TempDir on
// cleanup.

// TestIntegration_ClaudeRendererOverARealDirectory runs the FULL Renderer conformance suite with the
// production ClaudeRenderer and a Tree backed by a real directory on this host. Every drift property
// — missing, clean, content-differs — is settled by real files on real disk rather than by a map.
func TestIntegration_ClaudeRendererOverARealDirectory(t *testing.T) {
	t.Parallel()
	agentprofiletest.RunRendererSuite(t,
		func() agentprofile.Renderer { return agentprofile.ClaudeRenderer{} },
		realDirectoryTreeFactory(t),
	)
}

// TestIntegration_FakeRendererOverARealDirectory runs the identical suite with the fake Renderer over
// the same real substrate. It is the two-binding closure's other half measured against the real
// filesystem: a property that holds for the fake in memory and fails for the fake on disk would be a
// property of the map, not of the contract.
func TestIntegration_FakeRendererOverARealDirectory(t *testing.T) {
	t.Parallel()
	agentprofiletest.RunRendererSuite(t,
		func() agentprofile.Renderer { return agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode) },
		realDirectoryTreeFactory(t),
	)
}

// TestIntegration_EmissionSurvivesARealWriteReadRoundTrip writes the whole emission to a real
// directory exactly as a consumer would — creating each parent directory, writing each file at its
// declared mode — then reads every file back and asserts the recovered FileSet addresses IDENTICALLY.
// This is the fact the library's committability rests on and that no in-memory fixture can establish:
// the contract path is slash-separated on every host, the host's separator is applied on the way to
// disk, and nothing about the round trip perturbs a byte or a permission bit.
func TestIntegration_EmissionSurvivesARealWriteReadRoundTrip(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())

	root := t.TempDir()
	writeEmission(t, root, rendered)

	recovered := make(agentprofile.FileSet, 0, len(rendered))
	for i := range rendered {
		onDisk := filepath.Join(root, filepath.FromSlash(rendered[i].Path))
		content, err := os.ReadFile(onDisk) //nolint:gosec // a path this test just wrote under its own t.TempDir root
		if err != nil {
			t.Fatalf("reading back %s: %v", rendered[i].Path, err)
		}
		info, err := os.Stat(onDisk)
		if err != nil {
			t.Fatalf("stat %s: %v", rendered[i].Path, err)
		}
		if info.Mode().Perm() != rendered[i].Mode.Perm() {
			t.Errorf("%s landed on disk with mode %v, want %v", rendered[i].Path, info.Mode().Perm(), rendered[i].Mode.Perm())
		}
		if info.IsDir() {
			t.Errorf("%s landed on disk as a directory", rendered[i].Path)
		}
		recovered = append(recovered, agentprofile.File{Path: rendered[i].Path, Content: content, Mode: rendered[i].Mode})
	}
	if got, want := recovered.Digest(), rendered.Digest(); got != want {
		t.Errorf("the emission read back off disk addresses as %s, want %s — a committed profile does not survive its own round trip", got, want)
	}
}

// TestIntegration_DriftOverARealDirectoryReportsEveryReason drives the three drift verdicts against
// real files: nothing on disk (missing), the exact emission on disk (clean), and one file edited on
// disk by a single byte (content-differs). The edit is made with a real os.WriteFile, so this settles
// that the check reads what is actually there rather than what it rendered a moment ago.
func TestIntegration_DriftOverARealDirectoryReportsEveryReason(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}

	root := t.TempDir()
	compiler := compileCell(t, document, directoryTree{root: root})
	ctx := context.Background()

	missing, err := compiler.Drift(ctx, target)
	if err != nil {
		t.Fatalf("Drift over an empty directory: %v", err)
	}
	if len(missing) != len(rendered) {
		t.Fatalf("Drift over an empty directory reported %d divergence(s), want %d", len(missing), len(rendered))
	}
	for i, divergence := range missing {
		if divergence.Reason != agentprofile.DivergenceMissing {
			t.Errorf("divergence %d Reason = %q, want %q", i, divergence.Reason, agentprofile.DivergenceMissing)
		}
	}

	writeEmission(t, root, rendered)
	clean, err := compiler.Drift(ctx, target)
	if err != nil {
		t.Fatalf("Drift over the written emission: %v", err)
	}
	if len(clean) != 0 {
		t.Fatalf("Drift over a directory holding exactly the render reported %d divergence(s), want 0: %+v", len(clean), clean)
	}

	edited := rendered[0]
	onDisk := filepath.Join(root, filepath.FromSlash(edited.Path))
	if err := os.WriteFile(onDisk, append(append([]byte(nil), edited.Content...), '!'), 0o600); err != nil {
		t.Fatalf("editing %s on disk: %v", edited.Path, err)
	}
	differs, err := compiler.Drift(ctx, target)
	if err != nil {
		t.Fatalf("Drift over the edited directory: %v", err)
	}
	if len(differs) != 1 {
		t.Fatalf("a one-byte on-disk edit produced %d divergence(s), want exactly 1: %+v", len(differs), differs)
	}
	if differs[0].Reason != agentprofile.DivergenceContentDiffers || differs[0].Path != edited.Path {
		t.Errorf("got %+v, want DivergenceContentDiffers at %q", differs[0], edited.Path)
	}
}

// TestIntegration_DriftRefusesARealSymlink is RED FIRST against the REAL substrate, and it is the
// case that makes the requirement undeniable: os.ReadFile FOLLOWS a symlink, so a rendered path
// replaced on disk by a link to a file holding the right bytes reads back as correct and the gate
// reports clean. The estate's own workflow-twins check refuses a symlink outright for exactly this
// reason ("cmp follows a symlink"), and the contract carries that guard forward. Deciding a path IS a
// link needs a Stat that reports a mode; the one-method Tree port has none, so this fails today on
// the OUTCOME — a clean verdict over a tree where a committed artifact is not what it claims to be.
func TestIntegration_DriftRefusesARealSymlink(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}

	root := t.TempDir()
	writeEmission(t, root, rendered)

	// Replace one rendered file with a REAL symlink whose target holds the correct bytes.
	linked := rendered[0]
	onDisk := filepath.Join(root, filepath.FromSlash(linked.Path))
	elsewhere := filepath.Join(root, "planted-elsewhere.md")
	if err := os.WriteFile(elsewhere, linked.Content, 0o600); err != nil {
		t.Fatalf("planting the link target: %v", err)
	}
	if err := os.Remove(onDisk); err != nil {
		t.Fatalf("removing the real file: %v", err)
	}
	if err := os.Symlink(elsewhere, onDisk); err != nil {
		t.Fatalf("creating the symlink (this host may not support them): %v", err)
	}

	divergences, err := compileCell(t, document, directoryTree{root: root}).Drift(context.Background(), target)
	if err != nil {
		if !strings.Contains(err.Error(), linked.Path) {
			t.Errorf("Drift refused the tree but its error does not name the symlinked path %q: %v", linked.Path, err)
		}
		return
	}
	for _, divergence := range divergences {
		if divergence.Path == linked.Path {
			return
		}
	}
	t.Fatalf("Drift returned a nil error and %d divergence(s), none naming %q, over a REAL directory where that rendered path is a symlink; os.ReadFile followed the link and the gate reported clean over a file that is not there",
		len(divergences), linked.Path)
}

// TestIntegration_DriftReportsARealExtraneousFile is the second RED-FIRST case against the real
// substrate: a stale artifact left on disk under the emission's own subtree, which the render no
// longer produces. Drift walks the RENDER's files, so nothing ever asks the directory what else it
// contains, and the stale file survives every gate. Detecting it needs a reverse sweep — a List over
// the emission prefix — which the one-method Tree port cannot express. Asserted on the OUTCOME.
func TestIntegration_DriftReportsARealExtraneousFile(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	rendered := renderCanonicalCell(t, document, agentprofiletest.NewTree())
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}

	root := t.TempDir()
	writeEmission(t, root, rendered)

	stale := "profiles/" + string(agentprofiletest.CanonicalRole) + "/claude-code/.claude/rules/deleted-rule.md"
	onDisk := filepath.Join(root, filepath.FromSlash(stale))
	if err := os.MkdirAll(filepath.Dir(onDisk), 0o750); err != nil {
		t.Fatalf("creating the stale file's directory: %v", err)
	}
	if err := os.WriteFile(onDisk, []byte("a rule the document no longer declares"), 0o600); err != nil {
		t.Fatalf("planting the stale file: %v", err)
	}

	divergences, err := compileCell(t, document, directoryTree{root: root}).Drift(context.Background(), target)
	if err != nil {
		t.Fatalf("Drift: %v", err)
	}
	for _, divergence := range divergences {
		if divergence.Path == stale {
			return
		}
	}
	t.Fatalf("Drift reported %d divergence(s) over a REAL directory and none named the stale committed file %q; a render-only sweep never asks the tree what else is there",
		len(divergences), stale)
}

// ── the real-filesystem Tree binding ────────────────────────────────────────────────────────────

// directoryTree is a REAL agentprofile.Tree: ReadFile does an actual os.ReadFile under a root
// directory. This is the production-shaped edge a composition root injects — not a mock. os.ReadFile
// already returns an fs.ErrNotExist-satisfying error for an absent path, which is precisely why the
// port specifies that shape.
type directoryTree struct{ root string }

// ReadFile implements agentprofile.Tree against the host filesystem.
func (d directoryTree) ReadFile(_ context.Context, path string) ([]byte, error) {
	//nolint:wrapcheck // the port REQUIRES the raw fs error shape (errors.Is(err, fs.ErrNotExist)); wrapping it here would break the contract this lane exists to prove.
	return os.ReadFile(filepath.Join(d.root, filepath.FromSlash(path))) //nolint:gosec // a repository-relative contract path under this test's own t.TempDir root
}

// realDirectoryTreeFactory returns a TreeFactory that materialises each committed FileSet into its
// OWN fresh directory under one t.TempDir, so the suite's parallel subtests never share a tree. Every
// directory is reaped by t.TempDir's cleanup.
func realDirectoryTreeFactory(t *testing.T) agentprofiletest.TreeFactory {
	t.Helper()
	root := t.TempDir()
	var sequence atomic.Int64
	return func(committed agentprofile.FileSet) (agentprofile.Tree, error) {
		directory := filepath.Join(root, "tree-"+strconv.FormatInt(sequence.Add(1), 10))
		if err := os.MkdirAll(directory, 0o750); err != nil {
			//nolint:wrapcheck // the factory surfaces the raw filesystem error for the suite to report.
			return nil, err
		}
		for i := range committed {
			onDisk := filepath.Join(directory, filepath.FromSlash(committed[i].Path))
			if err := os.MkdirAll(filepath.Dir(onDisk), 0o750); err != nil {
				//nolint:wrapcheck // as above.
				return nil, err
			}
			if err := os.WriteFile(onDisk, committed[i].Content, committed[i].Mode.Perm()); err != nil {
				//nolint:wrapcheck // as above.
				return nil, err
			}
		}
		return directoryTree{root: directory}, nil
	}
}

// writeEmission materialises an emission under root exactly as a consumer would, creating every
// parent directory and honouring each file's declared mode.
func writeEmission(t *testing.T, root string, files agentprofile.FileSet) {
	t.Helper()
	for i := range files {
		onDisk := filepath.Join(root, filepath.FromSlash(files[i].Path))
		if err := os.MkdirAll(filepath.Dir(onDisk), 0o750); err != nil {
			t.Fatalf("creating the directory for %s: %v", files[i].Path, err)
		}
		if err := os.WriteFile(onDisk, files[i].Content, files[i].Mode.Perm()); err != nil {
			t.Fatalf("writing %s: %v", files[i].Path, err)
		}
	}
}
