//go:build lifecycle

package agentprofile_test

import (
	"context"
	"sync"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// ADR-0020 dimension (c) — the full object lifecycle: construct → use → first Close → SECOND Close is
// a no-op → CountOwned()==0, driven by libtesting.AssertLifecycle, with goleak.VerifyNone covering the
// orphan-goroutine half. Tagged `//go:build lifecycle` so the probe stays out of the fast unit run.
//
// WHAT THIS LIBRARY ACTUALLY OWNS, stated plainly rather than faked. A *Compiler holds NO closable
// external resource: no file handle, no socket, no container, no goroutine. New is pure — it parses,
// validates and binds, and touches nothing outside its two arguments — and everything that reaches
// the world does so through the injected Tree and Renderer ports, which the COMPOSITION ROOT owns and
// closes. Inventing a resource here so the lane had something to release would be a fixture proving a
// property the library does not have, which is the exact class of false green this phase exists to
// prevent.
//
// So the probe is written over what the Compiler DOES own: the RENDERING CAPABILITY conferred by its
// bound renderer set. That capability is measured by ACTION, never by inspecting a field —
// CountOwned attempts a real Render for every harness the matrix declares and counts the cells that
// still emit. Close releases the handle the way a caller does, by dropping it; the second Close finds
// nothing left and is a clean no-op; and CountOwned then reports zero because no cell can be rendered
// through a released handle. That is a true lifecycle statement about this library rather than a
// borrowed one.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle probe runs serially.
func TestLifecycle_CompilerReleaseIsIdempotentAndLeavesNoCapability(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := &lifecycleReport{t: t}
	harness := &lifecycleHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newCompilerProbe)
}

// lifecycleHarnesses is the set of cells the probe's capability count walks. The document declares
// the row for both, and both renderers are bound, so a live Compiler owns exactly two renderable
// cells and a released one owns none.
//
//nolint:gochecknoglobals // the probe's fixed cell set; package-level so Use and CountOwned agree.
var lifecycleHarnesses = []agentprofile.Harness{agentprofile.HarnessClaudeCode, agentprofile.HarnessOMP}

// compilerProbe binds a *agentprofile.Compiler to the libtesting.LifecycleProbe port.
type compilerProbe struct {
	mutex    sync.Mutex
	compiler *agentprofile.Compiler
}

// newCompilerProbe constructs a real Compiler over the conformance document with BOTH the built
// claude renderer and the unbuilt omp one bound, so the capability count has more than one cell to
// lose. It is the libtesting.LifecycleFactory the driver invokes once per run.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newCompilerProbe(_ context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	compiler, err := agentprofile.New(
		agentprofile.Config{
			Document:   agentprofiletest.CanonicalDocument(lifecycleHarnesses...),
			Repository: agentprofiletest.CanonicalOverlay,
		},
		agentprofile.Deps{
			Renderers: []agentprofile.Renderer{
				agentprofile.ClaudeRenderer{},
				agentprofiletest.NewRenderer(agentprofile.HarnessOMP),
			},
			Tree: agentprofiletest.NewTree(),
		},
	)
	if err != nil {
		return nil, nil, err
	}
	probe := &compilerProbe{compiler: compiler}
	// A final best-effort release, so a mid-run assertion failure never leaves the probe holding a
	// live handle past the test.
	return probe, func() { _ = probe.Close(context.Background()) }, nil
}

// Use exercises the live Compiler through its real load path: it renders a cell and drifts it against
// an empty tree, asserting both produce work. A handle that merely EXISTS proves nothing; a handle
// that emits and reports is alive.
func (p *compilerProbe) Use(ctx context.Context) error {
	p.mutex.Lock()
	compiler := p.compiler
	p.mutex.Unlock()
	if compiler == nil {
		return errReleasedCompiler
	}
	target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}
	files, err := compiler.Render(ctx, target)
	if err != nil {
		return err
	}
	if len(files) == 0 {
		return errEmptyEmission
	}
	divergences, err := compiler.Drift(ctx, target)
	if err != nil {
		return err
	}
	if len(divergences) != len(files) {
		return errDriftMismatch
	}
	return nil
}

// Close releases the handle by dropping the caller's reference to it, which is the only release a
// pure value has. It is IDEMPOTENT by construction: the second call finds nothing to drop and returns
// nil, which is the invariant AssertLifecycle asserts.
func (p *compilerProbe) Close(context.Context) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()
	p.compiler = nil
	return nil
}

// CountOwned reports how many cells the probe can still RENDER — the capability the Compiler owns,
// measured by attempting the work rather than by reading a field. A live Compiler owns one per
// declared harness; a released one owns none, which is the zero the driver requires after teardown.
func (p *compilerProbe) CountOwned(ctx context.Context) (int, error) {
	p.mutex.Lock()
	compiler := p.compiler
	p.mutex.Unlock()
	if compiler == nil {
		return 0, nil
	}
	owned := 0
	for _, harness := range lifecycleHarnesses {
		target := agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: harness}
		// The omp renderer is scripted to emit, so every declared cell of this document renders; a
		// cell that cannot render is not an owned capability.
		if files, err := compiler.Render(ctx, target); err == nil && len(files) > 0 {
			owned++
		}
	}
	return owned, nil
}

// The probe's own failure sentinels. They are declared values, never minted at the throw site, so the
// driver's report names the invariant that broke.
//
//nolint:gochecknoglobals // sentinels are package-level by construction.
var (
	errReleasedCompiler = probeFault("the probe was used after its Compiler was released")
	errEmptyEmission    = probeFault("the live Compiler rendered an empty emission")
	errDriftMismatch    = probeFault("Drift over an empty tree did not report every rendered file")
)

// probeFault is the probe's own error type, kept local so the lifecycle lane never depends on the
// library's error taxonomy to describe a failure of the PROBE.
type probeFault string

// Error implements error.
func (f probeFault) Error() string { return string(f) }

// ── *testing.T adapters for the libtesting.Harness / libtesting.Report ports ────────────────────

// lifecycleReport adapts *testing.T to the libtesting.Report sink AssertLifecycle reports into.
type lifecycleReport struct{ t *testing.T }

func (r *lifecycleReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *lifecycleReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *lifecycleReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// lifecycleHarness adapts *testing.T's lifecycle needs to the libtesting.Harness port. Only Cleanup
// and Context are exercised by AssertLifecycle; the deterministic-source accessors are part of the
// frozen 5-method port and are never called on this path. Cleanup delegates to *testing.T.Cleanup so
// the teardown runs at test end, keeping the goleak check honest even on a mid-run failure.
type lifecycleHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*lifecycleHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract: Harness.RandomSource returns the RandomSource port; unused here.
func (*lifecycleHarness) RandomSource() libtesting.RandomSource { return nil }

func (*lifecycleHarness) Has(string) bool { return false }

func (h *lifecycleHarness) Context() context.Context { return h.ctx }

func (h *lifecycleHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
