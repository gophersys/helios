package agentprofile_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// The conformance two-binding (ADR-0020 dimension (a), 08 §2). The SAME exported suite runs over
// BOTH bindings of the Renderer port — the in-memory fake and the production ClaudeRenderer — so
// substitutability is EXECUTED, not asserted. A property that holds on one binding and not the other
// is a real divergence, and the closure is the whole point: the fake is only trustworthy as a stand-in
// while it answers the same questions the real renderer does.

// TestConformanceFakeRenderer runs the Renderer suite against the canonical in-memory fake over the
// canonical in-memory Tree. This is the binding every OTHER library's tests will wire, so it is the
// one that must be provably substitutable.
func TestConformanceFakeRenderer(t *testing.T) {
	t.Parallel()
	agentprofiletest.RunRendererSuite(t,
		func() agentprofile.Renderer { return agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode) },
		func(committed agentprofile.FileSet) (agentprofile.Tree, error) {
			return agentprofiletest.NewTree().WithFileSet(committed), nil
		},
	)
}

// TestConformanceClaudeRenderer runs the IDENTICAL suite against the production
// agentprofile.ClaudeRenderer — the only harness with a built renderer. Every property the fake
// satisfies (determinism, non-empty sorted unique relative emission, digest stability, digest
// sensitivity to content, total precedence, typed not-found, and the three drift verdicts) must hold
// through the real emission layout too.
func TestConformanceClaudeRenderer(t *testing.T) {
	t.Parallel()
	agentprofiletest.RunRendererSuite(t,
		func() agentprofile.Renderer { return agentprofile.ClaudeRenderer{} },
		func(committed agentprofile.FileSet) (agentprofile.Tree, error) {
			return agentprofiletest.NewTree().WithFileSet(committed), nil
		},
	)
}

// TestConformanceUnbuiltRenderersFailLoudly binds the two DECLARED-BUT-UNBUILT renderers to the
// suite arm that asserts the loud failure. It is the anti-false-green half of the contract: an
// unbuilt harness returns a typed NotImplementedError naming itself under KindInternal, and NEVER an
// empty FileSet — a silent nothing would let a drift check pass over a profile that was never
// written, which is the exact failure this library exists to prevent.
func TestConformanceUnbuiltRenderersFailLoudly(t *testing.T) {
	t.Parallel()
	for _, renderer := range []agentprofile.Renderer{agentprofile.OMPRenderer{}, agentprofile.CodexRenderer{}} {
		t.Run(string(renderer.Harness()), func(t *testing.T) {
			t.Parallel()
			agentprofiletest.AssertLoudlyUnbuilt(t, renderer)
		})
	}
}
