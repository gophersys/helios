package observability_test

import (
	"testing"

	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/observabilitytest"
)

// TestConformance runs the exported contract conformance suite (§4) against the
// real Provider produced by observability.New. The fake runs the SAME suite in
// observabilitytest's own test, so adapter ≡ fake substitutability is proven
// against one set of properties (08 §2).
func TestConformance(t *testing.T) {
	observabilitytest.Run(t, observability.New)
}
