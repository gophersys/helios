package configurationtest

import "testing"

// RunParserSuite is the single primary conformance entrypoint (08 §2).
func RunParserSuite(t *testing.T, _ func() any) { _ = t }

// RunParserSuiteWithFake is the ONE sanctioned fake-only variant — permitted as the
// second entrypoint (it runs the suite over the in-tree fake).
func RunParserSuiteWithFake(t *testing.T) { _ = t }
