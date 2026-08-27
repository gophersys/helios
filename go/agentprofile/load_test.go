//go:build load

package agentprofile_test

import (
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// ADR-0020 dimension (e) — load and scale under -race. The `load` verb sets EDEN_LOAD_N (default 500
// in-process) and runs this lane with the race detector; goleak.VerifyNone asserts the goroutine
// high-water returns to baseline afterwards.
//
// The contract's concurrency claim is exact: "a *Compiler is immutable after New and is safe for
// concurrent use by multiple goroutines iff the injected Renderers and Tree are." The two cases below
// are that claim's two halves. The first fans N goroutines across ONE shared Compiler; the second
// fans them across one Compiler whose ports are the shared, mutex-guarded fakes, so a lock the fakes
// dropped would surface as a data race rather than as an occasional wrong answer.
//
// What makes this more than a smoke test is that every worker checks the ANSWER, not just the absence
// of an error: each computes the digest of its own render and compares it to a digest taken before
// the fan-out. A Compiler that mutated shared state under contention would produce a correct-looking
// FileSet with the wrong bytes, and only a value comparison catches that.

// loadN reads the fan-out width the `load` verb sets (EDEN_LOAD_N, default 500 in-process).
func loadN() int {
	if raw := os.Getenv("EDEN_LOAD_N"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentRenderIsRaceCleanAndByteStable fans N goroutines across ONE shared *Compiler,
// each rendering the same cell and checking its own emission addresses identically to the
// pre-computed baseline. 0 races, N identical digests, no orphan goroutine.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling's goroutines would make it flaky.
func TestLoad_ConcurrentRenderIsRaceCleanAndByteStable(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	compiler := newLoadCompiler(t, document, agentprofiletest.NewTree())
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}

	baseline, err := compiler.Render(t.Context(), target)
	if err != nil {
		t.Fatalf("baseline Render: %v", err)
	}
	want := baseline.Digest()

	var workers sync.WaitGroup
	workers.Add(n)
	for worker := range n {
		go func(worker int) {
			defer workers.Done()
			files, renderErr := compiler.Render(t.Context(), target)
			if renderErr != nil {
				t.Errorf("worker %d: Render: %v", worker, renderErr)
				return
			}
			if got := files.Digest(); got != want {
				t.Errorf("worker %d: emission addressed as %s, want %s — a shared Compiler produced different bytes under contention", worker, got, want)
			}
		}(worker)
	}
	workers.Wait()
}

// TestLoad_ConcurrentDriftIsRaceCleanAndAgrees fans N goroutines across one shared *Compiler whose
// Tree is the shared, mutex-guarded fake, each drifting the same cell against a tree that holds the
// render. Every worker must reach the SAME clean verdict: a drift check whose answer depended on how
// many goroutines were asking would be no check at all. The shared Tree is also the contended port,
// so a lock dropped from the fake's recorder surfaces here as a race.
//
//nolint:paralleltest // shares goleak's whole-process view with the sibling above.
func TestLoad_ConcurrentDriftIsRaceCleanAndAgrees(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}

	rendered, err := newLoadCompiler(t, document, agentprofiletest.NewTree()).Render(t.Context(), target)
	if err != nil {
		t.Fatalf("baseline Render: %v", err)
	}
	tree := agentprofiletest.NewTree().WithFileSet(rendered)
	compiler := newLoadCompiler(t, document, tree)

	var workers sync.WaitGroup
	workers.Add(n)
	for worker := range n {
		go func(worker int) {
			defer workers.Done()
			divergences, driftErr := compiler.Drift(t.Context(), target)
			if driftErr != nil {
				t.Errorf("worker %d: Drift: %v", worker, driftErr)
				return
			}
			if len(divergences) != 0 {
				t.Errorf("worker %d: Drift over a matching tree reported %d divergence(s), want 0", worker, len(divergences))
			}
		}(worker)
	}
	workers.Wait()

	// Every worker read every rendered file, so the fake's recorder holds exactly N x len(rendered)
	// entries. Reading it AFTER the join is safe — reading it before would be the documented race.
	if want := n * len(rendered); len(tree.Read) != want {
		t.Errorf("the shared Tree recorded %d read(s), want %d (N workers x %d rendered files) — a read was lost or duplicated under contention",
			len(tree.Read), want, len(rendered))
	}
}

// TestLoad_ConcurrentNewIsRaceClean fans N goroutines each constructing an INDEPENDENT Compiler over
// the same document bytes, proving New is pure and holds no shared state: N constructions must all
// succeed and all render to the same address. A package-level cache or a lazily-initialised global
// would surface as a race here.
//
//nolint:paralleltest // shares goleak's whole-process view with the siblings above.
func TestLoad_ConcurrentNewIsRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}

	baseline, err := newLoadCompiler(t, document, agentprofiletest.NewTree()).Render(t.Context(), target)
	if err != nil {
		t.Fatalf("baseline Render: %v", err)
	}
	want := baseline.Digest()

	var workers sync.WaitGroup
	workers.Add(n)
	for worker := range n {
		go func(worker int) {
			defer workers.Done()
			compiler, newErr := agentprofile.New(
				agentprofile.Config{Document: document, Repository: agentprofiletest.CanonicalOverlay},
				agentprofile.Deps{
					Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}},
					Tree:      agentprofiletest.NewTree(),
				},
			)
			if newErr != nil {
				t.Errorf("worker %d: New: %v", worker, newErr)
				return
			}
			files, renderErr := compiler.Render(t.Context(), target)
			if renderErr != nil {
				t.Errorf("worker %d: Render: %v", worker, renderErr)
				return
			}
			if got := files.Digest(); got != want {
				t.Errorf("worker %d: an independently constructed Compiler addressed as %s, want %s", worker, got, want)
			}
		}(worker)
	}
	workers.Wait()
}

// newLoadCompiler builds a Compiler over document with the canonical overlay, the real
// ClaudeRenderer, and the given tree.
func newLoadCompiler(t *testing.T, document []byte, tree agentprofile.Tree) *agentprofile.Compiler {
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
