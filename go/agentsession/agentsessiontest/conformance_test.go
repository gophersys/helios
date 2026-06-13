package agentsessiontest_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// TestFake_Conforms runs THE one conformance suite over the scripted fake Adapter — the
// fake ≡ adapter closure (08 §2). The SAME suite's parser-level properties run over the
// REAL claude-code adapter's stream-json normalizer in the claudeadapter package's tests
// (the live authenticated run is gated on the setup-token and never executed in tests).
// Two bindings, one suite (ADR-0016).
func TestFake_Conforms(t *testing.T) {
	t.Parallel()
	agentsessiontest.Run(t, func() *agentsessiontest.Adapter {
		return agentsessiontest.New(agentsessiontest.CanonicalScript()...)
	})
}
