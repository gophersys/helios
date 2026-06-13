package dependenciestest_test

import (
	"testing"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// The single shared port-substitutability suite (§4) must pass for the REAL
// host-backed adapters: this is the "fake ≡ real" proof anchor on the real side.
func TestPortSuiteReal(t *testing.T) {
	t.Parallel()
	dependenciestest.RunPortSuite(t, func() dependencies.Set {
		return dependencies.Resolve(dependencies.Set{})
	})
}

// ...and for the dependenciestest fakes: same suite, fresh fakes per construction.
func TestPortSuiteFakes(t *testing.T) {
	t.Parallel()
	dependenciestest.RunPortSuite(t, func() dependencies.Set {
		set, _, _, _ := dependenciestest.Fakes()
		return set
	})
}
