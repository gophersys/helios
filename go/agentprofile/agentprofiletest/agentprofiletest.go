// Package agentprofiletest provides the canonical in-memory fakes for the two agentprofile ports —
// Tree (the committed working tree) and Renderer (the harness emission seam) — plus the ONE
// exported conformance suite every Renderer binding is proven against (conformance.go).
//
// Both fakes are DETERMINISTIC by construction: no clock, no environment, no random source, no I/O,
// and no emission whose order is a Go map's iteration order. That is the same guarantee the library
// under test makes, so a binding that passes the suite against a fake and fails against the real
// renderer has a real defect rather than a fixture artifact.
//
// Both fakes are safe for concurrent use: every accessor takes the value's own mutex. Their exported
// recorder slices carry the same concurrency caveat the secretstest fake documents — quiesce the
// goroutines under test before reading one.
package agentprofiletest

import (
	"context"
	"io/fs"
	"strconv"
	"sync"

	"github.com/gophersys/libs/go/agentprofile"
)

// SeededCanary is the security lane's needle (ADR-0020 dimension (f), the secretstest.SeededPlaintext
// spirit). A test places it in a profile document's fragment body and then asserts it appears in NO
// surfaced artifact — not in an error message, not in a Divergence.Diff, not in a digest-adjacent
// field. It is high-entropy and self-labeling so a gitleaks match would be unambiguous if it ever
// escaped a rendered artifact into the repository.
const SeededCanary = "SEEDED-CANARY-YWdlbnRwcm9maWxl-8f14e45f-do-not-leak"

// fakeEmissionRoot is the repository-relative directory the fake Renderer's default emission lands
// under. It deliberately mirrors the production layout's shape (a per-cell subtree) so a drift or
// digest property that holds on the fake means the same thing it means on the real renderer.
const fakeEmissionRoot = "profiles"

// fakeFileMode is the permission bits the fake Renderer's default emission carries. Instrumentation
// is data an agent reads, never a program it runs.
const fakeFileMode fs.FileMode = 0o644

// Tree is a deterministic, in-memory agentprofile.Tree for tests: a map of repository-relative path
// to committed bytes. The ZERO VALUE reads nothing — every path is reported absent — so a test opts
// into content explicitly and a forgotten seed can never look like a clean drift check.
//
// It models one hazard on purpose: a SYMLINK entry (WithSymlink) whose ReadFile FOLLOWS the link,
// exactly as os.ReadFile does. A drift check that only reads bytes therefore cannot tell a real file
// from a link pointing at one, which is the guard the contract carries forward from the estate's
// workflow-twins check.
type Tree struct {
	// Read is an append-only log of every path ReadFile was asked for, in call order, for
	// "did the drift check look at this file?" assertions.
	//
	// CONCURRENCY CAVEAT (the secretstest.Provider.Resolved caveat, restated because it is the same
	// hazard): ReadFile appends under the Tree's own lock, but a read of this exported field goes
	// through no lock. Quiesce every goroutine that may still be in ReadFile — join them — BEFORE
	// inspecting it, or -race will flag the read.
	Read []string

	mutex    sync.Mutex
	files    map[string][]byte
	symlinks map[string]string
	failures map[string]error
}

// NewTree returns an empty fake Tree. It reads nothing until seeded, which is the same behaviour the
// zero value has; NewTree exists so a fluent chain reads left to right from a constructor.
func NewTree() *Tree { return &Tree{} }

// With seeds (or overrides) the committed bytes at path. It copies the content, so a caller cannot
// alias the seed and a later mutation of the caller's slice cannot silently change what the tree
// reports. Fluent: it returns the receiver.
func (t *Tree) With(path string, content []byte) *Tree {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	if t.files == nil {
		t.files = make(map[string][]byte)
	}
	t.files[path] = append([]byte(nil), content...)
	return t
}

// WithFileSet seeds every file of an emission at once — the "the tree holds exactly this render"
// state a clean drift check is asserted against. Fluent: it returns the receiver.
func (t *Tree) WithFileSet(files agentprofile.FileSet) *Tree {
	for i := range files {
		t.With(files[i].Path, files[i].Content)
	}
	return t
}

// WithSymlink seeds path as a SYMLINK to target. ReadFile FOLLOWS it and returns the target's bytes,
// which is precisely what os.ReadFile does on a real filesystem — so a drift check built only on
// ReadFile compares the target's bytes and reports a clean tree over a link. The link is recorded
// separately from the file map so a Tree port that later grows a Stat can distinguish the two.
// Fluent: it returns the receiver.
func (t *Tree) WithSymlink(path, target string) *Tree {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	if t.symlinks == nil {
		t.symlinks = make(map[string]string)
	}
	t.symlinks[path] = target
	return t
}

// FailWith forces ReadFile(path) to return err — the transport-fault arm a drift check must
// propagate rather than mistake for an absent file. Fluent: it returns the receiver.
func (t *Tree) FailWith(path string, err error) *Tree {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	if t.failures == nil {
		t.failures = make(map[string]error)
	}
	t.failures[path] = err
	return t
}

// IsSymlink reports whether path was seeded as a symlink. It is the data a Tree port that grows a
// Stat method would read; the fake records it today so a test can state the symlink requirement
// without this package inventing the Entry type the contract owner must declare.
func (t *Tree) IsSymlink(path string) bool {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	_, linked := t.symlinks[path]
	return linked
}

// Paths returns every seeded path — files and symlinks — sorted, as an independent copy. It is the
// data a Tree port that grows a List method would read, and it lets a test state the
// extraneous-committed-file requirement without this package declaring a contract type it does not
// own.
func (t *Tree) Paths() []string {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	paths := make([]string, 0, len(t.files)+len(t.symlinks))
	for path := range t.files {
		paths = append(paths, path)
	}
	for path := range t.symlinks {
		paths = append(paths, path)
	}
	sortStrings(paths)
	return paths
}

// ReadFile implements agentprofile.Tree. It records the path, then returns the forced failure, the
// followed symlink's bytes, the seeded bytes, or an fs.ErrNotExist-satisfying *fs.PathError — which
// is the shape the port REQUIRES for an absent path (os.ReadFile already returns it), and is how
// Drift tells a file that was never written from a tree it could not read.
func (t *Tree) ReadFile(_ context.Context, path string) ([]byte, error) {
	t.mutex.Lock()
	defer t.mutex.Unlock()

	t.Read = append(t.Read, path)

	if err, forced := t.failures[path]; forced {
		return nil, err
	}
	if target, linked := t.symlinks[path]; linked {
		// A symlink is FOLLOWED, exactly as os.ReadFile follows one. That is the hazard, not a
		// convenience: the bytes a caller gets back are the TARGET's.
		path = target
	}
	content, seeded := t.files[path]
	if !seeded {
		return nil, &fs.PathError{Op: "read", Path: path, Err: fs.ErrNotExist}
	}
	return append([]byte(nil), content...), nil
}

// Renderer is a deterministic, scripted agentprofile.Renderer for tests. It claims the harness it
// was constructed for, records every Resolved projection it was handed, and emits either a chosen
// FileSet, a chosen error, or — by default — a deterministic layout derived only from the Resolved,
// so the fake satisfies the same emission invariants the real renderer does.
type Renderer struct {
	// Resolved is an append-only log of every projection Render was handed, in call order, for
	// "which cell was this renderer asked for, and what did precedence resolve it to?" assertions.
	//
	// CONCURRENCY CAVEAT: the same one Tree.Read carries — Render appends under the Renderer's own
	// lock, a read of this exported field takes none. Join the goroutines first.
	Resolved []agentprofile.Resolved

	mutex    sync.Mutex
	harness  agentprofile.Harness
	emission agentprofile.FileSet
	scripted bool
	failure  error
}

// NewRenderer returns a fake Renderer claiming harness. With no further scripting it emits the
// deterministic default layout for whatever Resolved it is handed.
func NewRenderer(harness agentprofile.Harness) *Renderer {
	return &Renderer{harness: harness}
}

// Emitting scripts the exact FileSet every Render returns, regardless of the Resolved — the seam a
// test uses to hand the library an emission that violates one of its invariants (empty, duplicated,
// unusable path) and assert the guard fires. An EMPTY set is a legitimate script and is honoured as
// one: the scripted flag is what tells "emit nothing" apart from "was never scripted", and without
// it the empty-emission guard could never be exercised. Fluent: it returns the receiver.
func (r *Renderer) Emitting(files agentprofile.FileSet) *Renderer {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	r.emission = append(agentprofile.FileSet(nil), files...)
	r.scripted = true
	return r
}

// FailWith scripts the error every Render returns. It takes precedence over Emitting, because a
// renderer that fails emits nothing. Fluent: it returns the receiver.
func (r *Renderer) FailWith(err error) *Renderer {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	r.failure = err
	return r
}

// Harness implements agentprofile.Renderer. It is constant for the lifetime of the value, as the
// port requires.
func (r *Renderer) Harness() agentprofile.Harness { return r.harness }

// Render implements agentprofile.Renderer: it records the projection, then returns the scripted
// failure, the scripted emission, or the deterministic default layout.
//
//nolint:gocritic // hugeParam: Resolved is by value BY DESIGN — the frozen port signature; the copy is what makes the projection immutable to the renderer.
func (r *Renderer) Render(_ context.Context, resolved agentprofile.Resolved) (agentprofile.FileSet, error) {
	r.mutex.Lock()
	defer r.mutex.Unlock()

	r.Resolved = append(r.Resolved, resolved)

	if r.failure != nil {
		return nil, r.failure
	}
	if r.scripted {
		return append(agentprofile.FileSet(nil), r.emission...), nil
	}
	return defaultEmission(&resolved), nil
}

// defaultEmission is the fake's deterministic layout: one profile document for the instruction, one
// file per composed rule and one per composed skill, each stamped with a provenance notice derived
// ONLY from the Resolved. Nothing here reads a map in iteration order — the Resolved's fragment
// slices arrive already sorted by name — so two calls over one projection are byte-identical.
func defaultEmission(resolved *agentprofile.Resolved) agentprofile.FileSet {
	root := fakeEmissionRoot + "/" + resolved.Target.String()
	notice := fakeNotice(resolved)
	files := make(agentprofile.FileSet, 0, 1+len(resolved.Rules)+len(resolved.Skills))
	files = append(files, agentprofile.File{
		Path:    root + "/PROFILE.md",
		Content: []byte(notice + resolved.Instruction),
		Mode:    fakeFileMode,
	})
	for _, rule := range resolved.Rules {
		files = append(files, agentprofile.File{
			Path:    root + "/rules/" + rule.Name + ".md",
			Content: []byte(notice + rule.Body),
			Mode:    fakeFileMode,
		})
	}
	for _, skill := range resolved.Skills {
		files = append(files, agentprofile.File{
			Path:    root + "/skills/" + skill.Name + ".md",
			Content: []byte(notice + skill.Body),
			Mode:    fakeFileMode,
		})
	}
	return files
}

// fakeNotice is the fake's provenance line. It names the schema version, the cell and the overlay,
// so a fake emission is as self-describing as a real one and a digest over it changes when any of
// those change.
func fakeNotice(resolved *agentprofile.Resolved) string {
	overlay := resolved.Repository
	if overlay == "" {
		overlay = "none"
	}
	return "<!-- fake agentprofile emission (schemaVersion " + strconv.Itoa(resolved.SchemaVersion) +
		", cell " + resolved.Target.String() + ", overlay " + overlay + ") -->\n\n"
}

// sortStrings sorts in place with an insertion sort. The fake's path sets are tiny (one emission),
// and hand-rolling the three lines keeps this package's import graph to the ports it fakes.
func sortStrings(values []string) {
	for i := 1; i < len(values); i++ {
		for j := i; j > 0 && values[j] < values[j-1]; j-- {
			values[j], values[j-1] = values[j-1], values[j]
		}
	}
}
