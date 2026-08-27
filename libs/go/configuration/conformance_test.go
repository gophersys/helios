package configuration_test

import (
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// The real adapter must pass the substitutability conformance suite.
func TestConformance_RealParser(t *testing.T) {
	t.Parallel()
	configurationtest.RunParserSuite(t, configuration.New)
}

// The scripted fake Parser must pass the SAME suite (08 §2: adapter ≡ fake).
func TestConformance_FakeParser(t *testing.T) {
	t.Parallel()
	configurationtest.RunParserSuite(t, configurationtest.NewParser)
}
