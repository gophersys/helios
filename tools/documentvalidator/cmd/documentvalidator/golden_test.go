package main

import (
	"flag"
	"os"
	"path/filepath"
	"sort"
	"testing"

	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// updateGolden, set by `go test ./... -run Golden -update`, regenerates the
// golden projection fixtures instead of asserting against them.
var updateGolden = flag.Bool("update", false, "regenerate golden projection fixtures")

// goldenDir is the snapshot of the linkbox example's projections — the pinned UI
// contract (doc 11 §5 / ADR-0011). One <document-id>.json per document, in the
// canonical byte-stable form.
func goldenDir(t *testing.T) string {
	t.Helper()
	dir, err := filepath.Abs(filepath.Join("..", "..", "testdata", "golden", "linkbox"))
	if err != nil {
		t.Fatalf("resolve golden dir: %v", err)
	}
	return dir
}

// TestGoldenProjections asserts that `project --out` reproduces the linkbox
// goldens byte-for-byte. This pins the projection (the dashboard/AssistantSession
// contract): any drift in the projection logic must be an intentional golden
// regeneration (`go test ./... -run Golden -update`), never a silent change.
func TestGoldenProjections(t *testing.T) {
	golden := goldenDir(t)
	projections := projectExample(t)

	if *updateGolden {
		if err := os.RemoveAll(golden); err != nil {
			t.Fatalf("clearing golden dir: %v", err)
		}
		if err := os.MkdirAll(golden, 0o755); err != nil {
			t.Fatalf("creating golden dir: %v", err)
		}
		for id, content := range projections {
			path := filepath.Join(golden, id+".json")
			if err := os.WriteFile(path, content, 0o644); err != nil {
				t.Fatalf("writing golden %s: %v", path, err)
			}
		}
		t.Logf("regenerated %d golden projection fixtures in %s", len(projections), golden)
		return
	}

	// The set of golden files must match the set of projected documents exactly.
	wantFiles := goldenFileSet(t, golden)
	gotFiles := make(map[string]bool, len(projections))
	for id := range projections {
		gotFiles[id+".json"] = true
	}
	assertSameFileSet(t, wantFiles, gotFiles)

	for id, content := range projections {
		name := id + ".json"
		want, err := os.ReadFile(filepath.Join(golden, name))
		if err != nil {
			t.Errorf("missing golden %s (run: go test ./... -run Golden -update): %v", name, err)
			continue
		}
		if string(content) != string(want) {
			t.Errorf("projection of %s drifted from its golden.\n--- got ---\n%s\n--- want ---\n%s",
				name, content, want)
		}
	}
}

// projectExample projects every document in the linkbox example to its canonical
// byte form (the same content `project --out` writes: two-space indent + a
// trailing newline), keyed by document id.
func projectExample(t *testing.T) map[string][]byte {
	t.Helper()
	dir := exampleDir(t)
	paths, err := walkDocuments(dir)
	if err != nil {
		t.Fatalf("walk example: %v", err)
	}
	out := map[string][]byte{}
	for _, path := range paths {
		doc, perr := projection.Project(path)
		if perr != nil {
			t.Fatalf("project %s: %v", path, perr)
		}
		id := doc.DocumentID()
		if id == "" {
			t.Fatalf("%s has no meta.id", path)
		}
		marshaled, merr := projection.Marshal(doc.Projection)
		if merr != nil {
			t.Fatalf("marshal %s: %v", path, merr)
		}
		out[id] = append(marshaled, '\n')
	}
	return out
}

// goldenFileSet lists the *.json fixtures present in the golden directory.
func goldenFileSet(t *testing.T, dir string) map[string]bool {
	t.Helper()
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read golden dir %s (run: go test ./... -run Golden -update): %v", dir, err)
	}
	set := map[string]bool{}
	for _, e := range entries {
		if !e.IsDir() && filepath.Ext(e.Name()) == ".json" {
			set[e.Name()] = true
		}
	}
	return set
}

// assertSameFileSet fails the test if the projected and golden file sets differ,
// listing the symmetric difference.
func assertSameFileSet(t *testing.T, want, got map[string]bool) {
	t.Helper()
	var missing, extra []string
	for name := range want {
		if !got[name] {
			missing = append(missing, name)
		}
	}
	for name := range got {
		if !want[name] {
			extra = append(extra, name)
		}
	}
	sort.Strings(missing)
	sort.Strings(extra)
	if len(missing) > 0 {
		t.Errorf("golden fixtures with no projected document: %v", missing)
	}
	if len(extra) > 0 {
		t.Errorf("projected documents with no golden fixture (run -update): %v", extra)
	}
}
