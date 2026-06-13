package errors_test

import (
	"testing"

	"github.com/gophersys/libs/go/errors/errorstest"
)

// TestConformance runs the exported contract conformance suite against the
// production verbs (contract §4).
func TestConformance(t *testing.T) {
	t.Parallel()
	errorstest.RunConformance(t)
}
