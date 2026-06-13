package gitrepositorytest_test

import (
	"testing"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
)

// TestFake_Conforms runs THE one conformance suite over the in-memory fake Backend — the
// fake ≡ backend closure (08 §2). The SAME suite runs over a REAL system-git Backend in the
// integration test (//go:build integration). Two bindings, one suite (ADR-0016).
func TestFake_Conforms(t *testing.T) {
	t.Parallel()
	gitrepositorytest.Run(t, func() gitrepository.Backend {
		return gitrepositorytest.New()
	})
}
