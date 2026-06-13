package configuration_test

import (
	"testing"

	cfg "github.com/gophersys/libs/go/configuration"
	cfgtest "github.com/gophersys/libs/go/configuration/configurationtest"
)

// The real adapter must pass the substitutability conformance suite.
func TestConformance_RealParser(t *testing.T) {
	cfgtest.Run(t, cfg.New)
}

// The scripted fake Parser must pass the SAME suite (08 §2: adapter ≡ fake).
func TestConformance_FakeParser(t *testing.T) {
	cfgtest.Run(t, cfgtest.NewParser)
}
