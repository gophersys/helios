package codeinsight_test

import (
	"testing"

	"github.com/gophersys/libs/go/codeinsight/codeinsighttest"
)

// TestFake_Conforms runs THE one conformance suite over the in-memory fake History (the canonical
// commits replayed, backed by the canonical source files on disk) — the fake ≡ real closure (08 §2).
// The SAME suite runs over a REAL system-git History in the integration test (//go:build
// integration). Two bindings, one suite (ADR-0016).
func TestFake_Conforms(t *testing.T) {
	t.Parallel()
	codeinsighttest.RunAnalyzerSuite(t, codeinsighttest.FakeArm(t))
}
