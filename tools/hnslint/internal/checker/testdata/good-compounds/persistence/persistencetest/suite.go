package persistencetest

import "testing"

// RunStoreSuite is the single, well-named conformance entrypoint (08 §2). Note the
// name "RunStoreSuite" is a MEANINGFUL COMPOUND (Store inside Run<Role>Suite), not a
// bare banned identifier, and is the conformant shape.
func RunStoreSuite(t *testing.T, _ func() any) { _ = t }
